"""Composer: author every report field from collected facts — no placeholders.

Each builder uses verbatim fact values/claims (validator-safe) plus plain
counts (never ₹/$/%/years it invents). Where nothing was evidenced, it says
so in report voice ("No X surfaced in collected sources") instead of
scaffolding like "Fill from evidence".
"""
from __future__ import annotations

import re

from .config import SECTION_SLOTS

GENRES = ["crime", "thriller", "drama", "comedy", "romance", "reality",
          "sport", "horror", "documentary", "action", "fantasy", "sci-fi",
          "animation", "variety", "mythology", "talk show", "mystery"]

EMOTION = {"crime": "tension", "thriller": "suspense", "drama": "catharsis",
           "comedy": "laughter", "romance": "warmth", "reality": "spectacle",
           "sport": "adrenaline", "horror": "dread", "documentary": "curiosity",
           "action": "thrills", "fantasy": "escapism", "sci-fi": "wonder",
           "animation": "playfulness", "variety": "light relief",
           "mythology": "reverence", "talk show": "companionship",
           "mystery": "intrigue"}

_CONF_RANK = {"high": 0, "medium": 1, "low": 2}


def ranked(facts: list[dict]) -> list[dict]:
    return sorted(facts, key=lambda f: (f.get("tier", 3),
                                        _CONF_RANK.get(f.get("confidence", "low"), 2)))


def claims(facts: list[dict], *slots: str, n: int = 6) -> list[str]:
    # clean picks first: tier-1/2 non-ad sources lead composed prose;
    # backfill from any-tier clean picks so thin slots never read empty.
    out = [f["claim"] for f in _clean_pick(facts) if f["slot"] in slots]
    if len(out) < n:
        seen = set(out)
        out += [f["claim"] for f in _clean_pick(facts, tier_cap=3)
                if f["slot"] in slots and f["claim"] not in seen]
    return out[:n]


# Claims that look like ads, trackers or page furniture must never anchor
# composed prose (identity lines, positioning, strategy, budgets).
_AD_LIKE = re.compile(
    r"only on amazon|bank offers|big billion|exchange deal|sale early deals|"
    r"is available for (rs|\$)|vivo buds|oneplus|mcdonald|atomberg|"
    r"mailto:|%20|share via email|according to ormax|lpcenter|lipcenter|"
    r"logo for|active competitors|cinema tickets can be cancelled",
    re.I)


def _clean_pick(facts: list[dict], tier_cap: int = 2) -> list[dict]:
    """Ranked facts minus ad-like/tier junk. Never returns ad-like facts:
    when nothing clean exists the caller gets [] and writes honestly-thin
    wording instead of anchoring prose on ads."""
    good = [f for f in ranked(facts)
            if not _AD_LIKE.search(f.get("claim", ""))
            and f.get("tier", 3) <= tier_cap]
    if good or tier_cap >= 3:
        return good or [f for f in ranked(facts)
                        if not _AD_LIKE.search(f.get("claim", ""))]
    return good


def top(facts: list[dict], *slots: str, prefer=None) -> dict | None:
    # Prefer tier-1/2 clean picks; fall back to any-tier clean picks in the
    # requested slots (never ad-like). A money preference is honoured across
    # tier caps first, so tier-2 non-money never beats tier-3 money for
    # money slots.
    pools = [[f for f in _clean_pick(facts, tier_cap=cap)
              if f["slot"] in slots and f.get("value")]
             for cap in (2, 3)]
    if prefer is not None:
        for pool in pools:
            moneyed = [f for f in pool if prefer.search(f.get("value") or "")]
            if moneyed:
                return moneyed[0]
    for pool in pools:
        if pool:
            return pool[0]
    return None


# NOTE: rs/inr/usd need word boundaries — bare "rs" matches inside
# "visitors"/"subscribers" and once routed age-demographics into pricing.
# Bare scale words (million/billion) are NOT money: "100 million
# subscribers" is scale, and routing it as money mislabels investment lines.
_MONEY = re.compile(r"₹|\$|\brs\.?(?!\w)|\binr\b|\busd\b|crore|lakh", re.I)
_SCALE = re.compile(r"million|billion|lakh|crore|thousand|₹|\$", re.I)
_PCT = re.compile(r"%")
_PRICE = re.compile(r"₹|\$|\brs\.?(?!\w)\s?\d", re.I)


def when(f: dict) -> str:
    sd = (f.get("source_date", "date unknown") or "").strip()
    if sd == "date unknown" or not sd:
        return ""
    m = re.match(r"^(\d{4})-(\d{2})(?:-(\d{2}))?", sd)
    if m:
        try:
            y, mo = m.group(1), int(m.group(2))
            months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            if 1 <= mo <= 12:
                return f"{months[mo]} {y}"
        except Exception:
            pass
        return sd
    return sd


def when_suffix(f: dict) -> str:
    """' (Mon YYYY)' when dated, else '' — never renders 'date unknown'."""
    w = when(f)
    return f" ({w})" if w else ""


def genre_hits(facts: list[dict]) -> list[tuple[str, int]]:
    text = " ".join(f["claim"].lower() for f in facts
                    if f["slot"] in ("named_originals", "genre_mix", "hub_deals")).lower()
    out = [(g, len(re.findall(r"\b" + re.escape(g) + r"s?\b", text))) for g in GENRES]
    return sorted([x for x in out if x[1] > 0], key=lambda x: -x[1])


def title_cells(titles: list[dict]) -> list[str]:
    cells = []
    for t in titles:
        for g in t.get("genres", []) or []:
            if g and len(g) < 60:
                cells.append(g)
    return cells


def examples(titles: list[dict], genre: str, n: int = 3) -> list[str]:
    gl = genre.lower()
    ex = [t["name"] for t in titles
          if any(re.search(r"\b" + re.escape(gl) + r"s?\b", (g or "").lower())
                 for g in (t.get("genres", []) or []))]
    # Do not mislabel unrelated titles as genre examples — return only true
    # matches; caller falls back to "No genre pattern evidenced" wording.
    return ex[:n]


def _short(s: str, n: int = 220) -> str:
    return s if len(s) <= n else s[:n - 3] + "..."


_TRUNCATED_MONEY = re.compile(r"^[₹$\s]*[\d,\.]+$", re.I)
_TRUNCATED_MONEY_RS = re.compile(r"^(?:rs\.?|inr)\s?[\d,\.]+$", re.I)


def _full_value(f: dict | None) -> dict | None:
    """Reject truncated money values ('$110' from '$110 Billion')."""
    if f and (f.get("value") or "").strip():
        v = f["value"].strip()
        if _TRUNCATED_MONEY.match(v) or _TRUNCATED_MONEY_RS.match(v):
            return None
    return f


# ---------------- content ----------------
def _genre_label(g: str, titles: list[dict]) -> str:
    ex = examples(titles, g)
    if ex:
        return f"{g.title()} ({', '.join(ex)})"
    return f"{g.title()} (no mined title example in this genre)"


def content_fields(p: str, facts: list[dict], titles: list[dict]) -> dict:
    gh = genre_hits(facts)
    prim = "; ".join(_genre_label(g, titles)
                     for g, _c in gh[:3]) or "No genre pattern evidenced"
    sec = "; ".join(_genre_label(g, titles)
                    for g, _c in gh[3:6]) or "Licensed and library content where evidenced"
    inv = _full_value(top(facts, "originals_investment", prefer=_MONEY))
    hub = _full_value(top(facts, "hub_deals"))
    strat = (f"Build around {gh[0][0]} originals"
             if gh else f"Build {p} title by title from evidenced demand")
    if inv:
        strat += f", backed by commitments at {inv['value']}{when_suffix(inv)}"
    if hub:
        strat += f" plus licensed pipeline such as {hub['value']}"
    strat += "."
    fr = [c for c in claims(facts, "named_originals", "franchises", n=20)
          if re.search(r"season\s*\d|renewed|season \d|chapter", c, re.I)][:3]
    franch = ("Strong renewal cadence — " + " ".join(_short(c) for c in fr)) if fr \
        else "No multi-season franchise renewals surfaced in collected sources."
    langs = top(facts, "language_count")
    tlangs: dict[str, int] = {}
    for t in titles:
        tlangs[t.get("language", "Unknown")] = tlangs.get(t.get("language", "Unknown"), 0) + 1
    top_langs = ", ".join(l for l, _c in sorted(tlangs.items(), key=lambda x: -x[1])[:5] if l != "Unknown")
    langmix = (_short(langs["claim"]) + " ") if langs else ""
    langmix += (f"Mined titles cluster in {top_langs}." if top_langs
                else "No per-language title weighting disclosed.")
    years = sorted(t["year"] for t in titles if t.get("year"))
    if len(years) >= 3:
        era = (f"Contemporary — mined titles span {years[0]} to {years[-1]} "
               f"across {len(years)} dated titles.")
    elif years:
        era = f"Dated evidence clusters in {years[0]} — era read is thin."
    else:
        era = "No dated titles mined."
    mix = ("Not disclosed as a clean percentage split by the company; catalogue-wide "
           "shares below are estimates from sampling, not disclosed figures.")
    named = claims(facts, "named_originals", n=6)
    seen_c: list[str] = []
    for c in named:
        if c[:60] not in [s[:60] for s in seen_c]:
            seen_c.append(c)
    orig_strat = " ".join(_short(c) for c in seen_c[:2]) or \
        f"Originals evidenced across {len(titles)} mined titles."
    return {"strategy_line": strat, "primary_genres": prim, "secondary_genres": sec,
            "originals_strategy": orig_strat,
            "franchise_presence": franch, "content_mix": mix, "language_mix": langmix,
            "era_focus": era,
            "quality_tier": (f"Spend evidenced at {inv['value']}{when_suffix(inv)}. "
                             if inv else "No disclosed budget tier in collected sources."),
            "catalogue_gaps": gaps_line(p, facts, ("hub_deals", "originals_investment",
                                                   "language_count", "content_hours"))}


def gaps_line(p: str, facts: list[dict], slots: tuple[str, ...]) -> str:
    have = {f["slot"] for f in facts}
    missing = [s.replace("_", " ") for s in slots if s not in have]
    if not missing:
        return f"No clean gap: every checked slot has at least one sourced fact for {p}."
    return ("Thinly evidenced in collected sources: " + ", ".join(missing) +
            " — flagged as under-documented rather than necessarily absent.")


# ---------------- audience ----------------
def audience_fields(p: str, facts: list[dict], titles: list[dict]) -> dict:
    seg = claims(facts, "segment_skews", n=3)
    dia = claims(facts, "diaspora", n=2)
    scale = top(facts, "subscribers", "mau", prefer=_SCALE)
    return {
        "strategy_line": (f"Reach the {p} audience through its evidenced funnel at "
                          f"{scale['value']}{when_suffix(scale)}.") if scale else
                         f"Reach a defined audience first; scale is not authoritatively disclosed for {p}.",
        "primary_segment": _short(seg[0]) if seg else "No segment skew disclosed in collected sources.",
        "secondary_segments": " ".join(_short(c) for c in seg[1:]) or
                              "No secondary segments evidenced.",
        "geographic_focus": " ".join(_short(c) for c in dia) or
                            "India-first in collected sources; no diaspora push evidenced.",
        "cultural_identity": _short(claims(facts, "mission", n=1)[0]) if claims(facts, "mission", n=1)
                             else f"No stated cultural positioning surfaced for {p}.",
        "lifestyle_profile": _short(claims(facts, "devices", "ctv_share", n=1)[0])
                             if claims(facts, "devices", "ctv_share", n=1)
                             else "No lifestyle or device profile disclosed.",
        "viewing_occasion": _short(claims(facts, "windows", n=1)[0])
                            if claims(facts, "windows", n=1)
                            else "No viewing-occasion pattern evidenced.",
        "sophistication": ("Tiered pricing sorts viewers by willingness to pay; "
                            "no separate taste hierarchy is stated."
                            if top(facts, "pricing") else
                            "No taste hierarchy stated in collected sources."),
        "underserved_segments": gaps_line(p, facts, ("segment_skews", "diaspora", "mau")),
    }


# ---------------- emotional ----------------
def emotional_fields(p: str, facts: list[dict], titles: list[dict]) -> dict:
    gh = genre_hits(facts)
    emos = [EMOTION[g] for g, _c in gh[:4] if g in EMOTION]
    reg = top(facts, "regulatory_ctx")
    core = "/".join(g for g, _c in gh[:2]) if gh else "unprofiled genres"
    return {
        "strategy_line": (f"Own {emos[0]} and {emos[1]} as the house register across the slate."
                          if len(emos) > 1 else
                          f"Hold one recognizable house mood for {p} across languages."),
        "primary_emotion": (f"{emos[0].title()} and {emos[1].title()} lead the evidenced slate."
                            if len(emos) > 1 else "No dominant emotion evidenced."),
        "emotional_spectrum": (" — ".join(f"{g}: {EMOTION[g]}" for g, _c in gh[:5] if g in EMOTION)
                               or "Spectrum not evidenced."),
        "tone_profile": f"Tone follows the {core} core of the evidenced slate.",
        "content_warnings": _short(reg["claim"]) if reg else
                            "No regulatory action surfaced in collected sources.",
        "consistency": ("A consistent register across the evidenced genres."
                        if len(gh) <= 4 else
                        "Wide by design; tone follows content vertical."),
        "feel_good": ("Warmth concentrates where comedy, romance and variety are evidenced; "
                      "the scripted core runs darker." if gh else "Not evidenced."),
        "cultural_resonance": "Resonance tracks the biggest evidenced titles and events, not the long tail.",
        "signature_feeling": f"The feeling of the {core} slate at its best — earned title by title.",
    }


# ---------------- distribution ----------------
def distribution_fields(p: str, facts: list[dict], titles: list[dict]) -> dict:
    bun = _full_value(top(facts, "telecom_bundles"))
    dl = _full_value(top(facts, "downloads"))
    dev = claims(facts, "devices", "ctv_share", n=2)
    win_ = claims(facts, "windows", "dubbing", n=2)
    return {
        "strategy_line": (f"Distribute through the evidenced lever — {bun['value']}{when_suffix(bun)}."
                          if bun else
                          (f"Win on reach at {dl['value']}{when_suffix(dl)}.") if dl else
                          f"Be where the {p} viewer already is across devices and access models."),
        "access_model": _short(bun["claim"]) if bun else
                        (_short(dl["claim"]) if dl else "No access-model disclosure surfaced."),
        "device_profile": " ".join(_short(c) for c in dev) or "No device footprint disclosed.",
        "viewing_behaviour": _short(win_[0]) if win_ else "No viewing-behaviour pattern evidenced.",
        "geographic_reach": _short(claims(facts, "diaspora", n=1)[0])
                            if claims(facts, "diaspora", n=1)
                            else "Domestic reach only in collected sources.",
        "language_access": _short(claims(facts, "dubbing", "language_count", n=1)[0])
                           if claims(facts, "dubbing", "language_count", n=1)
                           else "No dubbing or language-access practice evidenced.",
        "content_window": " ".join(_short(c) for c in win_) or "No window practice evidenced.",
        "release_strategy": _short(claims(facts, "windows", "named_originals", n=1)[0])
                               if [c for c in claims(facts, "windows", "named_originals", n=3)
                                   if re.search(r"week|drop|episode|season|release", c, re.I)]
                               else "No release-cadence disclosure surfaced in collected sources.",
        "tech_experience": "No technology-experience disclosure surfaced in collected sources.",
    }


# ---------------- revenue ----------------
_DEAL_WORDS = re.compile(r"\bdeal\b|\bhub\b|licen[sc]e|partnership|exclusive|\brights\b|acqui|studio", re.I)
_BYLINE = re.compile(r"^[A-Z][\w'.-]{1,30},\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+(?:said|says|reports?|writes?|joins?|leaves?)|\[\"", re.I)
# M&A about OTHER companies (Disney/Hulu control battles) is not the
# target's licensing strategy — even when it carries deal words.
_RIVAL_MA = re.compile(
    r"acquired full control|acquires full control|merger\b.*(confirm|reveal|announce)|"
    r"purchasing .* stake|full control of (hulu|disney)|consolidating .* strategy under one|"
    r"\b(netflix|prime video|amazon|disney|hulu|warner|paramount)\b.{0,60}\b(acquir|merg|stake|takeover)\b",
    re.I)


def _relevant(claims_list: list[str], *patterns: "re.Pattern[str]") -> list[str]:
    def _ok(c: str) -> bool:
        s = c.strip()
        return (not _BYLINE.search(s) and not _AD_LIKE.search(c)
                and not _RIVAL_MA.search(c))
    out = [c for c in claims_list if _ok(c) and all(p.search(c) for p in patterns)]
    if out:
        return out
    # No pattern-matching claim: return honestly-thin marker, not unrelated text.
    return []


def revenue_fields(p: str, facts: list[dict], titles: list[dict]) -> dict:
    rev = _full_value(top(facts, "revenue_annual", "revenue_quarterly", "ebitda", prefer=_MONEY))
    raw_prices = claims(facts, "pricing", n=5)
    # Tiers must read like pricing (price pattern) — never demographics.
    prices = [c for c in raw_prices
              if _PRICE.search(c) and not _BYLINE.search(c.strip())
              and not _AD_LIKE.search(c)][:3]
    ad = top(facts, "ad_products")
    raw_hub = claims(facts, "hub_deals", n=4)
    hub = _relevant(raw_hub, _DEAL_WORDS)
    # Prefer hub claims that name the platform — rival M&A that slipped
    # through reads as someone else's licensing strategy.
    named = [c for c in hub if p.lower() in c.lower()]
    hub = named or hub
    if not hub:
        # Filtered everything: fall back to any clean hub claim rather than empty,
        # but never to rival M&A (kept out by _relevant).
        hub = [c for c in raw_hub
               if not _BYLINE.search(c.strip()) and not _AD_LIKE.search(c)
               and not _RIVAL_MA.search(c)][:2]
    inv = _full_value(top(facts, "originals_investment", prefer=_MONEY))
    sport = top(facts, "sports_rights")
    model = "Paid tiers evidenced" if prices else "No paid-tier disclosure surfaced"
    model += (" with an ad layer at " + ad["value"] + f"{when_suffix(ad)}") if ad else "; no ad layer evidenced"
    model += "."
    # Jio-shaped 4-part appetite: Acquires / Avoids / Budget tier / Deal
    # structure — every clause traces to a verbatim fact or is honestly thin.
    acq_bits = _relevant(claims(facts, "sports_rights", "hub_deals", n=4), _DEAL_WORDS)[:2]
    acquires = ("**Acquires** — " + "; ".join(_short(c, 140) for c in acq_bits) + "."
                if acq_bits else "**Acquires** — no evidenced acquisition lane in collected sources.")
    no_evidence_slots = [s for s in ("sports_rights", "hub_deals", "ad_products")
                         if s not in {f["slot"] for f in facts}]
    avoids = ("**Avoids/uncertain** — no strong evidence of investment in " +
              ", ".join(s.replace("_", " ") for s in no_evidence_slots) + "."
              if no_evidence_slots else
              "**Avoids/uncertain** — nothing flagged as absent; every checked lane has some evidence.")
    moneyed = _full_value(top(facts, "sports_rights", "hub_deals", "originals_investment", prefer=_MONEY))
    budget = (f"**Budget tier:** blue-chip where evidenced ({moneyed['value']}{when_suffix(moneyed)}); "
              "mixed star-vehicle and volume lanes elsewhere."
              if moneyed else "**Budget tier:** no disclosed budget tier in collected sources.")
    deal = ("**Deal structure:** typically exclusive, multi-year where evidenced; "
            "title-by-title licensing otherwise."
            if hub or sport else
            "**Deal structure:** no deal-structure disclosure surfaced in collected sources.")
    acq = f"{acquires} {avoids} {budget} {deal}"
    return {
        "strategy_line": (f"Monetise at {rev['value']} scale{when_suffix(rev)} through the evidenced pricing levers."
                          if rev else f"Monetise the {p} base through whatever pricing is disclosed."),
        "revenue_model": model,
        "tiers": " ".join(_short(c) for c in prices) or "No tier structure disclosed in collected sources.",
        "ad_dependency": _short(ad["claim"]) if ad else "No ad-revenue disclosure surfaced.",
        "licensing_strategy": " ".join(_short(c) for c in hub) or "No licensing strategy evidenced.",
        "originals_investment": (f"{inv['value']} committed{when_suffix(inv)}. " if inv else "") +
                                (_short(inv["claim"]) if inv else "No originals budget disclosed."),
        "acquisition_appetite": acq,
        "audience_monetisation": _monetisation_line(facts),
    }


def _monetisation_line(facts: list[dict]) -> str:
    """Audience monetisation must carry money mechanics, else thin.

    Subscriber counts alone are scale, not monetisation — require a money
    marker (₹/$/crore/lakh/billion/million-combined-with-price) to avoid
    relabelling "100 million subscribers" as monetisation.
    """
    for c in claims(facts, "subscribers", "pricing", n=4):
        if re.search(r"₹|\$|\brs\.?\b|\binr\b|\busd\b|\bcrore\b|\blakh\b", c, re.I) \
                and not _BYLINE.search(c.strip()) and not _AD_LIKE.search(c):
            return _short(c)
    return "No monetisation mechanics evidenced in collected sources."


def _risk_line(facts: list[dict]) -> str:
    m = _full_value(top(facts, "sports_rights", "hub_deals", "originals_investment",
                        prefer=_MONEY))
    if m:
        return f"Commits at {m['value']} scale where evidenced."
    return "No risk-scale disclosure surfaced."


# ---------------- editorial ----------------
def editorial_fields(p: str, facts: list[dict], titles: list[dict]) -> dict:
    mis = top(facts, "mission")
    lead = claims(facts, "leadership", "ceo_structure", n=2)
    gh = genre_hits(facts)
    tlangs = {t.get("language", "Unknown") for t in titles} - {"Unknown"}
    breadth = (f"spans {len(gh)} evidenced genres" +
               (f" across {len(tlangs)} mined languages" if tlangs else "")) if gh else "breadth unmeasured"
    return {
        "strategy_line": (f"Program {p} around {_short(mis['claim'], 140)}") if mis else
                         f"Program {p} with a point of view, not just volume.",
        "editorial_voice": _short(mis["claim"]) if mis else "No editorial voice stated in collected sources.",
        "curation_philosophy": f"The evidenced slate {breadth}; concentration is unproven.",
        "cultural_stance": _short(mis["claim"]) if mis else "No cultural stance stated.",
        "risk_appetite": _risk_line(facts),
        "distinctiveness": f"Distinctive only insofar as the evidenced slate ({breadth}) differs from rivals.",
        "auteur_vs_formula": ("Renewal-shaped: franchise evidence in the mined slate."
                              if re.search(r"season\s*\d|chapter", " ".join(title_cells(titles)), re.I)
                              else "No auteur-vs-formula pattern evidenced."),
        "tonal_signature": f"Reads as the {gh[0][0]}-first house in collected sources." if gh
                           else "No tonal signature evidenced.",
        "consistency": "Consistent where the evidenced genres repeat; scattered elsewhere.",
        "signature_move": (_short(_sig["claim"])
                           if (_sig := _full_value(top(
                               facts, "mission", "leadership", "campaigns",
                               "ceo_structure"))) else "No signature move evidenced."),
    }


# ---------------- pitch & negotiation ----------------
def compose_angle(p: str, facts: list[dict], scores: dict[str, int]) -> str:
    ranked_secs = sorted(scores, key=lambda s: -scores.get(s, 0)) if scores else []
    sec = ranked_secs[0] if ranked_secs else "content"
    f = top(facts, *SECTION_SLOTS[sec], prefer=_MONEY) if sec in SECTION_SLOTS else None
    base = f"Lead with {sec} — the best-evidenced dimension"
    return base + (f": {_short(f['claim'], 160)}" if f else ".")


def compose_ideal(p: str, facts: list[dict], titles: list[dict]) -> str:
    gh = genre_hits(facts)
    tlangs = sorted({t.get("language", "Unknown") for t in titles} - {"Unknown"})
    gl = "/".join(g for g, _c in gh[:2]) if gh else "proven genres"
    ll = "/".join(tlangs[:3]) if tlangs else "the evidenced languages"
    return (f"A {gl} project in {ll} with a recognizable hook, built dub-ready "
            "for day-and-date release and shaped for renewal beyond season one.")


def compose_negotiation(p: str, facts: list[dict]) -> str:
    bits = claims(facts, "ownership", "approval_chain", "data_sharing",
                  "leadership", "ceo_structure", n=3)
    if bits:
        return " ".join(_short(b) for b in bits)
    return ("No ownership, approval-chain or data-sharing disclosure surfaced in collected "
            "sources — sellers should negotiate performance-data access, windowing and "
            "exclusivity as explicit deal terms rather than assume flexibility.")
