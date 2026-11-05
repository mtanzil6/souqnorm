"""Command-line interface: `souqnorm "query"` or `souqnorm --file queries.txt`."""
from __future__ import annotations

import argparse
import json
import sys

from .arabic import NormalizerConfig
from .pipeline import QueryNormalizer


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="souqnorm", description="Normalize Arabic/English product search queries.")
    p.add_argument("query", nargs="*", help="query text (omit when using --file)")
    p.add_argument("-f", "--file", help="read one query per line ('-' for stdin); writes JSON Lines")
    p.add_argument("--keep-taa-marbuta", action="store_true", help="do not map ة to ه")
    p.add_argument("--keep-hamza", action="store_true", help="do not map ؤ/ئ to و/ي")
    p.add_argument("--no-article-strip", action="store_true", help="do not add ال-stripped keywords")
    a = p.parse_args(argv)

    cfg = NormalizerConfig(taa_marbuta_to_haa=not a.keep_taa_marbuta, hamza_carriers=not a.keep_hamza)
    qn = QueryNormalizer(cfg, strip_article=not a.no_article_strip)

    if a.file:
        fh = sys.stdin if a.file == "-" else open(a.file, encoding="utf-8")
        with fh:
            for line in fh:
                if line.strip():
                    print(json.dumps(qn.process(line.strip()).to_dict(), ensure_ascii=False))
        return 0
    if not a.query:
        p.error("provide a query or --file")
    print(json.dumps(qn.process(" ".join(a.query)).to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
