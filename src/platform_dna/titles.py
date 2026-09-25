"""Title dataset + computed stats (plan §4 Step 2). All splits computed in code."""
from __future__ import annotations

import os
import time
from collections import Counter

import httpx

from .config import SAMPLING_THRESHOLD


def tmdb_discover(provider_id: int, region: str = "IN", api_key: str | None = None) -> list[dict]:
    """TMDB discover with watch-provider ID. Returns [] without a key."""
    api_key = api_key or os.environ.get("TMDB_API_KEY")
    if not api_key:
        return []
    out, page = [], 1
    while page <= 5:
        try:
            r = httpx.get(
                "https://api.themoviedb.org/3/discover/tv",
                params={"api_key": api_key, "with_watch_providers": provider_id,
                        "watch_region": region, "page": page},
                timeout=30,
            )
            r.raise_for_status()
        except Exception:
            # Network/rate-limit: return what we have rather than crashing.
            time.sleep(1)
            break
        data = r.json()
        out += data.get("results", [])
        if page >= data.get("total_pages", 1):
            break
        page += 1
    return out


def compute_stats(titles: list[dict]) -> dict:
    n = len(titles)
    lang = dict(Counter(t.get("language", "Unknown") or "Unknown" for t in titles))
    typ = dict(Counter(t.get("type", "Unknown") or "Unknown" for t in titles))
    orig = sum(1 for t in titles if t.get("is_original"))
    return {
        "count": n,
        "by_language": lang,
        "by_type": typ,
        "originals": orig,
        "licensed": n - orig,
        "originals_share": round(orig / n * 100, 1) if n else 0.0,
    }


def header_sentence(platform: str, count: int, catalogue_note: str) -> str:
    base = (f"{platform}: **~{count} named titles/properties analysed** "
            f"(originals, licensed hubs, sports properties, reality formats) "
            f"cross-referenced against {catalogue_note}.")
    if count < SAMPLING_THRESHOLD:
        base += (" This is a **sampling-level** evidence base, not a full 150+ title "
                 "catalogue pull — no public catalogue export exists and third-party "
                 "coverage of the regional slate is sparse, so title-level claims below "
                 "are anchored to named, dateable sources; catalogue-wide percentages "
                 "are flagged as estimates where no hard figure was disclosed.")
    return base
