import json

import pytest

from souqnorm import NormalizerConfig, QueryNormalizer, normalize_text, process
from souqnorm.cli import main


@pytest.mark.parametrize("raw, expected", [
    ("أحمر شفاه", "احمر شفاه"),
    ("إيلاف", "ايلاف"),
    ("آمن", "امن"),
    ("مُرَطِّب", "مرطب"),
    ("الدهنيـــة", "الدهنيه"),
    ("مستشفى", "مستشفي"),
    ("لؤلؤ", "لولو"),
    ("مضيئة", "مضييه"),
    ("٤٠٠", "400"),
    ("۵۰", "50"),
    ("٣٫٤", "3.4"),
    ("3,4 oz", "3.4 oz"),
    ("1,000", "1,000"),
    ("Shampoo  ANTI-Dandruff", "shampoo anti-dandruff"),
    ("400مل", "400 مل"),
    ("spf50", "spf 50"),
    ("كريمcream", "كريم cream"),
    ("ﻻ", "لا"),  # presentation form via NFKC
])
def test_normalize_text(raw, expected):
    assert normalize_text(raw) == expected


def test_config_switches():
    cfg = NormalizerConfig(taa_marbuta_to_haa=False, unify_alef=False)
    assert normalize_text("أداة", cfg) == "أداة"


@pytest.mark.parametrize("query, label, base", [
    ("شامبو ٤٠٠مل", "400 ml", 400),
    ("شامبو 400 ملل", "400 ml", 400),
    ("شامبو 400 مللي", "400 ml", 400),
    ("lotion 250ML", "250 ml", 250),
    ("زيت 1 لتر", "1 l", 1000),
    ("perfume 3.4 fl oz", "3.4 fl oz", 100.55),
    ("serum 1.7oz", "1.7 oz", 50.275),
    ("عطر ١٠٠ مل", "100 ml", 100),
    ("كريم 50 جم", "50 g", 50),
    ("powder 1.5kg", "1.5 kg", 1500),
    ("فيتامين 500 ملغ", "500 mg", 0.5),
    ("مناديل 3 قطع", "3 pcs", 3),
    ("2x100ml", "2 x 100 ml", 200),
    ("٢×٥٠ مل", "2 x 50 ml", 100),
])
def test_quantities(query, label, base):
    qs = process(query).quantities
    assert len(qs) == 1
    assert qs[0].label == label
    assert qs[0].base_value == pytest.approx(base, rel=1e-3)


@pytest.mark.parametrize("query", ["spf 50 lotion", "50 غسول", "عطر رقم 5", "vitamin c 20%"])
def test_no_false_quantities(query):
    assert process(query).quantities == []


def test_keywords_filter_numbers_units_and_hyphens():
    r = process("كريم anti-aging للبشرة 50 مل")
    assert "مل" not in r.keywords
    assert "50" not in r.keywords
    assert all("-" not in k and " " not in k and k for k in r.keywords)
    assert {"anti", "aging", "antiaging"} <= set(r.keywords)


def test_article_stripping():
    r = process("شامبو للشعر الجاف بالصبار")
    assert {"شعر", "جاف", "صبار"} <= set(r.keywords)
    assert "شعر" not in QueryNormalizer(strip_article=False).process("للشعر").keywords


def test_variants_and_text_without_quantities():
    r = process("شامبو للشعر 400مل")
    assert r.text_without_quantities == "شامبو للشعر"
    assert "شامبو للشعر 400 ml" in r.variants
    assert r.variants[0] == r.normalized


def test_to_dict_is_json_serializable():
    json.dumps(process("عطر 100 مل").to_dict(), ensure_ascii=False)


def test_cli_single(capsys):
    assert main(["عطر", "١٠٠مل"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["quantities"][0]["label"] == "100 ml"


def test_cli_file(tmp_path, capsys):
    f = tmp_path / "q.txt"
    f.write_text("عطر 50 مل\n\nشامبو\n", encoding="utf-8")
    assert main(["--file", str(f)]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 2


def test_match_key_cross_unit():
    a = process("شامبو 400 مل").quantities[0].match_key()
    b = process("shampoo 13.5 fl oz").quantities[0].match_key()
    c = process("شامبو 0.4 لتر").quantities[0].match_key()
    assert a == b == c == "qty:400ml"


@pytest.mark.parametrize("query, label", [
    ("جل شعر - 340ج", "340 g"),
    ("كبسولات فيتامين - 60 كبسولة", "60 pcs"),
    ("مناديل - 48 منديل", "48 pcs"),
    ("بروتين - 1.6 باوند", "1.6 lb"),
    ("كيبل شحن بطول 1.2م", "1.2 m"),
    ("مجعد الشعر - 32 ملم", "32 mm"),
    ("حقيبة - 38*29.5سم", "29.5 cm"),
    ("أمبولة - 10x6مل", "10 x 6 ml"),
])
def test_real_catalog_patterns(query, label):
    assert [q.label for q in process(query).quantities] == [label]


@pytest.mark.parametrize("query", ["بطارية 7000 ملي امبير", "power bank 10000 mah"])
def test_battery_capacity_not_volume(query):
    assert process(query).quantities == []


def test_stopwords_and_count_nouns_in_keywords():
    r = process("أمبولة لتساقط الشعر من كيراستاس - 10x6مل")
    assert "من" not in r.keywords
    assert "امبوله" in r.keywords
    assert "مل" not in r.keywords
    assert "او" in process("عطر او دو بارفيوم").keywords
