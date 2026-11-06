"""Command-line interface: `souqnorm "query"` or `souqnorm --file queries.txt`."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields

from .arabic import NormalizerConfig
from .pipeline import QueryNormalizer

_CONFIG_FIELDS = sorted(f.name for f in fields(NormalizerConfig))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="souqnorm", description="Normalize Arabic/English product search queries.")
    p.add_argument("query", nargs="*", help="query text (omit when using --file)")
    p.add_argument("-f", "--file", help="read one query per line ('-' for stdin); writes JSON Lines")
    p.add_argument("--disable", metavar="SWITCHES",
                    help="comma-separated NormalizerConfig switches to turn off, e.g. "
                         "unify_alef,remove_tatweel. Choices: " + ", ".join(_CONFIG_FIELDS))
    p.add_argument("--no-article-strip", action="store_true", help="do not add ال-stripped keywords")
    a = p.parse_args(argv)

    overrides = {}
    if a.disable:
        for name in a.disable.split(","):
            name = name.strip()
            if name not in _CONFIG_FIELDS:
                p.error(f"unknown config switch: {name!r} (choices: {', '.join(_CONFIG_FIELDS)})")
            overrides[name] = False

    cfg = NormalizerConfig(**overrides)
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
