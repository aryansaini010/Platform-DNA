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


def save_report(pack: dict, report: dict, markdown: str,
                status: str = "valid", errors: list | None = None,
                reverted: list | None = None) -> dict:
    """Persist every generate — valid reports and failed drafts alike.

    status: "valid" (passed validation) or "draft" (saved with errors).
    Drafts never vanish silently: the sidecar .meta.json carries status,
    errors and reverted-fields so the UI can badge, list and offer retry.
    Valid reports are kept forever; drafts are pruned beyond the newest 3
    per platform+region so failed loops can't fill the disk.
    """
    import random
    import threading
    LIB.mkdir(parents=True, exist_ok=True)
    # Millisecond + pid + thread + random suffix: concurrent same-millisecond
    # generates (threads share pid) never collide via os.replace.
    _rand = f"{random.randint(0, 999999):06d}"
    _thr = f"{threading.get_ident() & 0xFFFFFF:06x}"
    rid = f"{_slug(pack)}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]}_{os.getpid()}_{_thr}_{_rand}"
    # Write meta FIRST so a crash between files never leaves a pack without
    # its status sidecar (which entry() would mislabel as valid).
    _atomic_write(LIB / f"{rid}.meta.json",
                  json.dumps({"status": status, "errors": errors or [],
                              "reverted": reverted or [],
                              "platform": pack.get("platform", "?"),
                              "region": pack.get("region", "?")},
                             indent=1, ensure_ascii=False))
    _atomic_write(LIB / f"{rid}.pack.json",
                  json.dumps(pack, indent=1, ensure_ascii=False))
    _atomic_write(LIB / f"{rid}.md", markdown)
    if status != "valid":
        _prune_drafts(pack.get("platform", ""), pack.get("region", ""), keep=3)
    return entry(rid, pack, report)


def _read_meta(rid: str) -> dict:
    try:
        return json.loads((LIB / f"{rid}.meta.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _prune_drafts(platform: str, region: str, keep: int = 3) -> None:
    """Keep the newest `keep` drafts per platform+region; valid reports are
    never pruned here. Newest-first by file mtime (rid embeds timestamp but
    starts with slug, so filename sort is not chronological)."""
    try:
        cands = []
        for m in LIB.glob("*.meta.json"):
            try:
                meta = json.loads(m.read_text(encoding="utf-8"))
            except Exception:
                continue
            if meta.get("status") == "draft" \
                    and (meta.get("platform") or "") == (platform or "") \
                    and (meta.get("region") or "") == (region or ""):
                cands.append(m)
        # Oldest first by mtime so slicing drops the oldest.
        ordered = sorted(cands, key=lambda p: p.stat().st_mtime)
        keep_n = max(0, keep)
        for m in ordered[:max(0, len(ordered) - keep_n)]:
            stem = m.name.removesuffix(".meta.json")
            (LIB / f"{stem}.pack.json").unlink(missing_ok=True)
            (LIB / f"{stem}.md").unlink(missing_ok=True)
            m.unlink(missing_ok=True)
    except Exception:
        pass


def entry(rid: str, pack: dict, report: dict) -> dict:
    scores = {k: v.get("score") for k, v in (report.get("sections", {}) or {}).items()}
    # rid format: <slug>_YYYYMMDD_HHMMSS[_mmm_pid] — the slug itself may
    # contain underscores, so extract the date/time via regex, not rsplit.
    import re as _re
    _m = _re.search(r"(\d{8})_(\d{6})", rid)
    created = f"{_m.group(1)} {_m.group(2)}" if _m else rid
    meta = _read_meta(rid)
    return {"id": rid, "platform": pack.get("platform", "?"),
            "region": pack.get("region", "?"),
            "overall": report.get("overall", {}).get("score"),
            "titles": report.get("titles_analysed", 0),
            "scores": scores,
            "created": created,
            # Legacy files predate .meta.json sidecars: they were only ever
            # written for validated reports, so default to "valid".
            "status": meta.get("status", "valid"),
            "errors": meta.get("errors", []),
            "reverted": meta.get("reverted", [])}


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
    c = LIB / f"{rid}.meta.json"
    existed = a.exists() or b.exists() or c.exists()
    a.unlink(missing_ok=True)
    b.unlink(missing_ok=True)
    c.unlink(missing_ok=True)
    return existed
