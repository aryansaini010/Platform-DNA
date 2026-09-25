"""Report library: every validated DNA report is stored, viewable, deletable."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

LIB = Path(__file__).resolve().parents[2] / "data" / "library"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def _slug(pack: dict) -> str:
    s = "".join(c.lower() if c.isalnum() else "_" for c in str(pack.get("slug") or pack.get("platform") or "report"))
    s = "_".join(p for p in s.split("_") if p)
    return s or "report"


def save_report(pack: dict, report: dict, markdown: str) -> dict:
    LIB.mkdir(parents=True, exist_ok=True)
    # Millisecond + pid suffix: concurrent same-second generates never collide.
    rid = f"{_slug(pack)}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]}_{os.getpid()}"
    _atomic_write(LIB / f"{rid}.pack.json",
                  json.dumps(pack, indent=1, ensure_ascii=False))
    _atomic_write(LIB / f"{rid}.md", markdown)
    return entry(rid, pack, report)


def entry(rid: str, pack: dict, report: dict) -> dict:
    scores = {k: v.get("score") for k, v in (report.get("sections", {}) or {}).items()}
    # rid format: <slug>_YYYYMMDD_HHMMSS[_mmm_pid] — the slug itself may
    # contain underscores, so extract the date/time via regex, not rsplit.
    import re as _re
    _m = _re.search(r"(\d{8})_(\d{6})", rid)
    created = f"{_m.group(1)} {_m.group(2)}" if _m else rid
    return {"id": rid, "platform": pack.get("platform", "?"),
            "region": pack.get("region", "?"),
            "overall": report.get("overall", {}).get("score"),
            "titles": report.get("titles_analysed", 0),
            "scores": scores,
            "created": created}


def list_reports() -> list[dict]:
    if not LIB.exists():
        return []
    out = []
    for p in sorted(LIB.glob("*.pack.json"), reverse=True):
        try:
            rid = p.name.removesuffix(".pack.json")
            pack = json.loads(p.read_text(encoding="utf-8"))
            from .writer import build_report
            out.append(entry(rid, pack, build_report(pack)))
        except Exception:
            continue
    return out


def load_report(rid: str) -> tuple[dict, str]:
    # Validate rid to prevent path traversal.
    if not rid or "/" in rid or "\\" in rid or ".." in rid:
        raise FileNotFoundError(f"invalid report id: {rid}")
    pack = json.loads((LIB / f"{rid}.pack.json").read_text(encoding="utf-8"))
    return pack, (LIB / f"{rid}.md").read_text(encoding="utf-8")


def delete_report(rid: str) -> bool:
    if not rid or "/" in rid or "\\" in rid or ".." in rid:
        return False
    a = LIB / f"{rid}.pack.json"
    b = LIB / f"{rid}.md"
    existed = a.exists() or b.exists()
    a.unlink(missing_ok=True)
    b.unlink(missing_ok=True)
    return existed
