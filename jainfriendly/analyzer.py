"""Turns ingredient text into tags with evidence.

Every finding records *why* a tag was assigned (which ingredient text, which lexicon phrase or
INS number, and for uncertain findings the reason), so results are auditable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .knowledge import LIKELIHOODS, Knowledge, Term, get_knowledge
from .parser import IngredientNode, parse_label
from .text import DESCRIPTORS, tokenize

STATUS_RANK = {"trace": 1, "possible": 2, "present": 3}
FLAVOUR_WORDS = {"flavour", "flavouring", "flavoured", "essence", "taste"}
NON_VEG_GROUPS = {"meat", "fish", "crustacean", "mollusc", "egg", "animal_byproduct", "insect_derived"}

_INS_PREFIXED = re.compile(r"\b(?:ins|e)\s*[-.:]?\s*(\d{3,4})\s*([a-f])?", re.I)
_BARE_NUMBER = re.compile(r"(?<![\d.])(\d{3,4})\s*([a-f])?(?![\d%.])", re.I)
_CODE_FILLER = {"ins", "e", "and", "i", "ii", "iii", "iv", "v", "vi"}


def _is_only_codes(text: str) -> bool:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return bool(tokens) and all(
        t in _CODE_FILLER or re.fullmatch(r"\d{3,4}[a-f]?", t) for t in tokens
    ) and any(t[0].isdigit() for t in tokens)


@dataclass
class Evidence:
    status: str  # present | possible | trace
    source: str  # ingredient | additive | allergen_statement | trace_statement | veg_mark
    ingredient: str  # path, e.g. "Seasoning › Onion Powder"
    matched: str  # lexicon phrase or "INS 627 (Disodium guanylate)"
    likelihood: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class TagResult:
    id: str
    label: str
    groups: list[str]
    status: str
    likelihood: str | None
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "label": self.label,
            "groups": self.groups,
            "status": self.status,
            "evidence": [e.to_dict() for e in self.evidence],
        }
        if self.likelihood:
            d["likelihood"] = self.likelihood
        return d


@dataclass
class Analysis:
    tags: dict[str, TagResult]
    ingredients: list[IngredientNode]
    unrecognized: list[str]
    declared_contains: list[str]
    declared_may_contain: list[str]
    warnings: list[str]

    def present(self) -> list[TagResult]:
        return [t for t in self.tags.values() if t.status == "present"]

    def to_dict(self, include_tree: bool = False) -> dict:
        order = sorted(
            self.tags.values(),
            key=lambda t: (-STATUS_RANK[t.status], -LIKELIHOODS.index(t.likelihood or "low"), t.label),
        )
        d = {
            "tags": [t.to_dict() for t in order],
            "contains": [t.id for t in order if t.status == "present"],
            "may_contain": [t.id for t in order if t.status == "possible"],
            "traces": [t.id for t in order if t.status == "trace"],
            "unrecognized": self.unrecognized,
            "declared": {"contains": self.declared_contains, "may_contain": self.declared_may_contain},
            "warnings": self.warnings,
        }
        if include_tree:
            d["ingredients"] = [n.to_dict() for n in self.ingredients]
        return d


@dataclass
class _Match:
    term: Term
    phrase: str
    flavour_only: bool


def _match_phrases(tokens: list[str], kb: Knowledge) -> tuple[list[_Match], list[str]]:
    """Longest-match-first scan. Returns matches and tokens that matched nothing."""
    matches: list[_Match] = []
    leftover: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        for length in range(min(kb.max_phrase_len, n - i), 0, -1):
            key = tuple(tokens[i : i + length])
            term = kb.phrases.get(key)
            if term is not None:
                nxt = tokens[i + length] if i + length < n else None
                matches.append(_Match(term, " ".join(key), nxt in FLAVOUR_WORDS))
                i += length
                break
        else:
            leftover.append(tokens[i])
            i += 1
    return matches, leftover


def _find_additives(text: str, kb: Knowledge) -> tuple[list[tuple[str, Term | None]], str]:
    """Find INS/E codes. Returns [(code, term|None)] and the text with codes removed."""
    found: list[tuple[str, Term | None]] = []
    prefixed = bool(_INS_PREFIXED.search(text))
    if not (prefixed or _is_only_codes(text)):
        return found, text
    for m in _BARE_NUMBER.finditer(text):
        num, letter = m.group(1), (m.group(2) or "").lower()
        code = num + letter
        term = kb.additives.get(code) or kb.additives.get(num)
        found.append((code, term))
    stripped = _BARE_NUMBER.sub(" ", text)
    stripped = re.sub(r"\b(?:ins|e)\b", " ", stripped, flags=re.I)
    stripped = re.sub(r"\(\s*(?:i|ii|iii|iv|v|vi)\s*\)", " ", stripped, flags=re.I)
    return found, stripped


class Analyzer:
    def __init__(self, kb: Knowledge | None = None):
        self.kb = kb or get_knowledge()

    # -- public -------------------------------------------------------------------------
    def analyze(self, text: str, veg_mark: str | None = None) -> Analysis:
        label = parse_label(text or "")
        findings: list[tuple[str, Evidence]] = []
        unrecognized: list[str] = []
        warnings: list[str] = []

        for node in label.ingredients:
            self._walk(node, [], findings, unrecognized)

        for item in label.contains:
            for tag_id in self._statement_tags(item):
                findings.append(
                    (tag_id, Evidence("present", "allergen_statement", f"Contains: {item}", item))
                )
        for item in label.may_contain:
            for tag_id in self._statement_tags(item):
                findings.append(
                    (tag_id, Evidence("trace", "trace_statement", f"May contain: {item}", item))
                )

        if veg_mark == "brown":
            findings.append(
                ("non_veg_mark", Evidence("present", "veg_mark", "Label mark", "FSSAI brown dot"))
            )
        elif veg_mark == "green":
            self._apply_green_mark(findings, warnings)
        elif veg_mark not in (None, ""):
            raise ValueError("veg_mark must be 'green', 'brown' or omitted")

        if not label.ingredients:
            warnings.append("No ingredients could be read from the text.")

        return Analysis(
            tags=self._aggregate(findings),
            ingredients=label.ingredients,
            unrecognized=unrecognized,
            declared_contains=label.contains,
            declared_may_contain=label.may_contain,
            warnings=warnings,
        )

    # -- internals ----------------------------------------------------------------------
    def _walk(self, node, path, findings, unrecognized) -> None:
        here = path + [node.name]
        where = " › ".join(here)
        additives, rest = _find_additives(node.name, self.kb)
        matches, leftover = _match_phrases(tokenize(rest), self.kb)

        for code, term in additives:
            if term is None:
                unrecognized.append(f"{where} (INS {code})")
                continue
            label = f"INS {code} ({term.name})"
            self._emit(term, label, where, "additive", bool(node.children), False, findings)

        for m in matches:
            self._emit(m.term, m.phrase, where, "ingredient", bool(node.children), m.flavour_only, findings)

        meaningful_left = [t for t in leftover if t not in DESCRIPTORS and not t.isdigit()]
        if not node.children and not matches and not additives and meaningful_left:
            unrecognized.append(where)

        for child in node.children:
            self._walk(child, here, findings, unrecognized)

    def _emit(self, term, matched, where, source, has_children, flavour_only, findings) -> None:
        for tag_id in term.tags:
            if flavour_only:
                label = self.kb.tags[tag_id].label.lower()
                findings.append(
                    (
                        tag_id,
                        Evidence(
                            "possible", source, where, matched, "high",
                            f"Named as a flavour: may be real {label} or a flavouring that imitates it.",
                        ),
                    )
                )
            else:
                findings.append((tag_id, Evidence("present", source, where, matched)))
        # A bracketed breakdown on the label resolves a generic term's uncertainty.
        if term.possible and not has_children:
            for p in term.possible:
                findings.append(
                    (p.tag, Evidence("possible", source, where, matched, p.likelihood, term.reason))
                )

    def _statement_tags(self, item: str) -> set[str]:
        additives, rest = _find_additives(item, self.kb)
        tags: set[str] = set()
        for _, term in additives:
            if term:
                tags |= set(term.tags)
        for m in _match_phrases(tokenize(rest), self.kb)[0]:
            tags |= set(m.term.tags)
        if not tags:  # generic allergen words used in statements
            words = set(tokenize(item))
            if words & {"nut", "treenut"}:
                tags.add("tree_nut")
            if words & {"cereal", "gluten"}:
                tags.add("wheat")
        return tags

    def _apply_green_mark(self, findings, warnings) -> None:
        note = "Product carries the FSSAI vegetarian (green) mark, so an animal source is unlikely."
        for tag_id, ev in findings:
            groups = set(self.kb.tags[tag_id].groups)
            if not groups & NON_VEG_GROUPS:
                continue
            if ev.status == "possible":
                ev.likelihood = "low"
                ev.reason = f"{ev.reason} {note}" if ev.reason else note
            elif ev.status == "present":
                warnings.append(
                    f"Label has a vegetarian (green) mark but lists "
                    f"{self.kb.tags[tag_id].label.lower()} ({ev.ingredient})."
                )

    def _aggregate(self, findings) -> dict[str, TagResult]:
        out: dict[str, TagResult] = {}
        for tag_id, ev in findings:
            tag = self.kb.tags[tag_id]
            res = out.get(tag_id)
            if res is None:
                res = out[tag_id] = TagResult(tag_id, tag.label, list(tag.groups), ev.status, None)
            if STATUS_RANK[ev.status] > STATUS_RANK[res.status]:
                res.status = ev.status
            res.evidence.append(ev)
        for res in out.values():
            if res.status == "possible":
                lk = [e.likelihood for e in res.evidence if e.status == "possible" and e.likelihood]
                res.likelihood = max(lk, key=LIKELIHOODS.index) if lk else "medium"
        return out


def analyze(text: str, veg_mark: str | None = None) -> Analysis:
    return Analyzer().analyze(text, veg_mark)
