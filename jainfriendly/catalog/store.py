"""Catalogue operations: match + merge incoming products, analyse them, and query them."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import sqlite3
from pathlib import Path

from .. import __version__
from ..analyzer import Analyzer
from ..knowledge import DATA_DIR, get_knowledge
from ..profiles import VERDICT_RANK, evaluate
from .db import connect
from .models import RawOffer, RawProduct
from .platforms import platform_name

NO_DATA = "no_data"
RANKS = {**VERDICT_RANK, NO_DATA: 9}

# Higher wins when two sources disagree about ingredient text.
SOURCE_PRIORITY = {"manufacturer": 4, "platform": 3, "feed": 2, "openfoodfacts": 1}

# Simple top-level categories for browsing, derived from source category tags.
CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Chips & namkeen", ("chip", "crisp", "namkeen", "salty-snack", "bhujia", "nachos", "popcorn", "puffed")),
    ("Biscuits & cookies", ("biscuit", "cookie", "cracker", "rusk", "wafer")),
    ("Chocolates & sweets", ("chocolate", "confectioner", "candies", "candy", "sweet", "mithai", "toffee", "gum")),
    ("Instant food", ("noodle", "instant", "pasta", "ready-meal", "meals", "soup", "ready-to")),
    ("Sauces & spreads", ("sauce", "ketchup", "spread", "condiment", "dip", "chutney", "pickle", "jam", "mayonnaise")),
    ("Spices & masala", ("spice", "masala", "seasoning", "herb")),
    ("Beverages", ("beverage", "drink", "juice", "tea", "coffee", "soda", "water")),
    ("Dairy", ("dairies", "dairy", "milk", "cheese", "yogurt", "curd", "butter", "ghee", "paneer", "ice-cream")),
    ("Breakfast & cereals", ("cereal", "breakfast", "muesli", "oat", "corn-flake", "granola")),
    ("Bakery", ("bread", "cake", "bakery", "bun", "pastr")),
    ("Snacks (other)", ("snack",)),
]

CATALOG_PROFILES = ["jain", "jain_strict", "vegetarian", "vegan"]


def knowledge_version() -> str:
    h = hashlib.sha256()
    for f in sorted(Path(DATA_DIR).glob("*.yaml")):
        h.update(f.read_bytes())
    return f"{__version__}+{h.hexdigest()[:12]}"


def _norm(s: str | None) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (s or "").lower()))


def match_key(name: str, brand: str | None, quantity: str | None) -> str:
    qty = re.sub(r"\s+", "", (quantity or "").lower())
    return f"{_norm(brand)}|{_norm(name)}|{qty}"


def clean_gtin(gtin: str | None) -> str | None:
    digits = re.sub(r"\D", "", gtin or "")
    if len(digits) < 8:
        return None
    core = digits.lstrip("0")  # GTIN-8/12/13/14 with leading zeros are the same code
    return core.zfill(13) if len(core) <= 13 else core


def top_category(categories: list[str], name: str = "") -> str | None:
    hay = " ".join(categories).lower() + " " + name.lower()
    for label, keys in CATEGORY_RULES:
        if any(k in hay for k in keys):
            return label
    return None


def _priority(source: str | None) -> int:
    if not source:
        return 0
    return SOURCE_PRIORITY.get(source.split(":")[0], 2)


class Catalog:
    def __init__(self, db: str | Path | sqlite3.Connection | None = None):
        self.conn = db if isinstance(db, sqlite3.Connection) else connect(db)
        self.kb = get_knowledge()
        self.analyzer = Analyzer(self.kb)
        self.version = knowledge_version()
        self.profiles = CATALOG_PROFILES + [p for p in self.kb.profiles if p.startswith("allergen:")]

    # ------------------------------------------------------------------ writing
    def upsert(self, raw: RawProduct) -> int:
        """Insert or merge a product and its offers, then (re)analyse it. Returns product id."""
        c = self.conn
        gtin = clean_gtin(raw.gtin)
        key = match_key(raw.name, raw.brand, raw.quantity)
        row = None
        if gtin:
            row = c.execute("SELECT * FROM products WHERE gtin = ?", (gtin,)).fetchone()
        if row is None and _norm(raw.brand) and _norm(raw.name):
            row = c.execute(
                "SELECT * FROM products WHERE match_key = ? AND (gtin IS NULL OR ? IS NULL)",
                (key, gtin),
            ).fetchone()

        text = (raw.ingredients_text or "").strip() or None
        category = top_category(raw.categories, raw.name)
        made_in_india = int(bool(gtin and gtin.startswith("890")))

        if row is None:
            cur = c.execute(
                """INSERT INTO products (gtin, match_key, name, brand, quantity, category, categories,
                       image_url, ingredients_image_url, ingredients_text, ingredients_source,
                       veg_mark, source, source_id, source_url, made_in_india)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    gtin, key, raw.name.strip(), raw.brand, raw.quantity, category,
                    json.dumps(raw.categories), raw.image_url, raw.ingredients_image_url, text,
                    raw.source if text else None, raw.veg_mark, raw.source, raw.source_id,
                    raw.source_url, made_in_india,
                ),
            )
            pid = cur.lastrowid
            changed_text = True
        else:
            pid = row["id"]
            take_text = text is not None and (
                row["ingredients_text"] is None
                or _priority(raw.source) >= _priority(row["ingredients_source"])
            )
            changed_text = take_text and text != row["ingredients_text"]
            c.execute(
                """UPDATE products SET
                       gtin = COALESCE(gtin, ?), brand = COALESCE(brand, ?),
                       quantity = COALESCE(quantity, ?), category = COALESCE(category, ?),
                       image_url = COALESCE(image_url, ?),
                       ingredients_image_url = COALESCE(ingredients_image_url, ?),
                       veg_mark = COALESCE(?, veg_mark),
                       ingredients_text = CASE WHEN ? THEN ? ELSE ingredients_text END,
                       ingredients_source = CASE WHEN ? THEN ? ELSE ingredients_source END,
                       made_in_india = MAX(made_in_india, ?),
                       updated_at = datetime('now')
                   WHERE id = ?""",
                (
                    gtin, raw.brand, raw.quantity, category, raw.image_url,
                    raw.ingredients_image_url, raw.veg_mark, take_text, text, take_text,
                    raw.source, made_in_india, pid,
                ),
            )
            changed_text = changed_text or bool(raw.veg_mark and raw.veg_mark != row["veg_mark"])

        for o in raw.offers:
            c.execute(
                """INSERT INTO offers (product_id, platform, platform_product_id, url, price, mrp,
                                       in_stock, location, seen_at)
                   VALUES (?,?,?,?,?,?,?,?, datetime('now'))
                   ON CONFLICT (product_id, platform, location) DO UPDATE SET
                       platform_product_id = COALESCE(excluded.platform_product_id, platform_product_id),
                       url = COALESCE(excluded.url, url), price = excluded.price, mrp = excluded.mrp,
                       in_stock = excluded.in_stock, seen_at = excluded.seen_at""",
                (
                    pid, o.platform, o.platform_product_id, o.url, o.price, o.mrp,
                    None if o.in_stock is None else int(o.in_stock), o.location or "",
                ),
            )

        if changed_text:
            self._analyze(pid)
        c.commit()
        return pid

    def _analyze(self, pid: int) -> None:
        c = self.conn
        row = c.execute("SELECT ingredients_text, veg_mark FROM products WHERE id = ?", (pid,)).fetchone()
        c.execute("DELETE FROM product_tags WHERE product_id = ?", (pid,))
        c.execute("DELETE FROM product_verdicts WHERE product_id = ?", (pid,))
        text = row["ingredients_text"]
        if not text:
            for p in self.profiles:
                c.execute(
                    "INSERT INTO product_verdicts VALUES (?,?,?,?)", (pid, p, NO_DATA, RANKS[NO_DATA])
                )
            c.execute(
                "UPDATE products SET analysis_json = NULL, analysis_version = ?, unrecognized_count = NULL WHERE id = ?",
                (self.version, pid),
            )
            return
        analysis = self.analyzer.analyze(text, row["veg_mark"])
        results = {p: evaluate(analysis, p, self.kb) for p in self.profiles}
        c.executemany(
            "INSERT INTO product_tags VALUES (?,?,?,?)",
            [(pid, t.id, t.status, t.likelihood) for t in analysis.tags.values()],
        )
        c.executemany(
            "INSERT INTO product_verdicts VALUES (?,?,?,?)",
            [(pid, p, r.verdict, RANKS[r.verdict]) for p, r in results.items()],
        )
        doc = analysis.to_dict()
        doc["profiles"] = {p: r.to_dict() for p, r in results.items()}
        c.execute(
            "UPDATE products SET analysis_json = ?, analysis_version = ?, unrecognized_count = ? WHERE id = ?",
            (json.dumps(doc), self.version, len(analysis.unrecognized), pid),
        )

    def reanalyze(self, all_products: bool = False) -> int:
        """Re-run analysis after the knowledge base changed. Returns count."""
        q = "SELECT id FROM products" + ("" if all_products else " WHERE analysis_version IS NOT ?")
        ids = [r[0] for r in self.conn.execute(q, () if all_products else (self.version,))]
        for pid in ids:
            self._analyze(pid)
        self.conn.commit()
        return len(ids)

    # ------------------------------------------------------------------ reading
    def search(
        self,
        q: str | None = None,
        diet: list[str] | None = None,
        include_likely: bool = True,
        free_from: list[str] | None = None,
        avoid_tags: list[str] | None = None,
        platform: str | None = None,
        category: str | None = None,
        made_in_india: bool | None = None,
        limit: int = 40,
        offset: int = 0,
    ) -> dict:
        where, args = ["1=1"], []
        max_rank = RANKS["likely_friendly"] if include_likely else RANKS["friendly"]
        for p in diet or []:
            if p not in self.profiles:
                raise KeyError(f"Unknown diet {p!r}")
            where.append(
                "EXISTS (SELECT 1 FROM product_verdicts v WHERE v.product_id = p.id AND v.profile = ? AND v.rank <= ?)"
            )
            args += [p, max_rank]
        for a in free_from or []:
            pid = a if a.startswith("allergen:") else f"allergen:{a}"
            if pid not in self.profiles:
                raise KeyError(f"Unknown allergen {a!r}")
            where.append(
                "EXISTS (SELECT 1 FROM product_verdicts v WHERE v.product_id = p.id AND v.profile = ? AND v.rank <= ?)"
            )
            args += [pid, max_rank]
        if avoid_tags:
            unknown = [t for t in avoid_tags if t not in self.kb.tags]
            if unknown:
                raise KeyError(f"Unknown tag(s): {', '.join(unknown)}")
            marks = ",".join("?" * len(avoid_tags))
            where.append("p.analysis_json IS NOT NULL")
            where.append(
                f"""NOT EXISTS (SELECT 1 FROM product_tags t WHERE t.product_id = p.id AND t.tag IN ({marks})
                    AND (t.status = 'present' OR (t.status = 'possible' AND t.likelihood != 'low')))"""
            )
            args += avoid_tags
        if platform:
            where.append("EXISTS (SELECT 1 FROM offers o WHERE o.product_id = p.id AND o.platform = ?)")
            args.append(platform)
        if category:
            where.append("p.category = ?")
            args.append(category)
        if made_in_india is not None:
            where.append("p.made_in_india = ?")
            args.append(int(made_in_india))
        if q and q.strip():
            terms = " ".join(f'"{w}"*' for w in re.findall(r"\w+", q))
            if terms:
                where.append("p.id IN (SELECT rowid FROM products_fts WHERE products_fts MATCH ?)")
                args.append(terms)

        sql_where = " AND ".join(where)
        total = self.conn.execute(f"SELECT COUNT(*) FROM products p WHERE {sql_where}", args).fetchone()[0]
        # Best matches first: verdict for the first chosen diet, then products with photos
        # and fully recognised ingredient lists.
        sort_profile = (diet or ["jain"])[0]
        rows = self.conn.execute(
            f"""SELECT p.* FROM products p
                LEFT JOIN product_verdicts sv ON sv.product_id = p.id AND sv.profile = ?
                WHERE {sql_where}
                ORDER BY COALESCE(sv.rank, 9), (p.image_url IS NULL), p.unrecognized_count, p.name
                LIMIT ? OFFSET ?""",
            [sort_profile] + args + [limit, offset],
        ).fetchall()
        return {"total": total, "items": [self._summary(r) for r in rows]}

    def get_by_gtin(self, gtin: str) -> dict | None:
        code = clean_gtin(gtin)
        row = self.conn.execute("SELECT id FROM products WHERE gtin = ?", (code,)).fetchone() if code else None
        return self.get(row["id"]) if row else None

    def get(self, pid: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
        if row is None:
            return None
        out = self._summary(row)
        out["ingredients_text"] = row["ingredients_text"]
        out["ingredients_source"] = row["ingredients_source"]
        out["analysis"] = json.loads(row["analysis_json"]) if row["analysis_json"] else None
        out["source"] = {"name": row["source"], "url": row["source_url"]}
        return out

    def _summary(self, row) -> dict:
        pid = row["id"]
        verdicts = {
            r["profile"]: r["verdict"]
            for r in self.conn.execute(
                "SELECT profile, verdict FROM product_verdicts WHERE product_id = ?", (pid,)
            )
        }
        tags = self.conn.execute(
            "SELECT tag, status, likelihood FROM product_tags WHERE product_id = ?", (pid,)
        ).fetchall()
        offers = self.conn.execute(
            "SELECT platform, url, price, mrp, in_stock, location, seen_at FROM offers WHERE product_id = ? ORDER BY price",
            (pid,),
        ).fetchall()
        label = lambda t: self.kb.tags[t].label if t in self.kb.tags else t  # noqa: E731
        return {
            "id": pid,
            "gtin": row["gtin"],
            "name": row["name"],
            "brand": row["brand"],
            "quantity": row["quantity"],
            "category": row["category"],
            "image_url": row["image_url"],
            "made_in_india": bool(row["made_in_india"]),
            "has_ingredients": row["ingredients_text"] is not None,
            "unrecognized_count": row["unrecognized_count"],
            "verdicts": verdicts,
            "contains": [{"id": t["tag"], "label": label(t["tag"])} for t in tags if t["status"] == "present"],
            "may_contain": [
                {"id": t["tag"], "label": label(t["tag"]), "likelihood": t["likelihood"]}
                for t in tags if t["status"] == "possible"
            ],
            "traces": [{"id": t["tag"], "label": label(t["tag"])} for t in tags if t["status"] == "trace"],
            "offers": [
                {
                    "platform": o["platform"],
                    "platform_name": platform_name(o["platform"]),
                    "url": o["url"],
                    "price": o["price"],
                    "mrp": o["mrp"],
                    "in_stock": None if o["in_stock"] is None else bool(o["in_stock"]),
                    "location": o["location"] or None,
                    "seen_at": o["seen_at"],
                }
                for o in offers
            ],
        }

    def facets(self) -> dict:
        c = self.conn
        return {
            "products": c.execute("SELECT COUNT(*) FROM products").fetchone()[0],
            "with_ingredients": c.execute(
                "SELECT COUNT(*) FROM products WHERE ingredients_text IS NOT NULL"
            ).fetchone()[0],
            "categories": [
                {"name": r[0], "count": r[1]}
                for r in c.execute(
                    "SELECT category, COUNT(*) FROM products WHERE category IS NOT NULL GROUP BY category ORDER BY 2 DESC"
                )
            ],
            "platforms": [
                {"id": r[0], "name": platform_name(r[0]), "products": r[1]}
                for r in c.execute(
                    "SELECT platform, COUNT(DISTINCT product_id) FROM offers GROUP BY platform ORDER BY 2 DESC"
                )
            ],
            "verdicts": {
                p: dict(
                    c.execute(
                        "SELECT verdict, COUNT(*) FROM product_verdicts WHERE profile = ? GROUP BY verdict",
                        (p,),
                    ).fetchall()
                )
                for p in CATALOG_PROFILES
            },
        }

    def top_unrecognized(self, limit: int = 50) -> list[tuple[str, int]]:
        """Most frequent unrecognised ingredients: the lexicon's to-do list."""
        counts: dict[str, int] = {}
        for (doc,) in self.conn.execute("SELECT analysis_json FROM products WHERE unrecognized_count > 0"):
            for path in json.loads(doc)["unrecognized"]:
                leaf = path.split(" › ")[-1].strip().lower()
                counts[leaf] = counts.get(leaf, 0) + 1
        return sorted(counts.items(), key=lambda kv: -kv[1])[:limit]


    # ------------------------------------------------------------------ snapshots
    def export_snapshot(self, path: str | Path) -> int:
        """Write every product (as its source reported it) plus offers, one JSON per line.
        Analysis is not stored: it is recomputed on load with the current knowledge base."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        opener = gzip.open if path.suffix == ".gz" else open
        n = 0
        with opener(path, "wt", encoding="utf-8") as fh:
            for r in self.conn.execute("SELECT * FROM products ORDER BY id"):
                offers = [
                    dict(o) for o in self.conn.execute(
                        "SELECT platform, platform_product_id, url, price, mrp, in_stock, location "
                        "FROM offers WHERE product_id = ?", (r["id"],)
                    )
                ]
                doc = {
                    "source": r["ingredients_source"] or r["source"], "source_id": r["source_id"],
                    "source_url": r["source_url"], "name": r["name"], "brand": r["brand"],
                    "quantity": r["quantity"], "gtin": r["gtin"],
                    "ingredients_text": r["ingredients_text"],
                    "categories": json.loads(r["categories"] or "[]"), "image_url": r["image_url"],
                    "ingredients_image_url": r["ingredients_image_url"], "veg_mark": r["veg_mark"],
                    "offers": offers,
                }
                fh.write(json.dumps(doc, ensure_ascii=False) + "\n")
                n += 1
        return n

    def load_snapshot(self, path: str | Path) -> int:
        path = Path(path)
        opener = gzip.open if path.suffix == ".gz" else open
        n = 0
        with opener(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                d = json.loads(line)
                offers = [
                    RawOffer(**{**o, "in_stock": None if o.get("in_stock") is None else bool(o["in_stock"])})
                    for o in d.pop("offers", [])
                ]
                self.upsert(RawProduct(**d, offers=offers))
                n += 1
        return n
