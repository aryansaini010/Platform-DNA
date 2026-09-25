import { useEffect, useMemo, useRef, useState } from "react";
import {
  deleteReport,
  generateDNA,
  getLibrary,
  getPlatforms,
  getProvider,
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
  const [errors, setErrors] = useState<string[]>([]);
  const [enhWarn, setEnhWarn] = useState<string[]>([]);
  const [lib, setLib] = useState<any[]>([]);
  const [forceFresh, setForceFresh] = useState(false);
  const [provider, setProvider] = useState<any | null>(null);
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [regionSnap, setRegionSnap] = useState<{ from: string; to: string } | null>(null);
  // Cumulative polish success across the initial generate + retries, so a
  // second retry only targets kinds that never succeeded (backend returns
  // per-attempt lists, not cumulative).
  const [doneKinds, setDoneKinds] = useState<Set<string>>(new Set());
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    getPlatforms()
      .then((p) => { if (p.length) setPlatforms(p); else setStatus("Backend returned 0 platforms — check /api/platforms."); })
      .catch((e) => setStatus(`Backend unreachable — showing bundled catalogue (${String(e?.message ?? e)})`));
    getRegions()
      .then((r) => { if (r.length) setRegions(r); })
      .catch(() => {});
    getProvider().then(setProvider).catch(() => {});
    refreshLib();
  }, []);

  async function refreshLib() {
    try {
      setLib(await getLibrary());
    } catch {
      setLib([]);
    }
  }

  const platformOptions = useMemo(
    () => platforms.map((p) => ({ value: p.name, label: p.name, group: p.group || "Other" })),
    [platforms]
  );

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
    // silently shrinking regionCount.
    return p.regions as string[];
  }, [platforms, platform, regions]);

  const regionOptions = useMemo(
    () =>
      allowedCodes.map((c) => {
        const label = codeToLabel.get(c) ?? c;
        const nm = regions.find((r) => r.code === c)?.name ?? label;
        return { value: label, label, group: nm.charAt(0).toUpperCase() };
      }),
    [allowedCodes, codeToLabel, regions]
  );

  const regionCount = allowedCodes.length;

  const allowedKey = allowedCodes.join(",");
  useEffect(() => {
    if (!allowedCodes.length) return;
    const cur = /\(([^)]+)\)\s*$/.exec(region || "")?.[1];
    if (!cur || !allowedCodes.includes(cur)) {
      setRegion(codeToLabel.get(allowedCodes[0]) ?? allowedCodes[0]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [platform, platforms, allowedKey]);

  function regionCode(label: string) {
    const m = /\(([^)]+)\)\s*$/.exec(label || "");
    if (m) return m[1];
    const hit = regions.find((r) => r.label === label || r.name === label || r.code === label);
    return hit?.code ?? label;
  }

  async function onGenerate() {
    if (!platform.trim() || busy) return;
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setBusy(true);
    setErrors([]);
    setEnhWarn([]);
    setRegionSnap(null);
    const backend = provider?.provider === "ollama" ? "Ollama GPU polish"
      : provider?.provider === "groq" ? "Groq polish" : "AI polish";
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
      const snap = res.stats?.region_snap;
      setRegionSnap(snap ?? null);
      const snapNote = snap ? ` Region snapped to ${snap.to} (platform doesn't serve ${snap.from}).` : "";
      const s = res.stats ?? {};
      const detail = s.reused ? "" :
        ` Research: ${s.pages_ok ?? "?"} ok / ${s.pages_failed ?? "?"} failed, ${s.queries ?? "?"} queries in ${s.research_s ?? "?"}s`
        + (s.gaps_remaining?.length ? `, gaps: ${s.gaps_remaining.join(", ")}` : ", no gaps")
        + (s.enhanced ? ` · polished: ${(s.enhanced ?? []).join(",")}${s.enhanced_top?.length ? "+" + s.enhanced_top.join(",") : ""} in ${s.enhance_s ?? "?"}s` : "");
      if ((res.errors ?? []).length === 0) {
        setStatus((res.reused ? `Loaded saved evidence (${res.reused}) — no re-scrape.` : `Valid — overall ${res.report?.overall?.score}/100 in ${s.elapsed_s ?? "?"}s. Saved to library.${detail}`) + snapNote);
        if (snap && snap.to) {
          const lbl = regions.find((r) => r.name === snap.to)?.label ?? snap.to;
          if (lbl) setRegion(lbl);
        }
        refreshLib();
      } else {
        setStatus("Generated with validation errors — fix facts or sharpen fields, then regenerate." + snapNote + detail);
        refreshLib();
      }
    } catch (e: any) {
      if (ctrl.signal.aborted) {
        setErrors(["Cancelled — the backend may still be working. Use Refresh below; a late-saved report will appear in Recently ready."]);
      } else {
        const msg = String(e?.message ?? e);
        const aborted = /abort/i.test(msg);
        setErrors([aborted
          ? "Request timed out after 13 min — the backend may still be working. Use Refresh below; a late-saved report will appear in Recently ready."
          : msg]);
      }
      setStatus("");
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
    const missing = all.filter((k) => !doneKinds.has(k));
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
      setStatus((res.errors ?? []).length === 0 ? "Retry complete — report saved." : "Retry done with validation errors (listed above).");
      refreshLib();
    } catch (e: any) {
      setErrors([String(e?.message ?? e)]);
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
      setErrors([]);
      setEnhWarn([]);
      setDoneKinds(new Set());
      setRegionSnap(null);
      // Sync the dropdowns to the opened report so Regenerate targets
      // the visible report instead of a stale dropdown selection.
      if (res.pack?.platform) setPlatform(res.pack.platform);
      if (res.pack?.region) {
        const lbl = regions.find((r) => r.name === res.pack.region || r.code === res.pack.region)?.label;
        setRegion(lbl ?? res.pack.region);
      }
      setStatus("");
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e: any) {
      setErrors([String(e?.message ?? e)]);
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
                label="Platform"
                value={platform}
                options={platformOptions}
                onPick={setPlatform}
                searchPlaceholder="Search platforms…"
              />
              <div className="hint">Sourced from the curated catalogue ({platforms.length} services).</div>
            </div>
            <div>
              <Dropdown
                label="Region"
                value={region}
                options={regionOptions}
                onPick={setRegion}
                searchPlaceholder="Search regions…"
              />
              <div className="hint">{regionCount} region(s) available for {platform || "—"}. Pick a platform first.</div>
            </div>
          </div>
          <div className="row" style={{ justifyContent: "center" }}>
            <button className="btn primary" disabled={!platform.trim() || busy} onClick={onGenerate}>✦ {busy ? "Generating…" : "Generate DNA"}</button>
            {busy && <button className="btn small" onClick={onCancel}>✕ Cancel</button>}
          </div>
          <div className="row" style={{ justifyContent: "center", marginTop: 8 }}>
            <label className="muted" style={{ display: "flex", gap: 6, alignItems: "center", cursor: "pointer" }}>
              <input type="checkbox" checked={forceFresh} disabled={busy} onChange={(e) => setForceFresh(e.target.checked)} />
              Force fresh re-research (ignore saved report)
            </label>
          </div>
          <div className="hint">Saved reports load instantly · fresh runs use deep research + AI polish.</div>
          {provider && (
            <div className="hint">
              Backend: {provider.provider}
              {provider.provider === "ollama" ? ` (${provider.ollama_model ?? "Ollama"})` : ""}
              {provider.provider === "groq" ? ` (${provider.groq_model ?? "Groq"})` : ""}
              {!provider.has_any ? " — no LLM configured; reports will be deterministic drafts." : ""}
              {provider.provider === "ollama" && !provider.has_ollama ? " — Ollama URL not reachable; check the SSH tunnel." : ""}
            </div>
          )}
          {regionSnap && (
            <div className="warn">Region snapped: {regionSnap.from} → {regionSnap.to} (platform doesn’t serve the requested region).</div>
          )}
          {status && <div className="ok" role="status">{busy ? <span className="spin">{status}</span> : status}</div>}
          {errors.length > 0 && <div className="err" role="alert">{errors.map((e, i) => <div key={i}>• {e}</div>)}
            {!entry && markdown && (
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
                <span className="muted">Not saved — failed validation.</span>
              </div>
            )}
          </div>}
          {enhWarn.length > 0 && <div className="warn">AI polish fell back to deterministic text:<div>{enhWarn.map((e, i) => <div key={i}>• {e}</div>)}</div>{pack && <div style={{ marginTop: 8 }}><button className="btn small" disabled={busy} onClick={retryPolish}>↻ Retry failed polish only (no re-research)</button></div>}</div>}
        </div>

        <div className="card">
          <div className="row" style={{ marginTop: 0 }}>
            <h2 style={{ textAlign: "left" }}>Recently ready</h2>
            <button className="btn small" onClick={refreshLib}>⟳ Refresh</button>
          </div>
          {lib.length === 0 && <div className="muted">Library is empty — generate a report above (auto-saved on success).</div>}
          {lib.slice(0, 12).map((r) => (
            <div className="lib-card" key={r.id} onClick={() => openEntry(r.id)} title="Open report">
              <div>
                <div className="lib-title">{r.platform} · {r.region}</div>
                <div className="muted">{r.created} · {r.titles} titles · overall {r.overall}/100</div>
              </div>
              <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span className="dot" />
                <button className="btn small" onClick={async (e) => { e.stopPropagation(); await deleteReport(r.id); refreshLib(); }}>✕</button>
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
