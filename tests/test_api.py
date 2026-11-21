from fastapi.testclient import TestClient

from jainfriendly.api import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_analyze_default_profiles():
    r = client.post("/v1/analyze", json={"ingredients": "Potato, salt, onion powder"})
    assert r.status_code == 200
    d = r.json()
    assert {"potato", "onion"} <= set(d["contains"])
    verdicts = {p["profile"]: p["verdict"] for p in d["profiles"]}
    assert verdicts == {"jain": "not_friendly", "vegetarian": "friendly", "vegan": "friendly"}


def test_analyze_profile_options_and_tree():
    r = client.post(
        "/v1/analyze",
        json={
            "ingredients": "Wheat flour, yeast",
            "profiles": [{"id": "jain", "options": {"yeast": True}}, "allergen:gluten"],
            "include_tree": True,
        },
    )
    d = r.json()
    assert [p["verdict"] for p in d["profiles"]] == ["not_friendly", "not_friendly"]
    assert d["ingredients"][0]["name"] == "Wheat flour"


def test_unknown_profile_is_422():
    r = client.post("/v1/analyze", json={"ingredients": "salt", "profiles": ["keto"]})
    assert r.status_code == 422


def test_batch():
    r = client.post(
        "/v1/analyze/batch",
        json={
            "products": [
                {"id": "sku-1", "ingredients": "Banana, coconut oil, salt"},
                {"id": "sku-2", "ingredients": "Potato, palm oil, salt"},
            ],
            "profiles": ["jain"],
        },
    )
    out = {p["id"]: p["verdicts"]["jain"] for p in r.json()["products"]}
    assert out == {"sku-1": "friendly", "sku-2": "not_friendly"}


def test_profiles_and_tags_listing():
    ps = client.get("/v1/profiles").json()
    jain = next(p for p in ps if p["id"] == "jain")
    assert {o["id"] for o in jain["options"]} >= {"yeast", "dried_rhizomes"}
    tags = client.get("/v1/tags").json()
    assert any(t["id"] == "onion" for t in tags["tags"])


def test_demo_page():
    assert "JainFriendly" in client.get("/").text
