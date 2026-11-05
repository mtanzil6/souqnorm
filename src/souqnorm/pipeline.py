"""End-to-end query processing: normalize -> extract quantities -> generate keywords and variants."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .arabic import AR_RANGE, NormalizerConfig, normalize_text
from .units import Quantity, UnitParser

_TOKEN = re.compile(rf"[{AR_RANGE}a-z0-9]+(?:[-'.][{AR_RANGE}a-z0-9]+)*")
_NUMERIC = re.compile(r"^\d+(?:\.\d+)?$")
# definite-article forms, longest first: wa-al, bi-al, ka-al, fa-al, li-l, al
_ARTICLE_PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال")
# Function words dropped from keywords. "او" is deliberately kept: in catalogs it is usually "eau" (او دو بارفيوم).
DEFAULT_STOPWORDS = frozenset({"من", "في", "مع", "علي", "الي", "عن", "لـ", "و", "ب", "ل", "الذي", "التي",
                               "for", "with", "and", "of", "the", "by", "from", "in", "to", "a", "an"})


@dataclass
class NormalizedQuery:
    original: str
    normalized: str
    tokens: list[str]
    quantities: list[Quantity]
    text_without_quantities: str
    keywords: list[str]
    variants: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "original": self.original,
            "normalized": self.normalized,
            "tokens": self.tokens,
            "quantities": [q.to_dict() for q in self.quantities],
            "text_without_quantities": self.text_without_quantities,
            "keywords": self.keywords,
            "variants": self.variants,
        }


def _dedupe(items):
    seen, out = set(), []
    for x in items:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


class QueryNormalizer:
    """Main entry point.

    >>> qn = QueryNormalizer()
    >>> r = qn.process("شامبو للشعر الجاف ٤٠٠مل")
    >>> r.normalized
    'شامبو للشعر الجاف 400 مل'
    >>> r.quantities[0].label
    '400 ml'
    """

    def __init__(self, config: NormalizerConfig | None = None, strip_article: bool = True,
                 min_keyword_len: int = 2, stopwords: frozenset[str] | None = DEFAULT_STOPWORDS):
        self.config = config or NormalizerConfig()
        self.units = UnitParser(self.config)
        self.strip_article = strip_article
        self.min_keyword_len = min_keyword_len
        self._unit_words = self.units.unit_words
        self.stopwords = frozenset(normalize_text(w, self.config) for w in (stopwords or ()))

    def normalize(self, text: str) -> str:
        return normalize_text(text, self.config)

    def tokenize(self, normalized: str) -> list[str]:
        return _TOKEN.findall(normalized)

    def keywords(self, tokens: list[str]) -> list[str]:
        """Alternative keywords: drops numbers, unit words (e.g. 'مل'), stopwords, special characters
        and empty strings; splits and joins hyphenated words; optionally adds article-stripped forms."""
        out: list[str] = []
        for tok in tokens:
            parts = [p for p in re.split(r"[-'.]", tok) if p]
            candidates = parts + (["".join(parts)] if len(parts) > 1 else [])
            for c in candidates:
                if _NUMERIC.match(c) or c.isdigit() or c in self._unit_words:
                    continue
                if len(c) < self.min_keyword_len or c in self.stopwords:
                    continue
                out.append(c)
                if self.strip_article:
                    for pre in _ARTICLE_PREFIXES:
                        if c.startswith(pre) and len(c) - len(pre) >= 3:
                            out.append(c[len(pre):])
                            break
        return _dedupe(out)

    def process(self, text: str) -> NormalizedQuery:
        norm = self.normalize(text)
        quantities = self.units.parse(norm)
        stripped = norm
        for q in reversed(quantities):
            stripped = stripped[: q.start] + " " + stripped[q.end:]
        stripped = re.sub(r"\s+", " ", stripped).strip()
        tokens = self.tokenize(norm)
        kws = self.keywords(self.tokenize(stripped))
        canonical = stripped
        if quantities:
            canonical = (stripped + " " + " ".join(q.label for q in quantities)).strip()
        variants = _dedupe([norm, canonical, stripped, " ".join(kws)])
        return NormalizedQuery(text, norm, tokens, quantities, stripped, kws, variants)


_default: QueryNormalizer | None = None


def process(text: str) -> NormalizedQuery:
    """Process *text* with a shared default :class:`QueryNormalizer`."""
    global _default
    if _default is None:
        _default = QueryNormalizer()
    return _default.process(text)
