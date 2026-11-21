"""Open Food Facts connector (https://world.openfoodfacts.org).

Data is licensed under the Open Database License (ODbL); product images under CC BY-SA.
Attribution is shown in the app and API. OFF asks API clients to send a descriptive
User-Agent and to keep search requests to about 10 per minute; this connector does both.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterator

from ..models import RawProduct

SEARCH_URL = "https://in.openfoodfacts.org/cgi/search.pl"
PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
USER_AGENT = "JainFriendly/0.1 (ingredient-tagging catalogue prototype)"
FIELDS = (
    "code,product_name,product_name_en,brands,quantity,categories_tags,image_front_small_url,"
    "image_ingredients_url,ingredients_text_en,ingredients_text,countries_tags,lang"
)


class SourceUnavailable(RuntimeError):
    """The source keeps refusing or failing; try again later."""


def _get_json(url: str, retries: int = 5, backoff: float = 10.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                body = resp.read().decode("utf-8")
            return json.loads(body)
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            if attempt == retries:
                raise SourceUnavailable(f"Open Food Facts request failed: {exc}") from exc
            throttled = isinstance(exc, urllib.error.HTTPError) and exc.code in (401, 403, 429, 503)
            # Rate-limited: wait much longer before retrying.
            time.sleep((60.0 if throttled else backoff) * (attempt + 1))
    raise AssertionError("unreachable")


def _english_text(p: dict) -> str | None:
    text = (p.get("ingredients_text_en") or "").strip()
    if not text and p.get("lang") in (None, "en"):
        text = (p.get("ingredients_text") or "").strip()
    if not text:
        return None
    letters = [c for c in text if c.isalpha()]
    if letters and sum(c.isascii() for c in letters) / len(letters) < 0.9:
        return None  # not Latin script; needs translation before analysis
    return text


def to_raw(p: dict) -> RawProduct | None:
    """Map one OFF product JSON object to a RawProduct (None if unusable)."""
    name = (p.get("product_name_en") or p.get("product_name") or "").strip()
    code = str(p.get("code") or "").strip()
    if not name or not code:
        return None
    brands = (p.get("brands") or "").split(",")
    return RawProduct(
        source="openfoodfacts",
        source_id=code,
        source_url=f"https://world.openfoodfacts.org/product/{code}",
        name=name,
        brand=brands[0].strip() or None,
        quantity=(p.get("quantity") or "").strip() or None,
        gtin=code,
        ingredients_text=_english_text(p),
        categories=[c.split(":", 1)[-1] for c in p.get("categories_tags") or []],
        image_url=p.get("image_front_small_url"),
        ingredients_image_url=p.get("image_ingredients_url"),
    )


class OpenFoodFactsConnector:
    name = "openfoodfacts"

    def __init__(self, page_size: int = 100, delay: float = 7.0):
        self.page_size = page_size
        self.delay = delay  # seconds between search pages (OFF limit ~10 searches/min)
        self.last_page_done = 0

    def search_page(self, page: int, country: str = "india") -> dict:
        params = {
            "action": "process",
            "tagtype_0": "countries",
            "tag_contains_0": "contains",
            "tag_0": country,
            "json": "1",
            "page_size": str(self.page_size),
            "page": str(page),
            "fields": FIELDS,
            "sort_by": "unique_scans_n",
        }
        return _get_json(f"{SEARCH_URL}?{urllib.parse.urlencode(params)}")

    def fetch(
        self, max_pages: int | None = None, start_page: int = 1, country: str = "india"
    ) -> Iterator[RawProduct]:
        page = start_page
        while True:
            data = self.search_page(page, country)
            products = data.get("products") or []
            for p in products:
                raw = to_raw(p)
                if raw:
                    yield raw
            last_page = -(-int(data.get("count", 0)) // self.page_size)
            if not products or page >= last_page or (max_pages and page - start_page + 1 >= max_pages):
                return
            page += 1
            self.last_page_done = page - 1
            time.sleep(self.delay)

    def fetch_barcode(self, code: str) -> RawProduct | None:
        data = _get_json(PRODUCT_URL.format(code=urllib.parse.quote(code)) + f"?fields={FIELDS}")
        if data.get("status") != 1:
            return None
        return to_raw(data["product"])
