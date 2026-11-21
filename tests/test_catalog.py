import json

import pytest
from fastapi.testclient import TestClient

from jainfriendly import api
from jainfriendly.catalog import Catalog, RawOffer, RawProduct
from jainfriendly.catalog.connectors.feed import read_feed
from jainfriendly.catalog.connectors.openfoodfacts import to_raw

CHIPS = "Potato, palm oil, seasoning (salt, onion powder, garlic powder)"
BHUJIA = "Gram flour, cottonseed oil, salt, spices (red chilli, black pepper, dry ginger)"
BISCUIT = "Wheat flour, sugar, palm oil, milk solids, emulsifier (471), salt"


@pytest.fixture
def cat(tmp_path):
    return Catalog(tmp_path / "t.db")


def add(cat, name, text, gtin=None, brand="Acme", offers=(), source="openfoodfacts"):
    return cat.upsert(
        RawProduct(source=source, name=name, brand=brand, gtin=gtin, quantity="100 g",
                   ingredients_text=text, categories=["snacks"], offers=list(offers))
    )


def test_upsert_analyses_and_filters(cat):
    add(cat, "Masala chips", CHIPS, "8901111111111")
    add(cat, "Bhujia", BHUJIA, "8902222222222")
    add(cat, "Cream biscuit", BISCUIT, "8903333333333")
    names = lambda r: {i["name"] for i in r["items"]}  # noqa: E731
    assert names(cat.search(diet=["jain"])) == {"Bhujia"}
    assert names(cat.search(diet=["vegan"])) == {"Masala chips", "Bhujia"}
    assert names(cat.search(diet=["jain_strict"])) == set()  # dry ginger
    assert names(cat.search(free_from=["milk"])) == {"Masala chips", "Bhujia"}
    assert names(cat.search(avoid_tags=["onion"])) == {"Bhujia", "Cream biscuit"}
    assert names(cat.search(q="bhuj")) == {"Bhujia"}
    chips = cat.search(q="masala")["items"][0]
    assert {t["id"] for t in chips["contains"]} >= {"potato", "onion", "garlic"}
    assert chips["made_in_india"] is True


def test_same_barcode_merges_offers_across_platforms(cat):
    a = add(cat, "Chips", CHIPS, "8901111111111",
            offers=[RawOffer("blinkit", url="https://example.test/b", price=20)], source="feed:blinkit")
    b = add(cat, "CHIPS!", None, "08901111111111",
            offers=[RawOffer("zepto", price=19, location="400001")], source="feed:zepto")
    assert a == b
    p = cat.get(a)
    assert {o["platform"] for o in p["offers"]} == {"blinkit", "zepto"}
    assert p["offers"][0]["price"] == 19  # sorted by price
    assert {i["id"] for i in cat.search(platform="zepto")["items"]} == {a}


def test_match_without_barcode_by_brand_name_quantity(cat):
    a = add(cat, "Aloo Bhujia", BHUJIA, gtin=None, brand="Haldi Co")
    b = add(cat, "aloo  bhujia", None, gtin=None, brand="HALDI CO",
            offers=[RawOffer("bigbasket", price=50)])
    assert a == b


def test_higher_priority_source_replaces_ingredients(cat):
    pid = add(cat, "X", BHUJIA, "8904444444444", source="openfoodfacts")
    assert cat.get(pid)["verdicts"]["jain"] == "friendly"
    add(cat, "X", CHIPS, "8904444444444", source="manufacturer")
    assert cat.get(pid)["verdicts"]["jain"] == "not_friendly"
    add(cat, "X", BHUJIA, "8904444444444", source="openfoodfacts")  # lower priority: ignored
    assert cat.get(pid)["verdicts"]["jain"] == "not_friendly"


def test_no_ingredients_is_no_data_and_excluded_from_diet_filters(cat):
    pid = add(cat, "Mystery snack", None, "8905555555555")
    assert cat.get(pid)["verdicts"]["jain"] == "no_data"
    assert cat.search(diet=["jain"])["total"] == 0
    assert cat.search()["total"] == 1


def test_reanalyze_only_stale(cat):
    add(cat, "Chips", CHIPS, "8901111111111")
    assert cat.reanalyze() == 0
    cat.conn.execute("UPDATE products SET analysis_version = 'old'")
    assert cat.reanalyze() == 1


def test_unknown_filters_raise(cat):
    with pytest.raises(KeyError):
        cat.search(diet=["keto"])
    with pytest.raises(KeyError):
        cat.search(avoid_tags=["unicorn"])


def test_feed_import_csv(cat, tmp_path):
    f = tmp_path / "blinkit_sample.csv"
    f.write_text(
        "Title,Brand,Quantity,EAN,Ingredients,Selling Price,MRP,In Stock,Pincode,Link\n"
        f'Chips,Acme,100 g,8901111111111,"{CHIPS}",20,25,yes,560001,https://example.test/1\n'
    )
    for raw in read_feed(f, platform="blinkit"):
        cat.upsert(raw)
    item = cat.search()["items"][0]
    assert item["offers"][0] == {
        "platform": "blinkit", "platform_name": "Blinkit", "url": "https://example.test/1",
        "price": 20.0, "mrp": 25.0, "in_stock": True, "location": "560001",
        "seen_at": item["offers"][0]["seen_at"],
    }
    assert item["verdicts"]["jain"] == "not_friendly"


def test_feed_rejects_unknown_platform(tmp_path):
    f = tmp_path / "x.json"
    f.write_text(json.dumps([{"name": "A", "platform": "dmart-ish"}]))
    with pytest.raises(ValueError):
        list(read_feed(f))


def test_off_mapping():
    raw = to_raw({
        "code": "8901491503051", "product_name": "Chilli chips", "brands": "Lays, PepsiCo",
        "quantity": "25g", "categories_tags": ["en:snacks", "en:chips-and-fries"],
        "ingredients_text_en": "Potato (80%), oil", "image_front_small_url": "https://img/x.jpg",
    })
    assert raw.brand == "Lays" and raw.gtin == "8901491503051"
    assert raw.categories == ["snacks", "chips-and-fries"]
    assert raw.ingredients_text.startswith("Potato")
    assert to_raw({"code": "1", "product_name": "X", "ingredients_text": "शक्कर, नमक", "lang": "hi"}).ingredients_text is None
    assert to_raw({"code": "", "product_name": "X"}) is None


def test_catalog_api(cat):
    add(cat, "Masala chips", CHIPS, "8901111111111", offers=[RawOffer("amazon", price=30)])
    add(cat, "Bhujia", BHUJIA, "8902222222222")
    api.set_catalog(cat)
    client = TestClient(api.app)
    r = client.get("/v1/products", params=[("diet", "jain")]).json()
    assert [i["name"] for i in r["items"]] == ["Bhujia"]
    assert "Open Food Facts" in r["attribution"]
    r = client.get("/v1/products", params=[("avoid", "potato"), ("free_from", "peanut")]).json()
    assert r["total"] == 1
    pid = client.get("/v1/products", params={"platform": "amazon"}).json()["items"][0]["id"]
    detail = client.get(f"/v1/products/{pid}").json()
    assert detail["analysis"]["profiles"]["jain"]["verdict"] == "not_friendly"
    assert client.get("/v1/products/99999").status_code == 404
    assert client.get("/v1/products", params={"diet": "keto"}).status_code == 422
    facets = client.get("/v1/catalog").json()
    assert facets["products"] == 2 and facets["platforms"][0]["id"] == "amazon"
    assert any(p["id"] == "zepto" for p in client.get("/v1/platforms").json())
    assert "JainFriendly" in client.get("/").text
    assert "checker" in client.get("/check").text


def test_snapshot_roundtrip(cat, tmp_path):
    add(cat, "Masala chips", CHIPS, "8901111111111", offers=[RawOffer("zepto", price=20, location="400001")])
    add(cat, "Bhujia", BHUJIA, None)
    snap = tmp_path / "snap.jsonl.gz"
    assert cat.export_snapshot(snap) == 2
    other = Catalog(tmp_path / "other.db")
    assert other.load_snapshot(snap) == 2
    items = {i["name"]: i for i in other.search()["items"]}
    assert items["Masala chips"]["offers"][0]["platform"] == "zepto"
    assert items["Bhujia"]["verdicts"]["jain"] == "friendly"


def test_barcode_lookup_api(cat):
    add(cat, "Masala chips", CHIPS, "8901111111111")
    api.set_catalog(cat)
    client = TestClient(api.app)
    assert client.get("/v1/products/barcode/08901111111111").json()["name"] == "Masala chips"
    assert client.get("/v1/products/barcode/123").status_code == 404
