"""Evaluates diet profiles (Jain, vegan, allergens...) against an Analysis.

Verdicts, from worst to best:
    not_friendly     an avoided tag is definitely present
    unclear          an avoided tag may be present (medium/high likelihood), or for allergen
                     profiles, a "may contain traces" statement
    likely_friendly  only low-likelihood possibilities, cross-contact traces, or some
                     ingredients we could not recognise
    friendly         every ingredient recognised and nothing avoided found
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .analyzer import Analysis
from .knowledge import Knowledge, Profile, get_knowledge

MIN_INGREDIENTS_FOR_FRIENDLY = 2
VERDICT_RANK = {"friendly": 0, "likely_friendly": 1, "unclear": 2, "not_friendly": 3}


@dataclass
class ProfileResult:
    profile: str
    name: str
    verdict: str
    headline: str
    violations: list[dict] = field(default_factory=list)  # avoided & present
    uncertain: list[dict] = field(default_factory=list)  # avoided & possibly present
    caveats: list[str] = field(default_factory=list)
    allowed_by_preference: list[dict] = field(default_factory=list)  # present, but user allows it
    not_detected: list[str] = field(default_factory=list)
    options: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def _brief(tag) -> dict:
    d = {"id": tag.id, "label": tag.label, "status": tag.status}
    if tag.likelihood:
        d["likelihood"] = tag.likelihood
    # Cite only evidence at the tag's own status: a "present" potato is because of "potato",
    # not because maltodextrin can sometimes be made from potato.
    evidence = [e for e in tag.evidence if e.status == tag.status] or tag.evidence
    d["because"] = sorted({e.ingredient for e in evidence})
    reasons = sorted({e.reason for e in evidence if e.reason})
    if reasons:
        d["reasons"] = reasons
    return d


def resolve_profile(spec, kb: Knowledge) -> tuple[Profile, dict[str, bool]]:
    """spec: "jain" or {"id": "jain", "options": {"yeast": true}}."""
    if isinstance(spec, str):
        pid, overrides = spec, {}
    else:
        pid, overrides = spec["id"], dict(spec.get("options") or {})
    if pid not in kb.profiles:
        raise KeyError(f"Unknown profile {pid!r}. Known: {', '.join(kb.profiles)}")
    profile = kb.profiles[pid]
    unknown = set(overrides) - set(profile.options)
    if unknown:
        raise KeyError(f"Unknown option(s) for {pid}: {', '.join(sorted(unknown))}")
    options = {oid: bool(overrides.get(oid, o.avoid)) for oid, o in profile.options.items()}
    return profile, options


def evaluate(analysis: Analysis, spec, kb: Knowledge | None = None) -> ProfileResult:
    kb = kb or get_knowledge()
    profile, options = resolve_profile(spec, kb)

    avoided = kb.resolve_targets(profile.avoid)
    tolerated_ids: set[str] = set()
    for oid, o in profile.options.items():
        targets = kb.resolve_targets(o.targets)
        if options[oid]:
            avoided |= targets
        else:
            tolerated_ids |= targets
    tolerated_ids -= avoided

    res = ProfileResult(profile.id, profile.name, "friendly", "", options=options)
    verdict = "friendly"

    def bump(v: str) -> None:
        nonlocal verdict
        if VERDICT_RANK[v] > VERDICT_RANK[verdict]:
            verdict = v

    for tag in analysis.tags.values():
        if tag.id in tolerated_ids and tag.status == "present":
            res.allowed_by_preference.append(_brief(tag))
        if tag.id not in avoided:
            continue
        if tag.status == "present":
            res.violations.append(_brief(tag))
            bump("not_friendly")
        elif tag.status == "possible":
            if tag.likelihood == "low":
                res.caveats.append(
                    f"{tag.label} is unlikely but possible ({', '.join(sorted({e.ingredient for e in tag.evidence}))})."
                )
                bump("likely_friendly")
            else:
                res.uncertain.append(_brief(tag))
                bump("unclear")
        elif tag.status == "trace":
            if profile.trace_policy == "unclear":
                res.uncertain.append(_brief(tag))
                bump("unclear")
            else:
                res.caveats.append(f"May contain traces of {tag.label.lower()} (shared facility).")
                bump("likely_friendly")

    if analysis.unrecognized:
        res.caveats.append(
            f"{len(analysis.unrecognized)} ingredient(s) not yet in our database: "
            + "; ".join(analysis.unrecognized)
        )
        bump("likely_friendly")
    if not analysis.ingredients:
        bump("unclear")
        res.caveats.append("No ingredients could be read.")
    elif len(analysis.ingredients) < MIN_INGREDIENTS_FOR_FRIENDLY:
        # Crowd-sourced or OCR'd lists are sometimes truncated ("chili powder extra").
        res.caveats.append("Very short ingredient list: it may be incomplete. Check the pack.")
        bump("likely_friendly")

    found = set(analysis.tags)
    res.not_detected = sorted(
        kb.tags[t].label for t in avoided if t not in found and t in kb.tags
    )
    res.verdict = verdict
    name = profile.name.lower() if profile.id.startswith("allergen:") else profile.name
    res.headline = profile.headlines[verdict].format(name=name)
    return res


DEFAULT_PROFILES = ("jain", "vegetarian", "vegan")
