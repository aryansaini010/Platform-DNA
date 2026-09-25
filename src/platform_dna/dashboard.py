"""Dashboard view: Content Intelligence "Platform DNA" reference theme.

Two renderers (same data, same order):
- report_to_html(r): returns the standalone HTML string (white page,
  dark slate text, colour-coded dimensions) — matches the Acorn TV
  reference PDF attached by the user.
- show_report(r): displays it inside Streamlit via components.html
  (isolated iframe) so the Streamlit dark theme can never bleach the
  text white-on-white. This is the visibility fix.
- display_report(r): native st.* fallback, always readable.
"""
from __future__ import annotations

import html
import math
import re

DIM_COLORS = {
    "content": "#2563eb",
    "audience": "#10b981",
    "emotional": "#e11d48",
    "distribution": "#4f46e5",
    "revenue": "#f59e0b",
    "editorial": "#9333ea",
}

SECTION_TITLES = {
    "content": ("CONTENT DNA", "Content Strategy"),
    "audience": ("AUDIENCE DNA", "Audience Identity"),
    "emotional": ("EMOTIONAL DNA", "Emotional Profile"),
    "distribution": ("DISTRIBUTION DNA", "Delivery & Format"),
    "revenue": ("REVENUE DNA", "Monetisation"),
    "editorial": ("EDITORIAL DNA", "Editorial Voice"),
}

ORDER = ["content", "audience", "emotional", "distribution", "revenue", "editorial"]

# Reference-PDF light theme. Body text is ALWAYS near-black (#111827 /
#1F2937) on pure white — never the pale grey that went invisible.
T1 = "#111827"
T2 = "#1F2937"
MUTED = "#374151"
FAINT = "#4B5563"

CSS = """
<style>
html,body{background:#ffffff !important}
.dna-wrap,.stMarkdown .dna-wrap{font-family:'Segoe UI',system-ui,-apple-system,sans-serif;color:#111827 !important;background:#ffffff !important;
 max-width:1100px;margin:0 auto;padding:28px 30px;border-radius:16px;box-shadow:0 1px 4px rgba(0,0,0,.08);opacity:1 !important}
.dna-wrap p,.dna-wrap div,.dna-wrap span{opacity:1 !important}
.dna-pill{display:inline-block;border:1px solid #6366f1;color:#4338ca !important;border-radius:999px;
 padding:4px 16px;font-size:12px;font-weight:700;letter-spacing:1.5px;background:#eef2ff !important}
.dna-h1,.stMarkdown .dna-h1{font-size:34px;font-weight:800;color:#111827 !important;margin:10px 0 4px}
.dna-meta,.stMarkdown .dna-meta{color:#1F2937 !important;font-size:15px;margin-bottom:6px}
.dna-region{display:inline-block;border:1px solid #67e8f9;color:#0e7490 !important;border-radius:999px;
 padding:2px 12px;font-size:13px;font-weight:700;background:#ecfeff !important}
.dna-quote,.stMarkdown .dna-quote{border-left:4px solid #4f46e5;padding:6px 18px;font-style:italic;color:#374151 !important;
 font-size:17px;margin:14px auto;max-width:640px;text-align:center}
.dna-head{display:flex;gap:24px;align-items:flex-start;justify-content:space-between;flex-wrap:wrap}
.dna-gauge{text-align:center;min-width:230px}
.dna-risk{display:inline-block;border:1px solid #6ee7b7;color:#065f46 !important;border-radius:999px;
 padding:5px 18px;font-size:12px;font-weight:800;letter-spacing:1px;margin:8px 0;background:#ecfdf5 !important}
.dna-summary,.stMarkdown .dna-summary{font-size:14px;color:#111827 !important;max-width:430px;margin:0 auto;line-height:1.6}
.dna-scores{display:flex;gap:14px;flex-wrap:wrap;margin:22px 0 6px}
.dna-score{flex:1 1 150px;background:#ffffff !important;border:1px solid #e5e7eb;border-top:4px solid #999;
 border-radius:12px;padding:10px 14px;display:flex;justify-content:space-between;align-items:center}
.dna-score .k{font-size:11px;font-weight:700;letter-spacing:1px;color:#374151 !important}
.dna-score .v{font-size:26px;font-weight:800}
.dna-pos{border:1px solid #e0e7ff;border-left:4px solid #6366f1;border-radius:12px;
 padding:12px 22px;margin:14px 0;text-align:center;background:#ffffff !important}
.dna-pos h3{letter-spacing:3px;color:#4B5563 !important;font-size:14px;margin:0 0 6px}
.dna-pos p,.stMarkdown .dna-pos p{color:#1F2937 !important;font-size:15px;margin:0;line-height:1.55}
.dna-sec-h,.stMarkdown .dna-sec-h{text-align:center;color:#374151 !important;letter-spacing:1px;margin:14px 0 8px;font-size:22px;font-weight:700}
.dna-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px 20px}
@media(max-width:800px){.dna-grid{grid-template-columns:1fr}}
.dna-bar{height:4px;border-radius:999px;margin:0 0 8px}
.dna-card{background:#ffffff !important;border:1px solid #e5e7eb;border-radius:0 0 12px 12px;padding:4px 20px 10px}
.dna-card .kick{font-size:11px;font-weight:800;letter-spacing:1.5px}
.dna-card h3,.stMarkdown .dna-card h3{color:#111827 !important;margin:2px 0 6px;font-size:20px;font-weight:700}
.dna-card .strat,.stMarkdown .dna-card .strat{color:#111827 !important;font-size:14.5px;font-weight:700;text-align:center;margin:4px 0 8px;line-height:1.5}
.dna-card .flabel{font-size:11px;font-weight:800;letter-spacing:1.2px;margin:10px 0 3px;text-align:center}
.dna-card .ftext,.stMarkdown .dna-card .ftext{font-size:13.5px;color:#1F2937 !important;text-align:center;margin:0 0 3px;line-height:1.55}
.dna-card .ev,.stMarkdown .dna-card .ev{font-size:13px;color:#1F2937 !important;text-align:left;line-height:1.55}
.ev-list{margin:4px 0 2px 18px;padding:0;color:#1F2937 !important;font-size:13px;line-height:1.55;text-align:left}
.ev-list li{margin:3px 0}
.dna-badge{width:56px;height:56px;border-radius:50%;display:flex;align-items:center;justify-content:center;
 font-weight:800;font-size:20px;flex:none;background:#ffffff !important}
.dna-cardhead{display:flex;justify-content:space-between;align-items:center;gap:10px}
.dna-standout,.stMarkdown .dna-standout{font-size:13px;color:#1F2937 !important;margin:4px 0;text-align:center;line-height:1.5}
.dna-wish{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}
@media(max-width:800px){.dna-wish{grid-template-columns:1fr}}
.dna-wishitem,.stMarkdown .dna-wishitem{border:1px solid #6ee7b7;border-radius:10px;padding:8px 14px;font-size:13.5px;color:#111827 !important;text-align:center;background:#ffffff !important;line-height:1.5}
.dna-wishitem b{color:#047857 !important;margin-right:8px}
.dna-yes,.stMarkdown .dna-yes{color:#1F2937 !important;font-size:13.5px;margin:4px 0;text-align:center;line-height:1.5}
.dna-yes b{color:#047857 !important;margin-right:6px}
.dna-no,.stMarkdown .dna-no{color:#1F2937 !important;font-size:13.5px;margin:4px 0;text-align:center;line-height:1.5}
.dna-no b{color:#b91c1c !important;margin-right:6px}
.dna-2col{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:800px){.dna-2col{grid-template-columns:1fr}}
.dna-pa,.dna-pi,.dna-pn,.stMarkdown .dna-pa,.stMarkdown .dna-pi,.stMarkdown .dna-pn{font-size:14.5px;color:#1F2937 !important;text-align:center;line-height:1.6;max-width:900px;margin:4px auto}
.dna-src,.stMarkdown .dna-src{font-size:12.5px;color:#374151 !important}
.dna-wrap{-webkit-print-color-adjust:exact;print-color-adjust:exact}
.dna-src a{color:#4338ca !important}
</style>
"""


def _esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def _palette(mode: str = "dark") -> tuple[str, str]:
    """Kept for backwards-compat. Colours are now fixed (light card)."""
    return T1, T2


def _gauge(score: int, color: str, size: int = 170) -> str:
    # Open 270-degree gauge like the reference (gap at the bottom).
    r = 54
    full = 2 * math.pi * r
    arc = full * 0.75
    frac = max(0, min(100, int(score))) / 100.0
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 130 130">'
        f'<circle cx="65" cy="65" r="{r}" fill="none" stroke="#e5e7eb" stroke-width="12" '
        f'stroke-linecap="round" stroke-dasharray="{arc:.1f} {full:.1f}" '
        f'transform="rotate(135 65 65)"/>'
        f'<circle cx="65" cy="65" r="{r}" fill="none" stroke="{color}" stroke-width="12" '
        f'stroke-linecap="round" stroke-dasharray="{frac * arc:.1f} {full:.1f}" '
        f'transform="rotate(135 65 65)"/>'
        f'<text x="65" y="66" text-anchor="middle" font-size="32" font-weight="800" fill="#1F2937">{int(score)}</text>'
        f'<text x="65" y="86" text-anchor="middle" font-size="12" fill="#4B5563">/ 100</text>'
        "</svg>"
    )


def _badge(score: int, color: str) -> str:
    return (f'<div class="dna-badge" style="border:3px solid {color};color:{color}">{int(score)}</div>')


def _label(key: str) -> str:
    return _esc(key.replace("_", " ").upper())


def _ev_html(evidence: str) -> str:
    """Structured evidence: one bullet per sourced claim, easy to scan.

    Evidence strings are '• ...' newline-joined (see writer._ev). Any
    legacy paragraph without bullets falls back to a single item. The
    raw 'date unknown' placeholder is stripped as a safety net so the
    report always looks authentic.
    """
    ev = (evidence or "").replace("date unknown", "").replace("(  )", "").replace("()", "").strip()
    ev = re.sub(r"\s{2,}", " ", ev)
    items = [x.strip(" •-\n\t") for x in re.split(r"\n+", ev) if x.strip(" •-\n\t")]
    if len(items) <= 1 and "•" in ev:
        items = [x.strip() for x in ev.split("•") if x.strip()]
    items = [re.sub(r"\s+([.,;])", r"\1", x) for x in items if x]
    if not items:
        return ""
    lis = "".join(f"<li>{_esc(x)}</li>" for x in items)
    return f"<ul class='ev-list'>{lis}</ul>"


def _section_card(key: str, s: dict) -> str:
    color = DIM_COLORS[key]
    kick, title = SECTION_TITLES[key]
    parts = ['<div>', f'<div class="dna-bar" style="background:{color}"></div>',
             '<div class="dna-card">',
             '<div class="dna-cardhead"><div>',
             f'<div class="kick" style="color:{color}">{kick}</div><h3>{title}</h3></div>',
             _badge(int(s.get("score", 0)), color),
             "</div>"]
    strat = (s.get("strategy_line") or "").strip()
    if strat:
        parts.append(f'<p class="strat">{_esc(strat)}</p>')
    if s.get("evidence"):
        parts.append(f'<div class="flabel" style="color:{color}">EVIDENCE</div>'
                     f'{_ev_html(s["evidence"])}')
    for k, v in s.items():
        if k in ("score", "evidence", "strategy_line", "standout_titles", "tiers_label"):
            continue
        if isinstance(v, str) and v.strip():
            parts.append(f'<div class="flabel" style="color:{color}">{_label(k)}</div>'
                         f'<p class="ftext">{_esc(v)}</p>')
    if key == "content":
        if s.get("standout_titles"):
            parts.append(f'<div class="flabel" style="color:{color}">STANDOUT TITLES</div>')
        for st in (s.get("standout_titles") or []):
            t, w = _esc(st.get("title", "")), _esc(st.get("why", ""))
            parts.append(f'<p class="dna-standout"><b>{t}</b> — {w}</p>')
    parts.append("</div></div>")
    return "".join(parts)


def _revenue_card(s: dict) -> str:
    # Revenue uses tiers_label as the visible label for the tiers field.
    s2 = dict(s)
    tiers_label = s2.pop("tiers_label", "Subscription Tiers")
    color = DIM_COLORS["revenue"]
    kick, title = SECTION_TITLES["revenue"]
    parts = ['<div>', f'<div class="dna-bar" style="background:{color}"></div>',
             '<div class="dna-card">',
             '<div class="dna-cardhead"><div>',
             f'<div class="kick" style="color:{color}">{kick}</div><h3>{title}</h3></div>',
             _badge(int(s2.get("score", 0)), color),
             "</div>"]
    if s2.get("strategy_line"):
        parts.append(f'<p class="strat">{_esc(s2["strategy_line"])}</p>')
    if s2.get("evidence"):
        parts.append(f'<div class="flabel" style="color:{color}">EVIDENCE</div>'
                     f'{_ev_html(s2["evidence"])}')
    order = ["revenue_model", "tiers", "ad_dependency", "licensing_strategy",
             "originals_investment", "acquisition_appetite", "audience_monetisation"]
    for k in order:
        v = s2.get(k)
        if isinstance(v, str) and v.strip():
            lab = tiers_label if k == "tiers" else k.replace("_", " ").upper()
            parts.append(f'<div class="flabel" style="color:{color}">{_esc(lab)}</div>'
                         f'<p class="ftext">{_esc(v)}</p>')
    parts.append("</div></div>")
    return "".join(parts)


def report_to_html(r: dict, mode: str = "dark") -> str:
    secs = r.get("sections", {}) or {}
    overall = r.get("overall", {}) or {}

    def _sint(v: object, default: int = 0) -> int:
        try:
            return int(float(str(v)))
        except Exception:
            return default

    score = _sint(overall.get("score", 0))
    region = _esc(r.get("region") or "Region not set")
    n = int(r.get("titles_analysed", 0))
    h = [CSS, '<div class="dna-wrap">',
         '<div style="text-align:center"><span class="dna-pill">⚡ PLATFORM DNA REPORT</span></div>',
         f'<div class="dna-head"><div style="flex:1;min-width:260px">',
         f'<div class="dna-h1">{_esc(r.get("platform", ""))}</div>',
         f'<div class="dna-meta"><span class="dna-region">🌍 {region}</span> &nbsp;•&nbsp; {n} titles analysed</div>',
         f'<div class="dna-quote">“{_esc(r.get("identity_line", ""))}”</div>',
         "</div>",
         '<div class="dna-gauge">',
         _gauge(score, "#10b981", 170),
         f'<div><span class="dna-risk">{_esc(overall.get("risk_tag", ""))}</span></div>',
         f'<p class="dna-summary">{_esc(overall.get("summary", ""))}</p>',
         "</div></div>"]
    h.append('<div class="dna-scores">')
    for k in ORDER:
        s = secs.get(k, {}) or {}
        c = DIM_COLORS[k]
        h.append(f'<div class="dna-score" style="border-top-color:{c}">'
                 f'<div class="k">{k.upper()}</div>'
                 f'<div class="v" style="color:{c}">{_sint(s.get("score", 0))}</div></div>')
    h.append("</div>")
    h.append(f'<div class="dna-pos"><h3>POSITIONING</h3><p>{_esc(r.get("positioning", ""))}</p></div>')
    h.append('<div class="dna-sec-h">DNA Deep Dive</div><div class="dna-grid">')
    for k in ORDER:
        s = secs.get(k, {}) or {}
        h.append(_revenue_card(s) if k == "revenue" else _section_card(k, s))
    h.append("</div>")
    h.append('<div class="dna-sec-h">ACQUISITION WISHLIST</div><div class="dna-wish">')
    for w in (r.get("wishlist") or []):
        h.append(f'<div class="dna-wishitem"><b>›</b>{_esc(w)}</div>')
    h.append("</div>")
    p = r.get("pitch", {})
    h.append('<div class="dna-sec-h">Pitch Playbook</div>')
    h.append('<div class="flabel" style="color:#4f46e5;text-align:center;font-size:12px;font-weight:800;letter-spacing:1.5px">PITCH ANGLE</div>'
             f'<p class="dna-pa">{_esc(p.get("angle", ""))}</p>')
    h.append('<div class="flabel" style="color:#312e81;text-align:center;font-size:12px;font-weight:800;letter-spacing:1.5px">IDEAL TITLE PROFILE</div>'
             f'<p class="dna-pi">{_esc(p.get("ideal_profile", ""))}</p>')
    h.append('<div class="dna-2col"><div><div class="flabel" style="color:#059669;text-align:center;font-size:12px;font-weight:800;letter-spacing:1.5px">INSTANT YES SIGNALS</div>')
    for y in (p.get("yes") or []):
        h.append(f'<p class="dna-yes"><b>✓</b>{_esc(y)}</p>')
    h.append('</div><div><div class="flabel" style="color:#dc2626;text-align:center;font-size:12px;font-weight:800;letter-spacing:1.5px">INSTANT NO SIGNALS</div>')
    for nn in (p.get("no") or []):
        h.append(f'<p class="dna-no"><b>✕</b>{_esc(nn)}</p>')
    h.append("</div></div>")
    h.append('<div class="flabel" style="color:#f59e0b;text-align:center;font-size:12px;font-weight:800;letter-spacing:1.5px">NEGOTIATION INTELLIGENCE</div>'
             f'<p class="dna-pn">{_esc(p.get("negotiation", ""))}</p>')
    sources = r.get("sources") or []
    if sources:
        h.append('<div class="dna-sec-h">SOURCES</div>')
        for s in sources:
            url = _esc(s.get("url", ""))
            lab = _esc(s.get("label", s.get("url", "")))
            h.append(f'<p class="dna-src">{int(s.get("n", 0))}. <a href="{url}" target="_blank">{lab}</a></p>')
    h.append("</div>")
    return "".join(h)


def citation_numbers(text: str) -> list[int]:
    """Extract [n] citation markers — used to cross-check sources in tests."""
    if not text:
        return []
    # Only standalone [n] (not [2024] years inside prose): require the
    # bracket to follow whitespace/start and precede whitespace/punct-end.
    return sorted({int(x) for x in re.findall(r"(?<!\S)\[(\d{1,3})\](?=\s|[.,;:)\]]|$)", text)})


def show_report(r: dict, height: int | None = None) -> None:
    """Display the reference-theme report inside an isolated iframe.

    components.html isolates our white-page/dark-text CSS from the
    Streamlit app theme, so text can never be bleached invisible again.
    Height auto-estimates from content length to avoid trailing white
    space; pass an explicit height to override. Falls back to
    display_report() if components is unavailable.
    """
    try:
        import streamlit.components.v1 as components

        body = report_to_html(r)
        doc = (
            "<html><head><meta charset='utf-8'></head>"
            "<body style='margin:0;padding:0;background:#ffffff;color:#111827;"
            "font-family:Segoe UI,system-ui,sans-serif'>"
            + body
            + "</body></html>"
        )
        if height is None:
            # Generous estimate so the iframe never cuts content off;
            # internal scrolling stays enabled as a safety net.
            height = max(4000, min(20000, len(doc) // 4))
        components.html(doc, height=height, scrolling=True)
    except Exception:
        display_report(r)


def display_report(r: dict, key_prefix: str = "dna") -> None:
    """Native Streamlit renderer — always readable, no custom HTML/CSS.

    Uses only st.* elements so text follows the active Streamlit theme
    (dark or light) automatically. This replaces the HTML card layout
    which kept going invisible when the app theme overrode its colours.
    """
    import streamlit as st

    def _safe_int(v: object, default: int = 0) -> int:
        try:
            return int(float(str(v)))
        except Exception:
            return default

    secs = r.get("sections", {}) or {}
    overall = r.get("overall", {}) or {}
    score = _safe_int(overall.get("score", 0))
    region = r.get("region") or "Region not set"
    n = _safe_int(r.get("titles_analysed", 0))

    st.markdown("### ⚡ PLATFORM DNA REPORT")
    st.header(r.get("platform", ""))
    st.caption(f"🌍 {region} • {n} titles analysed")
    if r.get("identity_line"):
        st.info(f"“{r['identity_line']}”")

    c1, c2 = st.columns([1, 2])
    with c1:
        st.metric("OVERALL", f"{score} / 100")
    with c2:
        if overall.get("risk_tag"):
            st.success(overall["risk_tag"])
        if overall.get("summary"):
            st.write(overall["summary"])

    st.divider()
    cols = st.columns(6)
    for i, k in enumerate(ORDER):
        s = secs.get(k, {}) or {}
        with cols[i]:
            st.metric(k.upper(), _safe_int(s.get("score", 0)))

    st.divider()
    st.subheader("POSITIONING")
    st.write(r.get("positioning", ""))

    st.subheader("DNA Deep Dive")
    for idx in range(0, len(ORDER), 2):
        pair = ORDER[idx:idx + 2]
        cc = st.columns(2)
        for j, k in enumerate(pair):
            s = secs.get(k, {}) or {}
            kick, title = SECTION_TITLES[k]
            with cc[j]:
                with st.container(border=True):
                    st.caption(kick)
                    st.markdown(f"**{title} — {_safe_int(s.get('score', 0))}**")
                    if s.get("strategy_line"):
                        st.write(s["strategy_line"])
                    if s.get("evidence"):
                        st.markdown("**EVIDENCE**")
                        _items = [x.strip(" •-\n\t") for x in re.split(r"\n+", s["evidence"].replace("date unknown", "")) if x.strip(" •-\n\t")]
                        for _it in _items:
                            st.markdown(f"- {_it}")
                    for fk, fv in s.items():
                        if fk in ("score", "evidence", "strategy_line",
                                  "standout_titles", "tiers_label"):
                            continue
                        if isinstance(fv, str) and fv.strip():
                            st.markdown(f"**{fk.replace('_', ' ').upper()}**")
                            st.write(fv)
                    if k == "content":
                        sts = s.get("standout_titles") or []
                        if sts:
                            st.markdown("**STANDOUT TITLES**")
                            for item in sts:
                                st.write(f"- *{item.get('title', '')}* — {item.get('why', '')}")
                    if k == "revenue" and s.get("tiers_label"):
                        st.caption(s["tiers_label"])

    st.subheader("ACQUISITION WISHLIST")
    w1, w2 = st.columns(2)
    for i, w in enumerate(r.get("wishlist") or []):
        with (w1 if i % 2 == 0 else w2):
            with st.container(border=True):
                st.write(f"› {w}")

    p = r.get("pitch", {})
    st.subheader("Pitch Playbook")
    st.markdown("**PITCH ANGLE**")
    st.write(p.get("angle", ""))
    st.markdown("**IDEAL TITLE PROFILE**")
    st.write(p.get("ideal_profile", ""))
    ycol, ncol = st.columns(2)
    with ycol:
        st.markdown("**INSTANT YES SIGNALS**")
        for y in (p.get("yes") or []):
            st.success(f"✓ {y}")
    with ncol:
        st.markdown("**INSTANT NO SIGNALS**")
        for x in (p.get("no") or []):
            st.error(f"✕ {x}")
    st.markdown("**NEGOTIATION INTELLIGENCE**")
    st.write(p.get("negotiation", ""))

    sources = r.get("sources") or []
    if sources:
        with st.expander("SOURCES"):
            for s in sources:
                st.write(f"{s.get('n', 0)}. [{s.get('label', s.get('url', ''))}]({s.get('url', '')})")
