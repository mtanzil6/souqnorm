"""Build a synthetic, reproducible Arabic/English beauty-product retrieval benchmark.

The catalog uses fictional brands and template-generated titles written in standard orthography.
Queries are derived from a target product by sampling a subset of its title words and applying
orthographic and formatting perturbations commonly seen in user-typed Arabic search queries
(hamza/alef variation, taa marbuta written as haa, alef maqsura/yaa confusion, tatweel, diacritics,
Arabic-Indic digits, unit spelling variants, number-unit concatenation, Latin case changes).

Usage:  python benchmarks/build_benchmark.py [--seed 13] [--out benchmarks/data]
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

BRANDS = [("لومورا", "Lumora"), ("فيليستا", "Velista"), ("روضة", "Rawda"), ("سراج", "Siraj"),
          ("نوريش", "Noorish"), ("أزورا", "Azora"), ("دانة", "Dana"), ("مِسك", "Misk")]

PRODUCTS = [  # (Arabic name, English name, measure kind)
    ("شامبو", "Shampoo", "ml"), ("بلسم", "Conditioner", "ml"), ("كريم مرطب", "Moisturizing Cream", "ml"),
    ("عطر", "Eau de Parfum", "ml"), ("واقي شمس", "Sunscreen", "ml"), ("زيت شعر", "Hair Oil", "ml"),
    ("غسول وجه", "Face Wash", "ml"), ("سيروم", "Serum", "ml"), ("مزيل عرق", "Deodorant", "ml"),
    ("أحمر شفاه", "Lipstick", "g"), ("بودرة", "Face Powder", "g"), ("لوشن جسم", "Body Lotion", "ml"),
    ("صابون", "Soap Bar", "g"), ("قناع شعر", "Hair Mask", "ml"), ("مقشر جسم", "Body Scrub", "g"),
    ("ماء ميسيلار", "Micellar Water", "ml"), ("كريم أساس", "Foundation", "ml"), ("مناديل مبللة", "Wet Wipes", "pcs"),
]

MODIFIERS = [("للشعر الجاف", "for Dry Hair"), ("للبشرة الدهنية", "for Oily Skin"), ("بالصبار", "with Aloe Vera"),
             ("بفيتامين سي", "with Vitamin C"), ("خالٍ من الكبريتات", "Sulfate Free"), ("مضاد للتجاعيد", "Anti-Wrinkle"),
             ("بزيت الأرغان", "with Argan Oil"), ("للبشرة الحساسة", "for Sensitive Skin"), ("بالورد", "with Rose"),
             ("مرطّب مكثّف", "Intense Hydration"), ("بالفحم", "with Charcoal"), ("بالعسل", "with Honey")]

SIZES = {"ml": [30, 50, 100, 150, 200, 250, 400, 500], "g": [4, 10, 50, 100, 200], "pcs": [10, 25, 50, 80]}
AR_UNIT = {"ml": "مل", "g": "جم", "pcs": "قطعة"}
EN_UNIT = {"ml": "ml", "g": "g", "pcs": "pcs"}

AR_UNIT_VARIANTS = {"ml": ["مل", "ملل", "مللي", "ml", "ML"], "g": ["جم", "غ", "غرام", "جرام", "g", "gm"],
                    "pcs": ["قطعة", "قطعه", "حبة", "pcs"]}
AR_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
HARAKAT = ["َ", "ُ", "ِ", "ّ", "ْ"]


def build_catalog(rng: random.Random) -> list[dict]:
    rows, pid = [], 0
    for (ar_p, en_p, kind) in PRODUCTS:
        for (ar_b, en_b) in rng.sample(BRANDS, 5):
            for (ar_m, en_m) in rng.sample(MODIFIERS, 3):
                size = rng.choice(SIZES[kind])
                pid += 1
                rows.append({
                    "id": f"P{pid:04d}",
                    "title_ar": f"{ar_p} {ar_b} {ar_m} {size} {AR_UNIT[kind]}",
                    "title_en": f"{en_b} {en_p} {en_m} {size}{EN_UNIT[kind]}",
                    "size": size, "unit": kind,
                    "_parts": [ar_p, ar_b, ar_m],
                })
    return rows


ARTICLES = ("لل", "بال", "ال")
OZ_PER_ML = 1 / 29.5735


def perturb_word(w: str, rng: random.Random) -> str:
    if rng.random() < 0.3:  # users often drop the article/preposition: "للشعر" -> "شعر"
        for pre in ARTICLES:
            if w.startswith(pre) and len(w) - len(pre) >= 3:
                w = w[len(pre):]
                break
    if rng.random() < 0.5:
        w = w.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    if rng.random() < 0.5:
        w = w.replace("ة", "ه")
    if rng.random() < 0.3:
        w = w.replace("ي", "ى") if w.endswith("ي") else w.replace("ى", "ي")
    if rng.random() < 0.15 and len(w) > 3:
        i = rng.randrange(1, len(w) - 1)
        w = w[:i] + "ـ" * rng.randint(1, 3) + w[i:]
    if rng.random() < 0.15:
        i = rng.randrange(1, len(w) + 1)
        w = w[:i] + rng.choice(HARAKAT) + w[i:]
    return w


def make_query(p: dict, rng: random.Random) -> tuple[str, dict]:
    """Return a perturbed query for product *p* and the constraints the query expresses."""
    ar_p, ar_b, ar_m = p["_parts"]
    words = ar_p.split()
    cons = {"product": ar_p, "brand": None, "modifier": None, "size": None}
    latin_brand = None
    if rng.random() < 0.6:
        cons["brand"] = ar_b
        if rng.random() < 0.3:  # brand typed in Latin script
            latin_brand = dict(BRANDS)[ar_b]
        else:
            words += ar_b.split()
    if rng.random() < 0.7:
        words += ar_m.split()[-1:] if rng.random() < 0.5 else ar_m.split()
        cons["modifier"] = ar_m
    words = [perturb_word(w, rng) for w in words]
    if latin_brand:
        words.insert(rng.randint(0, len(words)), latin_brand.lower() if rng.random() < 0.5 else latin_brand)
    num = str(p["size"])
    if rng.random() < 0.4:
        num = num.translate(AR_DIGITS)
    unit = rng.choice(AR_UNIT_VARIANTS[p["unit"]])
    size = num + unit if rng.random() < 0.5 else f"{num} {unit}"
    if p["unit"] == "ml" and p["size"] >= 30 and rng.random() < 0.15:  # size given in fluid ounces
        size = f"{p['size'] * OZ_PER_ML:.1f} {rng.choice(['oz', 'fl oz', 'أونصة'])}"
    if rng.random() < 0.8:
        words.insert(rng.randint(0, len(words)), size)
        cons["size"] = (p["size"], p["unit"])
    return " ".join(words), cons


def relevant_ids(catalog: list[dict], cons: dict) -> list[str]:
    """All products satisfying every constraint expressed in the query (graded as relevant)."""
    out = []
    for r in catalog:
        ar_p, ar_b, ar_m = r["_parts"]
        if ar_p != cons["product"]:
            continue
        if cons["brand"] and ar_b != cons["brand"]:
            continue
        if cons["modifier"] and ar_m != cons["modifier"]:
            continue
        if cons["size"] and (r["size"], r["unit"]) != cons["size"]:
            continue
        out.append(r["id"])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--queries-per-product", type=int, default=2)
    ap.add_argument("--out", default=str(Path(__file__).parent / "data"))
    a = ap.parse_args()
    rng = random.Random(a.seed)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    catalog = build_catalog(rng)
    with open(out / "catalog.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "title_ar", "title_en", "size", "unit"])
        w.writeheader()
        for r in catalog:
            w.writerow({k: r[k] for k in w.fieldnames})
    with open(out / "queries.jsonl", "w", encoding="utf-8") as fh:
        qid = 0
        for p in catalog:
            for _ in range(a.queries_per_product):
                qid += 1
                q, cons = make_query(p, rng)
                rec = {"qid": f"Q{qid:04d}", "query": q, "target": p["id"],
                       "relevant": relevant_ids(catalog, cons)}
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"catalog: {len(catalog)} products, queries: {qid} -> {out}")


if __name__ == "__main__":
    main()
