"""Shared pieces for quick-commerce platform connectors.

Rules (see CLAUDE.md): low request rates, cache product details (ingredients don't change per
pincode), no login-gated data, and never get around a captcha or bot check. When a platform
refuses us we raise `Blocked` and stop.
"""

from __future__ import annotations

import json
import random
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterator, Protocol

from ..models import RawProduct

USER_AGENT = "Mozilla/5.0 (compatible; JainFriendly/0.1; ingredient-tagging catalogue)"


class Blocked(RuntimeError):
    """The platform refused automated access (captcha, bot check, login wall, rate limit).
    We stop rather than work around it."""


@dataclass(frozen=True)
class Location:
    pincode: str
    lat: float
    lon: float


class Connector(Protocol):
    platform: str

    def fetch(self, query: str, location: Location, max_pages: int = 1) -> Iterator[RawProduct]: ...


# ---------------------------------------------------------------------------- small helpers
def slugify(name: str) -> str:
    """URL slug the way the platforms build it: "Haldiram's Bhujia | Spicy" -> "haldirams-bhujia-spicy"."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("'", "").replace("’", "")).strip("-")


def money(value) -> float | None:
    """'₹146' / '146' / 146 -> 146.0"""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(m.group()) if m else None


def veg_mark_from(text: str | None) -> str | None:
    """Platform diet labels -> FSSAI mark. 'veg' -> green; 'non-veg' / 'egg' -> brown."""
    t = (text or "").strip().lower()
    if not t:
        return None
    if "non" in t or "egg" in t:
        return "brown"
    if t in ("veg", "vegetarian", "pure veg"):
        return "green"
    return None


def compose_ingredients(ingredients: str | None, allergen_info: str | None) -> str | None:
    """Ingredient text plus the platform's separate allergen line, so the label parser sees
    'May contain ...' the way it would on a pack."""
    text = (ingredients or "").strip()
    if not text:
        return None
    allergen = (allergen_info or "").strip()
    if allergen and allergen.lower() not in text.lower():
        text = f"{text}\n{allergen}"
    return text


# ---------------------------------------------------------------------------- HTTP
_BOT_WALL = re.compile(r"verify you are human|captcha|awswaf|cf-chl|access denied|attention required", re.I)


class PoliteClient:
    """Sequential requests with a minimum gap (plus jitter). Any sign of a bot wall raises Blocked."""

    def __init__(self, min_interval: float = 4.0, timeout: float = 30.0):
        self.min_interval = min_interval
        self.timeout = timeout
        self._last = 0.0

    def _wait(self) -> None:
        gap = self.min_interval + random.uniform(0, self.min_interval / 2)
        delay = self._last + gap - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        self._last = time.monotonic()

    def request_json(self, method: str, url: str, headers: dict | None = None, body: dict | None = None) -> dict:
        self._wait()
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json",
                     **({"Content-Type": "application/json"} if data is not None else {}), **(headers or {})},
        )
        host = urllib.parse.urlsplit(url).netloc
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                text = resp.read().decode("utf-8", "replace")
                status, ctype = resp.status, resp.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", "replace") if exc.fp else ""
            if exc.code in (401, 403, 429, 503) or _BOT_WALL.search(text):
                raise Blocked(f"{host} refused the request (HTTP {exc.code}); not retrying.") from exc
            try:  # e.g. Blinkit: 400 {"error": "location not serviceable"}
                return {"error": json.loads(text).get("error") or text[:200], "status": exc.code}
            except (json.JSONDecodeError, AttributeError):
                raise exc from None
        if status == 202 or "json" not in ctype or _BOT_WALL.search(text[:2000]):
            raise Blocked(f"{host} answered with a bot check instead of data (HTTP {status}); not retrying.")
        return json.loads(text)


# ---------------------------------------------------------------------------- caches
DETAIL_TTL_DAYS = 30


class DetailCache:
    """Product details per platform. Ingredients don't change per pincode, so one fetch serves
    every location for DETAIL_TTL_DAYS."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get(self, platform: str, product_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT body FROM platform_details WHERE platform = ? AND product_id = ? "
            "AND fetched_at > datetime('now', ?)",
            (platform, product_id, f"-{DETAIL_TTL_DAYS} days"),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, platform: str, product_id: str, body: dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO platform_details (platform, product_id, fetched_at, body) "
            "VALUES (?, ?, datetime('now'), ?)",
            (platform, product_id, json.dumps(body, ensure_ascii=False)),
        )
        self.conn.commit()


def geocode_pincode(conn: sqlite3.Connection, pincode: str, client: PoliteClient | None = None) -> Location:
    """Pincode -> centre coordinates via OpenStreetMap Nominatim (cached; 1 request per new pincode)."""
    row = conn.execute("SELECT lat, lon FROM pincode_locations WHERE pincode = ?", (pincode,)).fetchone()
    if row:
        return Location(pincode, row[0], row[1])
    client = client or PoliteClient(min_interval=1.0)
    qs = urllib.parse.urlencode({"postalcode": pincode, "country": "India", "format": "json", "limit": 1})
    results = client.request_json("GET", f"https://nominatim.openstreetmap.org/search?{qs}")
    if not results:
        raise ValueError(f"Could not find coordinates for pincode {pincode}; pass --lat and --lon.")
    lat, lon = float(results[0]["lat"]), float(results[0]["lon"])
    conn.execute("INSERT OR REPLACE INTO pincode_locations VALUES (?, ?, ?, 'nominatim')", (pincode, lat, lon))
    conn.commit()
    return Location(pincode, lat, lon)
