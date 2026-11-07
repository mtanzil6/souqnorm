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
                     "غ", "غم", "غرام", "جم", "جرام", "قرام", "ج")),
    "kg": ("g", 1000.0, ("kg", "kgs", "kilo", "kilogram", "kilograms",
                         "كغ", "كجم", "كلغ", "كيلو", "كيلوغرام", "كيلوجرام")),
    "mg": ("g", 0.001, ("mg", "ملغ", "ملجم", "مجم", "ملغم", "مليغرام", "مليجرام")),
    "lb": ("g", 453.592, ("lb", "lbs", "pound", "pounds", "باوند", "رطل")),
    "pcs": ("pcs", 1.0, ("pc", "pcs", "piece", "pieces", "count", "ct", "capsules", "caps", "tablets", "tabs",
                         "sachets", "patches", "ampoules", "wipes", "pads",
                         "قطعة", "قطع", "حبة", "حبات", "كبسولة", "كبسولات", "قرص", "أقراص", "منديل", "مناديل",
                         "كيس", "أكياس", "لصقة", "لصقات", "أمبولة", "أمبولات", "وحدة", "وحدات", "قطنة",
                         "شريحة", "شرائح", "ظرف", "أظرف")),
    # length (dimensions of tools, cables, towels); multipliers are read as dimensions, not packs
    "mm": ("mm", 1.0, ("mm", "ملم", "مم", "مليمتر", "ملليمتر")),
    "cm": ("mm", 10.0, ("cm", "سم", "سنتيمتر", "سنتي")),
    "m": ("mm", 1000.0, ("m", "م", "متر", "meter", "meters", "metre", "metres")),
}

_LENGTH = {"mm", "cm", "m"}


@dataclass(frozen=True)
class Quantity:
    value: float          # numeric value as written (per item)
    unit: str             # canonical unit key, e.g. "ml", "fl_oz"
    multiplier: int       # pack multiplier, 1 if absent ("2x50ml" -> 2)
    base_value: float     # value * factor * multiplier in the base unit
    base_unit: str        # "ml", "g", "pcs" or "mm"
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
        *sig* significant figures (e.g. 400 ml and 13.5 fl oz -> 'qty:400ml'). The default is coarse
        enough to absorb cross-unit conversion rounding (e.g. fl oz -> ml); pass sig=3 or higher for
        exact same-unit sizes that should stay distinct (118 ml, 120 ml and 125 ml all collide into
        'qty:120ml' at the default but resolve to separate keys at sig=3)."""
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
            r"(?!\s*(?:ملي\s*امبير|امبير))"  # "7000 ملي امبير" is battery capacity, not volume.
            # English "mAh"/"amp"/"ampere" need no guard: the lone-letter "m" unit already can't match
            # ("mAh"'s trailing "h" fails the no-following-word-char check below), so adding "amp\b" here
            # only misfired on unrelated units, e.g. rejecting "zinc 50mg amp" (amp = ampoule abbreviation).
        )

    @property
    def unit_words(self) -> frozenset[str]:
        """Normalized measurement-unit tokens (volume, mass, length), e.g. {'مل', 'ml', 'جم', ...}.
        Count nouns such as 'مناديل' or 'امبوله' are excluded because they also name products."""
        return frozenset(w for s, u in self._surface_to_unit.items() if UNIT_LEXICON[u][0] != "pcs"
                         for w in s.split())

    def parse(self, normalized: str) -> list[Quantity]:
        """Find quantity expressions. For a two-number dimension like "38*29.5 سم" (width*height, not a
        pack), only the second number is kept as the Quantity; the first is discarded entirely and does
        not appear anywhere in the result."""
        out: list[Quantity] = []
        for m in self._pattern.finditer(normalized):
            unit = self._surface_to_unit[m.group("unit")]
            base_unit, factor, _ = UNIT_LEXICON[unit]
            value = float(m.group("num"))
            mult = int(m.group("mult")) if m.group("mult") else 1
            start = m.start()
            if unit in _LENGTH and mult > 1:  # "38*29.5 سم" is a size, not a pack of 38
                mult, start = 1, m.start("num")
            out.append(Quantity(value, unit, mult, round(value * factor * mult, 3), base_unit,
                                normalized[start:m.end()], start, m.end()))
        return out
