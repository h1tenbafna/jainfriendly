"""JainFriendly: ingredient tagging and diet checks for packaged food."""

__version__ = "0.1.0"

from .analyzer import Analysis, Analyzer, analyze  # noqa: E402
from .profiles import evaluate  # noqa: E402

__all__ = ["Analysis", "Analyzer", "analyze", "evaluate", "__version__"]
