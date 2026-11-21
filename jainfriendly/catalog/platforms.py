"""Where products are sold, and how each platform's data can legitimately be obtained.

Each platform gets a connector once a legitimate data route exists (affiliate feed, partner
API, or data shared under agreement). Until then, offers can be loaded through the generic
feed importer (`python -m jainfriendly.catalog import-feed`).
"""

PLATFORMS: dict[str, dict] = {
    "zepto": {
        "name": "Zepto",
        "kind": "quick-commerce",
        "data_route": "Partnership / catalogue sharing agreement. No public product API.",
    },
    "blinkit": {
        "name": "Blinkit",
        "kind": "quick-commerce",
        "data_route": "Partnership / catalogue sharing agreement. No public product API.",
    },
    "instamart": {
        "name": "Swiggy Instamart",
        "kind": "quick-commerce",
        "data_route": "Partnership / catalogue sharing agreement. No public product API.",
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
