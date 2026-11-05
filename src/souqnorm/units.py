"""Extraction and canonicalization of size/quantity expressions (e.g. '50 مل', '1.7oz', '2x100ml')."""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass

from .arabic import NormalizerConfig, normalize_text

# canonical unit -> (base unit, factor to base, surface forms in natural spelling)
UNIT_LEXICON: dict[str, tuple[str, float, tuple[str, ...]]] = {
    "ml": ("ml", 1.0, ("ml", "mls", "milliliter", "milliliters", "millilitre", "millilitres",
                       "مل", "ملل", "مللي", "ملي", "مليلتر", "ملليلتر", "ميليلتر")),
    "l": ("ml", 1000.0, ("l", "ltr", "ltrs", "liter", "liters", "litre", "litres", "لتر", "لترات", "ليتر")),
    "fl_oz": ("ml", 29.5735, ("fl oz", "fl. oz", "fl.oz", "floz")),
    "oz": ("ml", 29.5735, ("oz", "ounce", "ounces", "أونصة", "اونصة", "أوقية", "اوقية")),
    "g": ("g", 1.0, ("g", "gm", "gms", "gr", "grm", "gram", "grams", "gramme",
                     "غ", "غم", "غرام", "جم", "جرام", "قرام")),
    "kg": ("g", 1000.0, ("kg", "kgs", "kilo", "kilogram", "kilograms",
                         "كغ", "كجم", "كلغ", "كيلو", "كيلوغرام", "كيلوجرام")),
    "mg": ("g", 0.001, ("mg", "ملغ", "ملجم", "مجم", "ملغم", "مليغرام", "مليجرام")),
    "pcs": ("pcs", 1.0, ("pc", "pcs", "piece", "pieces", "قطعة", "قطع", "حبة", "حبات")),
}


@dataclass(frozen=True)
class Quantity:
    value: float          # numeric value as written (per item)
    unit: str             # canonical unit key, e.g. "ml", "fl_oz"
    multiplier: int       # pack multiplier, 1 if absent ("2x50ml" -> 2)
    base_value: float     # value * factor * multiplier in the base unit
    base_unit: str        # "ml", "g" or "pcs"
    text: str             # matched surface text (in normalized query)
    start: int
    end: int

    @property
    def label(self) -> str:
        unit = "fl oz" if self.unit == "fl_oz" else self.unit
        core = f"{self.value:g} {unit}"
        return f"{self.multiplier} x {core}" if self.multiplier > 1 else core

    def match_key(self, sig: int = 2) -> str:
        """Unit-independent key for matching sizes across unit systems, rounding the base value to
        *sig* significant figures (e.g. 400 ml and 13.5 fl oz -> 'qty:400ml')."""
        v = self.base_value
        if v > 0:
            v = round(v, sig - 1 - int(math.floor(math.log10(abs(v)))))
        return f"qty:{v:g}{self.base_unit}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["match_key"] = self.match_key()
        d["label"] = self.label
        return d


class UnitParser:
    """Finds quantity expressions in text that was produced by :func:`normalize_text`."""

    def __init__(self, config: NormalizerConfig | None = None):
        self.config = config or NormalizerConfig()
        self._surface_to_unit: dict[str, str] = {}
        for unit, (_, _, forms) in UNIT_LEXICON.items():
            for form in forms:
                self._surface_to_unit[normalize_text(form, self.config)] = unit
        alts = sorted(self._surface_to_unit, key=len, reverse=True)
        unit_re = "|".join(re.escape(a) for a in alts)
        self._pattern = re.compile(
            rf"(?:(?P<mult>\d+)\s*[x*]\s*)?(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>{unit_re})(?![\w])"
        )

    @property
    def unit_words(self) -> frozenset[str]:
        """Every normalized unit token (single words only), e.g. {'مل', 'ml', ...}."""
        return frozenset(w for s in self._surface_to_unit for w in s.split())

    def parse(self, normalized: str) -> list[Quantity]:
        out: list[Quantity] = []
        for m in self._pattern.finditer(normalized):
            unit = self._surface_to_unit[m.group("unit")]
            base_unit, factor, _ = UNIT_LEXICON[unit]
            value = float(m.group("num"))
            mult = int(m.group("mult")) if m.group("mult") else 1
            out.append(Quantity(value, unit, mult, round(value * factor * mult, 3), base_unit,
                                m.group(0), m.start(), m.end()))
        return out
