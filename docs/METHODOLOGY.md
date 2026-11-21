# Methodology

The aim is a result people can trust enough to eat by, and that a platform can trust enough to show to millions. That rests on four principles.

## 1. Never claim more than the label supports

| Status | Meaning | Example |
|---|---|---|
| present | The ingredient is named on the label (in English or Hindi) | "Onion powder" → Onion |
| possible | A generic ingredient or additive *may* be or contain it | "Seasoning" → Onion (medium), INS 631 → Meat (medium) |
| trace | Manufacturer declares cross-contact | "May contain traces of peanut" |
| not detected | Not found, and nothing on the label could hide it | |

A product is only `friendly` when **every ingredient was recognised** and nothing avoided is present or possible. Anything we don't recognise downgrades the verdict to `likely_friendly` and is listed, so gaps in our data are visible rather than silently ignored.

## 2. Known sources of hidden ingredients

- **Compound ingredients under 5%.** Under the FSSAI (Labelling and Display) Regulations, 2020, as under Codex rules, a compound ingredient making up less than 5% of the food need not list its own ingredients (additives excepted). "Seasoning", "spices & condiments" and "masala" can therefore hide onion or garlic powder. When the label *does* give a bracketed breakdown, we trust it and drop the uncertainty.
- **Spices & condiments.** Indian food standards class dehydrated onion and garlic as spices/condiments.
- **Additives with several possible sources.** Examples: INS 471 (mono- and diglycerides: animal or vegetable fat); INS 627/631/635 (nucleotides: meat, fish or yeast); INS 322 (lecithin: soy or egg); INS 120 (carmine, from insects); INS 162 (beetroot red, a root); INS 1422 and other modified starches (potato or tapioca are common sources); INS 904 (shellac); INS 920 (L-cysteine, often from feathers).
- **Look-alikes.** Coconut milk, cocoa butter and peanut butter are not dairy. Sweet potato is not potato, though it is still a root. Buckwheat (kuttu) is not wheat. Kalonji is often called "onion seed" but is unrelated to onion. Eggplant is not egg.
- **Compounded hing** often contains wheat flour.
- **Vitamin D3** is usually from lanolin (sheep's wool).
- **FSSAI veg mark.** The green dot is strong evidence against animal sources, so "possible" animal findings are downgraded to low likelihood. The brown dot is treated as non-vegetarian. A green-dot product that lists an animal ingredient raises a warning.

## 3. Jain rules are configurable, not imposed

The default `jain` profile follows the most widely shared practice:

- **Avoided:** kandmool (roots, tubers, bulbs, rhizomes: onion, garlic, potato, carrot, beetroot, radish, fresh ginger, yam, arbi, tapioca/sabudana…), honey, mushrooms, alcohol, and everything non-vegetarian.
- **Tolerated by default, but shown:** dry ginger (sonth), dry turmeric (haldi), yeast, fermented items, many-seeded vegetables (brinjal, fig).

Users switch these on to match their own practice; `jain_strict` turns them all on. Peanuts are deliberately not counted as underground (they are widely eaten in Jain households). Hing is not flagged as a root.

**Open questions to resolve with Jain scholars before calling this "verified":**
- Sabudana and tapioca starch
- Arrowroot
- Chicory-root inulin
- MSG and other fermentation-derived additives
- Curd and yogurt age rules
- Vinegar
- Dried root powders other than ginger and turmeric (e.g. onion powder is clearly avoided, but what about dried beetroot colour?)

## 4. Everything is auditable

- Each tag carries evidence: the path to the ingredient ("Seasoning › Spices & Condiments › Onion Powder"), the phrase or INS code matched, and for "possible" findings, the reason in plain language.
- The knowledge base is plain YAML. The loader refuses to start if a phrase is duplicated, a tag or group is unknown, or a "possible" entry has no reason.
- Tests encode real-world label patterns (see `tests/test_analyzer.py`). Every bug report should become a test.

## Contributing to the knowledge base

1. Find the phrase as it appears on real packs, and add it to `lexicon.yaml`. Matching is case- and plural-insensitive, and handles flavor/flavour, sulfite/sulphite and similar spellings.
2. If it may hide something, use `possible:` with an honest likelihood and a `reason`.
3. If the text contains commas, put it in quotes (the loader rejects malformed entries).
4. Add a test case, then run `pytest`.

## References

- FSSAI Food Safety and Standards (Labelling and Display) Regulations, 2020: allergen declaration, compound ingredients, veg/non-veg logos.
- FSSAI Food Safety and Standards (Food Products Standards and Food Additives) Regulations, 2011: spices and condiments; additive permissions.
- Codex Alimentarius CAC/GL 36-1989: Class Names and the International Numbering System for Food Additives.
- Codex General Standard for the Labelling of Prepackaged Foods (CXS 1-1985): the 5% compound-ingredient rule.
- Open Food Facts ingredient taxonomy and analysis: <https://openfoodfacts.github.io/documentation/>
