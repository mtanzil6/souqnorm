"""souqnorm: normalization, size parsing and keyword expansion for Arabic/English e-commerce search queries."""
from .arabic import NormalizerConfig, normalize_text
from .pipeline import DEFAULT_STOPWORDS, NormalizedQuery, QueryNormalizer, process
from .units import UNIT_LEXICON, Quantity, UnitParser

__version__ = "0.2.0"
__all__ = ["NormalizerConfig", "normalize_text", "NormalizedQuery", "QueryNormalizer", "process",
           "UNIT_LEXICON", "Quantity", "UnitParser", "DEFAULT_STOPWORDS", "__version__"]
