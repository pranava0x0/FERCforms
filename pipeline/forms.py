"""Detect which FERC form (and thus industry) an audit concerns, from its text.

Shared by `structure` (records industry on each report) and `classify` (triages
the whole corpus cheaply so we can scope to Form 1 / electric). Mapping:

  Form No. 1 -> electric (utilities and ISOs/RTOs that file Form 1)
  Form No. 2 -> gas (interstate natural-gas pipelines)
  Form No. 6 -> oil (oil pipelines)
"""
from __future__ import annotations

import re
from typing import Optional

_FORM_RE = re.compile(r"FERC Form No\.?\s*(\d+(?:-[A-Z])?)")
FORM_TO_INDUSTRY: dict[str, str] = {"1": "electric", "2": "gas", "6": "oil"}
_AUDIT_TYPE = {"FA": "financial", "PA": "performance"}

# Industry signals beyond the form number — financial audits cite the form, but
# performance (PA) audits identify the industry by governing statute / tariff /
# Uniform System of Accounts part. Weighted by how definitive each is.
_SIGNALS: dict[str, list[tuple[str, int]]] = {
    "electric": [
        (r"ferc form no\.?\s*1\b", 5), (r"federal power act", 2), (r"\bfpa\b", 1),
        (r"part\s*101\b", 4), (r"open access transmission tariff", 2), (r"\boatt\b", 2),
        (r"public utilities and licensees", 4), (r"electric utilit", 1),
        (r"regional transmission organization", 3), (r"independent system operator", 3),
        (r"\brto\b", 1), (r"\biso\b", 1), (r"market-based rate", 3), (r"wholesale electric", 2),
    ],
    "gas": [
        (r"ferc form no\.?\s*2\b", 5), (r"natural gas act", 2), (r"\bnga\b", 1),
        (r"part\s*201\b", 4), (r"natural gas companies", 3), (r"ferc gas tariff", 3),
        (r"interstate (natural )?gas pipeline", 1),
    ],
    "oil": [
        (r"ferc form no\.?\s*6\b", 5), (r"interstate commerce act", 3), (r"\bica\b", 1),
        (r"part\s*352\b", 4), (r"oil pipeline", 2), (r"carrier property", 1),
    ],
}
_COMPILED = {ind: [(re.compile(p), w) for p, w in pats] for ind, pats in _SIGNALS.items()}


def detect_forms(text: str) -> list[str]:
    """All distinct FERC form numbers mentioned, sorted."""
    return sorted(set(_FORM_RE.findall(text)))


def primary_industry(text: str) -> Optional[str]:
    """Best-scoring industry from form number + statute/tariff/USofA signals."""
    low = text.lower()
    scores = {
        ind: sum(len(rx.findall(low)) * w for rx, w in pats)
        for ind, pats in _COMPILED.items()
    }
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else None


def audit_type_from_docket(docket: Optional[str]) -> Optional[str]:
    """FA -> 'financial', PA -> 'performance' (from the docket prefix)."""
    if not docket:
        return None
    return _AUDIT_TYPE.get(docket[:2].upper())


# Functional focus within the electric sector — an audit can span several
# (a vertically-integrated utility's audit covers transmission AND distribution).
# Ordered generation -> transmission -> distribution for stable output.
_FUNCTION_SIGNALS: dict[str, list[str]] = {
    "generation": [
        r"market-based rate", r"generat(?:ion|or|ors|ing)", r"\bgads\b",
        r"generating availability data", r"exempt wholesale generator",
        r"qualifying facilit", r"power plant", r"\bmerchant\b", r"generator outage",
    ],
    "transmission": [
        r"open access transmission tariff", r"\boatt\b", r"attachment\s+[oh]\b",
        r"transmission formula rate", r"transmission owner",
        r"transmission revenue requirement", r"transmission rate base",
        r"regional transmission",
    ],
    "distribution": [
        r"wholesale distribution", r"distribution formula rate",
        r"distribution facilit", r"local delivery", r"load[- ]serving",
    ],
}
_FUNCTION_COMPILED = {
    fn: [re.compile(p, re.I) for p in pats] for fn, pats in _FUNCTION_SIGNALS.items()
}


def detect_functions(text: str, floor: int = 4, frac: float = 0.2) -> list[str]:
    """Functional focus areas present in the report (generation/transmission/
    distribution). Multi-valued: include any whose signal count clears both an
    absolute floor and a fraction of the top-scoring function (so a few stray
    mentions don't tag a function the audit isn't really about)."""
    scores = {
        fn: sum(len(rx.findall(text)) for rx in pats)
        for fn, pats in _FUNCTION_COMPILED.items()
    }
    top = max(scores.values())
    if top == 0:
        return []
    threshold = max(floor, frac * top)
    return [fn for fn in _FUNCTION_SIGNALS if scores[fn] >= threshold]
