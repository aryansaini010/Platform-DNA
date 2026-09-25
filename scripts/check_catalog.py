"""Validate the platform/region catalog invariant (no rebuild).

Invariant: every platform belongs to >=1 region, every region code exists,
no duplicate slugs/names. Exits non-zero with a loud list on violation.
Run:  python scripts/check_catalog.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / "data" / "catalog"


def main() -> int:
    plats = json.loads((CAT / "platforms.json").read_text(encoding="utf-8"))
    regions = json.loads((CAT / "regions.json").read_text(encoding="utf-8"))
    codes = {r["code"] for r in regions}
    errors: list[str] = []
    seen_slugs, seen_names = set(), set()
    name_lc = {p["name"].lower(): p["name"] for p in plats}
    for p in plats:
        if p["slug"] in seen_slugs:
            errors.append(f"duplicate slug: {p['slug']}")
        seen_slugs.add(p["slug"])
        if p["name"] in seen_names:
            errors.append(f"duplicate name: {p['name']}")
        seen_names.add(p["name"])
        if not p.get("regions"):
            errors.append(f"platform with no region (impossible): {p['name']}")
        for c in p.get("regions", []):
            if c not in codes:
                errors.append(f"dangling region code {c} on {p['name']}")
        for a in p.get("aliases", []) or []:
            hit = name_lc.get((a or "").lower())
            if hit and hit != p["name"]:
                errors.append(f"alias collision: alias '{a}' on {p['name']} equals platform '{hit}'")
    if errors:
        print("CATALOG INVARIANT VIOLATIONS:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"catalog ok: {len(plats)} platforms, {len(regions)} regions, invariant holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
