"""Research: SearXNG discovery + Firecrawl extraction (plan §3), cached + retry."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

SEARX = os.environ.get("SEARXNG_URL", "http://localhost:8081")
FIRE = os.environ.get("FIRECRAWL_URL", "http://localhost:3002")
CACHE = Path(os.environ.get("DNA_CACHE_DIR", ".cache"))
CACHE.mkdir(parents=True, exist_ok=True)

DEFAULT_LANGUAGE = "en-IN"
# English-market locales only. Non-English markets (DE/FR/JP/KR/...) keep
# en-IN on purpose: switching SearXNG to de-/fr-/ja- would return
# non-English pages the English-regex extractor cannot use (quality loss).
# English-locale results for the same query stay comparable across runs.
REGION_LANGUAGE = {
    "india": "en-IN", "in": "en-IN",
    "canada": "en-CA", "ca": "en-CA",
    "united states": "en-US", "usa": "en-US", "us": "en-US",
    "united kingdom": "en-GB", "uk": "en-GB", "gb": "en-GB",
    "australia": "en-AU", "au": "en-AU",
}
# JS-shell domains: first scrape attempt still runs (wait 0), but empty
# results are NOT escalated to wait-2000/retried. Measured: disneyplus.com
# marketing pages return 0 chars via Firecrawl; app-store walls never carry
# usable facts (STRICT_SLOTS). Skipping escalation can only save time — a
# page that yields nothing at wait-0 AND wait-2000 contributes no facts.
NO_ESCALATE_DOMAINS = ("disneyplus.com", "play.google.com/store", "apps.apple.com")


def locale_for_region(region: str = "") -> str:
    """SearXNG language tag for a report region name/code/label."""
    s = (region or "").strip().lower()
    if not s:
        return DEFAULT_LANGUAGE
    if s in REGION_LANGUAGE:
        return REGION_LANGUAGE[s]
    m = re.match(r"^(.*)\(([^)]+)\)\s*$", s)
    if m:
        code = m.group(2).strip().lower()
        if code in REGION_LANGUAGE:
            return REGION_LANGUAGE[code]
        name = m.group(1).strip().lower()
        if name in REGION_LANGUAGE:
            return REGION_LANGUAGE[name]
    return DEFAULT_LANGUAGE


def is_no_escalate(url: str) -> bool:
    u = (url or "").lower()
    return any(d in u for d in NO_ESCALATE_DOMAINS)


def _cache_get(key: str):
    p = CACHE / (hashlib.sha256(key.encode()).hexdigest() + ".json")
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def _cache_put(key: str, value) -> None:
    p = CACHE / (hashlib.sha256(key.encode()).hexdigest() + ".json")
    p.write_text(json.dumps(value)[:500_000], encoding="utf-8")


def searx(q, categories="general", time_range=None, pages=1, retries=2,
          language: str | None = None):
    """Direct SearXNG call (not via Firecrawl /search) for category/time control."""
    lang = language or DEFAULT_LANGUAGE
    results = []
    for p in range(1, pages + 1):
        params = {"q": q, "format": "json", "categories": categories,
                  "language": lang, "pageno": p}
        if time_range:
            params["time_range"] = time_range  # day | month | year
        key = f"searx:{json.dumps(params, sort_keys=True)}"
        hit = _cache_get(key)
        if hit is not None:
            results += hit
            continue
        for attempt in range(retries):
            try:
                r = httpx.get(f"{SEARX}/search", params=params, timeout=15)
                r.raise_for_status()
                items = r.json().get("results", [])
                # Never cache empty hits: a transient engine outage would
                # otherwise poison the cache and every later run would
                # instantly return 0 results for the same query.
                if items:
                    _cache_put(key, items)
                results += items
                break
            except Exception:
                if attempt == retries - 1:
                    break
                time.sleep(2 ** attempt)
        time.sleep(0.3)  # low concurrency: up to 4 parallel (plan §3)
    return results


def scrape(url, wait_ms=0, retries=2):
    """Firecrawl scrape with Playwright waitFor for JS pages. Cached by URL.

    Cache is wait-insensitive: a page scraped once is reused regardless of
    the wait_ms requested (avoids re-scraping the same URL from the Extract
    tab (wait 0) and Auto DNA (wait 2000)). Only a non-empty cached page
    is reused; failures are retried with the requested wait.
    """
    key = f"scrape:{url}:{wait_ms}"
    hit = _cache_get(key)
    if hit is not None:
        # Never trust a cached failure: a transient Firecrawl outage would
        # otherwise poison the cache and every later run would instantly
        # return "" for the same URL without retrying.
        if hit.get("markdown"):
            return hit["markdown"], hit["metadata"]
    # Fallback: reuse the same URL scraped with a different wait_ms.
    for alt_wait in (0, 2000):
        if alt_wait == wait_ms:
            continue
        alt = _cache_get(f"scrape:{url}:{alt_wait}")
        if alt is not None and alt.get("markdown"):
            return alt["markdown"], alt.get("metadata", {})
    body = {"url": url, "formats": ["markdown"],
            "onlyMainContent": True, "timeout": 30000}
    if wait_ms:
        body["waitFor"] = wait_ms
    short_chars = 0
    for attempt in range(retries):
        try:
            r = httpx.post(f"{FIRE}/v1/scrape", json=body, timeout=45)
            r.raise_for_status()
            data = r.json().get("data") or {}
            md, meta = data.get("markdown") or "", data.get("metadata") or {}
            if len((md or "").strip()) < 500:
                short_chars = max(short_chars, len((md or "").strip()))
                raise ValueError(f"short scrape ({len(md or '')} chars): {url}")
            _cache_put(key, {"markdown": md[:200_000], "metadata": meta})
            return md, meta
        except Exception:
            if attempt == retries - 1:
                # Do NOT cache failures — return transient "" so the next
                # run retries the live backend instead of replaying failure.
                # `chars` tells the caller whether a JS wait could help:
                # fully-empty pages sometimes hydrate; short-but-nonempty
                # paywalls never grow with waiting.
                return "", {"statusCode": 0, "failed": True, "chars": short_chars}
            time.sleep(2 ** attempt)
    return "", {"statusCode": 0, "failed": True, "chars": short_chars}


def scrape_many(urls: list[str], wait_ms: int = 0,
                max_workers: int = 6,
                progress=None, deadline_s: float | None = None,
                **kwargs) -> dict[str, tuple[str, dict]]:
    """Parallel scrape with live progress. Returns {url: (md, meta)} in order.

    deadline_s optionally bounds the whole batch: URLs still pending when it
    lapses are marked failed (error "deadline") instead of blocking the
    generate. Default None preserves legacy wait-for-all behavior.
    `scrape_deadline_s` is accepted as an alias for backward compat with
    callers that use the autodraft naming.
    """
    # Backward-compat alias: autodraft passes scrape_deadline_s.
    if deadline_s is None and "scrape_deadline_s" in kwargs:
        deadline_s = kwargs.pop("scrape_deadline_s")
    from concurrent.futures import TimeoutError as _FutTimeout
    from concurrent.futures import as_completed

    # Dedupe upfront so progress counts and thread budget are accurate.
    urls = list(dict.fromkeys(urls or []))
    if not urls:
        return {}

    def _one(u: str):
        try:
            return u, scrape(u, wait_ms=wait_ms)
        except Exception as e:  # noqa: BLE001
            return u, ("", {"statusCode": 0, "failed": True, "chars": 0,
                            "error": str(e)[:120]})

    out: dict[str, tuple[str, dict]] = {}
    if deadline_s is not None and deadline_s <= 0:
        # Explicit non-positive deadline means "no wait": mark all failed
        # immediately instead of clamping to 1s of work.
        for u in urls:
            out[u] = ("", {"statusCode": 0, "failed": True, "chars": 1,
                           "error": "deadline"})
        return {u: out[u] for u in urls if u in out}
    if deadline_s is None:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(_one, u): u for u in urls}
            for i, fut in enumerate(as_completed(futs)):
                try:
                    u, res = fut.result()
                except Exception as e:  # noqa: BLE001
                    u = futs.get(fut, "")
                    res = ("", {"statusCode": 0, "failed": True, "chars": 0,
                                "error": str(e)[:120]})
                out[u] = res
                if progress:
                    ok = sum(1 for m, _ in out.values() if m)
                    progress(f"scraped {i + 1}/{len(urls)} ({ok} with content)…")
        return {u: out[u] for u in urls if u in out}
    # Bounded pass: collect completions until the deadline, then mark the
    # rest failed. Threads are not killed — the pool is shut down without
    # waiting so a hung httpx.post does not block the generate; late
    # results are simply unused.
    _deadline = time.time() + max(1.0, deadline_s)
    ex = ThreadPoolExecutor(max_workers=max_workers)
    try:
        futs = {ex.submit(_one, u): u for u in urls}
        pending = dict(futs)
        while pending:
            wait = _deadline - time.time()
            if wait <= 0:
                break
            try:
                for fut in as_completed(list(pending), timeout=wait):
                    u = pending.pop(fut)
                    try:
                        _u, res = fut.result()
                    except Exception as e:  # noqa: BLE001
                        res = ("", {"statusCode": 0, "failed": True, "chars": 0,
                                    "error": str(e)[:120]})
                        _u = u
                    out[_u] = res
                    if progress:
                        ok = sum(1 for m, _ in out.values() if m)
                        progress(f"scraped {len(out)}/{len(urls)} ({ok} with content)…")
            except _FutTimeout:
                break
        for fut, u in pending.items():
            fut.cancel()
            if u not in out:
                # chars=1 so the escalation filter skips deadline-expired
                # URLs (a wait-2000 retry would also hit the deadline).
                out[u] = ("", {"statusCode": 0, "failed": True, "chars": 1,
                               "error": "deadline"})
    finally:
        try:
            ex.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            # Python <3.9 without cancel_futures.
            ex.shutdown(wait=False)
    return {u: out[u] for u in urls if u in out}
