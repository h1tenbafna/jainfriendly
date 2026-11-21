"""Loads and validates the knowledge base (tags, lexicon, additives, profiles)."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from .text import tokenize

DATA_DIR = Path(__file__).parent / "data"
LIKELIHOODS = ("low", "medium", "high")


class KnowledgeError(ValueError):
    """Raised when the knowledge base is internally inconsistent."""


@dataclass(frozen=True)
class Group:
    id: str
    label: str
    description: str = ""
    allergen: bool = False


@dataclass(frozen=True)
class Tag:
    id: str
    label: str
    groups: tuple[str, ...]


@dataclass(frozen=True)
class Possible:
    tag: str
    likelihood: str


@dataclass(frozen=True)
class Term:
    """A lexicon entry or additive: what a phrase / INS number implies."""

    key: str  # canonical phrase or "INS 471"
    tags: tuple[str, ...] = ()
    possible: tuple[Possible, ...] = ()
    reason: str = ""
    name: str = ""  # human name (additives)


@dataclass
class ProfileOption:
    id: str
    label: str
    targets: tuple[str, ...]
    avoid: bool


@dataclass
class Profile:
    id: str
    name: str
    description: str
    avoid: tuple[str, ...]
    options: dict[str, ProfileOption] = field(default_factory=dict)
    trace_policy: str = "caveat"
    headlines: dict[str, str] = field(default_factory=dict)


@dataclass
class Knowledge:
    groups: dict[str, Group]
    tags: dict[str, Tag]
    phrases: dict[tuple[str, ...], Term]
    additives: dict[str, Term]
    profiles: dict[str, Profile]
    max_phrase_len: int

    def tags_in_group(self, group_id: str) -> set[str]:
        return {t.id for t in self.tags.values() if group_id in t.groups}

    def resolve_targets(self, targets: tuple[str, ...] | list[str]) -> set[str]:
        out: set[str] = set()
        for target in targets:
            kind, _, ident = target.partition(":")
            if kind == "group":
                out |= self.tags_in_group(ident)
            elif kind == "tag":
                out.add(ident)
            else:
                raise KnowledgeError(f"Bad target {target!r}")
        return out


def _load_yaml(data_dir: Path, name: str):
    with open(data_dir / name, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _check_keys(entry: dict, allowed: set[str], where: str) -> None:
    extra = set(entry) - allowed
    if extra:
        raise KnowledgeError(
            f"{where}: unexpected key(s) {sorted(extra)} - quote text containing commas"
        )


def _possibles(raw, where: str, tags: dict[str, Tag]) -> tuple[Possible, ...]:
    out = []
    for p in raw or []:
        if p["tag"] not in tags:
            raise KnowledgeError(f"{where}: unknown tag {p['tag']!r}")
        if p["likelihood"] not in LIKELIHOODS:
            raise KnowledgeError(f"{where}: bad likelihood {p['likelihood']!r}")
        out.append(Possible(p["tag"], p["likelihood"]))
    return tuple(out)


def _check_tags(ids, where: str, tags: dict[str, Tag]) -> tuple[str, ...]:
    for t in ids or []:
        if t not in tags:
            raise KnowledgeError(f"{where}: unknown tag {t!r}")
    return tuple(ids or [])


DEFAULT_HEADLINES = {
    "friendly": "{name} friendly",
    "likely_friendly": "Likely {name} friendly",
    "unclear": "Unclear if {name} friendly",
    "not_friendly": "Not {name} friendly",
}

ALLERGEN_HEADLINES = {
    "friendly": "No {name} detected",
    "likely_friendly": "No {name} detected (some ingredients unverified)",
    "unclear": "May contain {name}",
    "not_friendly": "Contains {name}",
}


def load_knowledge(data_dir: Path = DATA_DIR) -> Knowledge:
    data_dir = Path(data_dir)
    raw_tags = _load_yaml(data_dir, "tags.yaml")
    groups = {
        gid: Group(gid, g["label"], g.get("description", "").strip(), bool(g.get("allergen")))
        for gid, g in raw_tags["groups"].items()
    }
    tags: dict[str, Tag] = {}
    for tid, t in raw_tags["tags"].items():
        _check_keys(t, {"label", "groups"}, f"tag {tid}")
        for g in t.get("groups", []):
            if g not in groups:
                raise KnowledgeError(f"tag {tid}: unknown group {g!r}")
        tags[tid] = Tag(tid, t["label"], tuple(t.get("groups", [])))

    # --- lexicon ---
    phrases: dict[tuple[str, ...], Term] = {}
    for i, entry in enumerate(_load_yaml(data_dir, "lexicon.yaml")):
        where = f"lexicon entry #{i + 1} ({entry['match'][0]!r})"
        _check_keys(entry, {"match", "tags", "possible", "reason"}, where)
        term_tags = _check_tags(entry.get("tags"), where, tags)
        poss = _possibles(entry.get("possible"), where, tags)
        if poss and not entry.get("reason"):
            raise KnowledgeError(f"{where}: 'possible' requires a 'reason'")
        for phrase in entry["match"]:
            key = tuple(tokenize(str(phrase)))
            if not key:
                raise KnowledgeError(f"{where}: empty phrase {phrase!r}")
            if key in phrases:
                raise KnowledgeError(
                    f"{where}: phrase {phrase!r} already defined by {phrases[key].key!r}"
                )
            phrases[key] = Term(
                key=" ".join(key), tags=term_tags, possible=poss, reason=entry.get("reason", "")
            )

    # --- additives ---
    additives: dict[str, Term] = {}
    for key, entry in _load_yaml(data_dir, "additives.yaml").items():
        where = f"additive {key}"
        _check_keys(entry, {"name", "tags", "possible", "reason"}, where)
        term_tags = _check_tags(entry.get("tags"), where, tags)
        poss = _possibles(entry.get("possible"), where, tags)
        for code in str(key).split(","):
            code = code.strip().lower()
            if code in additives:
                raise KnowledgeError(f"{where}: INS {code} defined twice")
            additives[code] = Term(
                key=f"INS {code}",
                tags=term_tags,
                possible=poss,
                reason=entry.get("reason", ""),
                name=entry["name"],
            )

    # --- profiles ---
    raw_profiles = _load_yaml(data_dir, "profiles.yaml")["profiles"]
    profiles: dict[str, Profile] = {}

    def build(pid: str) -> Profile:
        if pid in profiles:
            return profiles[pid]
        raw = raw_profiles[pid]
        avoid: list[str] = []
        options: dict[str, ProfileOption] = {}
        if "extends" in raw:
            parent = build(raw["extends"])
            avoid = list(parent.avoid)
            options = {
                k: ProfileOption(o.id, o.label, o.targets, o.avoid) for k, o in parent.options.items()
            }
        avoid += [a for a in raw.get("avoid", []) if a not in avoid]
        for oid, o in (raw.get("options") or {}).items():
            options[oid] = ProfileOption(oid, o["label"], tuple(o["targets"]), bool(o["avoid"]))
        for oid, val in (raw.get("option_defaults") or {}).items():
            if oid not in options:
                raise KnowledgeError(f"profile {pid}: unknown option {oid!r}")
            options[oid].avoid = bool(val)
        profile = Profile(
            id=pid,
            name=raw["name"],
            description=" ".join(raw.get("description", "").split()),
            avoid=tuple(avoid),
            options=options,
            trace_policy=raw.get("trace_policy", "caveat"),
            headlines=dict(DEFAULT_HEADLINES),
        )
        profiles[pid] = profile
        return profile

    for pid in raw_profiles:
        build(pid)

    for gid, g in groups.items():
        if g.allergen:
            short = gid.removeprefix("allergen_")
            pid = f"allergen:{short}"
            profiles[pid] = Profile(
                id=pid,
                name=g.label,
                description=f"Flags {g.label.lower()} as an allergen, including 'may contain' traces.",
                avoid=(f"group:{gid}",),
                trace_policy="unclear",
                headlines=dict(ALLERGEN_HEADLINES),
            )

    kb = Knowledge(
        groups=groups,
        tags=tags,
        phrases=phrases,
        additives=additives,
        profiles=profiles,
        max_phrase_len=max(len(k) for k in phrases),
    )
    for p in profiles.values():  # validate every target resolves
        kb.resolve_targets(p.avoid)
        for o in p.options.values():
            kb.resolve_targets(o.targets)
        for target in list(p.avoid) + [t for o in p.options.values() for t in o.targets]:
            kind, _, ident = target.partition(":")
            if (kind == "group" and ident not in groups) or (kind == "tag" and ident not in tags):
                raise KnowledgeError(f"profile {p.id}: unknown target {target!r}")
    return kb


@lru_cache(maxsize=1)
def get_knowledge() -> Knowledge:
    return load_knowledge()
