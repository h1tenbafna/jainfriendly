"""Command line:  python -m jainfriendly "Potato, Salt, Onion powder" -p jain -p vegan"""

from __future__ import annotations

import argparse
import json
import sys

from .analyzer import analyze
from .profiles import DEFAULT_PROFILES, evaluate

ICON = {"friendly": "✅", "likely_friendly": "\U0001f7e2", "unclear": "\U0001f7e1", "not_friendly": "❌"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="jainfriendly", description=__doc__)
    ap.add_argument("ingredients", nargs="?", help="ingredient text (reads stdin if omitted)")
    ap.add_argument("-p", "--profile", action="append", help="profile id (repeatable)")
    ap.add_argument("--avoid", action="append", default=[], metavar="OPTION",
                    help="switch on a profile option, e.g. --avoid yeast")
    ap.add_argument("--veg-mark", choices=["green", "brown"])
    ap.add_argument("--json", action="store_true", help="print full JSON")
    args = ap.parse_args(argv)

    text = args.ingredients if args.ingredients is not None else sys.stdin.read()
    analysis = analyze(text, args.veg_mark)
    specs = []
    for pid in args.profile or DEFAULT_PROFILES:
        from .knowledge import get_knowledge
        opts = {o: True for o in args.avoid if o in get_knowledge().profiles[pid].options}
        specs.append({"id": pid, "options": opts})
    results = [evaluate(analysis, s) for s in specs]

    if args.json:
        out = analysis.to_dict(include_tree=True)
        out["profiles"] = [r.to_dict() for r in results]
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    for r in results:
        print(f"{ICON[r.verdict]} {r.headline}")
        for v in r.violations:
            print(f"     contains {v['label']}: {'; '.join(v['because'])}")
        for u in r.uncertain:
            print(f"     maybe {u['label']} ({u.get('likelihood', 'trace')}): {'; '.join(u['because'])}")
        for c in r.caveats:
            print(f"     note: {c}")
    print()
    for label, ids in (("Contains", "present"), ("May contain", "possible"), ("Traces", "trace")):
        tags = [t.label for t in analysis.tags.values() if t.status == ids]
        if tags:
            print(f"{label}: {', '.join(sorted(tags))}")
    if analysis.unrecognized:
        print(f"Not recognised: {'; '.join(analysis.unrecognized)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
