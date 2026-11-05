First public release.

**What's in it**

- Arabic/English text normalization: alef forms, ى/ي, ة/ه, hamza carriers, diacritics, tatweel, Arabic-Indic digits, number/script splitting. Each step can be turned off through `NormalizerConfig`.
- Size parsing for volume, mass, count and length units in Arabic and English (مل, ملل, جم, ج, كبسولة, ml, g, oz …), pack sizes like `10x6مل`, and a `match_key()` so 400 مل, 0.4 لتر and 13.5 fl oz compare equal.
- Keyword generation for query expansion: drops numbers, unit words, stopwords and special characters, splits/joins hyphenated words, strips the definite article.
- `souqnorm` command-line tool with JSON / JSON Lines output.
- Benchmarks: a seeded synthetic retrieval benchmark with ablations, and `benchmarks/real_titles.py` for running the same evaluation on your own catalog.

No runtime dependencies. Python 3.9+.

```bash
pip install git+https://github.com/mtanzil6/souqnorm@v0.1.0
```
