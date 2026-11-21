"""Generic product feed importer (CSV or JSON / JSON-lines).

This is how platform data comes in until each platform has its own connector: affiliate
feeds (Amazon Associates / Flipkart Affiliate), catalogue exports a platform or brand
shares with us, or a team's own data collection.

Recognised columns (case-insensitive; extra columns are ignored):

    platform, platform_product_id, url, name, brand, quantity, gtin (or ean / barcode),
    ingredients, price, mrp, in_stock, location (or pincode), image_url, category, veg_mark
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, Iterator

from ..models import RawOffer, RawProduct
from ..platforms import PLATFORMS

ALIASES = {
    "ean": "gtin", "barcode": "gtin", "upc": "gtin",
    "pincode": "location", "city": "location",
    "ingredients_text": "ingredients", "ingredient_list": "ingredients",
    "title": "name", "product_name": "name",
    "selling_price": "price", "sp": "price",
    "image": "image_url", "link": "url", "product_url": "url",
    "sku": "platform_product_id", "asin": "platform_product_id", "fsn": "platform_product_id",
}


def _num(v) -> float | None:
    if v in (None, ""):
        return None
    try:
        return float(str(v).replace("₹", "").replace(",", "").strip())
    except ValueError:
        return None


def _bool(v) -> bool | None:
    if v in (None, ""):
        return None
    return str(v).strip().lower() in ("1", "true", "yes", "y", "in stock", "available")


def _rows(path: Path) -> Iterator[dict]:
    if path.suffix.lower() == ".csv":
        with open(path, newline="", encoding="utf-8-sig") as fh:
            yield from csv.DictReader(fh)
    elif path.suffix.lower() in (".jsonl", ".ndjson"):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    yield json.loads(line)
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
        yield from (data["products"] if isinstance(data, dict) else data)


def normalise(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        key = str(k).strip().lower().replace(" ", "_")
        out[ALIASES.get(key, key)] = v.strip() if isinstance(v, str) else v
    return out


def rows_to_products(rows: Iterable[dict], feed_name: str, platform: str | None = None) -> Iterator[RawProduct]:
    for raw_row in rows:
        r = normalise(raw_row)
        if not r.get("name"):
            continue
        plat = (platform or r.get("platform") or "").strip().lower() or None
        if plat and plat not in PLATFORMS:
            raise ValueError(f"Unknown platform {plat!r}; known: {', '.join(PLATFORMS)}")
        offers = []
        if plat:
            offers.append(
                RawOffer(
                    platform=plat,
                    url=r.get("url") or None,
                    platform_product_id=r.get("platform_product_id") or None,
                    price=_num(r.get("price")),
                    mrp=_num(r.get("mrp")),
                    in_stock=_bool(r.get("in_stock")),
                    location=str(r.get("location") or ""),
                )
            )
        veg = (r.get("veg_mark") or "").lower() or None
        yield RawProduct(
            source=f"feed:{feed_name}",
            source_id=r.get("platform_product_id") or r.get("gtin"),
            source_url=r.get("url") or None,
            name=r["name"],
            brand=r.get("brand") or None,
            quantity=r.get("quantity") or None,
            gtin=str(r.get("gtin") or "") or None,
            ingredients_text=r.get("ingredients") or None,
            categories=[r["category"]] if r.get("category") else [],
            image_url=r.get("image_url") or None,
            veg_mark=veg if veg in ("green", "brown") else None,
            offers=offers,
        )


def read_feed(path: str | Path, platform: str | None = None) -> Iterator[RawProduct]:
    path = Path(path)
    yield from rows_to_products(_rows(path), path.stem, platform)
