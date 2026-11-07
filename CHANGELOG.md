# Changelog

## Unreleased
- Fix: battery-capacity guard no longer rejects sizes followed by the standalone pharmacy abbreviation
  "amp" (ampoule), e.g. "zinc 50mg amp" -- the English mAh/amp/ampere lookahead was never actually
  load-bearing (the "mAh" pattern is already rejected because the lone-letter "m" unit can't match a
  trailing "h"), so it only ever misfired on unrelated units

## 0.2.0 (2026-11-07)
- Fix: battery-capacity guard no longer rejects legitimate sizes like "5 ml a day" or "500 mg a day",
  and no longer rejects ampoule products ("امبولة") that happen to start with the same letters as "امبير"
- Fix: thousands separators ("1,500 مل") no longer truncate the number to the last group ("500 مل")
- Fix: count nouns that are part of a quantity (e.g. "كبسولة" in "60 كبسولة") are kept as keywords instead
  of being discarded with the quantity
- Fix: measurement-unit words are only dropped from keywords when actually consumed by a matched quantity,
  so e.g. "ملي" in the (correctly rejected) "7000 ملي امبير" is no longer silently dropped
- Fix: `split_scripts` now splits Arabic/Latin boundaries correctly when `lowercase=False`
- Fix: tokens no longer absorb Arabic punctuation (، ؛ ؟) when `punctuation=False`
- `match_key()` now documents the sig-figs tolerance explicitly and supports a higher-precision opt-in
  (`match_key(sig=3)`) for distinguishing close same-unit sizes (118 ml vs. 120 ml vs. 125 ml)
- `Quantity`/`UnitParser.parse` docstring documents that a two-number dimension pattern ("38*29.5 سم")
  discards the first number
- `DEFAULT_STOPWORDS` is now exported from the package so callers can extend it
- CLI: replaced `--keep-taa-marbuta`/`--keep-hamza` with a general `--disable` flag covering every
  `NormalizerConfig` switch (breaking change)
- Benchmarks: hardware is recorded in `results.json`; `units_gold.jsonl` extended with real-catalog
  patterns; ablation now covers all 11 `NormalizerConfig` switches; `real_titles.py` reports both a
  strict known-item and a lenient relevance definition

## 0.1.0 (2026-11-05)
- Arabic/English orthographic normalization with per-step configuration
- Quantity extraction for volume, mass, count and length units, with pack multipliers and cross-unit match keys
- Alternative keyword generation (numbers, unit words and special characters removed; hyphen split/join; article stripping)
- CLI with JSON / JSON Lines output
- Synthetic benchmark and real-catalog evaluation script
