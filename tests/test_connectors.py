"""Platform connectors, tested on fixtures trimmed from real responses (never live calls)."""

import io
import json
import urllib.error
from pathlib import Path

import pytest

from jainfriendly.catalog import Catalog
from jainfriendly.catalog.__main__ import main as cli
from jainfriendly.catalog.connectors import base, blinkit, zepto
from jainfriendly.catalog.connectors.base import Blocked, DetailCache, Location, PoliteClient

FIX = Path(__file__).parent / "fixtures"
MUMBAI = Location("400001", 18.9388, 72.8354)


def load(name):
    text = (FIX / name).read_text(encoding="utf-8")
    return text if name.endswith(".html") else json.loads(text)


@pytest.fixture
def cat(tmp_path):
    return Catalog(tmp_path / "t.db")


# ---------------------------------------------------------------------------- helpers
def test_helpers():
    assert base.slugify("Haldiram's Bhujia | Spicy & Crunchy Snack") == "haldirams-bhujia-spicy-crunchy-snack"
    assert base.money("₹1,146") == 1146.0 and base.money(None) is None
    assert [base.veg_mark_from(x) for x in ("veg", "Veg", "Non-Veg", "non veg", "Egg", "", "Vegan?")] == [
        "green", "green", "brown", "brown", "brown", None, None]
    assert base.compose_ingredients("Salt", "May contain milk") == "Salt\nMay contain milk"
    assert base.compose_ingredients(None, "May contain milk") is None  # an allergen line alone isn't a list


# ---------------------------------------------------------------------------- Blinkit
def test_blinkit_search():
    items = blinkit.parse_search(load("blinkit_search_namkeen.json"), "400001")
    assert len(items) == 10
    sunder = items[0]
    assert (sunder.name, sunder.brand, sunder.quantity) == ("Sunder Surati Mixture Namkeen", "Sunder", "700 g")
    o = sunder.offers[0]
    assert (o.platform, o.price, o.mrp, o.in_stock, o.location) == ("blinkit", 146, 250, True, "400001")
    aloo = next(i for i in items if i.source_id == "35375")
    assert aloo.source_url == "https://blinkit.com/prn/haldirams-nagpur-aloo-bhujia/prid/35375"
    assert aloo.offers[0].mrp == 60  # no struck-through MRP shown when there is no discount
    assert aloo.ingredients_text is None  # search cards carry no ingredients
    path, body = blinkit.next_page(load("blinkit_search_namkeen.json"))
    assert path.startswith("/v1/layout/search?") and "offset=12" in path
    assert body["previous_search_query"] == "namkeen"


def test_blinkit_product_detail():
    p = blinkit.parse_product(load("blinkit_product_35375.json"), "400001")
    assert p.name == "Haldiram's Nagpur Aloo Bhujia" and p.quantity == "200 g"
    assert p.veg_mark == "green" and p.categories == ["Namkeen & Mixtures"]
    assert p.ingredients_text.startswith("Potatoes, Edible Vegetable Oil")
    assert p.ingredients_text.endswith("May Contains Wheat, Milk, Nut & Soy.")
    assert p.image_url.endswith("83bcbbbc-524c-41b6-ad75-8c22278a5c51.jpg")


class FakeBlinkit:
    """Serves fixture files for the two Blinkit endpoints and records calls."""

    def __init__(self):
        self.calls = []

    def request_json(self, method, url, headers=None, body=None):
        self.calls.append(url)
        assert headers == {"lat": "18.9388", "lon": "72.8354", "app_client": "consumer_web"}
        if "/v1/layout/search" in url:
            return load("blinkit_search_namkeen.json")
        pid = url.rsplit("/", 1)[-1]
        f = FIX / f"blinkit_product_{pid}.json"
        return json.loads(f.read_text()) if f.exists() else {"is_success": True, "response": {}}


def test_blinkit_connector_end_to_end(cat):
    fake = FakeBlinkit()
    conn = blinkit.BlinkitConnector(client=fake, cache=DetailCache(cat.conn))
    ids = [cat.upsert(raw) for raw in conn.fetch("namkeen", MUMBAI, max_pages=1)]
    assert len(ids) == 10 and len(fake.calls) == 11  # 1 search + 10 product details

    aloo = cat.search(q="aloo bhujia", platform="blinkit")["items"][0]
    assert aloo["verdicts"]["jain"] == "not_friendly"  # potatoes, dried garlic
    assert {t["id"] for t in aloo["traces"]} >= {"wheat", "soy"}  # from Blinkit's allergen line
    assert "milk" in {t["id"] for t in aloo["may_contain"]}  # unspecified flavours outrank the trace
    assert aloo["offers"][0]["location"] == "400001" and aloo["offers"][0]["price"] == 60
    detail = cat.get(aloo["id"])
    assert detail["ingredients_source"] == "blinkit"
    farsan = cat.search(q="farsan")["items"][0]
    assert farsan["unrecognized_count"] == 0  # "Bishops weed" (ajwain) is in the lexicon
    assert farsan["verdicts"]["jain"] == "unclear"  # "edible starch" may be potato/tapioca
    no_detail = cat.search(q="sunder")["items"][0]
    assert no_detail["verdicts"]["jain"] == "no_data"  # never "friendly" without an ingredient list

    # Product details are cached: a second sync only repeats the search request.
    fake.calls.clear()
    list(conn.fetch("namkeen", MUMBAI))
    assert len(fake.calls) == 1 + 8  # the 8 products whose detail response had no data are retried


def test_blinkit_unserviceable_location():
    class Unserviceable:
        def request_json(self, *a, **k):
            return {"error": "location not serviceable", "status": 400}

    with pytest.raises(ValueError, match="not serviceable"):
        list(blinkit.BlinkitConnector(client=Unserviceable()).fetch("namkeen", MUMBAI))


# ---------------------------------------------------------------------------- polite client
class FakeResponse(io.BytesIO):
    def __init__(self, body: str, status=200, ctype="application/json"):
        super().__init__(body.encode())
        self.status, self.headers = status, {"Content-Type": ctype}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_polite_client_stops_at_bot_walls(monkeypatch):
    client = PoliteClient(min_interval=0)

    def http_error(code, body):
        def urlopen(req, timeout):
            raise urllib.error.HTTPError(req.full_url, code, "x", {}, io.BytesIO(body.encode()))
        return urlopen

    monkeypatch.setattr(base.urllib.request, "urlopen", http_error(403, "<title>Access denied</title>"))
    with pytest.raises(Blocked):
        client.request_json("GET", "https://blinkit.com/x")
    # AWS WAF answers 202 with an HTML challenge page
    monkeypatch.setattr(base.urllib.request, "urlopen", lambda req, timeout: FakeResponse("<html>", 202, "text/html"))
    with pytest.raises(Blocked):
        client.request_json("GET", "https://www.zepto.com/x")
    monkeypatch.setattr(base.urllib.request, "urlopen", http_error(400, '{"error":"location not serviceable"}'))
    assert client.request_json("POST", "https://blinkit.com/x", body={})["error"] == "location not serviceable"
    monkeypatch.setattr(base.urllib.request, "urlopen", lambda req, timeout: FakeResponse('{"ok": 1}'))
    assert client.request_json("GET", "https://blinkit.com/x") == {"ok": 1}


# ---------------------------------------------------------------------------- Zepto
def test_zepto_search():
    items = zepto.parse_search(load("zepto_search_namkeen.json"), "400001")
    assert [i.name for i in items] == ["Haldiram's Mixture", "Haldiram's Bhujia", "Haldiram's Aloo Bhujia Sev"]
    mixture = items[0]
    assert mixture.quantity == "200 g" and mixture.brand == "Haldiram's"
    assert (mixture.offers[0].price, mixture.offers[0].mrp) == (55.0, 55.0)  # paise -> rupees
    assert mixture.source_url == ("https://www.zepto.com/pn/haldirams-mixture-crunchy-savory-snack"
                                  "/pvid/8182de89-dc3d-45df-9dac-ed962b646d10")
    assert mixture.image_url == ("https://cdn.zeptonow.com/production/cms/product_variant/"
                                 "10d086ca-847c-4a5d-96db-4a55e2c8034c.jpeg")
    assert items[2].ingredients_text is None
    assert zepto.next_page(load("zepto_search_namkeen.json")) == 1


def test_zepto_product_page():
    p = zepto.parse_product_page(load("zepto_product_07a87f32.html"), "400001")
    assert (p.name, p.brand, p.quantity) == ("Haldiram's Aloo Bhujia Sev", "Haldiram's", "200 g")
    assert p.veg_mark == "green" and p.categories == ["Munchies", "Namkeens"]
    assert p.ingredients_text.endswith("May contain: Peanut, Tree Nuts, Sesame Seed, Milk, Soy, Mustard Seed, Wheat")
    assert p.offers[0].price == 60 and p.offers[0].in_stock is True
    assert zepto.parse_product_page("<html>no data</html>") is None


def test_zepto_capture_import_fills_missing_ingredients(cat, tmp_path):
    """Search result without ingredients + its product page = one product with ingredients."""
    db = tmp_path / "t.db"
    assert cli(["--db", str(db), "import-capture", "zepto", str(FIX / "zepto_search_namkeen.json"),
                str(FIX / "zepto_product_07a87f32.html"), "--pincode", "400001"]) == 0
    c = Catalog(db)
    hits = c.search(q="aloo bhujia sev")["items"]
    assert len(hits) == 1
    p = c.get(hits[0]["id"])
    assert p["verdicts"]["jain"] == "not_friendly" and {"potato", "garlic"} <= {t["id"] for t in p["contains"]}
    assert [(o["platform"], o["location"], o["price"], o["mrp"]) for o in p["offers"]] == [("zepto", "400001", 60, 60)]
    bhujia = c.search(q="haldiram bhujia", platform="zepto")["items"]
    assert any(i["verdicts"]["jain"] == "friendly" or i["verdicts"]["jain"] == "likely_friendly" for i in bhujia)
