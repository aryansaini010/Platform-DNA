"""Structured generation (plan §4 Steps 4-6).

Order: content → audience → emotional → distribution → revenue → editorial →
overall summary + risk tag → positioning → wishlist → pitch → identity.
Top-of-report is written last (depends on finished sections).

Deterministic mode (default): assembles the report JSON from the verified
fact-pack. Evidence paragraphs are built from dated fact claims so every
figure traces to the store. If ANTHROPIC_API_KEY is set, `polish()` can be
used for wording only — it must never invent figures (validator enforces).
"""
from __future__ import annotations

import os
import re
from urllib.parse import urlparse

from .config import SAMPLING_THRESHOLD, SECTION_SLOTS
from .facts import Fact, detect_conflicts, mark_staleness
from .scores import overall
from .titles import compute_stats, header_sentence

SECTIONS = ["content", "audience", "emotional", "distribution", "revenue", "editorial"]


def _nice_date(iso: str) -> str:
    if not iso or not isinstance(iso, str):
        return iso
    m = re.match(r"^(\d{4})-(\d{2})(?:-(\d{2}))?", iso.strip())
    if m:
        try:
            months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            mo = int(m.group(2))
            if 1 <= mo <= 12:
                return "%s %s" % (months[mo], m.group(1))
        except Exception:
            pass
    return iso


EVIDENCE_MAX = 10


def _ev(facts: list[Fact], src_index: dict[str, int], *slots: str) -> str:
    """Tight Jio-style evidence paragraph: top-ranked claims only.

    Top 10 by source tier (then claim depth), joined as flowing prose —
    never a 100-bullet dump. Each claim carries a citation marker [n]
    pointing at the SOURCES list. Undated sources show no date at all
    (never the raw "date unknown" placeholder).
    """
    cands = [f for f in facts if f.slot in slots]
    # Rank by tier, then confidence, then claim depth (not length alone —
    # table soup is long but low-confidence).
    _conf_rank = {"high": 0, "medium": 1, "low": 2}
    cands.sort(key=lambda f: (f.tier, _conf_rank.get(f.confidence, 2), -len(f.claim)))
    bits = []
    for f in cands[:EVIDENCE_MAX]:
        # Authentic look: omit the date entirely when undisclosed.
        date = ""
        if f.source_date and f.source_date != "date unknown":
            date = f" ({_nice_date(f.source_date)})"
        flag = ""
        if "CONFLICT" in f.flags:
            flag = " [conflicting accounts — both reported, not resolved]"
        elif "STALE" in f.flags:
            flag = " [may be stale — source >18 months old]"
        cite = f" [{src_index[f.source_url]}]" if f.source_url in src_index else ""
        claim = f.claim.rstrip()
        if claim and not claim.endswith((".", "!", "?", "…")):
            claim += "."
        bits.append(f"• {claim}{date}{flag}{cite}")
    # Newline-joined bullets: single newlines collapse to spaces in Markdown
    # rendering, while dashboard/HTML views can split scannable lines.
    text = "\n".join(bits)
    if len(cands) > EVIDENCE_MAX:
        text += (f" ({len(cands) - EVIDENCE_MAX} further sourced claims "
                 "held in the fact store.)")
    return text if text else "No disclosed figure found in sourced material — treated as not disclosed."


def _repair_values(facts: "list[Fact]") -> None:
    """Heal truncated money values from old packs (see facts.repair_value)."""
    from .facts import repair_value
    for f in facts:
        f.value = repair_value(f.value, f.claim)


def build_report(pack: dict) -> dict:
    platform: str = pack.get("platform", "")
    if not platform:
        raise ValueError("pack.platform is required")
    region: str = pack.get("region", "India") or "India"
    facts: list[Fact] = []
    for f in pack.get("facts", []) or []:
        if not isinstance(f, dict):
            continue
        try:
            known = {k for k in Fact.__dataclass_fields__}
            facts.append(Fact(**{k: v for k, v in f.items() if k in known}))
        except Exception:
            continue
    _repair_values(facts)
    for f in facts:
        mark_staleness(f)
    conflicts = detect_conflicts(facts)
    titles = pack.get("titles", [])
    stats = compute_stats(titles)
    n = stats["count"]

    by_slot: dict[str, list[Fact]] = {}
    for f in facts:
        by_slot.setdefault(f.slot, []).append(f)

    # Global citation index: first-seen order across the fact store.
    src_index: dict[str, int] = {}
    for f in facts:
        if f.source_url and f.source_url not in src_index:
            src_index[f.source_url] = len(src_index) + 1
    sources = [{"n": n,
                "url": u,
                "label": urlparse(u).netloc or u}
               for u, n in sorted(src_index.items(), key=lambda kv: kv[1])]

    def ev(*slots: str) -> str:
        return _ev(facts, src_index, *slots)

    sec = pack.get("sections", {})
    # Auto-attach conflict / staleness surfacing + estimate flags to evidence.
    for key in SECTIONS:
        s = sec.get(key, {})
        extra = s.get("evidence_extra", "")
        base_ev = s.get("evidence", "")
        if not base_ev:
            # fall back to raw fact join so evidence is never empty
            slot_map = {
                "content": ("content_hours", "language_count", "originals_investment", "hub_deals"),
                "audience": ("mau", "subscribers", "segment_skews", "diaspora"),
                "emotional": ("genre_mix", "regulatory_ctx"),
                "distribution": ("downloads", "telecom_bundles", "devices", "linear_share", "ctv_share", "dubbing", "windows"),
                "revenue": ("revenue_annual", "revenue_quarterly", "ebitda", "pricing", "ad_products", "sports_rights"),
                "editorial": ("mission", "leadership", "campaigns", "ceo_structure",
                              "ownership"),
            }
            base_ev = ev(*slot_map[key])
        notes = []
        if extra:
            notes.append(extra)
        for c in conflicts:
            # Attach conflicts relevant to this section — every section's own
            # slots, not just content/audience. Match on the "slot=X:" marker
            # so short slot names ("mau") can't hit inside quoted values.
            sec_slots = set(SECTION_SLOTS.get(key, ()))
            if any(f"slot={sl}:" in c for sl in sec_slots):
                notes.append(c)
        if notes:
            base_ev = base_ev.rstrip() + " " + " ".join(notes)
        # estimate flag: only when % appears without any grounding cue
        # (disclosed/estimate/survey/reported) and without a date or source
        # citation. Dated disclosed figures ("25% (Jan 2026) [1]") must not
        # be flagged.
        low_ev = base_ev.lower()
        if "%" in base_ev and not any(k in low_ev for k in
                ("estimate", "disclosed", "survey", "reported", "according to")) \
                and not re.search(r"\(\w{3,9} \d{4}\)|\[\d+\]", base_ev):
            base_ev += " Where catalogue-wide percentages appear without a cited disclosure, treat them as estimates from sampling, not disclosed figures."
        # score rationale (spec: EVIDENCE states what pulled the score up/down)
        have_slots = {f.slot for f in facts}
        checked = SECTION_SLOTS.get(key, ())
        up = [s.replace("_", " ") for s in checked if s in have_slots]
        down = [s.replace("_", " ") for s in checked if s not in have_slots]
        if down:
            base_ev += (f" Score pulled up by depth in {', '.join(up) if up else 'general coverage'}; "
                        f"pulled down by no sourced evidence in {', '.join(down)}.")
        else:
            base_ev += " Score reflects even coverage across all checked slots in this dimension."
        # Pre-written evidence (hand-curated packs) carries no inline [n]
        # markers — append this section's source numbers so every section
        # stays one click away from its sources.
        if not re.search(r"\[\d+\]", base_ev):
            sec_nums = sorted({src_index[f.source_url] for f in facts
                               if f.slot in SECTION_SLOTS.get(key, ())
                               and f.source_url in src_index})
            if sec_nums:
                base_ev += (" Sources for this section: "
                            + " ".join(f"[{n}]" for n in sec_nums) + ".")
        s["evidence"] = base_ev.strip()
        sec[key] = s

    scores: dict[str, int] = {}
    for k in SECTIONS:
        try:
            scores[k] = max(0, min(100, int(sec.get(k, {}).get("score", 65))))
        except Exception:
            scores[k] = 65
    report = {
        "platform": platform,
        "region": region,
        "titles_analysed": n,
        "header_sentence": header_sentence(platform, n, pack.get("catalogue_note", "platform disclosures")),
        "identity_line": pack.get("identity_line", ""),
        "overall": {"score": overall(scores), "risk_tag": pack.get("risk_tag", ""), "summary": pack.get("summary", "")},
        "positioning": pack.get("positioning", ""),
        "sections": sec,
        "wishlist": pack.get("wishlist", []),
        "pitch": pack.get("pitch", {}),
        "stats": stats,
        "conflicts": conflicts,
        "sources": sources,
    }
    return report


def polish(text: str) -> str:
    """Optional LLM wording polish. Disabled without a key; never adds figures."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return text
    # Placeholder: integrate Anthropic API with prompt-cached example + the
    # "example rule" (structure/tone only, never reuse facts/phrasing).
    return text
