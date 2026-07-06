"""Extract the headline dollar figure a finding cites, with a page citation.

Scope (BACKLOG P1 #4, piloted 2026-07-06): a finding's `summary` and
`recommendations[].text` are already committed, verbatim, human/parser-verified
text (they went through the exec-summary / body-section parsers in
pipeline/structure.py, which are anchored/count-gated). This module does NOT
re-derive new "verbatim" text from an unvetted wider span of raw PDF text — the
2026-07-06 validation sweep found exactly that anti-pattern shipped 528 garbage
findings elsewhere in the corpus. Instead it:

  1. finds the FIRST dollar figure already present in a finding's own committed
     text (never a new region), at SENTENCE granularity (never a blind
     character window — the other anti-pattern from that same sweep), and
  2. locates which source-PDF page that same sentence (or, failing that, the
     bare dollar figure) appears on, as an independently-checkable citation.

If no dollar figure is present, or no page can be located, the corresponding
field(s) stay None — never a guessed or partial citation.
"""
from __future__ import annotations

import re
from typing import NamedTuple, Optional

from pipeline import config, extract, fetch
from pipeline.models import Finding, ListingEntry, PageText, ReportText

# $1,234 | $1,234.56 | $1.5 million | $2 billion | $500 thousand
# \b after the multiplier word matters: without it "$5 thousandths" would match
# "$5 thousand" (silently inflating the parsed amount 1000x) — \b stops the word
# match at a real word boundary, so a trailing "ths"/"s" correctly excludes it.
DOLLAR_RE = re.compile(
    r"\$\s?[\d,]+(?:\.\d{1,2})?(?:\s?(?:million|billion|thousand)\b)?",
    re.IGNORECASE,
)

# A dollar figure immediately followed by this is the LOW end of a stated range
# ("$5 to $10 million", "$5-$10 million") — its own multiplier (if any) may not
# reflect the range's actual multiplier, which typically appears once at the end.
# Skip it and prefer the next mention, which carries a complete, self-contained
# figure instead of a misleadingly small "primary" amount.
_RANGE_LOW_BOUND_RE = re.compile(r"^\s*(?:to|-)\s*\$", re.IGNORECASE)

_MULTIPLIERS = {"thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}

# Sentence boundary: bounded by real sentence-terminating punctuation. A period
# is deliberately NOT treated as a terminator when it sits between two digits (a
# decimal point, e.g. the "." in "$2.8 million") — without this, a dollar figure
# with a decimal fragments its own sentence, producing a garbled mid-word quote
# like "8 million to $25 million." instead of the full sentence (caught
# 2026-07-06 by inspecting real pilot output, not by the unit tests alone).
def _is_decimal_point(text: str, pos: int) -> bool:
    return (
        text[pos] == "."
        and pos > 0 and text[pos - 1].isdigit()
        and pos + 1 < len(text) and text[pos + 1].isdigit()
    )


class DollarMention(NamedTuple):
    raw: str            # the matched dollar substring, e.g. "$536,555"
    quote: str           # the containing sentence, verbatim from the finding's own text
    amount_usd: float    # parsed numeric value


def parse_dollar_amount(raw: str) -> float:
    """'$536,555' -> 536555.0; '$16.36 million' -> 16360000.0."""
    body = raw.strip().lstrip("$").strip()
    multiplier = 1
    for word, mult in _MULTIPLIERS.items():
        if body.lower().endswith(word):
            multiplier = mult
            body = body[: -len(word)].strip()
            break
    return float(body.replace(",", "")) * multiplier


def _sentence_containing(text: str, match_start: int, match_end: int) -> str:
    """The sentence spanning [match_start, match_end) in `text` (bounded by real
    sentence-terminating punctuation, never a fixed character count — decimal
    points inside numbers don't count, see _is_decimal_point)."""
    seg_start = 0
    i, n = 0, len(text)
    while i < n:
        if text[i] in ".!?" and not _is_decimal_point(text, i):
            j = i + 1
            while j < n and text[j] in ".!?" and not _is_decimal_point(text, j):
                j += 1
            if seg_start <= match_start and match_end <= j:
                return text[seg_start:j].strip()
            seg_start = j
            i = j
        else:
            i += 1
    if seg_start <= match_start:
        return text[seg_start:].strip()
    return text[max(0, match_start - 80): match_end + 80].strip()  # pathological fallback


def find_dollar_mention(text: Optional[str]) -> Optional[DollarMention]:
    if not text:
        return None
    for m in DOLLAR_RE.finditer(text):
        if _RANGE_LOW_BOUND_RE.match(text[m.end(): m.end() + 12]):
            continue  # the low end of "$5 to $10 million" — prefer the complete figure
        quote = _sentence_containing(text, m.start(), m.end())
        try:
            amount = parse_dollar_amount(m.group(0))
        except ValueError:
            continue
        return DollarMention(raw=m.group(0), quote=quote, amount_usd=amount)
    return None


def find_primary_dollar_mention(finding: Finding) -> Optional[DollarMention]:
    """The first dollar figure in a finding's OWN committed text: summary first,
    then each recommendation in order. Returns None if none is present."""
    hit = find_dollar_mention(finding.summary)
    if hit:
        return hit
    for rec in finding.recommendations:
        hit = find_dollar_mention(rec.text)
        if hit:
            return hit
    return None


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def locate_page(mention: DollarMention, pages: list[PageText]) -> Optional[int]:
    """Which source-PDF page carries this mention, as an independent citation
    check. Tries the full sentence first (strongest evidence); falls back to the
    bare dollar figure alone (a PDF line-wrap can break sentence-level matching
    even though the figure itself sits on one line). Never guesses — None if
    neither is found on any page."""
    quote_norm = _normalize(mention.quote)
    raw_norm = _normalize(mention.raw)
    # A trailing \b stops a short figure ("$5") from falsely matching as a prefix
    # of an unrelated longer one ("$500,000") on some other page.
    raw_re = re.compile(re.escape(raw_norm) + r"\b") if raw_norm else None
    raw_page = None
    for page in pages:
        page_norm = _normalize(page.text)
        if quote_norm and quote_norm in page_norm:
            return page.page
        if raw_page is None and raw_re and raw_re.search(page_norm):
            raw_page = page.page
    return raw_page


def fetch_and_extract(entry: ListingEntry, session) -> ReportText:
    """Fetch (cached) + extract a report's source PDF ONCE. Shared by
    pipeline.amounts_enrich and pipeline.verify_amounts so a report with several
    cited findings is only fetched/extracted a single time, not once per finding."""
    fetch.download_pdf(session, entry, config.RAW_DIR)
    return extract.extract_report(entry, config.RAW_DIR, config.PROCESSED_DIR)
