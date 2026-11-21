"""Data source connectors. Each yields RawProduct objects for Catalog.upsert()."""

from .feed import read_feed
from .openfoodfacts import OpenFoodFactsConnector

__all__ = ["OpenFoodFactsConnector", "read_feed"]
