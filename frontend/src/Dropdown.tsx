import { useEffect, useMemo, useRef, useState } from "react";

export type Option = { value: string; label: string; group?: string };

export default function Dropdown({
  label,
  value,
  options,
  onPick,
  searchPlaceholder,
}: {
  label: string;
  value: string;
  options: Option[];
  onPick: (v: string) => void;
  searchPlaceholder: string;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const list = needle
      ? options.filter((o) => (o.label + " " + (o.group || "")).toLowerCase().includes(needle))
      : options;
    const groups: Record<string, Option[]> = {};
    const order: string[] = [];
    for (const o of list) {
      const g = o.group || "Other";
      if (!groups[g]) {
        groups[g] = [];
        order.push(g);
      }
      groups[g].push(o);
    }
    order.sort((a, b) => a.localeCompare(b));
    for (const g of order) groups[g].sort((a, b) => a.label.localeCompare(b.label));
    return { groups, order, total: list.length };
  }, [options, q]);

  return (
    <div>
      <label className="lbl">{label}</label>
      <div className="dd" ref={boxRef}>
        <button
          type="button"
          className="dd-btn"
          aria-haspopup="listbox"
          aria-expanded={open}
          onClick={() => { setOpen(!open); setQ(""); }}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setOpen(!open); setQ(""); } }}
        >
          <span className="dd-val">{value || `Select ${label.toLowerCase()}…`}</span>
          <span className="dd-caret">▾</span>
        </button>
        {open && (
          <div className="dd-panel" role="listbox" aria-label={label}>
            <input
              type="text"
              className="dd-search"
              autoFocus
              placeholder={searchPlaceholder}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Escape") setOpen(false); }}
              aria-label={searchPlaceholder}
            />
            <div className="dd-list">
              {filtered.total === 0 && <div className="dd-empty">No matches.</div>}
              {filtered.order.map((g) => (
                <div key={g}>
                  <div className="dd-group">{g}</div>
                  {filtered.groups[g].map((o) => (
                    <div
                      key={o.value}
                      role="option"
                      aria-selected={o.value === value}
                      tabIndex={0}
                      className={"dd-item" + (o.value === value ? " sel" : "")}
                      onClick={() => { onPick(o.value); setOpen(false); }}
                      onKeyDown={(e) => { if (e.key === "Enter") { onPick(o.value); setOpen(false); } }}
                    >
                      {o.label}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
