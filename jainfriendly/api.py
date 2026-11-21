"""HTTP API.

    uvicorn jainfriendly.api:app --reload

GET  /v1/products       browse the catalogue: search + diet / allergen / tag / platform filters
GET  /v1/products/{id}  one product with full analysis and where to buy
GET  /v1/products/barcode/{gtin}  look up a scanned barcode
GET  /v1/catalog        catalogue facets (categories, platforms, verdict counts)
GET  /v1/platforms      supported platforms
POST /v1/analyze        analyse ingredient text directly
POST /v1/analyze/batch  analyse many products at once (for platform integrations)
GET  /v1/profiles       available diet profiles and their options
GET  /v1/tags           tag taxonomy
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Literal, Union

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import __version__
from .analyzer import Analyzer
from .catalog import Catalog
from .catalog.platforms import PLATFORMS
from .knowledge import get_knowledge
from .profiles import DEFAULT_PROFILES, evaluate

app = FastAPI(
    title="JainFriendly API",
    version=__version__,
    description="Tags what is inside a packaged food product and checks it against Jain, "
    "vegetarian, vegan and allergen profiles, with evidence for every result.",
)

STATIC = Path(__file__).parent / "static"


class ProfileSpec(BaseModel):
    id: str
    options: dict[str, bool] = Field(default_factory=dict)


ProfileArg = Union[str, ProfileSpec]


class AnalyzeRequest(BaseModel):
    ingredients: str = Field(..., description="Ingredient text as printed on the label.")
    profiles: list[ProfileArg] = Field(default_factory=lambda: list(DEFAULT_PROFILES))
    veg_mark: Literal["green", "brown"] | None = Field(
        None, description="FSSAI vegetarian (green) or non-vegetarian (brown) mark, if known."
    )
    include_tree: bool = False


class Product(BaseModel):
    id: str
    ingredients: str
    veg_mark: Literal["green", "brown"] | None = None


class BatchRequest(BaseModel):
    products: list[Product] = Field(..., max_length=1000)
    profiles: list[ProfileArg] = Field(default_factory=lambda: list(DEFAULT_PROFILES))


def _spec(p: ProfileArg):
    return p if isinstance(p, str) else p.model_dump()


def _run(ingredients: str, veg_mark, profiles, include_tree: bool) -> dict:
    kb = get_knowledge()
    analysis = Analyzer(kb).analyze(ingredients, veg_mark)
    try:
        results = [evaluate(analysis, _spec(p), kb).to_dict() for p in profiles]
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc.args[0])) from exc
    out = analysis.to_dict(include_tree=include_tree)
    out["profiles"] = results
    out["disclaimer"] = DISCLAIMER
    return out


DISCLAIMER = (
    "Results are derived from the ingredient text supplied. Manufacturers are not required "
    "to itemise compound ingredients below 5% of the product, so hidden ingredients are "
    "possible; check the pack or contact the manufacturer when it matters."
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.post("/v1/analyze")
def analyze(req: AnalyzeRequest) -> dict:
    return _run(req.ingredients, req.veg_mark, req.profiles, req.include_tree)


@app.post("/v1/analyze/batch")
def analyze_batch(req: BatchRequest) -> dict:
    out = []
    for p in req.products:
        full = _run(p.ingredients, p.veg_mark, req.profiles, False)
        out.append(
            {
                "id": p.id,
                "contains": full["contains"],
                "may_contain": full["may_contain"],
                "traces": full["traces"],
                "unrecognized_count": len(full["unrecognized"]),
                "verdicts": {r["profile"]: r["verdict"] for r in full["profiles"]},
            }
        )
    return {"products": out, "disclaimer": DISCLAIMER}


@app.get("/v1/profiles")
def profiles() -> list[dict]:
    kb = get_knowledge()
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "avoid": list(p.avoid),
            "options": [
                {"id": o.id, "label": o.label, "default": o.avoid, "targets": list(o.targets)}
                for o in p.options.values()
            ],
            "trace_policy": p.trace_policy,
        }
        for p in kb.profiles.values()
    ]


@app.get("/v1/tags")
def tags() -> dict:
    kb = get_knowledge()
    return {
        "groups": [g.__dict__ for g in kb.groups.values()],
        "tags": [{"id": t.id, "label": t.label, "groups": list(t.groups)} for t in kb.tags.values()],
    }


# ---------------------------------------------------------------------------- catalogue
_catalog: Catalog | None = None
_lock = threading.Lock()
ATTRIBUTION = (
    "Product data from Open Food Facts (openfoodfacts.org), available under the Open "
    "Database License; images CC BY-SA."
)


def get_catalog() -> Catalog:
    global _catalog
    if _catalog is None:
        _catalog = Catalog()
    return _catalog


def set_catalog(catalog: Catalog) -> None:
    global _catalog
    _catalog = catalog


@app.get("/v1/products")
def list_products(
    q: str | None = None,
    diet: list[str] = Query(default=[], description="e.g. jain, jain_strict, vegan, vegetarian"),
    free_from: list[str] = Query(default=[], description="allergens, e.g. peanut, milk, gluten"),
    avoid: list[str] = Query(default=[], description="tag ids to exclude, e.g. onion, potato"),
    platform: str | None = None,
    category: str | None = None,
    strict: bool = Query(False, description="only fully verified 'friendly' (exclude 'likely')"),
    made_in_india: bool | None = None,
    limit: int = Query(40, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    try:
        with _lock:
            res = get_catalog().search(
                q=q, diet=diet, include_likely=not strict, free_from=free_from, avoid_tags=avoid,
                platform=platform, category=category, made_in_india=made_in_india,
                limit=limit, offset=offset,
            )
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc.args[0])) from exc
    res["attribution"] = ATTRIBUTION
    return res


@app.get("/v1/products/barcode/{gtin}")
def get_product_by_barcode(gtin: str) -> dict:
    """For barcode scanning in the mobile app."""
    with _lock:
        product = get_catalog().get_by_gtin(gtin)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not in catalogue yet")
    product["attribution"] = ATTRIBUTION
    product["disclaimer"] = DISCLAIMER
    return product


@app.get("/v1/products/{product_id}")
def get_product(product_id: int) -> dict:
    with _lock:
        product = get_catalog().get(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    product["attribution"] = ATTRIBUTION
    product["disclaimer"] = DISCLAIMER
    return product


@app.get("/v1/catalog")
def catalog_facets() -> dict:
    with _lock:
        return get_catalog().facets()


@app.get("/v1/platforms")
def platforms() -> list[dict]:
    return [{"id": k, **v} for k, v in PLATFORMS.items()]


@app.get("/", include_in_schema=False)
def app_page() -> FileResponse:
    return FileResponse(STATIC / "app.html")


@app.get("/check", include_in_schema=False)
def checker_page() -> FileResponse:
    return FileResponse(STATIC / "index.html")
