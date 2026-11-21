"""Parses free-form ingredient text from a label into a tree.

    "Potato (60%), Seasoning [Salt, Spices (Onion Powder, Garlic)], Emulsifier (INS 322(i)).
     Allergen advice: Contains milk. May contain traces of peanut."

becomes a tree of IngredientNodes plus allergen ("contains") and trace ("may contain")
statements.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

OPEN = {"(": ")", "[": "]", "{": "}"}
CLOSE = set(OPEN.values())

_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_ROMAN = re.compile(r"^\s*(i|ii|iii|iv|v|vi|vii|viii|ix|x)\s*$", re.I)
_LEADING_INGREDIENTS = re.compile(r"^.*?\bingredients?\s*[:\-]\s*", re.I | re.S)

_TRACE = re.compile(
    r"(?:may\s+(?:also\s+)?contain(?:\s+traces?\s+of|\s+traces?)?"
    r"|(?:manufactured|made|processed|produced|packed|prepared)\s+(?:in|on)\s+[^.\n:]*?"
    r"(?:facility|unit|plant|premises|equipment|line|factory)[^.\n:]*?"
    r"(?:handles?|process(?:es)?|uses?|manufactures?|contains?)\s*)"
    r"\s*:?\s*(?P<body>[^.\n]*)",
    re.I,
)
_ALLERGEN = re.compile(
    r"(?:allergen(?:s)?(?:\s+(?:advice|information|info|declaration|statement|warning))?\s*[:\-]\s*"
    r"(?:contains?\s*:?)?|\bcontains\s*:)"
    r"\s*(?P<body>[^.\n]*)",
    re.I,
)
_SPLIT_LIST = re.compile(r"\s*(?:,|;|/|&|\band\b|\bor\b)\s*", re.I)


@dataclass
class IngredientNode:
    name: str
    percent: float | None = None
    children: list["IngredientNode"] = field(default_factory=list)

    def to_dict(self) -> dict:
        d: dict = {"name": self.name}
        if self.percent is not None:
            d["percent"] = self.percent
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        return d


@dataclass
class ParsedLabel:
    ingredients: list[IngredientNode]
    contains: list[str]  # declared allergens ("Contains: milk, soy")
    may_contain: list[str]  # cross-contact ("May contain traces of nuts")


def _split_items(body: str) -> list[str]:
    body = re.sub(r"\b(?:traces?\s+of|traces?)\b", " ", body, flags=re.I)
    return [x.strip(" .:-") for x in _SPLIT_LIST.split(body) if x and x.strip(" .:-")]


def _extract_statements(text: str) -> tuple[str, list[str], list[str]]:
    may: list[str] = []
    contains: list[str] = []

    def take_trace(m: re.Match) -> str:
        may.extend(_split_items(m.group("body")))
        return ". "

    def take_allergen(m: re.Match) -> str:
        contains.extend(_split_items(m.group("body")))
        return ". "

    text = _TRACE.sub(take_trace, text)
    text = _ALLERGEN.sub(take_allergen, text)
    return text, contains, may


def _finish(buf: list[str], children: list[IngredientNode], out: list[IngredientNode]) -> None:
    name = " ".join("".join(buf).split()).strip(" :-*•.")
    if _PERCENT.fullmatch(name) and not children:
        out.append(IngredientNode(name=name))  # bare "(58%)": the parent picks it up
        return
    percent = None
    kept: list[IngredientNode] = []
    for child in children:
        pm = _PERCENT.fullmatch(child.name.strip()) if not child.children else None
        if pm:
            percent = float(pm.group(1))
        elif _ROMAN.match(child.name) and not child.children:
            name = f"{name}({child.name.strip().lower()})"
        else:
            kept.append(child)
    m = _PERCENT.search(name)
    if m:
        percent = float(m.group(1)) if percent is None else percent
        name = " ".join(_PERCENT.sub(" ", name).split()).strip(" :-")
    if not name and not kept:
        return
    if not name:
        out.extend(kept)  # bare bracket group, e.g. "(salt, sugar)"
        return
    out.append(IngredientNode(name=name, percent=percent, children=kept))


def _parse_list(s: str, i: int, closing: str | None) -> tuple[list[IngredientNode], int]:
    out: list[IngredientNode] = []
    buf: list[str] = []
    children: list[IngredientNode] = []
    while i < len(s):
        c = s[i]
        if c in OPEN:
            sub, i = _parse_list(s, i + 1, OPEN[c])
            children.extend(sub)
            continue
        if c in CLOSE:
            if closing is not None:
                _finish(buf, children, out)
                return out, i + 1
            i += 1  # stray closing bracket at top level
            continue
        is_sep = c in ",;" or (
            c == "."
            and not (0 < i < len(s) - 1 and s[i - 1].isdigit() and s[i + 1].isdigit())
        )
        if is_sep:
            _finish(buf, children, out)
            buf, children = [], []
        else:
            buf.append(c)
        i += 1
    _finish(buf, children, out)
    return out, i


def parse_label(text: str) -> ParsedLabel:
    text = text.replace("–", "-").replace("—", "-")
    body, contains, may = _extract_statements(text)
    if re.search(r"\bingredients?\s*[:\-]", body, re.I):
        body = _LEADING_INGREDIENTS.sub("", body, count=1)
    nodes, _ = _parse_list(body, 0, None)
    return ParsedLabel(ingredients=nodes, contains=contains, may_contain=may)
