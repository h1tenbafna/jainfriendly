# JainFriendly — notes for Claude Code

The project is a consumer app (and later a B2B API) that shows which packaged foods sold on Indian grocery and quick-commerce platforms (Zepto, Blinkit, Swiggy Instamart, BigBasket, Amazon, Flipkart Minutes, JioMart) are Jain, vegetarian, vegan or allergen-free. Each product is tagged with what it contains (onion, potato, milk, gelatin…) and what it might contain hidden inside generic ingredients, with evidence for every tag.

The owner is Jain and does not eat potato, onion or garlic. They eat dry ginger (sonth) and yeast, which is why those are allowed by default in the `jain` profile.

## Run locally (everything is local, nothing depends on cloud services)

```bash
scripts/setup.sh      # venv + deps, builds data/catalog.db from seed/catalog.jsonl.gz, runs tests
scripts/run.sh        # http://localhost:8000 (catalogue), /check (paste ingredients), /docs (API)
.venv/bin/python -m pytest -q
```

- **Storage:** SQLite at `data/catalog.db`. It's gitignored; override with `JAINFRIENDLY_DB`. The committed `seed/catalog.jsonl.gz` is a portable snapshot of ~940 Indian products from Open Food Facts.
- **Catalogue commands** (`python -m jainfriendly.catalog …`):
  - `sync-off [--pages N] [--start-page N]` imports from Open Food Facts. It's rate-limited (about one page per minute) and resumable.
  - `barcode <ean>`, `import-feed <csv|json> --platform <id>`, `reanalyze`, `stats`.
  - `todo` lists the most common unrecognised ingredients, which is the lexicon's to-do list.
  - `export <path>` / `load <path>` write and read snapshots.

## Layout

| Path | What |
|---|---|
| `jainfriendly/data/*.yaml` | Knowledge base: `tags.yaml` (taxonomy), `lexicon.yaml` (label phrases → tags, ~1,400), `additives.yaml` (INS/E codes), `profiles.yaml` (diet rules). |
| `jainfriendly/parser.py` | Label text → ingredient tree plus "contains" / "may contain" statements. Strips footnotes, boilerplate and HTML entities. |
| `jainfriendly/analyzer.py` | Tree → tags (`present` / `possible`+likelihood / `trace`) with evidence. |
| `jainfriendly/profiles.py` | Tags → verdict per profile: `friendly` / `likely_friendly` / `unclear` / `not_friendly`. |
| `jainfriendly/catalog/` | Products, offers per platform+pincode, matching (barcode, else brand+name+size), connectors, SQLite store with FTS. |
| `jainfriendly/catalog/connectors/` | `openfoodfacts.py`, `feed.py` (generic CSV/JSON). Platform connectors go here. |
| `jainfriendly/api.py` | FastAPI. `/v1/products` (filters: `diet`, `free_from`, `avoid`, `platform`, `category`, `strict`, `q`), `/v1/products/{id}`, `/v1/products/barcode/{gtin}`, `/v1/analyze`, `/v1/analyze/batch`. |
| `jainfriendly/static/` | `app.html` (catalogue UI), `index.html` (ingredient checker). Plain HTML/JS, no build step. |
| `docs/METHODOLOGY.md` | How verdicts are decided, sources, open questions for Jain scholars. |

## Rules that keep results trustworthy (don't break these)

- **Never default to "friendly" on missing information.** All of these push the verdict to `likely_friendly` at best:
  - unrecognised ingredients
  - very short lists (fewer than 2 ingredients; crowd data is often truncated)
  - low-likelihood possibilities
  - traces
- **"Possible" lexicon entries need a `reason`**, which is shown to users. The loader enforces this and also rejects duplicate phrases, unknown tags and unexpected YAML keys.
- **Quote YAML text that contains commas.** Flow mappings `{...}` split on commas.
- **When a label gives a bracketed breakdown** of a generic ingredient ("Seasoning (salt, chilli)"), trust it and drop that term's `possible` list.
- **"of vegetable origin"** on an ingredient clears animal-source possibilities for it and its children.
- **Every bug found on a real label becomes a test** in `tests/`.
- **After editing `data/*.yaml`, run `reanalyze`.** The catalogue stores a knowledge-base hash per product.

## Decisions so far

- **Store data.** Owner has decided to build per-platform connectors the way price-comparison apps (e.g. Quick Compare) do: call each platform's web/app endpoints with a pincode. They accepted the terms-of-service risk, and this is unofficial access. Keep it gentle:
  - low request rates
  - cache product details (ingredients don't change per pincode; only price and stock do)
  - no login-gated data, no bypassing captchas
  - one module per platform behind the `Connector` interface (`fetch(...) -> Iterator[RawProduct]` with `RawOffer`s)
  - ideally make the request from the user's device in the mobile app, so the server only receives product details
- **Open Food Facts** data is ODbL: keep the attribution shown in the UI and API.
- **No fabricated data:** never seed fake prices or offers. Show "Store links coming soon" instead.

## Next steps

1. **Blinkit (then Zepto) connector.** On this machine, open the platform's website with a pincode set, watch the network calls in browser devtools or a Playwright script, and identify:
   - search / category listing → product IDs, name, brand, pack size, price, MRP, stock
   - product detail → ingredients text (often under "Product details" or "Ingredients") and the back-of-pack image URLs
   - barcode, if exposed

   Implement `jainfriendly/catalog/connectors/blinkit.py`. Add tests using saved JSON fixtures, never live calls. Add a CLI command `sync-platform blinkit --pincode 400001 --query namkeen`.
2. **Read ingredients from label photos (OCR)** for products with an image but no ingredient text: Open Food Facts `ingredients_image_url` and platform back-of-pack images. Options: Tesseract (local, free) or a vision model. Store the result with `source` set so the lower trust of OCR'd text is visible.
3. **Mobile app.** The owner wants one, and likes the clean dark UI of comparison apps (Quick Compare). Use that as inspiration only; build our own brand. Recommended: Expo (React Native) in `mobile/`, talking to this API:
   - onboarding: choose diet + personal options (sonth/yeast/brinjal…) + allergies
   - home: search and category browse with filter chips (same params as `/v1/products`)
   - barcode scanner (`expo-camera`) → `/v1/products/barcode/{gtin}`
   - product screen: verdict cards, contains / might-contain tags with evidence, "where to buy" rows with a store badge, price and deep link
   - later: on-device store fetching for the platform connectors, saved lists, "notify me when a Jain-friendly version is in stock"
4. **Jain rulebook review** with scholars (open questions in `docs/METHODOLOGY.md`).
