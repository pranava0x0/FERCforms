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

from pipeline.models import Finding, PageText

# $1,234 | $1,234.56 | $1.5 million | $2 billion | $500 thousand
_DOLLAR_RE = re.compile(
    r"\$\s?[\d,]+(?:\.\d{1,2})?(?:\s?(?:million|billion|thousand))?",
    re.IGNORECASE,
)

_MULTIPLIERS = {"thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}

# Sentence boundary: a run of non-terminator text ending in . ! or ? (followed by
# whitespace/end), OR a final fragment with no terminator. Deliberately simple —
# good enough to bound a dollar-bearing clause without a full NLP sentence splitter.
_SENTENCE_RE = re.compile(r"[^.!?]*[.!?]+(?:\s+|$)|[^.!?]+$")


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
    sentence punctuation, never a fixed character count)."""
    for m in _SENTENCE_RE.finditer(text):
        if m.start() <= match_start and match_end <= m.end():
            return m.group(0).strip()
    return text[max(0, match_start - 80): match_end + 80].strip()  # pathological fallback


def _first_dollar_mention(text: Optional[str]) -> Optional[DollarMention]:
    if not text:
        return None
    m = _DOLLAR_RE.search(text)
    if not m:
        return None
    quote = _sentence_containing(text, m.start(), m.end())
    try:
        amount = parse_dollar_amount(m.group(0))
    except ValueError:
        return None
    return DollarMention(raw=m.group(0), quote=quote, amount_usd=amount)


def find_primary_dollar_mention(finding: Finding) -> Optional[DollarMention]:
    """The first dollar figure in a finding's OWN committed text: summary first,
    then each recommendation in order. Returns None if none is present."""
    hit = _first_dollar_mention(finding.summary)
    if hit:
        return hit
    for rec in finding.recommendations:
        hit = _first_dollar_mention(rec.text)
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
    raw_page = None
    for page in pages:
        page_norm = _normalize(page.text)
        if quote_norm and quote_norm in page_norm:
            return page.page
        if raw_page is None and raw_norm in page_norm:
            raw_page = page.page
    return raw_page
