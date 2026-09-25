"""CLI: fact-pack in → validated Markdown out."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from platform_dna.renderer import render
from platform_dna.validator import validate
from platform_dna.writer import build_report


def main() -> int:
    ap = argparse.ArgumentParser(description="Platform DNA report generator")
    ap.add_argument("--platform", required=True)
    ap.add_argument("--fact-pack", required=True)
    ap.add_argument("--output", default="")
    ap.add_argument("--validate-only", action="store_true")
    args = ap.parse_args()

    pack = json.loads(Path(args.fact_pack).read_text(encoding="utf-8"))
    if pack.get("platform", "").lower() != args.platform.lower():
        print(f"warning: fact-pack platform '{pack.get('platform')}' != --platform '{args.platform}'",
              file=sys.stderr)
    try:
        report = build_report(pack)
    except Exception as e:  # noqa: BLE001
        print(f"BUILD FAILED: {e}", file=sys.stderr)
        return 2
    errors = validate(report, pack.get("facts", []), pack.get("titles", []))
    if errors:
        print("VALIDATION FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 2
    if args.validate_only:
        print(f"OK: {report['platform']} overall={report['overall']['score']} "
              f"titles={report['titles_analysed']}")
        return 0
    out = Path(args.output) if args.output else Path("outputs") / f"{pack.get('slug', 'report')}_Platform_DNA_Report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(report), encoding="utf-8")
    print(f"Wrote {out} (overall={report['overall']['score']}, titles={report['titles_analysed']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
