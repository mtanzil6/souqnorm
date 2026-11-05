"""Evaluate souqnorm on a real product-title catalog (one title per row; .xlsx, .csv or .txt).

The catalog file is NOT distributed with this repository. Run:

    python benchmarks/real_titles.py path/to/titles.xlsx [--sample 2000] [--seed 7]

Experiments
  E1  Orthographic variation in the catalog and how normalization consolidates it
  E2  Size/quantity coverage (souqnorm vs. a Latin-unit regex)
  E3  Known-item retrieval with BM25 over the full catalog. Queries are built from sampled titles:
      3-5 consecutive words of the product name, orthographic perturbations users commonly make, and the
      size re-written in a different but equivalent form. A title is relevant if it contains every query
      word (compared after normalization) and, when the query states a size, has the same size.
Writes benchmarks/results/real_titles.json
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from souqnorm import QueryNormalizer, normalize_text

sys.path.insert(0, str(Path(__file__).parent))
from run_benchmark import baseline_analyzer, naive_extract  # noqa: E402

RESULTS = Path(__file__).parent / "results"
AR_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
UNIT_SPELLINGS = {"ml": ["مل", "ملل", "مللي", "ml", "ML"], "g": ["جم", "غ", "جرام", "غرام", "g"],
                  "pcs": ["قطعة", "قطعه", "حبة", "pcs"]}


def load_titles(path: str) -> list[str]:
    p = Path(path)
    if p.suffix.lower() in {".xlsx", ".xlsm"}:
        import openpyxl  # optional, only for this script
        ws = openpyxl.load_workbook(p, read_only=True).worksheets[0]
        rows = [r[0] for r in ws.iter_rows(values_only=True)][1:]
    else:
        rows = p.read_text(encoding="utf-8").splitlines()[1 if p.suffix == ".csv" else 0:]
    return [str(r).strip() for r in rows if r and str(r).strip()]


class InvertedBM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.2, b: float = 0.75):
        self.k1, self.b, self.N = k1, b, len(docs)
        self.len = [len(d) for d in docs]
        self.avgdl = sum(self.len) / self.N
        self.post: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for i, d in enumerate(docs):
            for t, f in Counter(d).items():
                self.post[t].append((i, f))
        self.idf = {t: math.log(1 + (self.N - len(p) + 0.5) / (len(p) + 0.5)) for t, p in self.post.items()}

    def search(self, q: list[str], k: int = 10) -> list[int]:
        acc: dict[int, float] = defaultdict(float)
        for t in set(q):
            for i, f in self.post.get(t, ()):
                acc[i] += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avgdl))
        return [i for i, _ in sorted(acc.items(), key=lambda x: (-x[1], x[0]))[:k]]


def perturb(w: str, rng: random.Random) -> str:
    if rng.random() < 0.5:
        w = re.sub("[أإآ]", "ا", w)
    if rng.random() < 0.5:
        w = w.replace("ة", "ه")
    if w.endswith("ي") and rng.random() < 0.3:
        w = w[:-1] + "ى"
    if rng.random() < 0.1 and len(w) > 3:
        i = rng.randrange(1, len(w) - 1)
        w = w[:i] + "ـ" * rng.randint(1, 3) + w[i:]
    return w


def make_query(title: str, qn: QueryNormalizer, rng: random.Random):
    name = title.split(" - ")[0]
    words = [w for w in name.split() if re.search(r"[؀-ۿ]", w) and not re.search(r"\d", w)]
    if len(words) < 3:
        return None
    n = rng.randint(3, min(5, len(words)))
    s = rng.randrange(0, len(words) - n + 1)
    clean = words[s:s + n]
    query_words = [perturb(w, rng) for w in clean]
    qs = qn.process(title).quantities
    size = None
    if qs and qs[0].unit in UNIT_SPELLINGS and qs[0].multiplier == 1 and rng.random() < 0.7:
        q = qs[0]
        num = f"{q.value:g}"
        if rng.random() < 0.4:
            num = num.translate(AR_DIGITS)
        unit = rng.choice(UNIT_SPELLINGS[q.unit])
        query_words.insert(rng.randint(0, len(query_words)), num + unit if rng.random() < 0.5 else f"{num} {unit}")
        size = q.match_key()
    return " ".join(query_words), clean, size


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("titles")
    ap.add_argument("--sample", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    titles = load_titles(a.titles)
    qn = QueryNormalizer()
    processed = [qn.process(t) for t in titles]
    out: dict = {"num_titles": len(titles)}

    # E1 ---------------------------------------------------------------------------------------
    checks = {"hyphen": r"-", "taa_marbuta": "ة", "hamza_alef": "[أإآ]", "number_attached_to_word": r"\d[^\d\s.,%+\-)]",
              "latin_script": "[A-Za-z]", "alef_maqsura": "ى", "diacritics": "[ً-ْ]",
              "arabic_indic_digits": "[٠-٩۰-۹]", "tatweel": "ـ"}
    out["E1_phenomena"] = {k: sum(bool(re.search(p, t)) for t in titles) / len(titles) for k, p in checks.items()}
    raw_vocab = Counter(w for t in titles for w in baseline_analyzer(t))
    norm_vocab = Counter(w for r in processed for w in qn.tokenize(r.normalized))
    groups = defaultdict(set)
    for w in raw_vocab:
        groups[normalize_text(w)].add(w)
    out["E1_vocabulary"] = {
        "raw_types": len(raw_vocab), "normalized_types": len(norm_vocab),
        "reduction": 1 - len(norm_vocab) / len(raw_vocab),
        "raw_unique_titles": len(set(titles)), "normalized_unique_titles": len({r.normalized for r in processed}),
        "titles_changed_by_normalization": sum(r.normalized != t for r, t in zip(processed, titles)) / len(titles),
        "top_variant_groups": sorted(([k, sorted(v), sum(raw_vocab[x] for x in v)] for k, v in groups.items() if len(v) > 1),
                                     key=lambda x: -x[2])[:15],
    }

    # E2 ---------------------------------------------------------------------------------------
    unit_counts = Counter(q.unit for r in processed for q in r.quantities)
    out["E2_quantities"] = {
        "souqnorm_titles_with_size": sum(bool(r.quantities) for r in processed) / len(titles),
        "naive_titles_with_size": sum(bool(naive_extract(t)) for t in titles) / len(titles),
        "unit_distribution": dict(unit_counts.most_common()),
    }

    # E3 ---------------------------------------------------------------------------------------
    rng = random.Random(a.seed)
    norm_tok_sets = [set(qn.tokenize(r.normalized)) for r in processed]
    size_keys = [{q.match_key() for q in r.quantities} for r in processed]
    tok_index: dict[str, set[int]] = defaultdict(set)
    for i, toks in enumerate(norm_tok_sets):
        for tok in toks:
            tok_index[tok].add(i)
    queries = []
    for idx in rng.sample(range(len(titles)), min(a.sample * 3, len(titles))):
        m = make_query(titles[idx], qn, rng)
        if not m:
            continue
        q, clean, size = m
        need = set(qn.tokenize(qn.normalize(" ".join(clean))))
        if not need:
            continue
        rel = set.intersection(*(tok_index.get(w, set()) for w in need))
        rel = {i for i in rel if size is None or size in size_keys[i]} | {idx}
        queries.append({"query": q, "target": idx, "relevant": rel})
        if len(queries) == a.sample:
            break

    def sq_analyzer(text: str) -> list[str]:
        r = qn.process(text)
        return r.keywords + [q.match_key() for q in r.quantities]

    systems = {"baseline (lowercase+split)": baseline_analyzer,
               "souqnorm normalize": lambda t: qn.tokenize(qn.normalize(t)),
               "+ quantity keys": lambda t: (lambda r: qn.tokenize(r.text_without_quantities)
                                             + [q.match_key() for q in r.quantities])(qn.process(t)),
               "+ quantity keys + keywords": sq_analyzer}
    out["E3_retrieval"] = {"num_queries": len(queries),
                           "mean_relevant_per_query": sum(len(q["relevant"]) for q in queries) / len(queries)}
    for name, an in systems.items():
        t0 = time.perf_counter()
        index = InvertedBM25([an(t) for t in titles])
        p1 = mrr = rec = zero = 0.0
        for q in queries:
            hits = index.search(an(q["query"]), 10)
            rel = q["relevant"]
            zero += not hits
            p1 += bool(hits) and hits[0] in rel
            mrr += next((1 / r for r, h in enumerate(hits, 1) if h in rel), 0.0)
            rec += len(rel & set(hits)) / min(len(rel), 10)
        n = len(queries)
        out["E3_retrieval"][name] = {"P@1": p1 / n, "MRR@10": mrr / n, "Recall@10": rec / n,
                                     "ZeroResult": zero / n, "seconds": time.perf_counter() - t0}
    out["E3_examples"] = [{"query": q["query"], "target_title": titles[q["target"]], "num_relevant": len(q["relevant"])}
                          for q in queries[:12]]

    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "real_titles.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "E3_examples"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
