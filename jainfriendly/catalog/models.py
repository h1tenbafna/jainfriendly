"""Data shapes that connectors produce and the catalogue stores."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RawOffer:
    """A product being sold on a platform (price/availability can be location-specific)."""

    platform: str  # see platforms.PLATFORMS
    url: str | None = None
    platform_product_id: str | None = None
    price: float | None = None
    mrp: float | None = None
    in_stock: bool | None = None
    location: str = ""  # pincode / city / dark-store id; "" = national


@dataclass
class RawProduct:
    """One product as reported by one source, before matching and analysis."""

    source: str  # openfoodfacts | feed:<name> | manufacturer | <platform id>
    name: str
    source_id: str | None = None
    brand: str | None = None
    quantity: str | None = None
    gtin: str | None = None  # barcode (EAN-13 etc.)
    ingredients_text: str | None = None
    categories: list[str] = field(default_factory=list)
    image_url: str | None = None
    ingredients_image_url: str | None = None
    veg_mark: str | None = None  # green | brown
    source_url: str | None = None
    offers: list[RawOffer] = field(default_factory=list)
