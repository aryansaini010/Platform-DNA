"""FastAPI backend for Vite React frontend (127.0.0.1:8001).

Wraps the existing deterministic pipeline:
research -> draft -> Ollama enhance -> build_report -> validate -> library.
Pure Ollama-only backend: no cloud LLM fallback. Ollama down = loud 500.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))


def _load_dotenv() -> None:
    """Minimal .env loader (no extra dependency). Backend-only keys."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip("\"'")
        if k and k not in os.environ:
            os.environ[k] = v


_load_dotenv()

from platform_dna import research  # noqa: E402
from platform_dna.autodraft import (  # noqa: E402
    default_queries,
    draft_pack,
    heuristic_scores,
    mine_wikipedia_titles,
    research_platform,
)
from platform_dna.library import delete_report, list_reports, load_report, save_report  # noqa: E402
from platform_dna.llm import (  # noqa: E402
    active_provider,
    has_any_key,
    has_ollama,
    is_ollama_unreachable,
    ollama_reachable,
    split_example,
)
from platform_dna.pdf import markdown_to_pdf_bytes  # noqa: E402
from platform_dna.renderer import render  # noqa: E402
from platform_dna.scores import overall as overall_score  # noqa: E402
from platform_dna.titles import compute_stats  # noqa: E402
from platform_dna.validator import validate  # noqa: E402
from platform_dna.writer import build_report  # noqa: E402

research.SEARX = os.environ.get("SEARXNG_URL", "http://localhost:8081")
research.FIRE = os.environ.get("FIRECRAWL_URL", "http://localhost:3002")

CATALOG_DIR = ROOT / "data" / "catalog"

app = FastAPI(title="Platform DNA API", version="1.0.0")
_allowed_origins = [o.strip() for o in os.environ.get(
    "CORS_ORIGINS",
    "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:3001,http://localhost:3001,http://127.0.0.1:4173,http://localhost:4173").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


class GenerateRequest(BaseModel):
    platform: str
    region: str = "India"
    # Legacy client flags, IGNORED (hard-coded policy: deep + Ollama
    # + cache-first platform+region, never expires). Kept for compat.
    depth: str = "deep"
    force: bool = False
    enhance: bool = True
    scores: dict | None = None
    # - polish_facts: run per-fact copy-edit calls (default off; ~12 calls).
    # - pack + retry: skip research, re-enhance only listed kinds from a
    #   previous attempt ("content", "audience", ..., "voice", "deal").
    polish_facts: bool = False
    pack: dict | None = None
    retry: list[str] | None = None


def _catalog(name: str):
    p = CATALOG_DIR / name
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return []


@app.get("/api/health")
def health():
    has_oll = has_ollama()
    return {"ok": True, "provider": active_provider(),
            "ollama": has_oll, "any_key": has_oll,
            "has_ollama": has_oll, "has_any": has_oll,
            "searx": research.SEARX, "fire": research.FIRE,
            "time": int(time.time())}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _platform_entry(name: str) -> dict | None:
    """Catalog entry matching platform name or alias (exact or normalized)."""
    nl = (name or "").strip().lower()
    nn = _norm(name)
    if not nl:
        return None
    for p in _catalog("platforms.json"):
        names = [p.get("name", "")] + list(p.get("aliases", []))
        for n in names:
            if not n:
                continue
            if n.lower() == nl or _norm(n) == nn:
                return p
    return None


def _region_name(code_or_name: str) -> str:
    """Map 'IT'/'Italy (IT)'/'Italy' -> 'Italy' for report display.

    Research scoping keeps working on codes; only the stored/displayed
    region becomes a full name (template renders it verbatim).
    """
    s = (code_or_name or "").strip()
    if not s:
        return "India"
    for r in _catalog("regions.json"):
        if s.upper() == r.get("code", "").upper() or s == r.get("label") \
                or s.lower() == r.get("name", "").lower():
            return r["name"]
    m = re.match(r"^(.*)\(([^)]+)\)\s*$", s)
    if m and m.group(1).strip():
        return m.group(1).strip()
    return s


@app.get("/api/platforms")
def platforms(region: str | None = Query(default=None)):
    # Query() default is a params object, not None, on direct python calls
    # (HTTP calls resolve correctly via FastAPI DI) — normalize defensively.
    if region is not None and not isinstance(region, str):
        region = None
    items = _catalog("platforms.json")
    if not items:  # fallback to legacy config
        try:
            cfg = json.loads((ROOT / "config" / "platforms.json").read_text(encoding="utf-8"))
            items = [{"name": k, "slug": v.get("slug", k), "group": "India",
                      "aliases": v.get("aliases", []), "regions": ["IN"],
                      "regions_count": 1} for k, v in cfg.items()]
        except Exception:
            items = []
    if region:
        # Region-first lookup: ?region=AU | Australia | Australia (AU).
        # Matches code, name, or label (case-insensitive); unknown region
        # returns [] with the echo so the UI can show a gap message.
        want = (region or "").strip()
        code = None
        for r in _catalog("regions.json"):
            if want.upper() == str(r.get("code", "")).upper() \
                    or want.lower() == str(r.get("name", "")).lower() \
                    or want == r.get("label"):
                code = str(r.get("code", "")).upper()
                break
        if code is None:
            m = re.match(r"^(.*)\(([^)]+)\)\s*$", want)
            if m:
                code = m.group(2).strip().upper()
        if code is None:
            code = want.upper()
        items = [p for p in items
                 if code in [str(c).upper() for c in (p.get("regions") or [])]]
        return {"platforms": items, "count": len(items), "region": code}
    return {"platforms": items, "count": len(items)}


@app.get("/api/regions/{code}/platforms")
def region_platforms(code: str):
    # Alias route for region-first browsing: /api/regions/AU/platforms.
    return platforms(region=code)


@app.get("/api/regions")
def regions():
    items = _catalog("regions.json")
    return {"regions": items, "count": len(items)}


@app.get("/api/library")
def library():
    try:
        reports = list_reports()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"library rebuild failed: {str(e)[:300]}")
    return {"reports": reports, "count": len(reports)}


@app.get("/api/report/{rid}")
def get_report(rid: str):
    try:
        pack, _md = load_report(rid)
    except Exception:
        raise HTTPException(404, "report not found")
    # Rebuild live so sources/citations always match the stored pack even
    # after writer upgrades (stored .md may carry an older numbering).
    from platform_dna.renderer import render as _render
    from platform_dna.library import _read_meta as _rm
    report = build_report(pack)
    _meta = _rm(rid)
    return {"pack": pack, "report": report, "markdown": _render(report),
            "status": _meta.get("status", "valid"),
            "errors": _meta.get("errors", []),
            "reverted": _meta.get("reverted", [])}


@app.delete("/api/report/{rid}")
def del_report(rid: str):
    ok = delete_report(rid)
    if not ok:
        raise HTTPException(404, "report not found")
    return {"ok": True, "id": rid}


@app.get("/api/report/{rid}/json")
def get_pack_json(rid: str):
    try:
        pack, _ = load_report(rid)
    except Exception:  # noqa: BLE001
        raise HTTPException(404, "report not found")
    return JSONResponse(pack)


@app.get("/api/report/{rid}/markdown")
def get_markdown(rid: str):
    try:
        pack, _ = load_report(rid)
    except Exception:  # noqa: BLE001
        raise HTTPException(404, "report not found")
    from platform_dna.renderer import render as _render
    return PlainTextResponse(_render(build_report(pack)), media_type="text/markdown")


@app.get("/api/report/{rid}/pdf")
def get_pdf(rid: str):
    try:
        pack, _ = load_report(rid)
    except Exception:  # noqa: BLE001
        raise HTTPException(404, "report not found")
    from platform_dna.renderer import render as _render
    md = _render(build_report(pack))
    pdf = markdown_to_pdf_bytes(f"Platform DNA Report — {pack.get('platform', '')}", md)
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", rid)[:80]
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename={safe}.pdf"})


@app.post("/api/generate")
def generate(req: GenerateRequest):
    platform = (req.platform or "").strip()
    if not platform:
        raise HTTPException(400, "platform is required")
    region = (req.region or "India").strip() or "India"
    region = _region_name(region)
    # Invariant: a cataloged platform ALWAYS resolves to a region it serves.
    # A stale/invalid region snaps to the platform's first region (recorded
    # in stats); unknown platform names pass through untouched.
    region_snap: dict | None = None
    _pent = _platform_entry(platform)
    if _pent and _pent.get("regions"):
        _cat = _catalog("regions.json")
        _by_code = {str(r.get("code", "")).upper(): r for r in _cat if r.get("code")}
        _by_name = {str(r.get("name", "")).lower(): r for r in _cat if r.get("name")}
        _sent = region.strip()
        _code = (_sent.upper() if _sent.upper() in _by_code else None)
        if _code is None:
            _m = re.match(r"^(.*)\(([^)]+)\)\s*$", _sent)
            if _m and _m.group(2).strip().upper() in _by_code:
                _code = _m.group(2).strip().upper()
            elif _sent.lower() in _by_name:
                _code = _by_name[_sent.lower()].get("code", "").upper() or None
        _allowed = [str(c).upper() for c in _pent["regions"] if c]
        if _code not in _allowed:
            # Prefer India when served, else the platform's first region.
            _pick = _allowed[0]
            if "IN" in _allowed:
                _pick = "IN"
            _first = _by_code.get(_pick, {})
            _to = _first.get("name") or _pick
            region_snap = {"from": region, "to": _to}
            region = _to
    # LLM policy: Ollama-only (LLM_PROVIDER auto/ollama). force=true bypasses
    # the library cache for a fresh run.
    depth = "deep"

    # Cache-first (unless force): reuse a saved report matching platform AND
    # region. force=true skips the cache for a fresh re-research.
    if not req.force:
        for r in list_reports():
            if r["platform"].lower() == platform.lower() \
                    and (r.get("region", "") or "").lower() == region.lower():
                try:
                    pack, _md = load_report(r["id"])
                    report = build_report(pack)
                    from platform_dna.renderer import render as _render
                    stats0: dict = {"reused_library": r["id"]}
                    if region_snap:
                        stats0["region_snap"] = region_snap
                    return {"reused": r["id"], "pack": pack, "report": report,
                            "markdown": _render(report), "errors": [],
                            "entry": r,
                            "overall": (report.get("overall", {}) or {}).get("score"),
                            "stats": stats0}
                except Exception:
                    continue

    # Ollama-only gate: refuse loudly before burning research time.
    # OLLAMA_URL alone satisfies the gate (no key needed). Ollama down =
    # loud 500, never a silent deterministic report.
    if not has_any_key():
        raise HTTPException(
            500, "Ollama is mandatory but not configured. "
                 "Set OLLAMA_URL (e.g. via SSH tunnel to the GPU server) "
                 "in .env and restart the API.")
    if not ollama_reachable():
        raise HTTPException(
            500, "Ollama is unreachable (SSH tunnel down or server stopped). "
                 "Restart the tunnel/server, then retry — nothing was researched or saved.")

    t0 = time.time()
    # Retry path: re-enhance only listed kinds from a previous attempt's
    # pack — no research, no redraft (token-saving; fits the 3-4 min window).
    _valid_kinds = {"content", "audience", "emotional", "distribution",
                    "revenue", "editorial", "voice", "deal"}
    retry_kinds = set(req.retry or [])
    _bad = sorted(k for k in retry_kinds if k not in _valid_kinds)
    if _bad:
        raise HTTPException(400, f"unknown retry kinds: {_bad}; valid: {sorted(_valid_kinds)}")
    if req.pack and retry_kinds:
        facts = req.pack.get("facts", []) or []
        titles = req.pack.get("titles", []) or []
        scores = {}
        for k in ("content", "audience", "emotional",
                  "distribution", "revenue", "editorial"):
            try:
                scores[k] = max(0, min(100, int(float(req.pack.get("sections", {}).get(k, {}).get("score", 65)))))
            except Exception:
                scores[k] = 65
        pack = dict(req.pack)
        pack["platform"] = platform
        pack["region"] = region
        stats: dict = {"retry": sorted(retry_kinds)}
        if region_snap:
            stats["region_snap"] = region_snap
        wikisrc = ""
    else:
        _r0 = time.time()
        queries = default_queries(platform, region)
        # Per-region SearXNG locale (CA->en-CA etc.; non-English markets
        # keep en-IN so the English-regex extractor keeps working).
        language = research.locale_for_region(region)
        # Wiki mining overlaps main research (independent I/O) to save wall time.
        from concurrent.futures import ThreadPoolExecutor as _RPool
        with _RPool(max_workers=2) as _rp:
            _fr = _rp.submit(research_platform, platform, queries,
                             top_n=3, pages=1, depth=depth, progress=None,
                             language=language, scrape_deadline_s=60)
            _fw = _rp.submit(mine_wikipedia_titles, platform)
            facts, stats = _fr.result()
            titles, wikisrc = _fw.result()
        stats["research_s"] = round(time.time() - _r0, 1)
        stats["searx_lang"] = language
        stats.setdefault("polish_skipped", False)
        if req.polish_facts and has_any_key():
            # Opt-in only (~12 extra calls): polish fact claims BEFORE
            # drafting so standouts/grounding derive from polished text.
            try:
                from platform_dna.llm import polish_fact_claims as _polish
                facts = _polish(facts, limit=12)
            except Exception as e:  # noqa: BLE001
                stats["polish_error"] = str(e)[:200]
        scores = dict(req.scores) if req.scores else heuristic_scores(facts)
        # clamp scores
        for k in list(scores.keys()):
            try:
                scores[k] = max(0, min(100, int(float(scores[k]))))
            except Exception:
                scores[k] = 65
        catalogue_note = (f"{len(facts)} extracted facts and {len(titles)} named titles "
                          "from trade, investor and platform sources")
        pack = draft_pack(platform, facts, titles, scores, catalogue_note, region=region)

    enhanced_sections: list[str] = []
    enhanced_top: list[str] = []
    enhance_errors: list[str] = []
    if stats.get("polish_error"):
        enhance_errors.append(f"polish_facts: {stats.pop('polish_error')}")
        stats.pop("polish_skipped", None)

    def _try(label: str, fn, *args):
        """Ollama call + one retry; record failures.

        Ollama-unreachable errors (dead tunnel) skip the outer retry: the
        per-process cooldown guarantees an instant second failure.
        Per-call wall time is recorded in _timings for speed diagnosis.
        """
        _t0 = time.time()
        try:
            return fn(*args)
        except Exception as e1:  # noqa: BLE001
            if is_ollama_unreachable(e1):
                with _err_lock:
                    enhance_errors.append(f"{label}: {str(e1)[:400]} (no retry: ollama unreachable)")
                return None
            time.sleep(10 + _rnd.uniform(0, 2))
            try:
                return fn(*args)
            except Exception as e2:  # noqa: BLE001
                with _err_lock:
                    enhance_errors.append(f"{label}: {str(e2)[:400]}")
                return None
        finally:
            try:
                with _tim_lock:
                    _timings[label] = round(time.time() - _t0, 1)
            except Exception:
                pass

    def _wanted(kind: str) -> bool:
        return not retry_kinds or kind in retry_kinds

    # Ollama-only enhance: 6 sections + voice + deal, 2-wide pool with
    # draft-snapshot inputs (disjoint keys, identical to serial). No pacing,
    # no TPM bucket. Deadline 600s for local inference.
    import random as _rnd
    import threading as _th
    _provider = active_provider()
    ENHANCE_DEADLINE_S = float(os.environ.get("ENHANCE_DEADLINE_S", "600"))
    _enh_start = time.time()
    _err_lock = _th.Lock()
    _tim_lock = _th.Lock()
    _timings: dict = {}

    def _over_deadline() -> bool:
        return (time.time() - _enh_start) > ENHANCE_DEADLINE_S

    # Gate above already 500s when unreachable; this per-generate ping only
    # records timing context (a tunnel that died mid-generate surfaces per
    # call via is_ollama_unreachable fast-skip).

    try:
        from platform_dna.config import SECTION_SLOTS as _SSLOTS
        from platform_dna.llm import enhance_deal as _deal
        from platform_dna.llm import enhance_section as _enh
        from platform_dna.llm import enhance_voice as _voice
        ex = split_example()
        tstats = compute_stats(titles)
        tstats["facts"] = len(facts)

        _SECS = ("content", "audience", "emotional",
                 "distribution", "revenue", "editorial")

        def _enhance_one(sec: str):
            if not _wanted(sec):
                return sec, None, None
            if _over_deadline():
                return sec, None, "deadline"
            sec_facts = [f for f in facts if f["slot"] in _SSLOTS[sec]]
            fields = {"score": scores.get(sec, 65)}
            if sec == "content":
                try:
                    fields["standout_titles"] = pack["sections"][sec].get("standout_titles", [])
                except Exception:
                    fields["standout_titles"] = []
            new = _try(sec, _enh, platform, region, sec, fields,
                       sec_facts or facts[:10], tstats, ex.get(sec, ""))
            # A long LLM call started just before the deadline may finish
            # after it with new=None: flag it so the deadline note appears.
            if new is None and _over_deadline():
                return sec, None, "deadline"
            return sec, new, None

        def _voice_one():
            # Snapshot draft inputs BEFORE the pool starts so the prompt is
            # bit-identical whether run serially or overlapped with sections.
            # Voice reads only facts + draft top fields (never enhanced
            # section prose), so overlapping is quality-neutral.
            if not _wanted("voice"):
                return "voice", None, None
            if _over_deadline():
                return "voice", None, "deadline"
            v = _try("voice", _voice, platform, region, facts,
                     _voice_snap[0], _voice_snap[1], _voice_snap[2])
            if v is None and _over_deadline():
                return "voice", None, "deadline"
            return "voice", v, None

        def _deal_one():
            # Same snapshot guarantee as voice: facts + draft wishlist/pitch.
            if not _wanted("deal"):
                return "deal", None, None
            if _over_deadline():
                return "deal", None, "deadline"
            w = _try("deal", _deal, platform, region, facts,
                     _deal_snap[0], _deal_snap[1])
            if w is None and _over_deadline():
                return "deal", None, "deadline"
            return "deal", w, None

        # Snapshot draft top fields once: guarantees parallel prompts equal
        # serial prompts even if section merges ran first.
        try:
            _voice_snap = (pack.get("identity_line", ""), pack.get("summary", ""),
                           pack.get("positioning", ""))
        except Exception:
            _voice_snap = ("", "", "")
        try:
            _deal_snap = (pack.get("wishlist", []), pack.get("pitch", {}))
        except Exception:
            _deal_snap = ([], {})

        # Ollama 2-wide pool for all 8 jobs (6 sections + voice + deal):
        # voice/deal inputs are draft snapshots with disjoint keys, so merging
        # serially after join is identical to a serial tail while saving ~55s.
        try:
            _workers = max(1, min(2, int(os.environ.get("OLLAMA_CONCURRENCY", "2"))))
        except Exception:
            _workers = 2
        _deadline_hit = False
        if True:
            from concurrent.futures import ThreadPoolExecutor as _EPool
            _jobs = [(sec, _enhance_one, (sec,)) for sec in _SECS]
            _jobs += [("voice", _voice_one, ()), ("deal", _deal_one, ())]
            # Only submit wanted kinds that are not already past deadline;
            # _wanted/_over_deadline re-checked inside each worker for safety.
            with _EPool(max_workers=_workers) as _ep:
                _futs = [(kind, _ep.submit(fn, *args)) for kind, fn, args in _jobs]
                _results: dict = {}
                for kind, _fu in _futs:
                    try:
                        _results[kind] = _fu.result()
                    except Exception as e:  # noqa: BLE001
                        _results[kind] = (kind, None, None)
                        with _err_lock:
                            enhance_errors.append(f"{kind} pool: {str(e)[:200]}")
            # Merge serially in FIXED order so output is deterministic
            # regardless of thread completion order.
            for sec in _SECS:
                _r = _results.get(sec, (sec, None, None))
                _sec, new, note = _r[0], _r[1], _r[2] if len(_r) == 3 else None
                if note == "deadline":
                    _deadline_hit = True
                    continue
                if new:
                    try:
                        pack["sections"][sec].update(new)
                    except Exception:
                        pass
                    enhanced_sections.append(sec)
            _v = _results.get("voice", ("voice", None, None))
            if _v[2] == "deadline":
                _deadline_hit = True
            elif isinstance(_v[1], dict) and all((_v[1].get(k, "") or "").strip()
                                                 for k in ("identity_line", "summary", "positioning")):
                pack.update(_v[1])
                enhanced_top.append("voice")
            _w = _results.get("deal", ("deal", None, None))
            if _w[2] == "deadline":
                _deadline_hit = True
            elif isinstance(_w[1], dict):
                try:
                    from platform_dna.autodraft import _bold_lead as _bl
                    _w[1]["wishlist"] = [_bl(str(x)) for x in _w[1]["wishlist"]]
                except Exception:
                    pass
                try:
                    pack["wishlist"] = _w[1]["wishlist"]
                    pack["pitch"] = _w[1]["pitch"]
                    enhanced_top.append("deal")
                except Exception:
                    pass
        if _deadline_hit:
            with _err_lock:
                enhance_errors.append("enhance deadline: remaining sections kept deterministic")
        if _over_deadline():
            with _err_lock:
                enhance_errors.append("enhance deadline reached: kept deterministic text for remainder")
    except Exception as e:  # noqa: BLE001
        enhance_errors.append(f"enhance setup: {str(e)[:400]}")

    # Repair pass: demote LLM-invented 'N of M ≈N%' shares the strict
    # validator can never ground (genre/sample shares) to plain fractions.
    # validate() below still re-checks everything.
    try:
        from platform_dna.validator import repair_share_figures as _repair
        from platform_dna.validator import revert_fields as _revert
        for _note in _repair(pack, facts, titles):
            enhance_errors.append(f"share repair: {_note}")
    except Exception as e:  # noqa: BLE001
        _revert = None  # type: ignore[assignment]
        enhance_errors.append(f"share repair setup: {str(e)[:200]}")

    # Deterministic reference (never polished) for field-level auto-revert.
    try:
        from platform_dna.autodraft import draft_pack as _draft
        _det = _draft(platform, facts, titles, scores,
                      pack.get("catalogue_note", ""), region=region)
    except Exception as e:  # noqa: BLE001
        _det = None
        enhance_errors.append(f"deterministic redraft setup: {str(e)[:200]}")

    # Validate → revert failing prose fields → re-validate (max 3 passes).
    # Reverted fields keep deterministic validator-safe text and are
    # disclosed in stats; counts/structure errors still fail loudly (now
    # as saved drafts, never silent discards).
    reverted_all: list[str] = []
    report: dict = {}
    errors: list[str] = ["not validated"]
    for _pass in range(3):
        report = build_report(pack)
        errors = validate(report, pack.get("facts", []), pack.get("titles", []))
        if not errors or _det is None or _revert is None:
            break
        rev = _revert(pack, _det, errors)
        if not rev:
            break
        reverted_all = sorted(set(reverted_all) | set(rev))
    if reverted_all:
        enhance_errors.append("auto-revert to deterministic text: " + ", ".join(reverted_all))
    if region_snap:
        stats["region_snap"] = region_snap
    _elapsed = round(time.time() - t0, 1)
    try:
        _research_s = float(stats.get("research_s", 0) or 0)
    except Exception:
        _research_s = 0.0
    base_stats = {**stats, "elapsed_s": _elapsed,
                  "research_s": _research_s,
                  "enhance_s": round(max(0.0, _elapsed - _research_s), 1),
                  "enhanced": enhanced_sections,
                  "enhanced_top": enhanced_top,
                  "enhance_errors": enhance_errors,
                  "enhance_timings": dict(_timings),
                  "enhance_workers": _workers,
                  "reverted_fields": reverted_all,
                  "provider": active_provider()}
    # Save-everything: valid reports AND failed drafts persist. Drafts carry
    # status + errors in a sidecar so the UI can badge, list and retry them.
    # entry is never None anymore. (Step 2 threads reverted-fields here.)
    try:
        md = render(report)
    except Exception as e:  # noqa: BLE001
        # Structural draft that even the renderer rejects: persist the pack
        # with raw markdown fallback so nothing is silently discarded.
        md = f"# PLATFORM DNA REPORT\n\nRender failed: {str(e)[:500]}"
        enhance_errors.append(f"render fallback: {str(e)[:200]}")
        errors = (errors or []) + [f"render failed: {str(e)[:200]}"]
    ent = save_report(pack, report, md,
                      status="valid" if not errors else "draft",
                      errors=errors,
                      reverted=reverted_all or None)
    if errors:
        return {"pack": pack, "report": report, "markdown": md,
                "errors": errors, "entry": ent, "overall": (report.get("overall", {}) or {}).get("score"),
                "stats": base_stats}
    return {"pack": pack, "report": report, "markdown": md, "errors": [],
            "entry": ent, "overall": (report.get("overall", {}) or {}).get("score"),
            "stats": {**base_stats, "wikisrc": wikisrc}}


@app.get("/api/provider")
def provider():
    ollama_model = os.environ.get("OLLAMA_MODEL", "gpt-oss:20b")
    ollama_url = os.environ.get("OLLAMA_URL", "")
    has_oll = has_ollama()
    return {"provider": active_provider(),
            "ollama_model": ollama_model,
            "ollama": has_oll, "has_ollama": has_oll,
            "ollama_configured": bool(ollama_url),
            "any_key": has_oll, "has_any": has_oll,
            "hint": ("Ollama polish ready." if has_oll
                      else "Set OLLAMA_URL (SSH tunnel to GPU server) in .env then restart api.")}
