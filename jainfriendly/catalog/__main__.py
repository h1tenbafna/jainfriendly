"""Catalogue command line.

    python -m jainfriendly.catalog sync-off --pages 5        # import from Open Food Facts
    python -m jainfriendly.catalog barcode 8901491503051     # import one barcode
    python -m jainfriendly.catalog import-feed offers.csv --platform blinkit
    python -m jainfriendly.catalog reanalyze                 # after editing data/*.yaml
    python -m jainfriendly.catalog stats
    python -m jainfriendly.catalog todo                      # most common unrecognised ingredients
    python -m jainfriendly.catalog export seed/catalog.jsonl.gz   # portable snapshot
    python -m jainfriendly.catalog load seed/catalog.jsonl.gz     # rebuild a database from it
"""

from __future__ import annotations

import argparse
import json
import sys

from .connectors import OpenFoodFactsConnector, read_feed
from .store import Catalog


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="jainfriendly.catalog", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", help="SQLite path (default: $JAINFRIENDLY_DB or data/catalog.db)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sync-off", help="import products from Open Food Facts")
    s.add_argument("--pages", type=int, default=None, help="max pages of 100 (default: all)")
    s.add_argument("--start-page", type=int, default=1)
    s.add_argument("--country", default="india")
    b = sub.add_parser("barcode", help="import specific barcodes from Open Food Facts")
    b.add_argument("codes", nargs="+")
    f = sub.add_parser("import-feed", help="import a CSV/JSON product feed")
    f.add_argument("path")
    f.add_argument("--platform", help="platform id if the feed has no 'platform' column")
    r = sub.add_parser("reanalyze", help="re-run analysis on products analysed with an older knowledge base")
    r.add_argument("--all", action="store_true")
    sub.add_parser("stats")
    t = sub.add_parser("todo", help="most common unrecognised ingredients")
    t.add_argument("-n", type=int, default=40)
    e = sub.add_parser("export", help="write all products and offers to a .jsonl(.gz) snapshot")
    e.add_argument("path")
    ld = sub.add_parser("load", help="load a snapshot written by 'export'")
    ld.add_argument("path")
    args = ap.parse_args(argv)

    cat = Catalog(args.db)
    if args.cmd == "sync-off":
        from .connectors.openfoodfacts import SourceUnavailable

        n = 0
        off = OpenFoodFactsConnector()
        try:
            for raw in off.fetch(args.pages, args.start_page, args.country):
                cat.upsert(raw)
                n += 1
                if n % 100 == 0:
                    print(f"  {n} products (page {off.last_page_done + 1})...", file=sys.stderr, flush=True)
        except SourceUnavailable as exc:
            resume = max(off.last_page_done + 1, args.start_page)
            print(f"Imported {n} products, then stopped: {exc}\n"
                  f"Resume later with: sync-off --start-page {resume}")
            return 1
        print(f"Imported {n} products from Open Food Facts.")
    elif args.cmd == "barcode":
        conn = OpenFoodFactsConnector()
        for code in args.codes:
            raw = conn.fetch_barcode(code)
            print(f"{code}: {'imported #' + str(cat.upsert(raw)) if raw else 'not found'}")
    elif args.cmd == "import-feed":
        n = sum(1 for raw in read_feed(args.path, args.platform) if cat.upsert(raw))
        print(f"Imported {n} rows from {args.path}.")
    elif args.cmd == "reanalyze":
        print(f"Re-analysed {cat.reanalyze(args.all)} products.")
    elif args.cmd == "stats":
        print(json.dumps(cat.facets(), indent=2))
    elif args.cmd == "export":
        print(f"Exported {cat.export_snapshot(args.path)} products to {args.path}.")
    elif args.cmd == "load":
        print(f"Loaded {cat.load_snapshot(args.path)} products from {args.path}.")
    elif args.cmd == "todo":
        for text, count in cat.top_unrecognized(args.n):
            print(f"{count:5d}  {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
