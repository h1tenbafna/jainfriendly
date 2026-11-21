"""Product catalogue: gather products from sources, analyse them, let users browse/filter."""

from .models import RawOffer, RawProduct
from .store import Catalog

__all__ = ["Catalog", "RawOffer", "RawProduct"]
