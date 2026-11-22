# JainFriendly — notes for Claude Code

The project is a consumer app (and later a B2B API) that shows which packaged foods sold on Indian grocery and quick-commerce platforms (Zepto, Blinkit, Swiggy Instamart, BigBasket, Amazon, Flipkart Minutes, JioMart) are Jain, vegetarian, vegan or allergen-free. Each product is tagged with what it contains (onion, potato, milk, gelatin…) and what it might contain hidden inside generic ingredients, with evidence for every tag.

The owner is Jain and does not eat potato, onion or garlic. They eat dry ginger (sonth) and yeast, which is why those are allowed by default in the `jain` profile.

## Run locally (everything is local, nothing depends on cloud services)

```bash
scripts/setup.sh      # venv + deps, builds data/catalog.db from seed/catalog.jsonl.gz, runs tests
scripts/run.sh        # http://localhost:8000 (catalogue), /check (paste ingredients), /docs (API)
.venv/bin/python -m pytest -q
cd mobile && npm install && npx expo start   # mobile app; run the API with scripts/run.sh --host 0.0.0.0
```

- **Storage:** SQLite at `data/catalog.db`. It's gitignored; override with `JAINFRIENDLY_DB`. The committed `seed/catalog.jsonl.gz` is a portable snapshot of ~940 Indian products from Open Food Facts.
- **Catalogue commands** (`python -m jainfriendly.catalog …`):
  - `sync-off [--pages N] [--start-page N]` imports from Open Food Facts. It's rate-limited (about one page per minute) and resumable.
  - `barcode <ean>`, `import-feed <csv|json> --platform <id>`, `reanalyze`, `stats`.
  - `sync-platform blinkit --query namkeen --pincode 400001 [--lat --lon] [--pages N]` searches Blinkit live (4–6 s between requests, product details cached 30 days in `platform_details`). Without `--lat/--lon` the pincode is geocoded once via OpenStreetMap Nominatim.
  - `import-capture <blinkit|zepto> <files…> --pincode N` imports saved platform responses (JSON, or Zepto product-page HTML).
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
| `jainfriendly/catalog/connectors/` | `openfoodfacts.py`, `feed.py` (generic CSV/JSON), `base.py` (`Connector`, `Blocked`, polite HTTP client, detail cache), `blinkit.py` (live + parsers), `zepto.py` (parsers only). Endpoint notes are in each module's docstring; fixtures in `tests/fixtures/`. |
| `jainfriendly/api.py` | FastAPI. `/v1/products` (filters: `diet`, `free_from`, `avoid`, `platform`, `category`, `strict`, `q`), `/v1/products/{id}`, `/v1/products/barcode/{gtin}`, `POST /v1/products/{id}/evaluate` (personal options), `/v1/analyze`, `/v1/analyze/batch`. |
| `jainfriendly/static/` | `app.html` (catalogue UI), `index.html` (ingredient checker). Plain HTML/JS, no build step. |
| `mobile/` | Expo SDK 58 app (Expo Router, `src/app/`). See `mobile/README.md`. Check with `npx tsc --noEmit` and `npx expo lint`. |
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

1. **Store connectors.** *Status (2026-11-22)*, mapped by browsing in the owner's Chrome:
   - **Blinkit:** done (`connectors/blinkit.py`). The JSON endpoints (`POST /v1/layout/search`, `POST /v1/layout/product/{id}` with `lat`/`lon`/`app_client` headers) answered server-side requests from this machine, though the HTML pages show a Cloudflare captcha to headless browsers. Ingredients, allergen line and "Food Type" (veg mark) come from the product detail; no barcode, so matching is by brand + name + size. Not every product has an "Ingredients" attribute (those stay `no_data`). Pagination (`next_url` + `postback_params`) is implemented but only page 1 has been tried live.
   - **Zepto:** parsers only (`connectors/zepto.py`). Search (`bff-gateway.zepto.com/.../api/v1/search`) is signed per request (`request-signature`, CSRF headers) and the site is behind AWS WAF; we don't reproduce either. About half the search results include ingredients; product pages (`/pn/<slug>/pvid/<id>`) have schema.org JSON-LD with ingredients, allergens and diet. Data has to come from the Zepto page/app on the user's device → `import-capture`.
   - **Instamart:** the website asks for login before showing search results. Login-gated, so no connector.
   - **Next:** a device → server ingest endpoint (e.g. `POST /v1/ingest/{platform}` taking raw responses, parsed by the same Python parsers, authenticated so the catalogue can't be poisoned), and on-device fetching in the mobile app (a WebView on the platform's site lets the platform's own code make the requests). Then BigBasket, Amazon, Flipkart Minutes, JioMart.
2. **Read ingredients from label photos (OCR)** for products with an image but no ingredient text: Open Food Facts `ingredients_image_url` and platform back-of-pack images. Options: Tesseract (local, free) or a vision model. Store the result with `source` set so the lower trust of OCR'd text is visible.
3. **Mobile app.** *Started (2026-11-22):* onboarding, browse, scan, product and "You" screens are in `mobile/`, plus `POST /v1/products/{id}/evaluate` for personal options. Still to do: app icon/branding, saved lists, on-device store fetching, EAS builds. The original brief: the owner wants one, and likes the clean dark UI of comparison apps (Quick Compare). Use that as inspiration only; build our own brand. Recommended: Expo (React Native) in `mobile/`, talking to this API:
   - onboarding: choose diet + personal options (sonth/yeast/brinjal…) + allergies
   - home: search and category browse with filter chips (same params as `/v1/products`)
   - barcode scanner (`expo-camera`) → `/v1/products/barcode/{gtin}`
   - product screen: verdict cards, contains / might-contain tags with evidence, "where to buy" rows with a store badge, price and deep link
   - later: on-device store fetching for the platform connectors, saved lists, "notify me when a Jain-friendly version is in stock"
4. **Jain rulebook review** with scholars (open questions in `docs/METHODOLOGY.md`).
