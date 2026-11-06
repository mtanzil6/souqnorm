# souqnorm

**Normalization, size parsing and keyword expansion for Arabic/English e-commerce search queries.**

Shoppers in Arabic-speaking markets type the same product many ways: `شامبو ٤٠٠مل`, `شامبو 400 ملل`,
`شاـــمبو 400ml`, `shampoo 13.5 fl oz`. Off-the-shelf search analyzers treat each of these as different
text. `souqnorm` is a small, dependency-free Python library that turns these forms into one consistent
representation before indexing or querying, whatever search engine you use.

## Features (v0.2)

- **Arabic orthographic normalization.** It unifies alef forms (أ إ آ ٱ → ا), maps ى → ي, ة → ه and ؤ/ئ → و/ي,
  and strips diacritics (harakat) and tatweel. It also converts Arabic-Indic and Persian digits and the Arabic
  decimal mark (٫), applies NFKC, lowercases Latin text and splits number/script boundaries
  (`400مل` → `400 مل`). Every step can be switched off in `NormalizerConfig`.
- **Size and quantity parsing.** It recognizes Arabic and English unit spellings for volume (مل/ملل/مللي/ml, لتر/l,
  oz/fl oz/أونصة), mass (جم/ج/غرام/g, كجم/kg, ملغ/mg, باوند/lb), counts (قطعة/حبة/كبسولة/قرص/منديل/كيس/pcs) and
  length (ملم/سم/م/mm/cm/m), plus pack multipliers (`2×50 مل`, `10x6مل`). Battery capacity (`7000 ملي امبير`) is
  not mistaken for volume. It converts each size to a
  base unit (ml, g, pcs, mm) and gives it a unit-independent `match_key` (400 ml ≡ 13.5 fl oz ≡ 0.4 l).
- **Alternative keywords.** It builds a clean keyword list for query expansion. Numbers, matched-quantity
  unit words (e.g. `مل` in `400 مل`), special characters and empty strings are removed, while count nouns
  that are part of a quantity (`كبسولة` in `60 كبسولة`) are kept. Hyphenated words are both split and joined
  (`anti-aging` → `anti`, `aging`, `antiaging`), and article-stripped forms are added (`للشعر` → `شعر`, `بالصبار` → `صبار`).
- **CLI and batch mode** with JSON / JSON Lines output.

## Install

```bash
pip install souqnorm
```

For development:

```bash
git clone https://github.com/mtanzil6/souqnorm.git
cd souqnorm
pip install -e ".[dev]"
pytest
```

## Usage

```python
from souqnorm import process

r = process("شامبـــو للشعر الجاف ٤٠٠مل")
r.normalized                  # 'شامبو للشعر الجاف 400 مل'
r.quantities[0].label         # '400 ml'
r.quantities[0].match_key()   # 'qty:400ml'
r.text_without_quantities     # 'شامبو للشعر الجاف'
r.keywords                    # ['شامبو', 'للشعر', 'شعر', 'الجاف', 'جاف']
```

```bash
souqnorm "عطر ٣٫٤ fl oz"
souqnorm --file queries.txt > normalized.jsonl
souqnorm --disable unify_alef,remove_tatweel "أحمر شفاه"
```

Custom configuration:

```python
from souqnorm import NormalizerConfig, QueryNormalizer
qn = QueryNormalizer(NormalizerConfig(taa_marbuta_to_haa=False), strip_article=False)
```

## Reproducing the paper's numbers

```bash
python benchmarks/build_benchmark.py      # synthetic catalog + perturbed queries (seeded)
python benchmarks/run_benchmark.py        # writes benchmarks/results/results.json
```

`results.json` holds the quantity-extraction precision/recall/F1, the BM25 retrieval table (baseline vs.
each pipeline stage), the per-switch ablation, the throughput figures and the hardware they were measured
on -- these are the numbers reported in the paper.

The real-catalog title data used for the paper's E1-E3 experiments is **not distributed with this
repository**. To reproduce those numbers on your own catalog:

```bash
pip install openpyxl
python benchmarks/real_titles.py path/to/titles.xlsx   # writes benchmarks/results/real_titles.json
```

The `build_benchmark.py` retrieval benchmark is **synthetic**. It uses fictional brands and template titles, and its queries are made by
applying common Arabic spelling variations. It shows how each normalization step affects results, but it is not a
substitute for evaluation on real query logs.

## Known limitations

- Article stripping is a heuristic and can wrongly shorten transliterated brand names that start with فال/بال
  (it only adds variants and keeps the original keyword).
- `oz` is treated as fluid ounces (volume), the usual meaning in beauty retail.
- A bare `م` (metre) is ambiguous with other one-letter Arabic abbreviations; it is kept as a unit because
  real catalog titles write cable/tool lengths this way (`1.2م`), at the cost of occasional false positives.
- `match_key()` defaults to a coarse tolerance (2 significant figures) so that cross-unit conversions
  (e.g. fl oz → ml) collapse together despite rounding; pass `sig=3` for exact same-unit sizes that should
  stay distinct (118 ml vs. 120 ml vs. 125 ml).
- There is no spelling correction, stemming beyond articles, or Arabizi (Latin-script Arabic) transliteration yet.

## Citation

A SoftwareX submission describing this library is in preparation. Until it is published, cite the
software itself:

```bibtex
@software{tanzil_souqnorm_2026,
  author  = {Tanzil, Muhammad},
  title   = {souqnorm: Normalization, size parsing and keyword expansion for Arabic/English e-commerce search queries},
  year    = {2026},
  url     = {https://github.com/mtanzil6/souqnorm},
  version = {0.2.0}
}
```

This section will be updated with the paper's citation and DOI once it is accepted.

## License

MIT © 2026 Muhammad Tanzil
