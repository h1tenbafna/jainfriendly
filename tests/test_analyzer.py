import pytest

from jainfriendly import analyze, evaluate
from jainfriendly.knowledge import load_knowledge
from jainfriendly.parser import parse_label


def verdict(text, profile, veg_mark=None):
    return evaluate(analyze(text, veg_mark), profile).verdict


def status(text, tag):
    t = analyze(text).tags.get(tag)
    return t.status if t else None


MASALA_CHIPS = (
    "Ingredients: Potato (58%), Edible Vegetable Oil (Palmolein, Rice Bran Oil), Seasoning "
    "(Sugar, Iodised Salt, Spices & Condiments (Onion Powder, Garlic Powder, Chilli Powder, "
    "Coriander, Ginger Powder), Milk Solids, Tomato Powder, Flavour Enhancers (INS 627, INS 631), "
    "Acidity Regulator (INS 330)). Contains Added Flavour (Natural and Nature Identical "
    "Flavouring Substances). Allergen advice: Contains milk. May contain traces of peanut."
)
JAIN_BHUJIA = (
    "Ingredients: Gram Flour (Besan), Edible Vegetable Oil (Cottonseed Oil), Moth Bean Flour, "
    "Iodised Salt, Spices (Red Chilli, Black Pepper, Dry Ginger, Cardamom, Clove, Turmeric)."
)
CREAM_BISCUIT = (
    "Refined Wheat Flour (Maida), Sugar, Edible Vegetable Fat (Palm), Invert Sugar Syrup, "
    "Cocoa Solids (4%), Milk Solids, Raising Agents [503(ii), 500(ii)], Emulsifiers [322, 471], "
    "Iodised Salt, Colour (INS 150d), Artificial Flavouring Substances. Contains wheat, milk, soy."
)


# ---------------------------------------------------------------- knowledge base integrity
def test_knowledge_base_loads_and_validates():
    kb = load_knowledge()
    assert len(kb.phrases) > 1000
    assert {"jain", "jain_strict", "vegetarian", "vegan", "allergen:peanut"} <= set(kb.profiles)
    for p in kb.profiles.values():
        assert kb.resolve_targets(p.avoid), p.id


# ---------------------------------------------------------------- parser
def test_parser_nesting_percent_and_statements():
    label = parse_label(MASALA_CHIPS)
    names = [n.name for n in label.ingredients]
    assert names[0] == "Potato" and label.ingredients[0].percent == 58
    seasoning = label.ingredients[2]
    assert seasoning.name == "Seasoning"
    spices = seasoning.children[2]
    assert [c.name for c in spices.children][:2] == ["Onion Powder", "Garlic Powder"]
    assert label.contains == ["milk"]
    assert label.may_contain == ["peanut"]


def test_parser_roman_numerals_stay_with_code():
    label = parse_label("Emulsifier (INS 322(i)), Raising agent [500(ii)]")
    assert label.ingredients[0].children[0].name == "INS 322(i)"


def test_decimal_percent_not_split():
    label = parse_label("Cocoa solids (4.5%), sugar")
    assert label.ingredients[0].percent == 4.5
    assert len(label.ingredients) == 2


# ---------------------------------------------------------------- tagging
def test_masala_chips_tags_and_verdicts():
    a = analyze(MASALA_CHIPS)
    assert {"potato", "onion", "garlic", "milk", "ginger_dry"} <= {t.id for t in a.present()}
    assert a.tags["peanut"].status == "trace"
    assert a.tags["meat"].status == "possible"  # INS 631
    assert verdict(MASALA_CHIPS, "jain") == "not_friendly"
    assert verdict(MASALA_CHIPS, "vegan") == "not_friendly"
    assert verdict(MASALA_CHIPS, "vegetarian") == "unclear"
    assert verdict(MASALA_CHIPS, "allergen:peanut") == "unclear"


def test_jain_bhujia_is_friendly_but_not_for_strict():
    assert verdict(JAIN_BHUJIA, "jain") == "friendly"
    r = evaluate(analyze(JAIN_BHUJIA), "jain")
    assert {x["id"] for x in r.allowed_by_preference} >= {"ginger_dry", "turmeric_dry"}
    assert verdict(JAIN_BHUJIA, "jain_strict") == "not_friendly"
    assert verdict(JAIN_BHUJIA, {"id": "jain", "options": {"dried_rhizomes": True}}) == "not_friendly"


def test_cream_biscuit_emulsifiers_and_green_mark():
    assert verdict(CREAM_BISCUIT, "jain") == "unclear"  # 471 may be animal fat
    assert verdict(CREAM_BISCUIT, "vegetarian") == "unclear"
    assert verdict(CREAM_BISCUIT, "vegetarian", veg_mark="green") == "likely_friendly"
    assert verdict(CREAM_BISCUIT, "vegan") == "not_friendly"
    a = analyze(CREAM_BISCUIT)
    assert a.tags["soy"].status == "present"  # from "Contains ... soy"
    assert a.tags["wheat"].status == "present"
    assert not a.unrecognized


@pytest.mark.parametrize(
    "text, tag, expected",
    [
        ("Sweet potato chips, salt", "potato", None),
        ("Sweet potato chips, salt", "sweet_potato", "present"),
        ("Coconut milk, sugar", "milk", None),
        ("Peanut butter, salt", "milk", None),
        ("Peanut butter, salt", "peanut", "present"),
        ("Buckwheat flour (kuttu atta)", "wheat", None),
        ("Aloo, pyaz, lahsun", "garlic", "present"),
        ("Aloo, pyaz, lahsun", "potato", "present"),
        ("Tapioca starch, salt", "tapioca", "present"),
        ("Colour (INS 162)", "beetroot", "present"),
        ("Colour (E120)", "carmine", "present"),
        ("Gelatine, sugar", "gelatin", "present"),
        ("Onions, Tomatoes", "onion", "present"),
        ("Kalonji, cumin", "onion", None),
        ("Natural onion flavour", "onion", "possible"),
        ("Seasoning", "onion", "possible"),
        ("Seasoning (salt, chilli)", "onion", None),
        ("Tomato ketchup", "garlic", "possible"),
        ("Vitamin D3", "lanolin", "possible"),
        ("Glazing agent (INS 904)", "shellac", "present"),
        ("Asafoetida", "wheat", "possible"),
        ("Sulfur dioxide", "sulphite", "present"),
        ("Soy sauce", "wheat", "possible"),
        ("Modified starch (INS 1422)", "potato", "possible"),
        ("Honey, oats", "honey", "present"),
    ],
)
def test_tagging_examples(text, tag, expected):
    assert status(text, tag) == expected


def test_ginger_form_unknown_is_unclear_for_jain():
    assert verdict("Salt, ginger", "jain") == "unclear"
    assert verdict("Salt, dry ginger", "jain") == "friendly"
    assert verdict("Salt, ginger paste", "jain") == "not_friendly"


def test_yeast_option():
    text = "Wheat flour, yeast, salt"
    assert verdict(text, "jain") == "friendly"
    assert verdict(text, {"id": "jain", "options": {"yeast": True}}) == "not_friendly"


def test_unrecognized_downgrades_to_likely():
    r = evaluate(analyze("Salt, zorblax extract"), "jain")
    assert r.verdict == "likely_friendly"
    assert any("zorblax" in c for c in r.caveats)


def test_unknown_ins_code_is_reported():
    a = analyze("Colour (INS 999)")
    assert a.unrecognized and "999" in a.unrecognized[0]


def test_brown_mark_is_not_vegetarian():
    assert verdict("Salt, sugar", "vegetarian", veg_mark="brown") == "not_friendly"


def test_green_mark_conflict_warns():
    a = analyze("Chicken extract, salt", veg_mark="green")
    assert a.warnings


def test_empty_text():
    r = evaluate(analyze(""), "jain")
    assert r.verdict == "unclear"


def test_evidence_is_traceable():
    a = analyze(MASALA_CHIPS)
    ev = a.tags["onion"].evidence[0]
    assert ev.ingredient == "Seasoning › Spices & Condiments › Onion Powder"
    assert ev.matched == "onion powder"


def test_unknown_profile_and_option():
    a = analyze("salt")
    with pytest.raises(KeyError):
        evaluate(a, "keto")
    with pytest.raises(KeyError):
        evaluate(a, {"id": "jain", "options": {"bogus": True}})
