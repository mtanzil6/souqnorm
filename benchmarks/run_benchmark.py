"""Evaluate souqnorm: (1) quantity extraction on a labeled set, (2) BM25 retrieval on the synthetic
benchmark with ablations, (3) throughput. Writes benchmarks/results/results.json and prints tables.

Usage:  python benchmarks/build_benchmark.py && python benchmarks/run_benchmark.py
"""
from __future__ import annotations

import csv
import json
import math
import os
import platform
import re
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path

from souqnorm import NormalizerConfig, QueryNormalizer, __version__

HERE = Path(__file__).parent
DATA = HERE / "data"
RESULTS = HERE / "results"


# ----------------------------------------------------------------------------- BM25
class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.2, b: float = 0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.N = len(docs)
        self.avgdl = sum(map(len, docs)) / self.N
        df = Counter(t for d in docs for t in set(d))
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}
        self.tf = [Counter(d) for d in docs]

    def search(self, q: list[str], k: int = 10) -> list[tuple[int, float]]:
        scores = []
        for i, (tf, d) in enumerate(zip(self.tf, self.docs)):
            s = 0.0
            for t in set(q):
                f = tf.get(t)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * len(d) / self.avgdl))
            if s > 0:
                scores.append((i, s))
        scores.sort(key=lambda x: (-x[1], x[0]))
        return scores[:k]


# ----------------------------------------------------------------------------- analyzers
_BASIC = re.compile(r"\w+", re.UNICODE)


def baseline_analyzer(text: str) -> list[str]:
    """Typical out-of-the-box analyzer: lowercase + Unicode word split, no Arabic normalization."""
    return _BASIC.findall(text.lower())


def souqnorm_analyzer(qn: QueryNormalizer, use_quantities: bool, use_keywords: bool):
    """normalize only -> tokens of the normalized text;
    + quantities -> size spans replaced by a unit-independent match key;
    + keywords -> alternative keywords (hyphen split/join, article stripping) instead of raw tokens."""
    def analyze(text: str) -> list[str]:
        r = qn.process(text)
        if not use_quantities:
            return qn.tokenize(r.normalized)
        toks = r.keywords if use_keywords else qn.tokenize(r.text_without_quantities)
        return toks + [q.match_key() for q in r.quantities]
    return analyze


def evaluate_retrieval(analyzer, catalog, queries) -> dict:
    index = BM25([analyzer(f"{p['title_ar']} {p['title_en']}") for p in catalog])
    ids = [p["id"] for p in catalog]
    p1 = mrr = rec = zero = 0.0
    for q in queries:
        rel = set(q["relevant"])
        hits = [ids[i] for i, _ in index.search(analyzer(q["query"]), 10)]
        if not hits:
            zero += 1
        if hits and hits[0] in rel:
            p1 += 1
        for rank, h in enumerate(hits, 1):
            if h in rel:
                mrr += 1 / rank
                break
        rec += len(rel & set(hits)) / min(len(rel), 10)
    n = len(queries)
    return {"P@1": p1 / n, "MRR@10": mrr / n, "Recall@10": rec / n, "ZeroResult": zero / n}


# ----------------------------------------------------------------------------- unit extraction
_NAIVE = re.compile(r"(\d+(?:\.\d+)?)\s*(ml|l|g|kg|oz|mg)\b", re.I)
_NAIVE_F = {"ml": (1, "ml"), "l": (1000, "ml"), "oz": (29.5735, "ml"), "g": (1, "g"), "kg": (1000, "g"),
            "mg": (0.001, "g")}


def naive_extract(text: str):
    return [(round(float(n) * _NAIVE_F[u.lower()][0], 3), _NAIVE_F[u.lower()][1]) for n, u in _NAIVE.findall(text)]


def evaluate_units(extract, gold_rows) -> dict:
    tp = fp = fn = 0
    for row in gold_rows:
        gold = [(float(v), u) for v, u in row["gold"]]
        pred = list(extract(row["text"]))
        for g in gold:
            m = next((p for p in pred if p[1] == g[1] and math.isclose(p[0], g[0], rel_tol=1e-2)), None)
            if m:
                tp += 1
                pred.remove(m)
            else:
                fn += 1
        fp += len(pred)
    prec = tp / (tp + fp) if tp + fp else 0.0
    recl = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * recl / (prec + recl) if prec + recl else 0.0
    return {"precision": prec, "recall": recl, "F1": f1, "tp": tp, "fp": fp, "fn": fn}


# ----------------------------------------------------------------------------- main
def fmt(rows: dict, cols: list[str]) -> str:
    w = max(map(len, rows)) + 2
    out = ["".ljust(w) + "".join(c.rjust(12) for c in cols)]
    for name, m in rows.items():
        out.append(name.ljust(w) + "".join(f"{m[c]:12.3f}" for c in cols))
    return "\n".join(out)


def main() -> None:
    catalog = list(csv.DictReader(open(DATA / "catalog.csv", encoding="utf-8")))
    queries = [json.loads(l) for l in open(DATA / "queries.jsonl", encoding="utf-8")]
    gold = [json.loads(l) for l in open(DATA / "units_gold.jsonl", encoding="utf-8")
            if l.strip() and not l.lstrip().startswith("#")]
    qn = QueryNormalizer()

    units = {
        "naive regex (Latin units)": evaluate_units(naive_extract, gold),
        "souqnorm": evaluate_units(lambda t: [(q.base_value, q.base_unit) for q in qn.process(t).quantities], gold),
    }

    retrieval = {
        "baseline (lowercase+split)": evaluate_retrieval(baseline_analyzer, catalog, queries),
        "souqnorm normalize": evaluate_retrieval(souqnorm_analyzer(qn, False, False), catalog, queries),
        "+ quantity keys": evaluate_retrieval(souqnorm_analyzer(qn, True, False), catalog, queries),
        "+ quantity keys + keywords": evaluate_retrieval(souqnorm_analyzer(qn, True, True), catalog, queries),
    }

    ablation = {}
    full = NormalizerConfig()
    for flag in ["unicode_nfkc", "digits", "punctuation", "remove_diacritics", "remove_tatweel", "unify_alef",
                 "alef_maqsura_to_yaa", "taa_marbuta_to_haa", "hamza_carriers", "lowercase", "split_scripts"]:
        q2 = QueryNormalizer(replace(full, **{flag: False}))
        ablation[f"- {flag}"] = evaluate_retrieval(souqnorm_analyzer(q2, True, True), catalog, queries)
    ablation["- article stripping"] = evaluate_retrieval(
        souqnorm_analyzer(QueryNormalizer(strip_article=False), True, True), catalog, queries)

    texts = [q["query"] for q in queries] * 20
    t0 = time.perf_counter()
    for t in texts:
        qn.process(t)
    dt = time.perf_counter() - t0

    results = {
        "souqnorm_version": __version__, "python": platform.python_version(), "machine": platform.machine(),
        "hardware": {"processor": platform.processor(), "cpu_count": os.cpu_count(),
                     "ci": os.environ.get("CI", "").lower() in ("1", "true")},
        "catalog_size": len(catalog), "num_queries": len(queries), "unit_gold_size": len(gold),
        "unit_extraction": units, "retrieval": retrieval, "ablation": ablation,
        "throughput_queries_per_sec": len(texts) / dt, "mean_latency_ms": 1000 * dt / len(texts),
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Catalog {len(catalog)} products, {len(queries)} queries, {len(gold)} labeled unit strings\n")
    print("Quantity extraction\n" + fmt(units, ["precision", "recall", "F1"]) + "\n")
    print("Retrieval (BM25)\n" + fmt(retrieval, ["P@1", "MRR@10", "Recall@10", "ZeroResult"]) + "\n")
    print("Ablation from full pipeline\n" + fmt(ablation, ["P@1", "MRR@10", "Recall@10", "ZeroResult"]) + "\n")
    print(f"Throughput: {results['throughput_queries_per_sec']:.0f} queries/s "
          f"({results['mean_latency_ms']:.3f} ms/query) on Python {results['python']}")


if __name__ == "__main__":
    main()
