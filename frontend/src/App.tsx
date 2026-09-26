import { useEffect, useMemo, useRef, useState } from "react";
import {
  deleteReport,
  generateDNA,
  getLibrary,
  getPlatforms,
  getRegions,
  getReport,
  jsonUrl,
  markdownUrl,
  pdfUrl,
} from "./api";
import localPlatforms from "./data/platforms.json";
import localRegions from "./data/regions.json";
import Dropdown from "./Dropdown";

const COLORS: Record<string, string> = {
  content: "#3b82f6",
  audience: "#10b981",
  emotional: "#f43f5e",
  distribution: "#6366f1",
  revenue: "#f59e0b",
  editorial: "#a855f7",
};
const ORDER = ["content", "audience", "emotional", "distribution", "revenue", "editorial"];
const TITLES: Record<string, [string, string]> = {
  content: ["CONTENT DNA", "Content Strategy"],
  audience: ["AUDIENCE DNA", "Audience Identity"],
  emotional: ["EMOTIONAL DNA", "Emotional Profile"],
  distribution: ["DISTRIBUTION DNA", "Delivery & Format"],
  revenue: ["REVENUE DNA", "Monetisation"],
  editorial: ["EDITORIAL DNA", "Editorial Voice"],
};

function MixBars({ text, color }: { text: string; color: string }) {
  const rows = useMemo(() => {
    const out: { label: string; pct: number }[] = [];
    const re = /([A-Za-z][A-Za-z /&.'-]{2,40}?)\s+(\d{1,3})%/g;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) && out.length < 8) {
      const pct = Math.min(100, parseInt(m[2], 10));
      if (/^(the|and|with|from|this|that|estimat)/i.test(m[1].trim())) continue;
      out.push({ label: m[1].trim(), pct });
    }
    return out;
  }, [text]);
  if (rows.length < 2) return <div className="ftext">{text}</div>;
  return (
    <div>
      {rows.map((r, i) => (
        <div key={i} style={{ margin: "5px 0" }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, color: "#cbd5e1" }}>
            <span>{r.label}</span><span>{r.pct}%</span>
          </div>
          <div className="bar"><i style={{ width: `${r.pct}%`, background: color }} /></div>
        </div>
      ))}
      <div className="ftext" style={{ marginTop: 6 }}>{text}</div>
    </div>
  );
}

function Gauge({ score }: { score: number }) {
  const r = 54;
  const full = 2 * Math.PI * r;
  const arc = full * 0.75;
  const frac = Math.max(0, Math.min(100, score)) / 100;
  return (
    <svg width="150" height="150" viewBox="0 0 130 130">
      <circle cx="65" cy="65" r={r} fill="none" stroke="#1e293b" strokeWidth="12"
        strokeLinecap="round" strokeDasharray={`${arc.toFixed(1)} ${full.toFixed(1)}`}
        transform="rotate(135 65 65)" />
      <circle cx="65" cy="65" r={r} fill="none" stroke="#10b981" strokeWidth="12"
        strokeLinecap="round" strokeDasharray={`${(frac * arc).toFixed(1)} ${full.toFixed(1)}`}
        transform="rotate(135 65 65)" />
      <text x="65" y="68" textAnchor="middle" fontSize="30" fontWeight="800" fill="#e5e9f2">{score}</text>
      <text x="65" y="86" textAnchor="middle" fontSize="11" fill="#93a0b8">/ 100</text>
    </svg>
  );
}

function truncateEvidence(text: string, max = 4000) {
  const s = String(text);
  if (s.length <= max) return s;
  let cut = s.slice(0, max);
  // Never cut inside a [12 citation marker.
  const open = cut.lastIndexOf("[");
  if (open !== -1 && !/\[\d+\]/.test(cut.slice(open)) && /^\[\d*$/.test(cut.slice(open))) {
    cut = cut.slice(0, open);
  }
  return cut;
}

function CiteText({ text, valid }: { text: string; valid?: Set<number> }) {
  // Renders [n] citation markers as jump links to the source panel rows.
  const parts = String(text).split(/(\[\d+\])/g);
  return (
    <>
      {parts.map((p, i) => {
        const m = /^\[(\d+)\]$/.exec(p);
        if (!m) return <span key={i}>{p}</span>;
        const n = Number(m[1]);
        if (valid && !valid.has(n)) return <span key={i}>{p}</span>;
        return (
          <a key={i} className="cite" href={`#src-${n}`} title={`Source ${n}`}>[{n}]</a>
        );
      })}
    </>
  );
}

export default function App() {
  const [platforms, setPlatforms] = useState<any[]>(localPlatforms as any[]);
  const [regions, setRegions] = useState<any[]>(localRegions as any[]);
  const [platform, setPlatform] = useState("ZEE5");
  const [region, setRegion] = useState("India (IN)");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [report, setReport] = useState<any | null>(null);
  const [pack, setPack] = useState<any | null>(null);
  const [entry, setEntry] = useState<any | null>(null);
  // Validation diagnostics are kept in state for retry math but never
  // rendered as log lists (green timing banner + re-polish button only).
  const [, setErrors] = useState<string[]>([]);
  const [enhWarn, setEnhWarn] = useState<string[]>([]);
  const [lib, setLib] = useState<any[]>([]);
  const [forceFresh, setForceFresh] = useState(false);
  const [libBusy, setLibBusy] = useState(false);
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [regionSnap, setRegionSnap] = useState<{ from: string; to: string } | null>(null);
  // Cumulative polish success across the initial generate + retries, so a
  // second retry only targets kinds that never succeeded (backend returns
  // per-attempt lists, not cumulative).
  const [doneKinds, setDoneKinds] = useState<Set<string>>(new Set());
  // Kinds polished then auto-reverted to deterministic text — retry must
  // include them even though they appear in doneKinds.
  const [revertedKinds, setRevertedKinds] = useState<string[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    getPlatforms()
      .then((p) => { if (p.length) setPlatforms(p); else setStatus("Backend returned 0 platforms — check /api/platforms."); })
      .catch((e) => setStatus(`Backend unreachable — showing bundled catalogue (${String(e?.message ?? e)})`));
    getRegions()
      .then((r) => { if (r.length) setRegions(r); })
      .catch(() => {});
    refreshLib();
  }, []);

  async function refreshLib() {
    if (libBusy) return;
    setLibBusy(true);
    try {
      setLib(await getLibrary());
    } catch (e: any) {
      console.warn("library refresh failed", e);
      setStatus(`Library refresh failed: ${String(e?.message ?? e)} — is the API on :8001?`);
      // Never wipe a populated list on a failed manual refresh; a failed
      // first load still lands on [] via the initial state.
      setLib((prev) => (prev.length ? prev : []));
    } finally {
      setLibBusy(false);
    }
  }

  // Bidirectional invariant: platform ⇄ region always resolve to a valid
  // pair. Picking a region filters the channel list to that region's
  // catalogued channels; picking a platform filters regions to its coverage.
  // Either picker snap-corrects the other when the pair goes out of scope.
  const platformOptions = useMemo(() => {
    const code = regionCode(region);
    const list = code
      ? platforms.filter((p) => (p.regions ?? []).includes(code))
      : platforms;
    // Fall back to the full list when the region has no catalogued
    // channels yet.
    const shown = list.length ? list : platforms;
    return shown.map((p) => ({ value: p.name, label: p.name, group: p.group || "Other" }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [platforms, region, regions]);

  const channelNames = useMemo(
    () => new Set(platformOptions.map((o) => o.value)),
    [platformOptions]
  );

  const allowedKey = platformOptions.map((o) => o.value).join(",");
  useEffect(() => {
    // Region-first snap: if the selected platform isn't served in the
    // selected region, switch to that region's first channel. The
    // platform-first effect below then sees a valid pair and stays quiet,
    // so the two effects converge instead of ping-ponging.
    if (!channelNames.size) return;
    if (!channelNames.has(platform)) {
      const first = platformOptions[0]?.value;
      if (first) setPlatform(first);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [region, regions, platforms, allowedKey]);

  // Invariant: a selected platform ALWAYS resolves to ≥1 region.
  // The dropdown offers only the platform's regions; changing platform
  // auto-switches an out-of-scope region to the platform's first region.
  const codeToLabel = useMemo(
    () => new Map(regions.map((r) => [r.code, r.label] as [string, string])),
    [regions]
  );

  const allowedCodes: string[] = useMemo(() => {
    const p = platforms.find((x) => x.name === platform);
    if (!p) return regions.map((r) => r.code);
    if (!p.regions?.length) {
      console.error(`catalog violation: platform ${p.name} has 0 regions`);
      return [];
    }
    const known = new Set(regions.map((r) => r.code));
    const unknown = p.regions.filter((c: string) => !known.has(c));
    if (unknown.length) console.warn(`dangling region codes for ${p.name}: ${unknown.join(",")}`);
    // Keep unknown codes visible (label falls back to the code) instead of
    // silently shrinking the region list.
    return p.regions as string[];
  }, [platforms, platform, regions]);

  // Region-first: full region list, unfiltered — picking one filters
  // the channel list above via platformOptions.
  const regionOptionsFull = useMemo(
    () =>
      regions.map((r) => ({ value: r.label, label: r.label, group: r.name.charAt(0).toUpperCase() })),
    [regions]
  );

  const regionKey = allowedCodes.join(",");
  useEffect(() => {
    if (!allowedCodes.length) return;
    const cur = /\(([^)]+)\)\s*$/.exec(region || "")?.[1];
    if (!cur || !allowedCodes.includes(cur)) {
      setRegion(codeToLabel.get(allowedCodes[0]) ?? allowedCodes[0]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [platform, platforms, regionKey]);

  function regionCode(label: string) {
    const m = /\(([^)]+)\)\s*$/.exec(label || "");
    if (m) return m[1];
    const hit = regions.find((r) => r.label === label || r.name === label || r.code === label);
    return hit?.code ?? label;
  }

  function timingsSuffix(s: any) {
    if (!s?.enhance_timings) return "";
    const parts = Object.entries(s.enhance_timings).map(([k, v]) => `${k} ${v}s`).join(", ");
    return ` [${parts}${s.enhance_workers ? ` · ${s.enhance_workers}-wide` : ""}]`;
  }

  async function onGenerate() {
    if (!platform.trim() || busy) return;
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setBusy(true);
    setErrors([]);
    setEnhWarn([]);
    setRegionSnap(null);
    const backend = "Ollama GPU polish";
    // Fresh runs: research (~2 min) + 8 enhance calls. Timeout is 13 min.
    setStatus(forceFresh
      ? `Fresh re-research requested — deep research + ${backend} (up to 13 min timeout)…`
      : `Checking saved reports, then deep research + ${backend} (up to 13 min timeout for fresh runs)…`);
    try {
      const res = await generateDNA({
        platform: platform.trim(),
        region: regionCode(region),
        depth: "deep",
        force: forceFresh,
        enhance: true,
      }, ctrl.signal);
      setReport(res.report);
      setPack(res.pack);
      setMarkdown(res.markdown ?? null);
      setEntry(res.entry ?? null);
      setErrors(res.errors ?? []);
      setEnhWarn(res.stats?.enhance_errors ?? []);
      setDoneKinds(new Set([...(res.stats?.enhanced ?? []), ...(res.stats?.enhanced_top ?? [])]));
      // Reverted kinds were polished then rolled back to deterministic text:
      // surface them so a retry can re-polish them.
      const _rev: string[] = res.stats?.reverted_fields ?? [];
      setRevertedKinds(_rev);
      if (_rev.length) {
        setEnhWarn((prev) => [...prev, `auto-revert to deterministic text: ${_rev.join(", ")} — retry will re-polish`]);
      }
      const snap = res.stats?.region_snap;
      setRegionSnap(snap ?? null);
      const snapNote = snap ? ` Region snapped to ${snap.to} (platform doesn't serve ${snap.from}).` : "";
      const s = res.stats ?? {};
      const _tim = timingsSuffix(s);
      const detail = s.reused ? "" :
        ` Research: ${s.pages_ok ?? "?"} ok / ${s.pages_failed ?? "?"} failed, ${s.queries ?? "?"} queries in ${s.research_s ?? "?"}s`
        + (s.gaps_remaining?.length ? `, gaps: ${s.gaps_remaining.join(", ")}` : ", no gaps")
        + (s.enhanced ? ` · polished: ${(s.enhanced ?? []).join(",")}${s.enhanced_top?.length ? "+" + s.enhanced_top.join(",") : ""} in ${s.enhance_s ?? "?"}s${_tim}` : "");
      if ((res.errors ?? []).length === 0) {
        setStatus((res.reused ? `Loaded saved evidence (${res.reused}) — no re-scrape.` : `Valid — overall ${res.report?.overall?.score}/100 in ${s.elapsed_s ?? "?"}s. Saved to library.${detail}`) + snapNote);
        if (snap && snap.to) {
          const lbl = regions.find((r) => r.name === snap.to)?.label ?? snap.to;
          if (lbl) setRegion(lbl);
        }
        refreshLib();
      } else {
        setStatus("Saved to Recently ready — use Retry polish to improve it." + snapNote + detail);
        refreshLib();
      }
    } catch (e: any) {
      if (ctrl.signal.aborted) {
        setStatus("Cancelled — the backend may still be working. Use Refresh below; a late-saved report will appear in Recently ready.");
      } else {
        const msg = String(e?.message ?? e);
        const aborted = /abort/i.test(msg);
        setStatus(aborted
          ? "Request timed out after 13 min — the backend may still be working. Use Refresh below; a late-saved report will appear in Recently ready."
          : msg);
      }
      // Backend may finish late even after abort — refresh so a late save appears.
      refreshLib();
    } finally {
      abortRef.current = null;
      setBusy(false);
    }
  }

  function onCancel() {
    abortRef.current?.abort();
  }

  async function retryPolish() {
    if (!pack || busy) return;
    const all = ["content", "audience", "emotional", "distribution", "revenue", "editorial", "voice", "deal"];
    // doneKinds tracks polished kinds; revertedKinds tracks polished kinds
    // that were rolled back to deterministic text — both need a retry.
    // Also parse the enhance_errors string fallback for older responses.
    const revertedFromWarn: string[] = [];
    for (const w of enhWarn) {
      const m = /auto-revert[^:]*:\s*(.+)/i.exec(w);
      if (m) {
        for (const k of m[1].split(",")) {
          const kk = k.trim().split(/\s+/)[0].replace(/[.,;]+$/, "");
          if (all.includes(kk) && !revertedFromWarn.includes(kk)) revertedFromWarn.push(kk);
        }
      }
    }
    const mustRetry = new Set([...revertedKinds, ...revertedFromWarn]);
    const missing = all.filter((k) => !doneKinds.has(k) || mustRetry.has(k));
    if (!missing.length) return;
    setBusy(true);
    setStatus(`Retrying AI polish for: ${missing.join(", ")} (no research, saves tokens)…`);
    try {
      const res = await generateDNA({
        platform: pack.platform ?? platform,
        region: regionCode(pack.region ?? region),
        depth: "deep", force: true, enhance: true, pack, retry: missing,
      });
      setReport(res.report);
      setPack(res.pack);
      setMarkdown(res.markdown ?? markdown);
      setEntry(res.entry ?? entry);
      setErrors(res.errors ?? []);
      setEnhWarn(res.stats?.enhance_errors ?? []);
      setDoneKinds((prev) => new Set([...prev, ...(res.stats?.enhanced ?? []), ...(res.stats?.enhanced_top ?? [])]));
      setRevertedKinds(res.stats?.reverted_fields ?? []);
      {
        const rs = res.stats ?? {};
        const rtim = timingsSuffix(rs);
        const polished = [...(rs.enhanced ?? []), ...(rs.enhanced_top ?? [])].join(",");
        setStatus((res.errors ?? []).length === 0
          ? `Retry complete —${polished ? ` polished ${polished}` : ""}${rs.enhance_s != null ? ` in ${rs.enhance_s}s` : ""}${rtim}. Report saved.`
          : "Retry done — report saved to Recently ready; use Retry polish to improve further.");
      }
      refreshLib();
    } catch (e: any) {
      setStatus(String(e?.message ?? e));
      refreshLib();
    } finally {
      setBusy(false);
    }
  }

  async function openEntry(id: string) {    try {
      const res = await getReport(id);
      setReport(res.report);
      setPack(res.pack);
      setMarkdown(res.markdown ?? null);
      setEntry({ id });
      // Drafts carry validation context from the sidecar — surface it in
      // the opened view instead of clearing it. Polish timings live only on
      // fresh generate/retry responses (GET /report has no timings), so the
      // green banner keeps the draft message here.
      setErrors(res.errors ?? []);
      setEnhWarn(res.enhance_errors ?? []);
      if ((res.status ?? "valid") !== "valid" && (res.errors ?? []).length) {
        setStatus(`Opened report ${id} — use Retry polish to improve it.`);
      } else {
        setStatus("");
      }
      setDoneKinds(new Set());
      setRevertedKinds(res.reverted ?? []);
      setRegionSnap(null);
      // Sync the dropdowns to the opened report so Regenerate targets
      // the visible report instead of a stale dropdown selection.
      if (res.pack?.platform) setPlatform(res.pack.platform);
      if (res.pack?.region) {
        const lbl = regions.find((r) => r.name === res.pack.region || r.code === res.pack.region)?.label;
        setRegion(lbl ?? res.pack.region);
      }
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e: any) {
      setStatus(String(e?.message ?? e));
    }
  }

  const secs = report?.sections ?? {};
  const overall = report?.overall ?? {};
  const [showSources, setShowSources] = useState(false);
  const sources: any[] = report?.sources ?? [];

  // Enriched source meta: which sections cite [n] + fact counts from pack.
  const citedIn = useMemo(() => {
    const m: Record<number, string[]> = {};
    for (const s of sources) {
      const n = s.n;
      const hits = ORDER.filter((k) => new RegExp(`\\[${n}\\]`).test(secs[k]?.evidence ?? ""));
      if (hits.length) m[n] = hits;
    }
    return m;
  }, [report, sources.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const factCounts = useMemo(() => {
    const m: Record<string, number> = {};
    for (const f of pack?.facts ?? []) {
      const u = f.source_url;
      if (u) m[u] = (m[u] ?? 0) + 1;
    }
    return m;
  }, [pack]);

  return (
    <>
      <div className="wrap">
        <div className="hero">
          <div className="logo">✦</div>
          <div>
            <h1>Content Intelligence</h1>
            <p>AI modules, report generation, and the reports vault — all in one place.</p>
          </div>
        </div>

        <div className="card">
          <h2>Platform DNA</h2>
          <div className="sub">Generate a demand-aware content DNA profile for any streaming platform + region.</div>
          <div className="grid2">
            <div>
              <Dropdown
                label="Region"
                value={region}
                options={regionOptionsFull}
                onPick={setRegion}
                searchPlaceholder="Search regions…"
              />
            </div>
            <div>
              <Dropdown
                label="Platform"
                value={platform}
                options={platformOptions}
                onPick={setPlatform}
                searchPlaceholder="Search channels…"
              />
            </div>
          </div>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
            <label className="muted" style={{ display: "flex", gap: 6, alignItems: "center", cursor: "pointer" }}>
              <input type="checkbox" checked={forceFresh} disabled={busy} onChange={(e) => setForceFresh(e.target.checked)} />
              Force fresh re-research (ignore saved report)
            </label>
            <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <button className="btn primary" disabled={!platform.trim() || !regionCode(region) || busy} onClick={onGenerate}>✦ {busy ? "Generating…" : "Generate DNA"}</button>
              {busy && <button className="btn small" onClick={onCancel}>✕ Cancel</button>}
            </span>
          </div>
          {regionSnap && (
            <div className="warn">Region snapped: {regionSnap.from} → {regionSnap.to} (platform doesn’t serve the requested region).</div>
          )}
          {status && <div className="ok" role="status">{busy ? <span className="spin">{status}</span> : status}</div>}
          {pack && !busy && (
            <div style={{ marginTop: 8 }}>
              <button className="btn small" onClick={retryPolish}>↻ Retry polish only (no re-research)</button>
            </div>
          )}
          {!entry && markdown && (
            <div className="err" role="alert">
              <div style={{ marginTop: 8 }}>
                <button
                  className="btn small"
                  onClick={() => {
                    const blob = new Blob([markdown], { type: "text/markdown" });
                    const a = document.createElement("a");
                    a.href = URL.createObjectURL(blob);
                    a.download = "Platform_DNA_DRAFT_unsaved.md";
                    a.click();
                    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
                  }}
                >⬇ Download unsaved draft (Markdown)</button>{" "}
                <span className="muted">Transport failed before the backend could save — use Refresh; a late save may appear above.</span>
              </div>
            </div>
          )}
        </div>

        <div className="card">
          <div className="row" style={{ marginTop: 0 }}>
            <h2 style={{ textAlign: "left" }}>Recently ready</h2>
            <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <button className="btn small" disabled={libBusy} onClick={refreshLib}>{libBusy ? "⟳ Refreshing…" : "⟳ Refresh"}</button>
            </span>
          </div>
          {lib.length === 0 && !libBusy && <div className="muted">Library is empty — generate a report above (every run is saved).</div>}
          {lib.slice(0, 12).map((r) => (
            <div className="lib-card" key={r.id} onClick={() => openEntry(r.id)} title="Open report">
              <div>
                <div className="lib-title">{r.platform} · {r.region}</div>
                <div className="muted">{r.created} · {r.titles} titles · overall {r.overall}/100</div>
              </div>
              <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span className="dot" />
                <button className="btn small" onClick={async (e) => {
                  e.stopPropagation();
                  if (!window.confirm(`Delete ${r.platform} · ${r.region} (${r.id})?`)) return;
                  try {
                    await deleteReport(r.id);
                    // If the deleted entry is open, clear the stale view.
                    if (entry?.id === r.id) {
                      setReport(null); setPack(null); setEntry(null);
                      setMarkdown(null); setErrors([]); setEnhWarn([]);
                      setStatus("Deleted open report — library refreshed.");
                    }
                  } catch (err: any) {
                    setStatus(`Delete failed: ${String(err?.message ?? err)}`);
                  }
                  refreshLib();
                }}>✕</button>
              </span>
            </div>
          ))}
        </div>

        {report && (
          <div className="card">
            <div style={{ textAlign: "center" }}><span className="pill">⚡ PLATFORM DNA REPORT</span></div>
            <div className="rep-head">
              <div style={{ flex: 1, minWidth: 260 }}>
                <div className="rep-title">{report.platform}</div>
                <div className="rep-meta">
                  <span className="region-pill">🌍 {report.region || "Region not set"}</span>
                  <span> • {report.titles_analysed} titles analysed</span>
                </div>
                <div className="quote">“{report.identity_line}”</div>
                <div>
                  {sources.length > 0 && (
                    <><button className="btn small" onClick={() => setShowSources(!showSources)}>
                      {showSources ? "▾" : "▸"} Sources ({sources.length})
                    </button>{" "}</>
                  )}
                  {entry?.id && <>
                    <a className="btn small" href={pdfUrl(entry.id)} target="_blank" rel="noreferrer">⬇ PDF / Print</a>{" "}
                    <a className="btn small" href={jsonUrl(entry.id)} target="_blank" rel="noreferrer">⬇ JSON</a>{" "}
                    <a className="btn small" href={markdownUrl(entry.id)} target="_blank" rel="noreferrer">⬇ Markdown</a>{" "}
                    <button className="btn small" onClick={onGenerate}>⟳ Regenerate</button>
                  </>}
                </div>
              </div>
              <div className="gauge-wrap">
                <Gauge score={overall.score ?? 0} />
                <div><span className="risk">{overall.risk_tag}</span></div>
                <p className="summary">{overall.summary}</p>
              </div>
            </div>

            {showSources && sources.length > 0 && (
              <div className="src-panel">
                <h3 className="sec-h">SOURCES ({sources.length})</h3>
                <div className="muted" style={{ textAlign: "center", marginBottom: 8 }}>
                  Every figure in this report traces to a page below — citation numbers in EVIDENCE point here.
                </div>
                {sources.map((s) => (
                  s?.n == null || !s?.url ? null : (
                  <div className="src-row" key={s.n} id={`src-${s.n}`}>
                    <span className="src-n">{s.n}</span>
                    <span style={{ minWidth: 0 }}>
                      <div className="src-label">{s.label || s.url}</div>
                      <a className="src-url" href={s.url} target="_blank" rel="noreferrer">{s.url}</a>
                      <div className="src-meta">
                        {(citedIn[s.n] ?? []).map((k) => (
                          <span className="chip" key={k} style={{ borderColor: COLORS[k], color: COLORS[k] }}>{k}</span>
                        ))}
                        {factCounts[s.url] ? <span className="muted"> · {factCounts[s.url]} fact{factCounts[s.url] === 1 ? "" : "s"}</span> : null}
                      </div>
                    </span>
                  </div>
                  )
                ))}
              </div>
            )}

            <div className="scores">
              {ORDER.map((k) => (
                <div className="score" key={k}>
                  <div className="k">{k.toUpperCase()}</div>
                  <div className="v" style={{ color: COLORS[k] }}>{secs[k]?.score ?? 0}</div>
                  <div className="bar"><i style={{ width: `${secs[k]?.score ?? 0}%`, background: COLORS[k] }} /></div>
                </div>
              ))}
            </div>

            <div className="pos">
              <h3>POSITIONING</h3>
              <p>{report.positioning}</p>
            </div>

            <h3 className="sec-h" style={{ marginTop: 18 }}>DNA DEEP DIVE</h3>
            <div className="deep">
              {ORDER.map((k) => {
                const s = secs[k] ?? {};
                const [kick, title] = TITLES[k];
                const skip = new Set(["score", "evidence", "strategy_line", "standout_titles", "tiers_label"]);
                return (
                  <div className="dcard" key={k} style={{ borderTopColor: COLORS[k] }}>
                    <div className="badge" style={{ borderColor: COLORS[k], color: COLORS[k] }}>{s.score ?? 0}</div>
                    <div className="kick" style={{ color: COLORS[k] }}>{kick}</div>
                    <h4>{title}</h4>
                    <div className="strat">{s.strategy_line}</div>
                    {s.evidence && <>
                      <div className="flabel" style={{ color: COLORS[k] }}>EVIDENCE</div>
                      <div className="ev"><CiteText text={truncateEvidence(s.evidence)} valid={new Set(sources.map((x: any) => x.n))} /></div>
                    </>}
                    {Object.entries(s).map(([fk, fv]) => {
                      if (skip.has(fk) || typeof fv !== "string" || !fv.trim()) return null;
                      const label = k === "revenue" && fk === "tiers" ? (s.tiers_label || "SUBSCRIPTION TIERS") : fk.replace(/_/g, " ").toUpperCase();
                      const val = String(fv);
                      if (fk === "content_mix") {
                        return (
                          <div key={fk}>
                            <div className="flabel" style={{ color: COLORS[k] }}>{label}</div>
                            <MixBars text={val} color={COLORS[k]} />
                          </div>
                        );
                      }
                      const looksLikeList = val.length > 120 && /[,;]/.test(val);
                      return (
                        <div key={fk}>
                          <div className="flabel" style={{ color: COLORS[k] }}>{label}</div>
                          {looksLikeList && (fk.includes("genre") || fk.includes("segment"))
                            ? <div className="chips">{val.split(/[,;]+/).slice(0, 6).map((c, i) => <span className="chip" key={i}>{c.trim().slice(0, 60)}</span>)}</div>
                            : <div className="ftext">{val}</div>}
                        </div>
                      );
                    })}
                    {k === "content" && (s.standout_titles ?? []).length > 0 && <>
                      <div className="flabel" style={{ color: COLORS[k] }}>STANDOUT TITLES</div>
                      {(s.standout_titles ?? []).map((t: any, i: number) => (
                        <div className="ftext" key={i} style={{ margin: "4px 0" }}><b>{t.title}</b> — {t.why}</div>
                      ))}
                    </>}
                  </div>
                );
              })}
            </div>

            <h3 className="sec-h" style={{ marginTop: 18 }}>ACQUISITION WISHLIST</h3>
            <div className="wish">
              {(report.wishlist ?? []).map((w: string, i: number) => {
                const segs = String(w).split("**");
                // Balanced ** only: odd segments are bold; unbalanced text stays plain.
                const balanced = segs.length >= 3 && segs.length % 2 === 1;
                return (
                <div className="wishitem" key={i}>
                  › {balanced
                    ? segs.map((seg, j) => (j % 2 === 1 ? <b key={j}>{seg}</b> : <span key={j}>{seg}</span>))
                    : <span>{String(w).replace(/\*\*/g, "")}</span>}
                </div>
                );
              })}
            </div>

            <h3 className="sec-h" style={{ marginTop: 18 }}>PITCH PLAYBOOK</h3>
            <div className="flabel" style={{ color: "#6366f1" }}>PITCH ANGLE</div>
            <div className="ftext" style={{ textAlign: "center", maxWidth: 900, margin: "0 auto" }}>{report.pitch?.angle}</div>
            <div className="flabel" style={{ color: "#a855f7" }}>IDEAL TITLE PROFILE</div>
            <div className="ftext" style={{ textAlign: "center", maxWidth: 900, margin: "0 auto" }}>{report.pitch?.ideal_profile}</div>
            <div className="yesno" style={{ marginTop: 10 }}>
              <div>
                <div className="flabel" style={{ color: "#10b981" }}>INSTANT YES SIGNALS</div>
                <ul style={{ listStyle: "none", padding: 0 }}>
                  {(report.pitch?.yes ?? []).map((y: string, i: number) => <li key={i}>✓ {y}</li>)}
                </ul>
              </div>
              <div>
                <div className="flabel" style={{ color: "#f43f5e" }}>INSTANT NO SIGNALS</div>
                <ul style={{ listStyle: "none", padding: 0 }}>
                  {(report.pitch?.no ?? []).map((n: string, i: number) => <li key={i}>✕ {n}</li>)}
                </ul>
              </div>
            </div>
            <div className="flabel" style={{ color: "#f59e0b" }}>NEGOTIATION INTELLIGENCE</div>
            <div className="ftext" style={{ textAlign: "center", maxWidth: 900, margin: "0 auto" }}>{report.pitch?.negotiation}</div>
            {pack && <div className="hint" style={{ marginTop: 10 }}>Evidence: {pack.facts?.length ?? 0} facts · {(pack.titles ?? []).length} titles · validated before delivery.</div>}
          </div>
        )}
      </div>
    </>
  );
}
