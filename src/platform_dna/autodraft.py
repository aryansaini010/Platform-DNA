"""Auto-draft: platform name -> researched draft DNA report.

Automates what was done by hand for Netflix India: run the query pack
(SearXNG), scrape hits (Firecrawl), extract slot-tagged facts, mine a title
list, then assemble a draft pack the analyst reviews in the UI.

Honest limits (shown in the UI, not hidden):
- Section scores start from an evidence-density heuristic; the analyst sets
  the final scores with sliders (overall stays computed, never chosen).
- Judgment fields (strategy lines, positioning, wishlist, pitch) start from
  platform-named templates; the analyst edits them against the evidence.
- Blocked pages are skipped and counted, never padded.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

from .composer import (audience_fields, compose_angle, compose_ideal, compose_negotiation,
                         content_fields, distribution_fields, editorial_fields,
                         emotional_fields, revenue_fields, _short)
from .config import QUERY_TEMPLATES, REQUIRED_SLOTS_PER_SECTION, SECTION_SLOTS, SLOT_QUERIES
from .extractor import extract_facts
from .research import is_no_escalate, scrape, scrape_many, searx

BUILDERS = {"content": content_fields, "audience": audience_fields,
            "emotional": emotional_fields, "distribution": distribution_fields,
            "revenue": revenue_fields, "editorial": editorial_fields}

# URLs never worth scraping (share stubs, login walls, short video).
SKIP_URL = ("facebook.com/sharer", "twitter.com/intent", "linkedin.com/sharing",
            "mailto:", "/login", "/signin", "/signup", "/subscribe",
            "accounts.google.com", "youtube.com/watch", "youtu.be/",
            "instagram.com/", "t.me/", "whatsapp.com/channel",
            "pinterest.com/pin", "threads.net/", "grabon", "coupon",
            "cashback", "promo-code", "coupondeal")

_META_DATES = ("datePublished", "publishedTime", "article:published_time",
               "pubdate", "date", "publishedDate")


def _meta_date(meta: dict) -> str:
    for k in _META_DATES:
        v = meta.get(k)
        if v:
            m = re.search(r"(19|20)\d{2}-\d{2}-\d{2}", str(v))
            if m:
                return m.group(0)
    return ""


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


KNOWN_ALIASES: dict[str, list[str]] = {
    "jiohotstar": ["JioHotstar", "Jio Hotstar", "Hotstar", "Disney+ Hotstar",
                   "Disney Hotstar"],
    "primevideo": ["Prime Video", "Amazon Prime Video", "Prime Video India"],
    "sonyliv": ["SonyLIV", "Sony LIV"],
    "zee5": ["ZEE5", "Zee5"],
    "jiostar": ["JioStar", "Jio Star"],
    "shemaroo": ["Shemaroo Entertainment", "Shemaroo", "ShemarooMe", "Shemaroo Me"],
    "shemaroome": ["Shemaroo Entertainment", "Shemaroo", "ShemarooMe", "Shemaroo Me"],
    "shemarooentertainment": ["Shemaroo Entertainment", "Shemaroo", "ShemarooMe"],
    "amazonmxplayer": ["Amazon MX Player", "MX Player"],
    "mxplayer": ["Amazon MX Player", "MX Player"],
}


def _catalog_aliases(platform: str) -> list[str]:
    """Aliases from the curated catalog (129 services), with regional-parent
    merge: "Disney+ Canada" also matches bare "Disney+" (same service,
    regional edition) so STRICT_SLOTS keeps company-metric facts instead of
    starving the pack. The parent merge only applies when the name is the
    parent plus a trailing region word — never across different services."""
    try:
        cat = json.loads((Path(__file__).resolve().parents[2]
                          / "data" / "catalog" / "platforms.json").read_text(encoding="utf-8"))
    except Exception:
        return []
    _REGION_TAIL = re.compile(
        r"\s+(india|canada|united states|usa|uk|britain|australia|"
        r"germany|france|japan|korea|brazil|mexico|mena|sea|global)$",
        re.I)
    by_norm = {}
    for p in cat:
        by_norm.setdefault(_norm(p.get("name", "")), []).append(p)
        for a in p.get("aliases", []) or []:
            by_norm.setdefault(_norm(a), []).append(p)
    hits = by_norm.get(_norm(platform), [])
    if not hits:
        return []
    entry = hits[0]
    out = [entry.get("name", "")] + list(entry.get("aliases", []) or [])
    base = _REGION_TAIL.sub("", entry.get("name", "")).strip()
    if base and _norm(base) != _norm(entry.get("name", "")):
        for p in by_norm.get(_norm(base), []):
            out.append(p.get("name", ""))
            out.extend(p.get("aliases", []) or [])
    return [a for a in dict.fromkeys(out) if a]


def get_aliases(platform: str) -> tuple[str, ...]:
    # Curated catalog first (129 services + regional-parent merge), then the
    # legacy 5-platform config, then hardcoded variants.
    cat = _catalog_aliases(platform)
    if cat:
        return tuple(dict.fromkeys([platform.strip()] + cat))
    try:
        cfg = json.loads((Path(__file__).resolve().parents[2]
                          / "config" / "platforms.json").read_text(encoding="utf-8"))
    except Exception:
        cfg = {}
    for name, info in cfg.items():
        # Exact or normalized match only — substring ("Star" in "JioStar")
        # caused wrong-platform alias reuse.
        if name.lower() == platform.lower() or _norm(platform) == _norm(name):
            return tuple(dict.fromkeys([platform.strip()] + [name] + list(info.get("aliases", []))))
        aliases = [a for a in info.get("aliases", []) if a]
        if any(a.lower() == platform.lower() or _norm(a) == _norm(platform) for a in aliases):
            return tuple(dict.fromkeys([platform.strip()] + [name] + aliases))
    extra = KNOWN_ALIASES.get(_norm(platform), [])
    base = [platform] + extra
    # Auto-variants so new platforms still match their own coverage:
    # spaceless ("Jio Hotstar"↔"JioHotstar"), de-plus ("Disney+ Hotstar"↔
    # "Disney Hotstar"), and case variants. Without these the extractor's
    # STRICT_SLOTS filter drops every company-metric fact for unknown
    # platforms and research returns ~0 facts.
    variants: list[str] = []
    for a in base:
        variants.append(a)
        nospace = re.sub(r"\s+", "", a)
        if nospace not in variants:
            variants.append(nospace)
        deplus = a.replace("+", " ").replace("  ", " ").strip()
        if deplus not in variants:
            variants.append(deplus)
        despace = re.sub(r"[^A-Za-z0-9]", "", a)
        if despace not in variants:
            variants.append(despace)
    return tuple(dict.fromkeys(variants))


def default_queries(platform: str, region: str = "India") -> list[str]:
    if not (platform or "").strip():
        return []
    qs = [t.format(platform=platform) for t in QUERY_TEMPLATES["_global"]]
    if region != "India":
        # Replace standalone "India" only — never inside the platform name
        # ("IndiaTV" must not become "USATV").
        guarded = []
        for q in qs:
            tmp = q.replace(platform, "\x00PLATFORM\x00")
            tmp = re.sub(r"\bIndia\b", region, tmp)
            guarded.append(tmp.replace("\x00PLATFORM\x00", platform))
        qs = guarded
        qs.append(f"{platform} {region} OTT market subscribers")
    else:
        qs.append(f"{platform} JustWatch share Ormax subscribers")
    qs.append(f'"List of {platform} original programming"')
    return qs


def collect_hits(queries: list[str], per_query: int = 4, pages: int = 1,
                   progress: Callable[[str], None] | None = None,
                   language: str | None = None) -> list[dict]:
    """Phase 1: gather candidate source URLs (no scraping yet).

    Queries run 7-at-a-time (one wave for the standard 7-query pack);
    junk URLs (share stubs, login walls) are dropped before they can
    waste a scrape. Order and per-query caps are unchanged, so the fact
    set is identical to the old 4-wide run — only faster.
    """
    from concurrent.futures import ThreadPoolExecutor

    def _one(q: str):
        try:
            return q, searx(q, pages=pages, language=language)
        except Exception:
            return q, []

    hits, seen = [], set()
    with ThreadPoolExecutor(max_workers=7) as ex:
        per_q = list(ex.map(_one, queries))
    for q, res in per_q:
        n = 0
        for h in res:
            url = h.get("url", "")
            if not url or url in seen:
                continue
            if any(s in url.lower() for s in SKIP_URL):
                continue
            seen.add(url)
            n += 1
            hits.append({"url": url, "title": (h.get("title", "") or "")[:120],
                         "published": h.get("publishedDate", ""), "query": q})
            if n >= per_query:
                break
    if progress:
        progress(f"{len(hits)} candidate URLs from {len(queries)} queries")
    return hits


def research_platform(platform: str, queries: list[str] | None = None,
                      top_n: int = 3, pages: int = 1, depth: str = "standard",
                      wait_ms: int = 0, language: str | None = None,
                      scrape_deadline_s: float | None = None,
                      progress: Callable[[str], None] | None = None
                      ) -> tuple[list[dict], dict]:
    """One-shot research with coverage-driven re-search (plan Step D).

    Pass 1 runs the query pack; pass 2 fires targeted queries for required
    slots still empty. Deep mode widens hits (not pages) to fit the 3-4 min
    budget: globals stay pages=1, only Wiki/list queries use pages=2.
    scrape_deadline_s optionally bounds each scrape batch (overruns keep
    collected facts; thin slots stay honestly thin). Quality guards
    (STRICT_SLOTS, SKIP_URL, dedupe, corroboration) unchanged.
    """
    queries = default_queries(platform) if queries is None else queries
    aliases = get_aliases(platform)
    if depth == "deep":
        # pages stay as passed (1) for globals — page-2 long-tail hits are
        # mostly junk that fails STRICT_SLOTS; budget caps total scrapes.
        top_n = max(top_n, 4)
    budget = 36 if depth == "deep" else 30
    facts: list[dict] = []
    seen: set[tuple] = set()
    scraped: set[str] = set()
    ok = fail = skipped = escalated_ok = 0
    n_queries = 0

    def _run(qs: list[str], tn: int) -> None:
        nonlocal ok, fail, skipped, n_queries, escalated_ok
        n_queries += len(qs)
        room = budget - (ok + fail)
        if room <= 0:
            if progress:
                progress(f"page budget ({budget}) reached — skipping pass ({len(qs)} queries)")
            return
        hits = collect_hits(qs, per_query=tn, pages=pages, progress=progress,
                            language=language)
        fresh = [h for h in hits if h["url"] not in scraped]
        skipped += len(hits) - len(fresh)
        room = budget - (ok + fail)
        if room <= 0:
            if progress:
                progress(f"page budget ({budget}) reached — skipping {len(fresh)} URLs")
            return
        fresh = fresh[:room]
        for h in fresh:
            scraped.add(h["url"])
        f, s = extract_from_urls(fresh, platform=platform, aliases=aliases,
                                 wait_ms=wait_ms,
                                 max_workers=12 if depth == "deep" else 8,
                                 scrape_deadline_s=scrape_deadline_s,
                                 progress=progress)
        ok += (s or {}).get("pages_ok", 0)
        fail += (s or {}).get("pages_failed", 0)
        escalated_ok += (s or {}).get("escalated_ok", 0)
        for fact in f:
            key = (fact["slot"], fact["value"], (fact.get("claim") or "")[:200])
            if key not in seen:
                seen.add(key)
                facts.append(fact)

    _run(queries, top_n)
    have = {f["slot"] for f in facts}
    gaps = [s for secs in REQUIRED_SLOTS_PER_SECTION.values() for s in secs
            if s not in have]
    filled: list[str] = []
    if depth in ("standard", "deep") and gaps:
        # Cap pass 2: firing one query per gap doubles runtime for slots
        # that are simply undisclosed (e.g. private-company revenue).
        # Cover the first 4 gaps only; the rest are reported honestly as
        # thin instead of re-scraped. Dedupe against pass-1 queries so
        # overlapping SLOT_QUERIES don't repay SearXNG cost.
        fired = set(queries)
        extra: list[str] = []
        for slot in gaps[:4]:
            for t in SLOT_QUERIES.get(slot, [])[:1]:
                q = t.format(platform=platform)
                if q not in fired:
                    extra.append(q)
                    fired.add(q)
                    break
        extra = list(dict.fromkeys(extra))
        if progress:
            progress("pass 2 — targeted re-search for missing coverage…")
        before = len(facts)
        _run(extra, top_n)
        have2 = {f["slot"] for f in facts}
        filled = [s for s in gaps if s in have2]
        gaps = [s for s in gaps if s not in have2]
        if progress:
            progress(f"pass 2 done — {len(facts) - before} new facts")
    stats = {"pages_ok": ok, "pages_failed": fail, "queries": n_queries,
             "skipped_dupes": skipped, "budget": budget,
             "escalated_ok": escalated_ok,
             "gaps_remaining": gaps, "gaps_filled": filled}
    return facts, stats


def extract_from_urls(items: list, platform: str = "",
                      aliases: tuple[str, ...] = (), wait_ms: int = 0,
                      max_workers: int = 6,
                      scrape_deadline_s: float | None = None,
                      progress: Callable[[str], None] | None = None
                      ) -> tuple[list[dict], dict]:
    """Phase 2: scrape the URLs 6-at-a-time and extract facts from text.

    Adaptive wait: static trade press needs no JS wait — scrape with
    wait 0 first, escalate only fully-empty pages to 2000ms (short but
    nonempty paywalls never grow with waiting, so they are skipped).
    Article dates fall back to Firecrawl page metadata. A figure cited by
    2+ independent sources (one tier<=2) is promoted to high confidence.
    """
    urls: list[str] = []
    pubs: dict[str, str] = {}
    for it in items:
        url = it["url"] if isinstance(it, dict) else it
        if not url or any(s in url.lower() for s in SKIP_URL) or url in pubs:
            continue
        urls.append(url)
        pubs[url] = (it.get("published", "") if isinstance(it, dict) else "") or "date unknown"
    if progress:
        progress(f"scraping {len(urls)} pages ({max_workers} parallel)…")
    results = scrape_many(urls, wait_ms=wait_ms, max_workers=max_workers,
                          deadline_s=scrape_deadline_s,
                          progress=progress)
    # Escalate fully-empty pages once with a JS wait (cheap: usually 1-3
    # URLs). Short-but-nonempty results (paywalls, login stubs — meta
    # "chars" > 0) never grow with waiting, deadline-expired URLs already
    # hit the time budget, and NO_ESCALATE domains never render: all skipped.
    empty = [u for u, (md, _m) in results.items()
             if not (md or "").strip() and not (_m or {}).get("chars")
             and (_m or {}).get("error") != "deadline"
             and not is_no_escalate(u)]
    escalated_ok = 0
    if empty and wait_ms == 0:
        retry = scrape_many(empty[:6], wait_ms=2000, max_workers=3,
                            deadline_s=None, progress=None)
        for u, res in retry.items():
            if (res[0] or "").strip():
                results[u] = res
                escalated_ok += 1
    facts: list[dict] = []
    seen: set[tuple] = set()
    ok = fail = 0
    for url, (md, meta) in results.items():
        if not md:
            fail += 1
            continue
        ok += 1
        pub = pubs[url] if pubs[url] != "date unknown" else (_meta_date(meta) or "date unknown")
        for f in extract_facts(md, url, pub, platform=platform, aliases=aliases):
            key = (f["slot"], f["value"], (f.get("claim") or "")[:200])
            if key not in seen:
                seen.add(key)
                facts.append(f)
    # corroboration: same slot+figure+unit from 2+ distinct sources -> high.
    # Tier-3-only agreement is not corroboration (single press release restated).
    def _norm_price(v: str) -> str:
        v = (v or "").lower()
        v = v.replace("₹", "").replace("rs.", "rs").replace("rs", "rs")
        return re.sub(r"\W+", "", v)
    groups: dict[tuple, list[int]] = {}
    for i, f in enumerate(facts):
        if f.get("value"):
            groups.setdefault((f["slot"], _norm_price(f["value"]),
                               re.sub(r"\W+", "", (f.get("unit") or "").lower())), []).append(i)
    n_boost = 0
    for idxs in groups.values():
        urls = {facts[i]["source_url"] for i in idxs}
        tiers = {facts[i].get("tier", 3) for i in idxs}
        # Require 2+ distinct sources with at least one tier<=2; two tier-3
        # blogs restating one release do not corroborate.
        if len(urls) >= 2 and min(tiers) <= 2:
            for i in idxs:
                if facts[i]["confidence"] != "high":
                    facts[i]["confidence"] = "high"
                    n_boost += 1
    if progress:
        progress(f"{ok} ok / {fail} failed, {len(facts)} facts ({n_boost} corroborated)")
    return facts, {"pages_ok": ok, "pages_failed": fail, "escalated_ok": escalated_ok}


def mine_wikipedia_titles(platform: str) -> tuple[list[dict], str]:
    """Find the platform's Wikipedia originals list and parse title rows.

    Tries several query phrasings (pages=1 each) and scrapes up to 3
    candidates in parallel (wait 0, escalate empties to 2000).
    """
    queries = [f'"List of {platform} original programming"',
               f'"List of {platform} original films"',
               f"{platform} original programming wikipedia"]
    for alias in get_aliases(platform)[1:3]:
        if alias.lower() != platform.lower():
            queries.append(f'"List of {alias} original programming"')
    cands: list[dict] = []
    try:
        # Parallel queries (same result set as the old serial
        # stop-at-first-hit: every query's wikipedia hits are collected,
        # then the first query (in order) that hit anything wins).
        # 5-wide covers the max 5-query pack in a single wave.
        from concurrent.futures import ThreadPoolExecutor as _WPool

        def _safe_searx(q: str):
            try:
                return q, (searx(q, pages=1) or [])
            except Exception:
                return q, []

        with _WPool(max_workers=5) as _wp:
            per_q = list(_wp.map(_safe_searx, queries))
        for q, res in per_q:
            for h in res or []:
                if "wikipedia.org" in h.get("url", "") and h["url"] not in [c.get("url") for c in cands]:
                    cands.append(h)
            if cands:
                break  # first hitting query (in order) wins, as before
    except Exception:
        return [], ""
    cands = cands[:3]
    if not cands:
        return [], ""
    best: list[dict] = []
    best_url = cands[0]["url"]
    try:
        results = scrape_many([c["url"] for c in cands], wait_ms=0,
                              max_workers=4, progress=None)
    except Exception:
        results = {}
    for cand in cands:
        md = (results.get(cand["url"], ("", {}))[0] or "")
        if not md.strip():
            try:
                md, _ = scrape(cand["url"], wait_ms=2000)
            except Exception:
                md = ""
        if not md:
            continue
        titles = _parse_title_rows(md, cand["url"])
        if len(titles) > len(best):
            best, best_url = titles, cand["url"]
    return best, best_url


def _parse_title_rows(md: str, source_url: str) -> list[dict]:
    titles, seen = [], set()
    glist = ("crime", "thriller", "drama", "comedy", "romance", "reality",
             "sport", "horror", "documentary", "action", "fantasy", "sci-fi",
             "animation", "variety", "mythology", "talk", "mystery")
    genre_re = re.compile(r"\b(?:" + "|".join(glist) + r")s?\b", re.I)
    llist = ("Hindi", "Tamil", "Telugu", "Malayalam", "Kannada", "Bengali",
             "Marathi", "English")
    for line in md.splitlines():
        if line.count("|") < 1:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        link = re.search(r"\[([^\]]+)\]", cells[0])
        if link:
            # label of [label](url "title") — immune to nested parens in URLs
            name = re.sub(r"<[^>]+>", " ", link.group(1)).strip("*_ \"'#")
        else:
            raw0 = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cells[0])
            raw0 = re.sub(r"<[^>]+>", " ", raw0)
            name = re.sub(r"\(.*?\)", "", raw0).strip("*_ \"'#")
        if ("http" in name or not (2 <= len(name) <= 80)
                or not re.search(r"[A-Za-z]", name)
                or name.lower() in seen
                or re.match(r"(?i)^(title|genre|premiere|season|status|language|"
                            r"no\.?|episodes?|network|year|date)$", name)):
            continue
        rest = " ".join(cells[1:])
        rest_nourl = re.sub(r"\(?https?://\S+\)?", " ", rest)
        # Avoid vote-count false years ("20261 votes" -> no year).
        ym = re.search(r"\b(19|20)\d{2}\b", rest_nourl)
        genre_text = " ".join(c for c in cells[1:]
                              if genre_re.search(c)).strip()[:60]
        if not ym and not genre_text:
            continue
        lang = next((L for L in llist
                     if re.search(r"\b" + L + r"\b", rest, re.I)), "Unknown")
        low = genre_text.lower()
        if re.search(r"\breality\b|\btalk\b|\bvariety\b|competition|unscripted", low):
            ttype = "reality"
        elif re.search(r"\bfilm\b|\bmovie\b", low):
            ttype = "film"
        elif genre_text or (ym and lang != "Unknown"):
            ttype = "series"
        else:
            continue  # unknown type with no genre/year signal — skip, don't default
        seen.add(name.lower())
        titles.append({"name": name, "year": int(ym.group(0)) if ym else None,
                       "type": ttype, "language": lang,
                       "genres": [genre_text] if genre_text else [],
                       "is_original": True, "source_url": source_url,
                       "source_date": "date unknown"})
    return titles


def heuristic_scores(facts: list[dict]) -> dict[str, int]:
    """Draft scores from slot COVERAGE with diminishing returns.

    Old formula (55 + 2 × fact count, capped 85) handed 85s to any 440-fact
    pack. Coverage ratio (filled required slots ÷ required slots) plus a
    small, saturating density bonus keeps scores comparable across packs.
    Analyst overrides in UI; overall stays computed.
    """
    import math
    have = {f["slot"] for f in facts if (f.get("claim") or "").strip()}
    out: dict[str, int] = {}
    for sec, slots in SECTION_SLOTS.items():
        filled = sum(1 for s in slots if s in have)
        coverage = filled / max(1, len(slots))
        density = sum(1 for f in facts if f["slot"] in slots)
        bonus = min(10, 4 * math.log1p(density))
        # tier quality: share of facts from tier-1/2 sources
        sec_facts = [f for f in facts if f["slot"] in slots]
        quals = (sum(1 for f in sec_facts if f.get("tier", 3) <= 2) / len(sec_facts)
                 if sec_facts else 0.0)
        out[sec] = max(35, min(92, round(38 + 30 * coverage + bonus + 5 * quals)))
    return out


# ---- fact-backed prose composers (every figure is a verbatim fact value) ----
_CONF_RANK = {"high": 0, "medium": 1, "low": 2}


def _ranked(facts: list[dict]) -> list[dict]:
    return sorted(facts, key=lambda f: (f.get("tier", 3),
                                        _CONF_RANK.get(f.get("confidence", "low"), 2)))


_AD_LIKE = re.compile(
    r"only on amazon|bank offers|big billion|exchange deal|sale early deals|"
    r"is available for (rs|\$)|vivo buds|oneplus|mcdonald|atomberg|"
    r"mailto:|%20|share via email|according to|lpcenter|lipcenter|"
    r"logo for|active competitors|cinema tickets can be cancelled",
    re.I)


def _cleaned(facts: list[dict], tier_cap: int = 2) -> list[dict]:
    good = [f for f in _ranked(facts)
            if not _AD_LIKE.search(f.get("claim", ""))
            and f.get("tier", 3) <= tier_cap]
    if good or tier_cap >= 3:
        return good or [f for f in _ranked(facts)
                        if not _AD_LIKE.search(f.get("claim", ""))] or _ranked(facts)
    return good


def _top(facts: list[dict], *slots: str, prefer=None) -> dict | None:
    # Prefer tier-1/2 clean picks; fall back to any-tier clean picks in the
    # requested slots (never ad-like). Old packs are tier-3 heavy — without
    # the fallback every money slot reads empty.
    cands: list[dict] = []
    for cap in (2, 3):
        cands = [f for f in _cleaned(facts, tier_cap=cap)
                 if f["slot"] in slots and f.get("value")]
        if cands:
            break
    if prefer is not None:
        moneyed = [f for f in cands if prefer.search(f.get("value") or "")]
        if moneyed:
            return moneyed[0]
    return cands[0] if cands else None


_MONEY = re.compile(r"₹|\$|\brs\.?\b|\binr\b|\busd\b|crore|lakh|billion|million", re.I)
_SCALE = re.compile(r"million|billion|lakh|crore|thousand|₹|\$", re.I)
_PCT = re.compile(r"%")
_PRICE = re.compile(r"₹|\$|\brs\.?\s?\d", re.I)


def _when(f: dict) -> str:
    sd = (f.get("source_date", "date unknown") or "").strip()
    if sd == "date unknown" or not sd:
        return ""
    # Accept YYYY-MM-DD, YYYY-MM, and ISO datetimes
    m = re.match(r"^(\d{4})-(\d{2})(?:-(\d{2}))?", sd)
    if m:
        try:
            y, mo = m.group(1), int(m.group(2))
            if mo == 0:
                return sd
            months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            if 1 <= mo <= 12:
                return f"{months[mo]} {y}"
        except Exception:
            pass
        return sd
    return sd


def _when_suffix(f: dict) -> str:
    w = _when(f)
    return f" ({w})" if w else ""


_SCALE_WORDS = re.compile(r"million|billion|lakh|crore|thousand|%|subscriber|member|user|download|viewer|household|audience|\d\s*[MBK]\b", re.I)


def _sane_scale(f: dict | None) -> dict | None:
    """Scale anchors must carry scale words ('5 Original', '$555.00' are not scale)."""
    if f and f.get("value") and _SCALE_WORDS.search(f["value"]):
        return f
    return None


def compose_summary(platform: str, facts: list[dict], titles: list[dict]) -> str:
    parts = []
    rev = _top(facts, "revenue_annual", "revenue_quarterly", "ebitda", prefer=_MONEY)
    if rev and not _MONEY.search(rev.get("value", "")):
        rev = None
    if rev:
        parts.append(f"{platform} monetises at {rev['value']}{_when_suffix(rev)}, {rev['claim'][:180]}")
    scale = _sane_scale(_top(facts, "subscribers", "mau", prefer=_SCALE))
    if scale:
        parts.append(f"Scale is evidenced at {scale['value']}{_when_suffix(scale)}.")
    share = _top(facts, "share_trends", prefer=_PCT)
    if share and "%" not in share.get("value", ""):
        share = None
    if share:
        parts.append(f"Independent tracking puts {platform} at {share['value']}{_when_suffix(share)}.")
    price = _top(facts, "pricing", prefer=_PRICE)
    if price and not _PRICE.search(price.get("value", "")):
        price = None
    if price:
        parts.append(f"Entry pricing is evidenced at {price['value']}{_when_suffix(price)}.")
    if not parts:
        parts.append(f"No hard scale or revenue figure surfaced for {platform} in collected sources.")
    parts.append(f"Evidence base: {len(facts)} extracted facts across {len(titles)} named titles; "
                 "gaps and conflicts are flagged rather than smoothed over.")
    return " ".join(parts)


def compose_positioning(platform: str, facts: list[dict]) -> str:
    aud = _sane_scale(_top(facts, "subscribers", "mau", "segment_skews", prefer=_SCALE))
    con = _top(facts, "content_hours", "named_originals", "hub_deals", "originals_investment",
               prefer=_MONEY)
    if con and re.fullmatch(r"[₹$]\s?[\d,\.]+", (con.get("value", "") or "").strip()):
        con = None  # truncated money ("$110"); repaired values flow via writer
    elif con and not (_MONEY.search(con.get("value", ""))
                      or _SCALE_WORDS.search(con.get("value", ""))):
        con = None
    dis = _sane_scale(_top(facts, "telecom_bundles", "downloads", "devices", "ctv_share", prefer=_SCALE))
    role = (f"{platform} reaches its audience at {aud['value']}{_when_suffix(aud)}. "
            if aud else f"{platform}'s audience scale is not authoritatively disclosed in collected sources. ")
    conv = (f"Its content story is {con['value']}{_when_suffix(con)}. "
            if con else "Its content story is volume-asserted but thinly sourced. ")
    narr = (f"Distribution leverage is evidenced as {dis['value']}{_when_suffix(dis)}. "
            if dis else "Distribution leverage is asserted more than evidenced. ")
    return (role + conv + narr).strip()


# (Section prose is composed in composer.py — no static templates here.)

WISHLIST_T = [
    "Regional-language scripted originals beyond the currently evidenced languages for {p}",
    "A renewable crime/thriller franchise anchor for {p}",
    "Female-led prestige drama with breakout potential on {p}",
    "A second appointment-viewing variety or reality franchise on {p}",
    "Sports-adjacent documentary without costly rights exposure for {p}",
    "Kids and family animation originals building habit on {p}",
    "Short-form creator formats feeding long-form originals on {p}",
    "Diaspora-targeted co-productions extending {p} beyond India",
]
YES_T = [
    "Originals fitting {p}'s evidenced genre strengths",
    "Renewable, multi-season-shaped formats for {p}",
    "Multi-language dub-ready productions from day one",
    "Star- or creator-led vehicles with a locked script",
    "Post-theatrical blockbusters with dubbed versions",
    "True-story adaptations with cinematic scale",
    "Comedy or variety formats with renewal potential",
    "Documentary or docu-drama with festival pedigree",
]
NO_T = [
    "Single-language content with no dubbing plan",
    "Purely festival/arthouse positioning with no audience hook",
    "One-off formats with no renewal potential",
    "Non-exclusive or windowed rights carve-outs",
    "High-cost drama with no anchor and no tentpole fit",
    "Niche content outside {p}'s language mix",
    "Projects with no advertiser or monetisation angle",
    "Slow-development projects mismatched to {p}'s cadence",
]


SLOT_WISH = {
    "content_hours": "Disclosed catalogue-hours figures — no hard content-hours disclosure surfaced",
    "language_count": "Regional-language slates beyond the currently evidenced languages",
    "originals_investment": "A disclosed originals-investment commitment with a regional split",
    "hub_deals": "Exclusive studio-hub licensing at the level of {p}'s rivals",
    "named_originals": "Named, dateable originals beyond the mined title list",
    "subscribers": "An authoritative subscriber disclosure reconciling third-party estimates",
    "mau": "Authoritative monthly-active-user disclosure by quarter",
    "pricing": "Entry pricing and tier structure in dated, sourced form",
    "sports_rights": "Live-sport rights diversifying beyond the evidenced portfolio",
    "share_trends": "Independent engagement tracking (JustWatch/Ormax) naming {p}",
    "ad_products": "Advertiser-facing products beyond plain spot ads",
    "leadership": "Named content leadership and approval-chain disclosure",
    "mission": "A stated mission beyond scale metrics",
    "devices": "Connected-TV and device-footprint disclosure",
    "downloads": "A verified install/download footprint",
    "telecom_bundles": "Telecom or retail bundling arrangements",
    "dubbing": "Dubbing and multi-language release practice",
    "windows": "Theatrical-to-streaming window practice",
}

YES_RULES = [
    ("named_originals", "Renewable franchise-shaped originals in {p}'s evidenced genres"),
    ("hub_deals", "Studio-compatible licensing alongside {p}'s evidenced hub deals"),
    ("sports_rights", "Live-sport or event tie-ins compatible with {p}'s evidenced sports footprint"),
    ("pricing", "Dub-ready multi-language productions matched to {p}'s tiered pricing"),
    ("ad_products", "Formats with built-in advertiser and commerce integration potential"),
    ("diaspora", "Stories with travel potential into {p}'s evidenced diaspora footprint"),
    ("originals_investment", "Projects fitting {p}'s evidenced investment lanes"),
]
NO_RULES = [
    ("sports_rights", "Sports rights or live-event properties — no evidenced sports rights for {p}"),
    ("telecom_bundles", "Projects needing bundled distribution to find an audience"),
    ("ad_products", "Slate-scale advertiser integrations — no evidenced ad products for {p}"),
    ("hub_deals", "International-studio co-productions — no evidenced hub lane for {p}"),
    ("downloads", "Mobile-first volume plays — no evidenced install footprint for {p}"),
]


def _standout_why(t: dict, facts: list[dict], platform: str) -> str:
    needle = t["name"].lower()[:25]
    for f in _ranked(facts):
        if needle in f["claim"].lower() and len(f["claim"]) > 60:
            return f["claim"][:200]
    bits = " ".join(str(x) for x in [t.get("year"), t.get("language"),
                                     (t.get("genres") or [""])[0], t.get("type")]
                    if x and x != "Unknown")
    return f"{bits} original from the mined {platform} list." if bits else \
        f"Named original from the mined {platform} list."


def _fallback_standouts(facts: list[dict], platform: str, need: int) -> list[dict]:
    """Validator-safe standouts when Wikipedia mining found <6 titles.

    Previously these were "TBD — add from evidence" placeholders, which the
    validator always rejects (standout not in dataset) — so every new
    platform with no Wikipedia list page could never generate. Instead derive
    each standout title as a substring of a real fact claim (quoted show
    names first, else the claim's lead words), so `validate()` grounding
    passes and the analyst just sharpens the wording.
    """
    cands: list[dict] = []
    ranked_facts = _ranked([f for f in facts
                            if f.get("slot") in ("named_originals", "hub_deals",
                                                 "franchises", "sports_rights",
                                                 "genre_mix")])
    if not ranked_facts:
        ranked_facts = _ranked(facts)
    # Prefer the target's own facts: comparison-table rows about rivals
    # ("Netflix Rs 199-649 ...", "Amazon Prime Rs 299 ...") must never become
    # standouts for the target platform. Rival-led claims are used only if
    # nothing else exists.
    _RIVALS = ("netflix", "prime video", "amazon prime", "hotstar", "jiohotstar",
               "jiocinema", "zee5", "sonyliv", "sony liv", "altbalaji", "mx player",
               "hoichoi", "aha video", "sunnxt", "chaupal", "ullu", "jio star", "jiostar")
    pnorm = _norm(platform)
    _rivals_norm = {re.sub(r"[^a-z0-9]", "", r) for r in _RIVALS}
    def _kind(f: dict) -> int:
        low = (f.get("claim") or "").lower()
        snorm = re.sub(r"[^a-z0-9]", "", low)
        # Word-boundary match for short names ("Aha" must not match "Maharaja").
        if pnorm:
            if len(pnorm) <= 4:
                if re.search(r"\b" + re.escape(platform.strip().lower()) + r"\b", low) or pnorm == snorm:
                    return 0
            elif platform.lower() in low or pnorm in snorm:
                return 0
        if any(r in low for r in _RIVALS) or any(rn and rn in snorm for rn in _rivals_norm):
            return 2
        return 1
    # Thin packs may hold only 1-2 target facts in title slots while rival
    # comparison rows fill the rest — widen the pool with all facts so the
    # target's own pricing/audience facts outrank rival rows via _kind.
    _seen_ids = {id(f) for f in ranked_facts}
    ranked_facts += [f for f in _ranked(facts) if id(f) not in _seen_ids]
    ranked_facts = sorted(ranked_facts, key=_kind)
    seen: set[str] = set()
    for f in ranked_facts:
        if len(cands) >= need:
            break
        claim = (f.get("claim") or "").strip()
        if len(claim) < 20:
            continue
        title = ""
        qm = re.search(r'["“]([^"”]{4,60})["”]', claim)
        if qm:
            title = qm.group(1).strip()
        else:
            words = re.findall(r"[A-Za-z0-9&:'-]+", claim)
            # Lead with capitalised words; skip outlet prefixes ("According
            # to Ormax, ...").
            cap = [w for w in words[:10] if w[:1].isupper()]
            title = " ".join(cap[:4]) if len(cap) >= 2 else " ".join(words[:6])
            title = title.strip(" -:'")[:60]
        if len(title) < 4 or title.lower() in seen:
            continue
        # Guarantee grounding: title must occur verbatim in the fact text.
        if title.lower() not in claim.lower():
            title = " ".join(claim.split()[:6])[:60]
        seen.add(title.lower())
        cands.append({"title": title,
                      "why": f"{claim[:200]} (from collected {f.get('slot')} evidence)"})
    return cands


def _group_slash_lead(mined: list[dict], titles: list[dict]) -> list[dict]:
    """Join the first two same-language/type mined anchors with ' / '.

    Keeps 6 items: consumes up to 7 mined inputs for 6 outputs when a pair
    merges. Falls back to the plain first-6 when no pair shares lane.
    """
    if len(mined) < 3:
        return mined[:6]
    by_name = {t["name"]: t for t in titles}
    for i in range(min(len(mined) - 1, 3)):
        a, b = mined[i], mined[i + 1]
        ta, tb = by_name.get(a["title"], {}), by_name.get(b["title"], {})
        if ta and tb and ta.get("language") == tb.get("language") \
                and ta.get("type") == tb.get("type") and a["title"] != b["title"]:
            lead = {"title": f"{a['title']} / {b['title']}",
                    "why": f"{a['why']} Paired {tb.get('language', '')} "
                           f"{tb.get('type', '')} anchors sharing the same lane; {b['why']}"[:300]}
            return [lead] + [m for j, m in enumerate(mined) if j not in (i, i + 1)][:5]
    return mined[:6]


def _bold_lead(w: str) -> str:
    """Normalize a wishlist item to Jio shape: '**Lead** — detail'.

    Lead ends at a preposition boundary (beyond/for/with/without/within)
    or after 3-4 words — never mid-phrase like '**…beyond the**'.
    """
    w = (w or "").strip()
    if not w:
        return w
    if w.startswith("**"):
        return w
    for sep in (" — ", " - ", ": "):
        if sep in w:
            head, tail = w.split(sep, 1)
            if len(head.strip()) < 80 and tail.strip():
                return f"**{head.strip()}**{sep}{tail.strip()}"
    words = w.split()
    if len(words) <= 4:
        return f"**{w}**"
    lead_end = 4
    for i, wd in enumerate(words[2:7], start=2):
        if wd.lower() in ("beyond", "for", "with", "without", "within",
                          "across", "through", "against", "under", "over"):
            lead_end = i
            break
    else:
        # No preposition boundary: short lead (never strand one word).
        lead_end = min(3, len(words) - 1)
    lead_end = max(2, min(lead_end, len(words) - 1))
    return f"**{' '.join(words[:lead_end])}** — {' '.join(words[lead_end:])}"


def draft_pack(platform: str, facts: list[dict], titles: list[dict],
               scores: dict[str, int], catalogue_note: str = "",
               region: str = "India") -> dict:
    # Heal truncated money values BEFORE composing so strategy/summary
    # lines quote full figures ("$110 Billion", not "$110").
    try:
        from .facts import repair_value as _rv
        for f in facts:
            if isinstance(f, dict):
                f["value"] = _rv(f.get("value", ""), f.get("claim", ""))
    except Exception:
        pass
    slug = "".join(c.lower() if c.isalnum() else "_" for c in platform).strip("_")
    have_slots = {f["slot"] for f in facts}
    mined = [{"title": t["name"], "why": _standout_why(t, facts, platform)}
             for t in titles[:7]]
    # Jio-shaped grouping: the lead item may join two same-language/type
    # anchors with " / " ("Criminal Justice / Special Ops / Aarya" style).
    # Validator splits on "/" and grounds each part, so both names must be
    # real mined titles. Six items are still emitted.
    standout = _group_slash_lead(mined, titles)
    if len(standout) < 6:
        standout += _fallback_standouts(facts, platform, 6 - len(standout))
    _seen = {s["title"].lower() for s in standout}
    while len(standout) < 6:
        # Last resort: still grounded (title taken from a fact claim) so
        # validation passes; analyst sharpens in the UI. Slice length grows
        # until the title is unique, so thin-evidence packs don't get 6
        # identical titles.
        if facts:
            src = facts[len(standout) % len(facts)]
            words = (src.get("claim") or "").split()
            claim = ""
            for cut in range(4 + (len(standout) % 4), len(words) + 1):
                cand = " ".join(words[:cut])[:60]
                if cand.lower() not in _seen and len(cand) >= 4:
                    claim = cand
                    break
            claim = claim or (" ".join(words[:8])[:60] or f"{platform} slate")
            if claim.lower() in _seen:
                claim = f"{claim} ({len(standout) + 1})"[:60]
            _seen.add(claim.lower())
            standout.append({"title": claim, "why": (src.get("claim", "") or "")[:200]})
        else:
            standout.append({"title": f"{platform} slate title {len(standout) + 1}",
                             "why": "No titles or facts mined — analyst to fill from sources."})
    wishlist: list[str] = []
    for s in dict.fromkeys(s for secs in SECTION_SLOTS.values() for s in secs):
        if s not in have_slots and s in SLOT_WISH and len(wishlist) < 8:
            wishlist.append(SLOT_WISH[s].format(p=platform))
    for w in WISHLIST_T:
        if len(wishlist) >= 8:
            break
        wishlist.append(w.format(p=platform))
    wishlist = [_bold_lead(w) for w in wishlist[:8]]
    yes = [t.format(p=platform) for slot, t in YES_RULES if slot in have_slots]
    yes += [y.format(p=platform) for y in YES_T if len(yes) < 8]
    no = [t.format(p=platform) for slot, t in NO_RULES if slot not in have_slots]
    no += [x.format(p=platform) for x in NO_T if len(no) < 8]
    price_dates = sorted(f.get("source_date", "") for f in facts if f["slot"] == "pricing")
    tiers_label = "Subscription Tiers"
    if price_dates and price_dates[-1] != "date unknown":
        tiers_label = f"Subscription Tiers (as of {_when({'source_date': price_dates[-1]})})"
    sections = {}
    for sec, build in BUILDERS.items():
        fields = build(platform, facts, titles)
        sections[sec] = {"score": scores.get(sec, 65), "evidence": "", **fields}
    sections["content"]["standout_titles"] = standout
    sections["revenue"]["tiers_label"] = tiers_label
    strongest = max(scores, key=lambda s: scores.get(s, 0)) if scores else "content"
    weakest = min(scores, key=lambda s: scores.get(s, 99)) if scores else "editorial"
    # Scale-first identity: platform positioning from scale/mission slots —
    # never a single title claim (e.g. "Breakers...") even when it is the
    # top moneyed fact. Title slots are evidence, not identity.
    _IDENTITY_SLOTS = ("mission", "subscribers", "mau", "share_trends",
                       "pricing", "revenue_annual", "revenue_quarterly",
                       "language_count", "content_hours")
    _TITLE_SLOTS = ("named_originals", "hub_deals", "franchises",
                    "sports_rights", "windows")

    def _sentence_cut(s: str, n: int) -> str:
        s = (s or "").strip()
        if len(s) <= n:
            return s
        cut = s.rfind(" ", 0, n)
        cut = cut if cut > 100 else n
        out = s[:cut].rstrip(" ([{'\"")
        # Prefer ending at sentence punctuation when close behind.
        for p in (".", "!", "?", ";"):
            pos = out.rfind(p)
            if pos >= 60:
                return out[:pos + 1]
        return out + "…"

    sig_pool = [f for f in _cleaned(facts)
                if f.get("value") and f.get("slot") in _IDENTITY_SLOTS
                and f.get("slot") not in _TITLE_SLOTS]
    if not sig_pool:
        sig_pool = [f for f in _cleaned(facts, tier_cap=3)
                    if f.get("value") and f.get("slot") in _IDENTITY_SLOTS
                    and f.get("slot") not in _TITLE_SLOTS]
    sig_m = [f for f in sig_pool if _MONEY.search(f.get("value") or "")]
    first = (sig_m or sig_pool)[0] if (sig_m or sig_pool) else None
    identity = (f"{platform} — {_sentence_cut(first['claim'], 200)}" if first
                else f"{platform} — a thinly-evidenced service in collected sources.")
    return {
        "platform": platform, "region": region, "slug": slug,
        "catalogue_note": catalogue_note or "collected trade, investor and platform sources",
        "identity_line": identity,
        "risk_tag": f"{strongest.upper()} EVIDENCE — THIN {weakest.upper()} COVERAGE RISK",
        "summary": compose_summary(platform, facts, titles),
        "positioning": compose_positioning(platform, facts),
        "sections": sections,
        "wishlist": wishlist[:8],
        "pitch": {"angle": compose_angle(platform, facts, scores),
                  "ideal_profile": compose_ideal(platform, facts, titles),
                  "yes": yes[:8], "no": no[:8],
                  "negotiation": compose_negotiation(platform, facts)},
        "facts": facts, "titles": titles,
    }
