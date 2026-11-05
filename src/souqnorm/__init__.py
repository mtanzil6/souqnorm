"""souqnorm: normalization, size parsing and keyword expansion for Arabic/English e-commerce search queries."""
from .arabic import NormalizerConfig, normalize_text
from .pipeline import NormalizedQuery, QueryNormalizer, process
from .units import UNIT_LEXICON, Quantity, UnitParser

__version__ = "0.1.0"
__all__ = ["NormalizerConfig", "normalize_text", "NormalizedQuery", "QueryNormalizer", "process",
           "UNIT_LEXICON", "Quantity", "UnitParser", "__version__"]
