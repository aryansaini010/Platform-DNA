const API = (import.meta as any).env?.VITE_API_URL || "http://127.0.0.1:8001";

function throwDetail(path: string, status: number, text: string): never {
  // Surface backend JSON detail ({detail}) instead of a bare status.
  // Attaches .status so callers can still distinguish 4xx from 5xx/network.
  let msg = text.slice(0, 500) || `${path} failed: ${status}`;
  try {
    const j = JSON.parse(text);
    msg = (j as any).detail || msg;
  } catch {
    /* plain-text body: use as-is */
  }
  const err: any = new Error(msg);
  err.status = status;
  throw err;
}

async function jget(path: string) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 30000);
  try {
    const r = await fetch(API + path, { signal: ctrl.signal });
    if (!r.ok) throwDetail(path, r.status, await r.text());
    return r.json();
  } finally {
    clearTimeout(t);
  }
}

export async function getPlatforms() {
  try {
    const d = await jget("/api/platforms");
    // Empty list from the backend is authoritative (do not mask with stale bundle).
    if (!Array.isArray(d.platforms)) throw new Error("/api/platforms: bad shape");
    return d.platforms as any[];
  } catch (e: any) {
    if (e?.status && e.status < 500) throw e;
    console.warn("backend unreachable, using bundled platforms.json", e);
    const m = await import("./data/platforms.json");
    return (m as any).default ?? (m as any);
  }
}

export async function getRegions() {
  try {
    const d = await jget("/api/regions");
    if (!Array.isArray(d.regions)) throw new Error("/api/regions: bad shape");
    return d.regions as any[];
  } catch (e: any) {
    if (e?.status && e.status < 500) throw e;
    console.warn("backend unreachable, using bundled regions.json", e);
    const m = await import("./data/regions.json");
    return (m as any).default ?? (m as any);
  }
}

export async function getLibrary() {
  const d = await jget("/api/library");
  return d.reports as any[];
}

export async function getReport(id: string) {
  return jget(`/api/report/${encodeURIComponent(id)}`);
}

export async function generateDNA(body: {
  platform: string;
  region: string;
  depth: string;
  force: boolean;
  enhance: boolean;
  polish_facts?: boolean;
  pack?: any;
  retry?: string[];
}, signal?: AbortSignal) {
  const ctrl = new AbortController();
  // Worst case: research (~130s) + Ollama deadline (600s) + retries.
  // Abort budget sits above the backend worst case (~730s) with margin.
  const t = setTimeout(() => ctrl.abort(), 780000);
  const onAbort = () => ctrl.abort();
  signal?.addEventListener("abort", onAbort);
  try {
    const r = await fetch(API + "/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
    if (!r.ok) throwDetail("/api/generate", r.status, await r.text());
    return r.json();
  } finally {
    clearTimeout(t);
    signal?.removeEventListener("abort", onAbort);
  }
}

export async function deleteReport(id: string) {
  const r = await fetch(API + `/api/report/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`delete failed: ${r.status}`);
  return r.json();
}

export function pdfUrl(id: string) {
  return `${API}/api/report/${encodeURIComponent(id)}/pdf`;
}

export function jsonUrl(id: string) {
  return `${API}/api/report/${encodeURIComponent(id)}/json`;
}

export function markdownUrl(id: string) {
  return `${API}/api/report/${encodeURIComponent(id)}/markdown`;
}

export async function getProvider() {
  try {
    return await jget("/api/provider");
  } catch {
    return { provider: "unknown" };
  }
}

export { API };
