"""Where products are sold, and how each platform's data reaches the catalogue.

Platform connectors live in catalog/connectors/ (see CLAUDE.md for the rules: gentle request
rates, cached product details, no login-gated data, never get around captchas or bot checks).
Anything else can be loaded through the generic feed importer (`import-feed`).
"""

PLATFORMS: dict[str, dict] = {
    "zepto": {
        "name": "Zepto",
        "kind": "quick-commerce",
        "data_route": "Website responses parsed by connectors/zepto.py. Search requests are signed, "
        "so they must come from the Zepto page/app on the user's device (import-capture).",
    },
    "blinkit": {
        "name": "Blinkit",
        "kind": "quick-commerce",
        "data_route": "Website search + product endpoints (connectors/blinkit.py): sync-platform, "
        "or import-capture for responses fetched on a device. Behind a Cloudflare check.",
    },
    "instamart": {
        "name": "Swiggy Instamart",
        "kind": "quick-commerce",
        "data_route": "Website search requires login (2026-11-22), which we don't use. No connector.",
    },
    "bigbasket": {
        "name": "BigBasket",
        "kind": "grocery",
        "data_route": "Partnership / affiliate programme feed.",
    },
    "amazon": {
        "name": "Amazon India",
        "kind": "marketplace",
        "data_route": "Amazon Associates + Product Advertising API (links, prices; no ingredients).",
    },
    "flipkart": {
        "name": "Flipkart",
        "kind": "marketplace",
        "data_route": "Flipkart Affiliate API product feeds (links, prices; no ingredients).",
    },
}


def platform_name(pid: str) -> str:
    return PLATFORMS.get(pid, {}).get("name", pid)
