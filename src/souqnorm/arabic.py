"""Character-level normalization for Arabic/English product search queries."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Harakat, Quranic annotation marks, superscript alef.
_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
_TATWEEL = "ـ"

_ALEF = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا"})
_ALEF_MAQSURA = str.maketrans({"ى": "ي"})
_TAA_MARBUTA = str.maketrans({"ة": "ه"})
_HAMZA_CARRIERS = str.maketrans({"ؤ": "و", "ئ": "ي"})
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "0123456789" * 2)
_PUNCT = str.maketrans({"٫": ".", "٬": ",", "،": ",", "؛": ";", "؟": "?", "٪": "%", "×": "x"})

_THOUSANDS = re.compile(r"\b\d{1,3}(?:,\d{3})+\b")
_DECIMAL_COMMA = re.compile(r"(?<=\d),(?=\d{1,2}\b)")
_WS = re.compile(r"\s+")

AR_RANGE = "؀-ۿݐ-ݿࢠ-ࣿ"


@dataclass(frozen=True)
class NormalizerConfig:
    """Switches for each normalization step (all on by default)."""

    unicode_nfkc: bool = True
    digits: bool = True
    punctuation: bool = True
    remove_diacritics: bool = True
    remove_tatweel: bool = True
    unify_alef: bool = True
    alef_maqsura_to_yaa: bool = True
    taa_marbuta_to_haa: bool = True
    hamza_carriers: bool = True
    lowercase: bool = True
    split_scripts: bool = True  # "50مل" -> "50 مل", "spf50" -> "spf 50"


_SPLIT_DIGIT = re.compile(r"(?<=\d)(?=[^\d\s.,%])|(?<=[^\d\s.,])(?=\d)")
_SPLIT_SCRIPT = re.compile(rf"(?<=[{AR_RANGE}])(?=[a-zA-Z])|(?<=[a-zA-Z])(?=[{AR_RANGE}])")


def normalize_text(text: str, config: NormalizerConfig | None = None) -> str:
    """Return a normalized form of *text* suitable for indexing and matching."""
    c = config or NormalizerConfig()
    s = text
    if c.unicode_nfkc:
        s = unicodedata.normalize("NFKC", s)
    if c.digits:
        s = s.translate(_DIGITS)
    if c.punctuation:
        s = s.translate(_PUNCT)
        s = _THOUSANDS.sub(lambda m: m.group(0).replace(",", ""), s)
        s = _DECIMAL_COMMA.sub(".", s)
    if c.remove_diacritics:
        s = _DIACRITICS.sub("", s)
    if c.remove_tatweel:
        s = s.replace(_TATWEEL, "")
    if c.unify_alef:
        s = s.translate(_ALEF)
    if c.alef_maqsura_to_yaa:
        s = s.translate(_ALEF_MAQSURA)
    if c.taa_marbuta_to_haa:
        s = s.translate(_TAA_MARBUTA)
    if c.hamza_carriers:
        s = s.translate(_HAMZA_CARRIERS)
    if c.lowercase:
        s = s.lower()
    if c.split_scripts:
        s = _SPLIT_DIGIT.sub(" ", s)
        s = _SPLIT_SCRIPT.sub(" ", s)
    return _WS.sub(" ", s).strip()
