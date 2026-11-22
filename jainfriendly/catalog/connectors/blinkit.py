"""Blinkit connector.

Endpoints, as observed in the Blinkit website (2026-11-22). Requests carry `lat`, `lon` and
`app_client: consumer_web` headers.

    POST https://blinkit.com/v1/layout/search?q=<query>&search_type=type_to_search   body {}
         -> {"is_success", "response": {"snippets": [...], "pagination": {"next_url"}}, "postback_params"}
         product cards: snippet.widget_type == "product_card_snippet_type_2"; snippet.data has
         product_id, name.text, brand_name.text, variant.text (pack size), normal_price.text,
         mrp.text (only when discounted), image.url, inventory, is_sold_out, product_state and
         atc_action.add_to_cart.cart_item {price, mrp, unit, brand, ...} with numeric prices.
         Next page: POST pagination.next_url with the previous postback_params as body.
    POST https://blinkit.com/v1/layout/product/<product_id>   body {}
         -> response.tracking.le_meta.custom_data.seo: product_name, brand, price, mrp, inventory,
         images[], page_url, attributes[{name, value}] incl. "Ingredients",
         "Allergen Information", "Food Type" (veg / non veg), "Unit", "Type".

No barcode is exposed, so products match the catalogue by brand + name + pack size.

Blinkit puts the website behind a Cloudflare check, so server-side syncing may be refused
(`Blocked`). The parsers also accept responses fetched on a user's device
(`python -m jainfriendly.catalog import-capture blinkit <file.json>`).
"""

from __future__ import annotations

import urllib.parse
from typing import Iterator

from ..models import RawOffer, RawProduct
from .base import (
    Blocked, DetailCache, Location, PoliteClient, compose_ingredients, money, slugify, veg_mark_from,
)

PLATFORM = "blinkit"
BASE = "https://blinkit.com"
SEARCH_PATH = "/v1/layout/search?q={q}&search_type=type_to_search"
PRODUCT_PATH = "/v1/layout/product/{id}"
PRODUCT_CARD = "product_card_snippet_type_2"


def headers(location: Location) -> dict:
    return {"lat": str(location.lat), "lon": str(location.lon), "app_client": "consumer_web"}


def product_url(product_id: str, name: str) -> str:
    return f"{BASE}/prn/{slugify(name)}/prid/{product_id}"


def _inner(resp: dict) -> dict:
    """Accept the full API response ({is_success, response}) or just its `response` part."""
    return resp.get("response", resp) if isinstance(resp, dict) else {}


def _text(v) -> str | None:
    if isinstance(v, dict):
        v = v.get("text")
    return v.strip() if isinstance(v, str) and v.strip() else None


# ---------------------------------------------------------------------------- search
def parse_search(resp: dict, pincode: str = "") -> list[RawProduct]:
    out = []
    for snip in _inner(resp).get("snippets") or []:
        if snip.get("widget_type") != PRODUCT_CARD:
            continue
        d = snip.get("data") or {}
        item = ((d.get("atc_action") or {}).get("add_to_cart") or {}).get("cart_item") or {}
        pid = str(d.get("product_id") or item.get("product_id") or (d.get("identity") or {}).get("id") or "")
        name = _text(d.get("name")) or item.get("product_name")
        if not pid or not name:
            continue
        price = money(item.get("price")) if item.get("price") is not None else money(_text(d.get("normal_price")))
        mrp = money(item.get("mrp")) if item.get("mrp") is not None else money(_text(d.get("mrp")))
        inventory = d.get("inventory", item.get("inventory"))
        in_stock = (
            not d.get("is_sold_out")
            and d.get("product_state", "available") == "available"
            and (inventory is None or inventory > 0)
        )
        url = product_url(pid, name)
        out.append(
            RawProduct(
                source=PLATFORM,
                source_id=pid,
                source_url=url,
                name=name,
                brand=_text(d.get("brand_name")) or item.get("brand"),
                quantity=_text(d.get("variant")) or item.get("unit"),
                image_url=(d.get("image") or {}).get("url") or item.get("image_url"),
                offers=[RawOffer(PLATFORM, url=url, platform_product_id=pid, price=price,
                                 mrp=mrp if mrp is not None else price, in_stock=in_stock, location=pincode)],
            )
        )
    return out


def next_page(resp: dict) -> tuple[str, dict] | None:
    """(path, body) for the next search page, or None at the end."""
    nxt = (_inner(resp).get("pagination") or {}).get("next_url")
    if not nxt:
        return None
    return nxt, (resp.get("postback_params") or {}) if isinstance(resp, dict) else {}


# ---------------------------------------------------------------------------- product detail
def seo_of(resp: dict) -> dict | None:
    """The product-detail part we use (and cache): response.tracking.le_meta.custom_data.seo."""
    tracking = _inner(resp).get("tracking") or {}
    seo = ((tracking.get("le_meta") or {}).get("custom_data") or {}).get("seo")
    return seo if isinstance(seo, dict) and seo.get("attributes") is not None else None


def parse_product(resp_or_seo: dict, pincode: str = "") -> RawProduct | None:
    seo = seo_of(resp_or_seo) or (resp_or_seo if "attributes" in resp_or_seo else None)
    if not seo:
        return None
    attrs = {a.get("name"): a.get("value") for a in seo.get("attributes") or [] if isinstance(a, dict)}
    pid = str(seo.get("id") or seo.get("entity_id") or "")
    name = (seo.get("product_name") or "").strip()
    if not pid or not name:
        return None
    url = seo.get("page_url") or product_url(pid, name)
    images = seo.get("images") or []
    price, mrp = money(seo.get("price")), money(seo.get("mrp"))
    inventory = seo.get("inventory")
    return RawProduct(
        source=PLATFORM,
        source_id=pid,
        source_url=url,
        name=name,
        brand=(seo.get("brand") or "").strip() or None,
        quantity=attrs.get("Unit"),
        ingredients_text=compose_ingredients(attrs.get("Ingredients"), attrs.get("Allergen Information")),
        categories=[attrs["Type"]] if attrs.get("Type") else [],
        image_url=images[0] if images else None,
        veg_mark=veg_mark_from(attrs.get("Food Type")),
        offers=[RawOffer(PLATFORM, url=url, platform_product_id=pid, price=price, mrp=mrp,
                         in_stock=None if inventory is None else inventory > 0, location=pincode)],
    )


def merge(listing: RawProduct, detail: RawProduct | None) -> RawProduct:
    """Search card (price, stock at this pincode) + product detail (ingredients, diet mark)."""
    if detail is None:
        return listing
    listing.ingredients_text = detail.ingredients_text
    listing.veg_mark = detail.veg_mark
    listing.categories = detail.categories or listing.categories
    listing.brand = listing.brand or detail.brand
    listing.quantity = listing.quantity or detail.quantity
    return listing


def parse_capture(data: dict, pincode: str = "") -> list[RawProduct]:
    """A saved search or product response (e.g. fetched on a user's device)."""
    if seo_of(data):
        p = parse_product(data, pincode)
        return [p] if p else []
    return parse_search(data, pincode)


# ---------------------------------------------------------------------------- live connector
class BlinkitConnector:
    platform = PLATFORM

    def __init__(self, client: PoliteClient | None = None, cache: DetailCache | None = None):
        self.client = client or PoliteClient()
        self.cache = cache

    def _detail(self, pid: str, location: Location) -> RawProduct | None:
        seo = self.cache.get(PLATFORM, pid) if self.cache else None
        if seo is None:
            resp = self.client.request_json("POST", BASE + PRODUCT_PATH.format(id=pid), headers(location), {})
            seo = seo_of(resp)
            if seo and self.cache:
                self.cache.put(PLATFORM, pid, seo)
        return parse_product(seo, location.pincode) if seo else None

    def fetch(self, query: str, location: Location, max_pages: int = 1) -> Iterator[RawProduct]:
        path, body = SEARCH_PATH.format(q=urllib.parse.quote(query)), {}
        for _ in range(max_pages):
            resp = self.client.request_json("POST", BASE + path, headers(location), body)
            if resp.get("error"):
                raise ValueError(f"Blinkit: {resp['error']} (pincode {location.pincode})")
            for listing in parse_search(resp, location.pincode):
                yield merge(listing, self._detail(listing.source_id, location))
            nxt = next_page(resp)
            if not nxt:
                return
            path, body = nxt
