"""Zepto parsers.

What the Zepto website does, as observed on 2026-11-22:

    GET https://bff-gateway.zepto.com/search-federator-service/api/v1/search
        ?query=<q>&pageNumber=<n>&mode=AUTOSUGGEST
        -> {"layout": [{"widgetId": "PRODUCT_GRID", "data": {"resolver": {"data": {"items": [
               {"productResponse": {product: {id, name, brand, ingredients, ...},
                                    productVariant: {id, formattedPacksize, packsize, unitOfMeasure,
                                                     images: [{path}]},
                                    mrp, sellingPrice, discountedSellingPrice (paise),
                                    outOfStock, availableQuantity}}]}}}}, ...],
            "nextPageParams": {"pageNumber": n}, "hasReachedEnd": bool, "totalProductCount": n}
    https://www.zepto.com/pn/<slug>/pvid/<variant id>  (product page, server-rendered)
        -> schema.org JSON-LD Product with additionalProperty [{name, value}] including
           "Ingredients", "Allergen information", "Dietary preference", "Unit"; offers.price (₹).

The search request carries a per-request signature and CSRF headers, and the site sits
behind an AWS WAF browser check. We don't reproduce either, so there is no server-side Zepto
search: these parsers take responses that the Zepto page or app fetched itself (on a user's
device), via `python -m jainfriendly.catalog import-capture zepto <file>`.

About half of search results include `product.ingredients`; for the rest, the product page's
JSON-LD has them.
"""

from __future__ import annotations

import json
import re

from ..models import RawOffer, RawProduct
from .base import compose_ingredients, money, slugify, veg_mark_from

PLATFORM = "zepto"
BASE = "https://www.zepto.com"
IMAGE_BASE = "https://cdn.zeptonow.com/production/"
UNITS = {"GRAM": "g", "KILOGRAM": "kg", "MILLILITRE": "ml", "MILLILITER": "ml", "LITRE": "l", "LITER": "l", "PIECE": "pc"}


def product_url(variant_id: str, full_name: str) -> str:
    return f"{BASE}/pn/{slugify(full_name)}/pvid/{variant_id}"


def clean_name(name: str) -> str:
    """Zepto appends marketing text after ' | ' ("Haldiram's Bhujia | Spicy & Crunchy Snack")."""
    return name.split(" | ")[0].strip()


def quantity(variant: dict) -> str | None:
    """'1 pack (200 g)' -> '200 g'; else packsize + unit."""
    fmt = (variant.get("formattedPacksize") or "").strip()
    m = re.search(r"\(([^()]+)\)\s*$", fmt)
    if m:
        return m.group(1).strip()
    if variant.get("packsize") and variant.get("unitOfMeasure") in UNITS:
        return f"{variant['packsize']} {UNITS[variant['unitOfMeasure']]}"
    return fmt or None


def _paise(v) -> float | None:
    return None if v is None else round(float(v) / 100, 2)


# ---------------------------------------------------------------------------- search
def parse_search(resp: dict, pincode: str = "") -> list[RawProduct]:
    out = []
    for widget in resp.get("layout") or []:
        if widget.get("widgetId") != "PRODUCT_GRID":
            continue
        items = (((widget.get("data") or {}).get("resolver") or {}).get("data") or {}).get("items") or []
        for item in items:
            pr = item.get("productResponse") or {}
            product, variant = pr.get("product") or {}, pr.get("productVariant") or {}
            vid, full_name = variant.get("id"), (product.get("name") or "").strip()
            if not vid or not full_name:
                continue
            url = product_url(vid, full_name)
            images = variant.get("images") or []
            price = _paise(pr.get("discountedSellingPrice", pr.get("sellingPrice")))
            out.append(
                RawProduct(
                    source=PLATFORM,
                    source_id=vid,
                    source_url=url,
                    name=clean_name(full_name),
                    brand=(product.get("brand") or "").strip() or None,
                    quantity=quantity(variant),
                    ingredients_text=compose_ingredients(product.get("ingredients"), None),
                    image_url=IMAGE_BASE + images[0]["path"] if images and images[0].get("path") else None,
                    offers=[RawOffer(PLATFORM, url=url, platform_product_id=vid, price=price,
                                     mrp=_paise(pr.get("mrp")) or price,
                                     in_stock=None if pr.get("outOfStock") is None else not pr["outOfStock"],
                                     location=pincode)],
                )
            )
    return out


def next_page(resp: dict) -> int | None:
    if resp.get("hasReachedEnd"):
        return None
    return (resp.get("nextPageParams") or {}).get("pageNumber")


# ---------------------------------------------------------------------------- product page
_LD_JSON = re.compile(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S | re.I)


def _ld_products(html: str) -> list[dict]:
    found = []
    for block in _LD_JSON.findall(html):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        for node in data if isinstance(data, list) else data.get("@graph", [data]):
            if isinstance(node, dict) and node.get("@type") == "Product":
                found.append(node)
    return found


def parse_product_page(html: str, pincode: str = "") -> RawProduct | None:
    products = _ld_products(html)
    if not products:
        return None
    p = products[0]
    props = {(a.get("name") or "").strip().lower(): a.get("value") for a in p.get("additionalProperty") or []}
    vid = p.get("sku") or ""
    name = (p.get("name") or "").strip()
    if not vid or not name:
        return None
    offer = p.get("offers") or {}
    if isinstance(offer, list):
        offer = offer[0] if offer else {}
    url = (offer.get("url") or p.get("url") or "").split("#")[0] or None
    availability = str(offer.get("availability") or "")
    brand = p.get("brand")
    image = p.get("image")
    unit = props.get("unit") or p.get("size")
    m = re.search(r"\(([^()]+)\)\s*$", unit or "")
    return RawProduct(
        source=PLATFORM,
        source_id=vid,
        source_url=url,
        name=clean_name(name),
        brand=(brand.get("name") if isinstance(brand, dict) else brand) or None,
        quantity=m.group(1).strip() if m else unit,
        gtin=p.get("gtin13") or p.get("gtin") or None,
        ingredients_text=compose_ingredients(props.get("ingredients"), props.get("allergen information")),
        categories=[c.strip() for c in str(p.get("category") or "").split(">") if c.strip()],
        image_url=image[0] if isinstance(image, list) and image else image if isinstance(image, str) else None,
        veg_mark=veg_mark_from(props.get("dietary preference")),
        offers=[RawOffer(PLATFORM, url=url, platform_product_id=vid, price=money(offer.get("price")),
                         in_stock=("InStock" in availability) if availability else None, location=pincode)],
    )


def parse_capture(data, pincode: str = "") -> list[RawProduct]:
    """A saved search response (dict) or product page (HTML string)."""
    if isinstance(data, str):
        p = parse_product_page(data, pincode)
        return [p] if p else []
    return parse_search(data, pincode)
