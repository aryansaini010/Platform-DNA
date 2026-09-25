"""Fact extraction (plan Step B): Firecrawl markdown -> slot-tagged facts.

Rule-based ("cheap LLM" substitute): keeps sentences carrying dated, sourced
figures — money, percents, subscriber/user counts, title announcements — and
classifies them into the report's SLOT checklist. Output dicts plug straight
into Fact / the fact-pack schema, so every figure the writer uses traces to
a stored source (validator grounding holds).

If ANTHROPIC_API_KEY is set, `llm_refine()` can polish claims; it is never
required and never invents figures.
"""
from __future__ import annotations

import os
import re
from urllib.parse import urlparse

# ---- figure patterns (ordered: money > percent > counts > dates) ----
INR = (r"(?:₹|Rs\.?|INR)\s?[\d,]+(?:\.\d+)?(?:\s?(?:crore|lakh|cr\b|L\b|bn\b|billion|mn\b|million))?"
       r"|\b[\d,]+(?:\.\d+)?\s?(?:crore|lakh)\b")
USD = r"(?:\$|USD)\s?[\d,]+(?:\.\d+)?(?:\s?(?:bn\b|billion|mn\b|million|trillion|m\b|b\b))?"
PCT = r"\d[\d,.]*\s?%"
COUNT = (r"\d[\d,.]*(?:\.\d+)?\s?(?:million|billion|thousand|lakh|crore)?"
         r"\s?(?:paid\s+)?(?:subscriber|member|user|download|title|show|episode|"
         r"season|hour|language|original|viewer|vote|chat|advertiser|country|"
         r"screen|device)s?\b")
DATE = (r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}"
        r"|\bQ[1-4]\s+FY\d{2,4}\b|\bFY\d{2,4}\b|\bH[12]\s*[-']?\s*20\d{2}\b|\bH[12]\s+20\d{2}\b")

FIGURE = re.compile(f"({INR}|{USD}|{PCT}|{COUNT})", re.IGNORECASE)
_MONEYS_RE = re.compile(f"({INR}|{USD})", re.IGNORECASE)
DATE_RE = re.compile(f"({DATE})")
# Note: "Rs." abbreviation must not split sentences ("Rs. 149 per month").
# We split then re-join fragments ending with known abbreviations (see _split_sentences).
SENT_SPLIT = re.compile(r"\n+|(?<=[.!?])\s+(?=[A-Z0-9\"'])")
# Tail abbreviations + decimal fragments ("U.S.", "No.", "5.") rejoin with
# the next fragment instead of splitting mid-figure.
_ABBREV_TAIL = re.compile(
    r"(?:\b(?:Rs|Mr|Mrs|Ms|Dr|St|Jr|Sr|vs|etc|e\.g|i\.e|No|Fig|U\.S)\.?|(?<=\d)\.)$",
    re.I)


def _split_sentences(text: str) -> list[str]:
    parts = SENT_SPLIT.split(text)
    merged: list[str] = []
    for p in parts:
        if merged and _ABBREV_TAIL.search(merged[-1].strip()):
            merged[-1] = merged[-1] + " " + p
        else:
            merged.append(p)
    return merged

# ---- slot rules: first match wins (order matters) ----
SLOT_RULES: list[tuple[str, list[str]]] = [
    ("sports_rights", ["ipl", "icc", "cricket", "wpl", "bcci", "sports rights", "premier league", "hundred", "sa20", "bbl"]),
    ("pricing", ["per month", "/month", "/quarter", "/year", "price", "plan", "tier", "subscription fee", "rs."]),
    ("revenue_annual", ["revenue", "turnover", "pbt", "ebitda", "net income", "net profit", "profit after tax", "operating margin", "fiscal", "crore", "lakh crore"]),
    ("subscribers", ["subscriber", "paid member", "paid user", "membership", "paying"]),
    ("mau", ["mau", "monthly active", "active user", "user base", "daily active"]),
    ("share_trends", ["market share", "% share", "share of", "justwatch", "ormax", "chrome ott", "svod"]),
    ("content_hours", ["hours of content", "content hours", "lakh hours", "library spans", "catalogue", "catalog spans"]),
    ("language_count", ["languages"]),
    ("originals_investment", ["invest", "commit", "fund", "slate", "ecosystem", "creator"]),
    ("hub_deals", ["hub", "licensing", "partnership", "exclusive", "deal", "acqui", "streaming rights"]),
    ("downloads", ["download", "play store", "app store", "install"]),
    ("telecom_bundles", ["recharge", "bundl", "prepaid plan", "postpaid"]),
    ("devices", ["connected tv", "ctv", "smart tv", "devices", "screens"]),
    ("windows", ["theatrical", "day-and-date", "window", "streaming from", "ott release", "premiere"]),
    ("ad_products", ["advertis", "ad revenue", "sponsor", "commerce", "brand partner"]),
    ("named_originals", ["season", "series", "original", "renewed", "show", "film", "movie", "episode", "starring", "directed"]),
    ("ownership", ["stake", "joint venture", "merger", "acquisition", "ownership"]),
    ("leadership", ["ceo", "appoint", "heads", "joins", "named ", "vice president", "president"]),
    ("mission", ["mission", "vision", "accessible", "initiative", "possibilities"]),
    ("campaigns", ["campaign", "marketing", "launch event", "brand"]),
    ("regulatory_ctx", ["it rules", "mib", "ministry of information", "ban", "takedown", "regulation", "self-regulation", "code of ethics"]),
    ("approval_chain", ["approval", "sign-off", "greenlit", "commission"]),
    ("data_sharing", ["performance data", "transparency", "viewership data", "shared with"]),
]

TIER1_DOMAINS = ("netflix.com", "about.netflix", "ir.netflix", "help.netflix",
                 "jiohotstar.com", "jio.com", "reliance", "jiostar",
                 "primevideo.com", "amazon.in", "amazon.com", "zee5.com", "sonyliv.com",
                 "hotstar.com", "disney", "disneyplus.com", "investor.disney",
                 "thewaltdisneycompany.com")
TIER2_DOMAINS = ("storyboard18", "exchange4media", "afaqs", "ormaxmedia",
                 "variety.com", "hollywoodreporter", "deadline.com",
                 "economictimes", "business-standard", "livemint",
                 "medianews4u", "pitchonnet", "thehindu", "indianexpress",
                 "hindustantimes", "tribuneindia",
                 "timesofindia", "techobserver", "communicationstoday",
                 "justwatch.com", "the-ormax", "ormax")


def infer_tier(url: str) -> int:
    try:
        host = urlparse(url or "").netloc.lower().split(":")[0]
    except Exception:
        return 3
    if not host:
        return 3
    for d in TIER1_DOMAINS:
        d = d.lower()
        if host == d or host.endswith("." + d):
            return 1
    for d in TIER2_DOMAINS:
        d = d.lower()
        if host == d or host.endswith("." + d):
            return 2
    return 3


def _clean_text(md: str) -> str:
    md = re.sub(r"<[^>]{1,60}>", " ", md)                      # html tags
    md = re.sub(r"!\[[^\]]*\]\s*(?:\([^)]*\))?", "", md)    # images (with or w/o target)
    md = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", md)      # links -> label BEFORE
    # leftover-(url) strip: otherwise "[label](https://…)" degrades to
    # "[label] " and the label is lost
    md = re.sub(r"\(https?://[^)]*\)", " ", md)                # leftover (url) groups
    md = re.sub(r"https?://\S+", " ", md)                      # bare URLs (source stored separately)
    md = re.sub(r"\(?mailto:[^)\]]*\)?", " ", md)              # mailto share links
    md = re.sub(r"Subject=[^\n\"']{0,300}", " ", md)           # URL-encoded share blobs
    md = re.sub(r"Share via Email", " ", md, flags=re.I)
    md = re.sub(r"\[\s*\]\([^)]+\)", " ", md)                  # share-button stubs (before bare [])
    md = re.sub(r"\[\s*\]", " ", md)                           # empty [] stubs left behind
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'),
                 ("—", "-"), ("–", "-"), ("•", "*"), (" ", " ")):
        md = md.replace(a, b)
    md = re.sub(r"\[#{1,6}\s*", " ", md)                       # [###### headline] residue
    md = md.replace("\\[", "[").replace("\\]", "]")           # unescape brackets
    md = re.sub(r"\[\[\d+\]\]", " ", md)                       # [[2]] cite residue
    md = re.sub(r"\[citation needed\]", " ", md, flags=re.I)
    md = re.sub(r"^#{1,6}\s+", "", md, flags=re.M)          # headings
    md = re.sub(r"^>\s?", "", md, flags=re.M)                 # blockquote markers
    md = re.sub(r"\\\s", " ", md)                              # trailing-`\` fragments
    md = re.sub(r"\\", " ", md)
    md = re.sub(r"[*_]{1,3}", "", md)                        # emphasis
    md = re.sub(r"^\s*\|", "", md, flags=re.M)               # table pipes
    md = re.sub(r"\|+", " ", md)
    md = re.sub(r"[ \t]+", " ", md)
    return md


# Sentences matching any of these are ads, trackers, directories or page
# furniture — never facts, even on target-about pages.
AD_PATTERNS = (
    "only on amazon", "check exchange deal", "bank offers", "big billion days",
    "sale early deals", "is available for rs", "is available for $",
    "price tracker", "compare prices", "emi starts", "no cost emi",
    "vivo buds", "oneplus 12", "mcdonald", "atomberg", "lipcenter", "lpcenter",
    "according to ormax", "to devices (", "streaming on up to (according",
    "cinema tickets can be cancelled", "refund policy",
)
DIRECTORY_PATTERNS = (
    "active competitors", "that have exited", "acquired subscription-based",
    "acquired provider of on-demand", "acquired online video",
    "santa monica ([united states]", "san francisco ([united states]",
    "shanghai ([china]", "75/100", "74/100", "70/100",
)
TABLE_HEADER = re.compile(
    r"^(title\s+episodes?\s+genre|title\s+episodes?\s+genre\s+premiere|"
    r"genre\s+premiere\s+date\s+language|premiere\s+date\s+language)",
    re.IGNORECASE)


# Wikipedia reference-desk rows, FAQ residue and bracket-dense table rows
# are page furniture, never facts ("Goldsmith, Jill (February 27, 2026).
# ["Massive Merger..."]", "Ans: HBO Max has...", "[Title] [genre] [date]
# 1 season, 10 episodes").
REF_ROW = re.compile(
    r"^[A-Z][\w'.-]{1,30},\s+[A-Z][\w'.-]{1,30}\s+\(|^\[\"|^\"\s*[A-Z]")
FAQ_RESIDUE = re.compile(r"^(ans|q)\s*:", re.IGNORECASE)


def _is_junk_sentence(sent: str) -> bool:
    low = sent.lower()
    if "mailto:" in low or "%20" in sent or "share via email" in low:
        return True
    if TABLE_HEADER.match(sent.strip()):
        return True
    if REF_ROW.match(sent.strip()) or FAQ_RESIDUE.match(sent.strip()):
        return True
    if sent.count("[") >= 3 and re.search(r"\bseason\b|\bepisodes?\b", low) \
            and not re.search(r"announced|renewed|premieres?|starring|renewal", low):
        return True
    if any(p in low for p in AD_PATTERNS):
        return True
    if any(p in low for p in DIRECTORY_PATTERNS):
        return True
    # unbalanced leftovers: more closers than openers, or dangling fragments
    if sent.count(")") > sent.count("(") + 1 or sent.count("]") > sent.count("[") + 2:
        return True
    if re.search(r"\b(logo for|acquired provider|acquired online)\b", low):
        return True
    return False


NAV_SKIP = re.compile(
    r"list of programs broadcast|jump to content|^main page$|recent changes|"
    r"random article|edit (source|this page)|^talk\b|\btalk page|what links here|"
    r"skip to (content|navigation|search)|cookie|newsletter signup|all rights reserved",
    re.IGNORECASE)


def _value_unit(sentence: str) -> tuple[str, str]:
    # NOTE: INR/USD patterns must match case-insensitively ("$110 Billion",
    # "$555.00M") or values truncate to bare "$110" / "$555.00".
    m = re.search(INR, sentence, re.IGNORECASE)
    if m:
        v = m.group(0)
        if re.search(r"crore|\bcr\b", v, re.I):
            return v, "crore INR"
        if re.search(r"lakh|\bL\b", v):
            # \bL\b case-sensitive: lowercase l would false-match inside words
            return v, "lakh INR"
        if re.search(r"lakh", v, re.I):
            return v, "lakh INR"
        if re.search(r"million|\bmn\b", v, re.I):
            return v, "million INR"
        if re.search(r"billion|\bbn\b|\bb\b", v, re.I):
            return v, "billion INR"
        return v, "INR"
    m = re.search(USD, sentence, re.IGNORECASE)
    if m:
        v = m.group(0)
        if re.search(r"trillion", v, re.I):
            return v, "trillion USD"
        if re.search(r"billion|\bbn\b|\bb\b", v, re.I):
            return v, "billion USD"
        if re.search(r"million|\bmn\b|\bm\b", v, re.I):
            return v, "million USD"
        return v, "USD"
    m = re.search(PCT, sentence)
    if m:
        return m.group(0), "percent"
    m = re.search(COUNT, sentence, re.IGNORECASE)
    if m:
        v = m.group(0)
        unit = "count"
        for w in ("subscriber", "member", "user", "download", "title", "show",
                  "episode", "season", "hour", "language", "original", "viewer",
                  "vote", "chat", "advertiser", "country", "screen", "device"):
            if re.search(w, v, re.I):
                unit = w + "s"
                break
        if re.search(r"million", v, re.I):
            unit = "million " + unit if unit != "count" else "million"
        elif re.search(r"billion", v, re.I):
            unit = "billion " + unit if unit != "count" else "billion"
        return v, unit
    return "", ""


def _slot(sentence: str) -> str:
    low = sentence.lower()
    for slot, keys in SLOT_RULES:
        if any(k in low for k in keys):
            if slot == "pricing" and not re.search(
                    r"₹|\$|\brs\.?(?!\w)|price|/month|per month|subscription|tier|inr|usd",
                    low):
                # "media plan" / "business plan" sentences are not pricing.
                continue
            return slot
    # Table-row fallback: price tables lose their header context when pipes
    # are stripped ("Monthly ₹149 Full Library 1 30 Days" carries no word
    # "price"/"plan"), so money + tenure words imply pricing. Guarded against
    # MAU confusion ("monthly active users" has no ₹/$/Rs figure).
    if re.search(r"₹|\$|\brs\.?(?!\w)", sentence, re.I) and re.search(
            r"monthly|annual|yearly|quarterly|per month|per year|/month|/year|"
            r"\bdays?\b|validity|tenure|subscription", low):
        return "pricing"
    return "general"


def names_target_check(slow: str, name_pairs: list[tuple[str, str]]) -> bool:
    snorm = re.sub(r"[^a-z0-9]", "", slow)
    for n, nn in name_pairs:
        if len(nn) >= 5:
            if (n in slow) or (nn in snorm):
                return True
        # Short aliases ("aha", "zee5") must match standalone, never inside
        # other words ("maharaja", "heroes" must not attach).
        elif re.search(r"\b" + re.escape(n) + r"\b", slow):
            return True
    return False


def extract_facts(markdown: str, source_url: str,
                 source_date: str = "date unknown",
                 max_facts: int = 60, platform: str = "",
                 aliases: tuple[str, ...] = ()) -> list[dict]:
    """Return slot-tagged fact dicts, money/% first, deduped.

    When `platform`/`aliases` are given, company-specific slots (revenue,
    pricing, subscribers, …) must name the target — otherwise a stray page
    about another firm pollutes the fact store. Comparison slots
    (share_trends, regulatory_ctx, general, genre_mix) are exempt: rival
    mentions there are the point.
    """
    if not markdown or len(markdown.strip()) < 80:
        return []
    names = [a.lower() for a in ((platform,) + tuple(aliases)) if a]
    # normalized (spaceless) forms: "Jio Hotstar" still matches "JioHotstar",
    # "Disney+ Hotstar" matches "Disney Hotstar".
    name_pairs = [(n, re.sub(r"[^a-z0-9]", "", n)) for n in names]
    strict = bool(name_pairs)
    # Company-attributed metrics must name the target — except on the
    # platform's own official pages (tier 1), which are inherently about it.
    # Descriptive and comparison slots stay lenient everywhere.
    STRICT_SLOTS = {"revenue_annual", "revenue_quarterly", "ebitda", "pricing",
                    "subscribers", "mau", "downloads", "telecom_bundles",
                    "ad_products"}
    tier = infer_tier(source_url)
    text = _clean_text(markdown)
    # Page-level aboutness: table rows on a page about the platform
    # (".../hoichoi-subscription-price-plans-...") omit the platform name in
    # every row, so the sentence-level strict filter below would drop them
    # all. If the URL slug or page head names the target, rows that mention
    # neither the target nor a rival are still the target's.
    _RIVALS = ("netflix", "prime video", "amazon prime", "hotstar", "jiohotstar",
               "jiostar", "jio star", "jiocinema", "zee5", "sonyliv", "sony liv",
               "altbalaji", "mx player", "hoichoi", "aha video", "sunnxt",
               "chaupal", "stage", "ullu", "eros", "voot", "shemaroo", "discovery")
    page_norm = re.sub(r"[^a-z0-9]", "", source_url.lower())
    head_norm = re.sub(r"[^a-z0-9]", "", text[:1500].lower())
    page_raw = (source_url + " " + text[:1500]).lower()
    page_about_target = strict and any(
        nn and ((len(nn) >= 5 and (nn in page_norm or nn in head_norm))
                or re.search(r"\b" + re.escape(n) + r"\b", page_raw))
        for n, nn in name_pairs)
    seen: set[str] = set()
    scored: list[tuple[int, dict]] = []
    for sent in _split_sentences(text):
        sent = sent.strip().strip("-•* ").strip()
        if len(sent) < 40 or len(sent) > 600:
            continue
        figs = FIGURE.findall(sent)
        slot = _slot(sent)
        # financial-table rows ("EPS in Rs 15.05 19.19 …", "OPM % 5.07% …")
        # are number soup, not facts — drop figure-dense sentences. Pricing
        # tables are exempt: multi-price rows ("Rs 149, 299, 499, 649") are
        # legitimately digit-dense.
        digits = len(re.sub(r"\D", "", sent))
        if slot != "pricing" and (len(figs) > 6 or len(re.findall(r"\d+\.\d+", sent)) >= 5
                or (len(sent) > 0 and digits / len(sent) > 0.35)):
            continue
        has_title_signal = bool(re.search(
            r"season|renewed|premiere|announced|starring|original series|"
            r"\bfilm\b|\bmovie\b|episode|directed", sent, re.I))
        if not figs and not has_title_signal:
            continue
        if re.match(r"^(skip|menu|search|login|sign in|subscribe|follow|share|read more|"
                     r"advertisement|cookie)", sent, re.I):
            continue
        if NAV_SKIP.search(sent):
            continue
        if _is_junk_sentence(sent):
            continue
        if slot == "general" and not figs:
            continue
        # Non-comparison slots must stay on-topic: drop sentences dense
        # with rival names (directory rows, listicles) unless the slot is
        # inherently comparative. Rival mentions are counted longest-match
        # first so "JioHotstar" is one hit, not two ("jiohotstar"+"hotstar").
        if slot not in ("share_trends", "regulatory_ctx", "general", "genre_mix"):
            slow_cmp = sent.lower()
            _masked = slow_cmp
            rival_hits = 0
            for _r in sorted(_RIVALS, key=len, reverse=True):
                if _r in _masked:
                    rival_hits += 1
                    _masked = _masked.replace(_r, " ")
            if rival_hits >= 2 and not names_target_check(slow_cmp, name_pairs):
                continue
        # Company-attributed metrics must name the target — including on
        # tier-1 official pages, which are only exempt when the whole page
        # is about the target (a wrong-platform official page, e.g. a
        # JioHotstar page scraped for Disney+, gets full strict treatment).
        if strict and slot in STRICT_SLOTS and (tier != 1 or not page_about_target):
            slow = sent.lower()
            snorm = re.sub(r"[^a-z0-9]", "", slow)
            names_target = any((n in slow) or (nn in snorm) for n, nn in name_pairs)
            if not names_target:
                # Rival rows on comparison pages ("Netflix Rs 199-649 ...")
                # must never attach to the target, even on target-about pages.
                if any(r in slow for r in _RIVALS):
                    continue
                # Otherwise keep the fact only if the whole page is about
                # the target (table rows that omit the name per-row).
                if not page_about_target:
                    continue
        value, unit = _value_unit(sent)
        key = (slot, re.sub(r"\W+", "", (value or "").lower()),
               re.sub(r"\W+", "", sent.lower()))
        if key in seen:
            continue
        seen.add(key)
        has_date = bool(DATE_RE.search(sent)) or source_date != "date unknown"
        score = (3 if _MONEYS_RE.search(sent) else 0) + (2 if re.search(PCT, sent) else 0) \
            + (1 if figs else 0) + (1 if has_date else 0)
        # Cut at a word boundary; never leave bracket/quote fragments open.
        # Keep the extracted value inside the claim so validator grounding holds.
        if len(sent) <= 320:
            claim = sent
        else:
            cut = sent.rfind(" ", 0, 300)
            cut = cut if cut > 200 else 300
            if value:
                pos = sent.lower().find(value.lower())
                if pos != -1 and pos + len(value) > cut:
                    # Extend to include the full value plus a word boundary
                    end = sent.find(" ", pos + len(value))
                    cut = end if end != -1 and end <= 400 else pos + len(value)
            claim = sent[:cut].rstrip(" ([{'\"") + "..."
        scored.append((score, {
            "slot": slot, "claim": claim, "value": value, "unit": unit,
            "source_url": source_url, "source_date": source_date,
            "tier": tier,
            "confidence": "high" if score >= 4 else ("medium" if score >= 2 else "low"),
            "metric": "",
        }))
    scored.sort(key=lambda x: -x[0])
    # Near-dupe collapse: same slot + same normalized figure + same date
    # keeps one; different dates are distinct (time-series preserved for
    # conflict detection). Empty values never collapse.
    deduped: list[dict] = []
    seen_val: set[tuple] = set()
    for _, f in scored:
        if f["value"]:
            vkey = (f["slot"], re.sub(r"\W+", "", (f["value"] or "").lower()),
                    re.sub(r"\W+", "", (f.get("unit") or "").lower()),
                    (f.get("source_date") or "date unknown"))
            if vkey in seen_val:
                continue
            seen_val.add(vkey)
        deduped.append(f)
        if len(deduped) >= max_facts:
            break
    return deduped


def slot_counts(facts: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for f in facts:
        out[f["slot"]] = out.get(f["slot"], 0) + 1
    return dict(sorted(out.items(), key=lambda x: -x[1]))


def llm_refine(facts: list[dict]) -> list[dict]:
    """Optional wording polish. No-op without ANTHROPIC_API_KEY; never adds figures."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return facts
    return facts
