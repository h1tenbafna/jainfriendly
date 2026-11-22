"""Catalogue command line.

    python -m jainfriendly.catalog sync-off --pages 5        # import from Open Food Facts
    python -m jainfriendly.catalog barcode 8901491503051     # import one barcode
    python -m jainfriendly.catalog import-feed offers.csv --platform blinkit
    python -m jainfriendly.catalog sync-platform blinkit --pincode 400001 --query namkeen
    python -m jainfriendly.catalog import-capture zepto search.json product.html --pincode 400001
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

from pathlib import Path

from .connectors import (
    CAPTURE_PARSERS, LIVE_CONNECTORS, Blocked, DetailCache, Location, OpenFoodFactsConnector,
    geocode_pincode, read_feed,
)
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
    sp = sub.add_parser("sync-platform", help="search a store platform at a pincode and import results")
    sp.add_argument("platform", choices=sorted(LIVE_CONNECTORS))
    sp.add_argument("--query", required=True)
    sp.add_argument("--pincode", required=True)
    sp.add_argument("--lat", type=float, help="defaults to the pincode's centre (OpenStreetMap)")
    sp.add_argument("--lon", type=float)
    sp.add_argument("--pages", type=int, default=1)
    ic = sub.add_parser("import-capture", help="import saved platform responses (JSON, or product page HTML)")
    ic.add_argument("platform", choices=sorted(CAPTURE_PARSERS))
    ic.add_argument("paths", nargs="+")
    ic.add_argument("--pincode", default="", help="where the prices/stock were seen")
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
    elif args.cmd == "sync-platform":
        if (args.lat is None) != (args.lon is None):
            ap.error("pass both --lat and --lon, or neither")
        loc = (Location(args.pincode, args.lat, args.lon) if args.lat is not None
               else geocode_pincode(cat.conn, args.pincode))
        connector = LIVE_CONNECTORS[args.platform](cache=DetailCache(cat.conn))
        n = 0
        try:
            for raw in connector.fetch(args.query, loc, max_pages=args.pages):
                cat.upsert(raw)
                n += 1
        except Blocked as exc:
            print(f"Imported {n} products, then stopped: {exc}")
            return 1
        print(f"Imported {n} products from {args.platform} for {args.query!r} at {args.pincode}.")
    elif args.cmd == "import-capture":
        parse = CAPTURE_PARSERS[args.platform]
        n = 0
        for path in map(Path, args.paths):
            text = path.read_text(encoding="utf-8")
            data = text if path.suffix.lower() in (".html", ".htm") else json.loads(text)
            for raw in parse(data, args.pincode):
                cat.upsert(raw)
                n += 1
        print(f"Imported {n} products from {len(args.paths)} {args.platform} file(s).")
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
