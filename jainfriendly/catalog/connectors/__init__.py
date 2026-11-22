"""Data source connectors. Each yields RawProduct objects for Catalog.upsert()."""

from . import blinkit, zepto
from .base import Blocked, DetailCache, Location, PoliteClient, geocode_pincode
from .feed import read_feed
from .openfoodfacts import OpenFoodFactsConnector

# Platforms we can query from the server (subject to the platform not blocking us).
LIVE_CONNECTORS = {"blinkit": blinkit.BlinkitConnector}

# Parsers for responses captured elsewhere (e.g. on the user's device): platform -> parse_capture.
CAPTURE_PARSERS = {"blinkit": blinkit.parse_capture, "zepto": zepto.parse_capture}

__all__ = [
    "Blocked", "CAPTURE_PARSERS", "DetailCache", "LIVE_CONNECTORS", "Location", "OpenFoodFactsConnector",
    "PoliteClient", "geocode_pincode", "read_feed",
]
