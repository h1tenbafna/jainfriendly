"""SQLite storage for the product catalogue."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(os.environ.get("JAINFRIENDLY_DB", "data/catalog.db"))

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS products (
    id                    INTEGER PRIMARY KEY,
    gtin                  TEXT UNIQUE,
    match_key             TEXT NOT NULL,
    name                  TEXT NOT NULL,
    brand                 TEXT,
    quantity              TEXT,
    category              TEXT,
    categories            TEXT,
    image_url             TEXT,
    ingredients_image_url TEXT,
    ingredients_text      TEXT,
    ingredients_source    TEXT,
    veg_mark              TEXT,
    source                TEXT NOT NULL,
    source_id             TEXT,
    source_url            TEXT,
    made_in_india         INTEGER NOT NULL DEFAULT 0,
    analysis_json         TEXT,
    analysis_version      TEXT,
    unrecognized_count    INTEGER,
    updated_at            TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_products_match ON products(match_key);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);

CREATE TABLE IF NOT EXISTS offers (
    id                  INTEGER PRIMARY KEY,
    product_id          INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    platform            TEXT NOT NULL,
    platform_product_id TEXT,
    url                 TEXT,
    price               REAL,
    mrp                 REAL,
    in_stock            INTEGER,
    location            TEXT NOT NULL DEFAULT '',
    seen_at             TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (product_id, platform, location)
);
CREATE INDEX IF NOT EXISTS idx_offers_platform ON offers(platform, product_id);

CREATE TABLE IF NOT EXISTS product_tags (
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    tag        TEXT NOT NULL,
    status     TEXT NOT NULL,
    likelihood TEXT,
    PRIMARY KEY (product_id, tag)
);
CREATE INDEX IF NOT EXISTS idx_tags_tag ON product_tags(tag, status);

CREATE TABLE IF NOT EXISTS product_verdicts (
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    profile    TEXT NOT NULL,
    verdict    TEXT NOT NULL,
    rank       INTEGER NOT NULL,
    PRIMARY KEY (product_id, profile)
);
CREATE INDEX IF NOT EXISTS idx_verdicts ON product_verdicts(profile, rank);

CREATE VIRTUAL TABLE IF NOT EXISTS products_fts USING fts5(
    name, brand, ingredients_text, content='products', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS products_ai AFTER INSERT ON products BEGIN
    INSERT INTO products_fts(rowid, name, brand, ingredients_text)
    VALUES (new.id, new.name, new.brand, new.ingredients_text);
END;
CREATE TRIGGER IF NOT EXISTS products_ad AFTER DELETE ON products BEGIN
    INSERT INTO products_fts(products_fts, rowid, name, brand, ingredients_text)
    VALUES ('delete', old.id, old.name, old.brand, old.ingredients_text);
END;
CREATE TRIGGER IF NOT EXISTS products_au AFTER UPDATE ON products BEGIN
    INSERT INTO products_fts(products_fts, rowid, name, brand, ingredients_text)
    VALUES ('delete', old.id, old.name, old.brand, old.ingredients_text);
    INSERT INTO products_fts(rowid, name, brand, ingredients_text)
    VALUES (new.id, new.name, new.brand, new.ingredients_text);
END;
"""


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(path or DEFAULT_DB)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn
