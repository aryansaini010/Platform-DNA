"""Facts: typed store + conflict/staleness detection in code (plan Step 3)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from .config import CONFLICT_PCT, STALENESS_MONTHS


@dataclass
class Fact:
    slot: str
    claim: str
    value: str = ""
    unit: str = ""
    source_url: str = ""
    source_date: str = "date unknown"  # YYYY-MM-DD or 'date unknown'
    tier: int = 3
    confidence: str = "medium"
    flags: list[str] = field(default_factory=list)
    # Two facts are only compared for conflict when they share an explicit
    # metric id (e.g. two rival India-subscriber estimates). Without it, each
    # fact is its own series and time-series/global-vs-India pairs never
    # false-positive.
    metric: str = ""


_NUM_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> list[float]:
    out: list[float] = []
    for m in _NUM_RE.finditer(text.replace("\u20b9", "").replace("$", "")):
        try:
            out.append(float(m.group(0).replace(",", "")))
        except ValueError:
            pass
    return out


def _parse_date(s: str):
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    # Accept YYYY-MM-DD, YYYY-MM, YYYY-MM-DDTHH:MM:SS (ISO prefix), YYYY/MM/DD
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y/%m/%d", "%Y/%m"):
        try:
            return datetime.strptime(s[:len(fmt)] if len(s) >= len(fmt) else s, fmt).date()
        except Exception:
            continue
    # Fallback: ISO prefix e.g. 2026-03-15T00:00:00
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except Exception:
        return None


def mark_staleness(f: Fact, today: date | None = None) -> bool:
    d = _parse_date(f.source_date)
    if d is None:
        return False
    today = today or date.today()
    # Day-precision: compare month boundaries correctly.
    months = (today.year - d.year) * 12 + (today.month - d.month)
    if today.day < d.day:
        months -= 1
    if months > STALENESS_MONTHS:
        if "STALE" not in f.flags:
            f.flags.append("STALE")
        return True
    return False


def _norm_unit(u: str) -> str:
    u = (u or "").strip().lower()
    u = re.sub(r"\s+", " ", u)
    # Unify money scales: "INR", "crore INR", "Rs", "₹" -> comparable families
    if not u:
        return ""
    if "crore" in u:
        return "crore"
    if "lakh" in u:
        return "lakh"
    if "billion" in u:
        return "billion"
    if "million" in u:
        return "million"
    if "thousand" in u:
        return "thousand"
    if u in ("inr", "rs", "rs.", "₹", "rupee", "rupees"):
        return "inr"
    if u in ("usd", "$", "dollar", "dollars"):
        return "usd"
    # Subscriber/download synonyms: "users" vs "subscribers" for the same
    # slot is the same metric restated, not a different one.
    if u in ("subscribers", "subscriber", "users", "user", "members",
             "member", "memberships", "membership"):
        return "subscribers"
    if u in ("downloads", "download", "installs", "install"):
        return "downloads"
    if "percent" in u or u == "%":
        return "percent"
    return u


_DATE_STRIP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}|\d{4}/\d{2}/\d{2}"
    r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}",
    re.I,
)


def _fact_numbers(f: Fact) -> list[float]:
    """Prefer explicit value numbers; fall back to claim with dates stripped.

    Prevents years (2026-01-15 -> 2026,1,15) from becoming the compared metric.
    """
    if (f.value or "").strip():
        ns = numbers_in(f.value)
        if ns:
            return ns
    claim = _DATE_STRIP_RE.sub(" ", f.claim or "")
    ns = numbers_in(claim)
    # Drop bare 4-digit years when other numbers exist (year is not the metric)
    if len(ns) > 1:
        filtered = [n for n in ns if not (1900 <= n <= 2100 and float(n).is_integer())]
        if filtered:
            return filtered
    return ns


_MONEY_SCALE = {"inr": 1.0, "crore": 1e7, "lakh": 1e5}


def _conflict_group(unit: str) -> str:
    """Grouping key for conflict detection. INR money scales (inr/crore/
    lakh) group together so restatements ("Rs 325 crore" vs "Rs 3.25
    billion" is out of scope) like "Rs 325 crore" vs a plain "Rs" figure
    meet and compare by scaled value. USD and scale-ambiguous units keep
    their own groups: no cross-currency false conflicts."""
    nu = _norm_unit(unit)
    if nu in _MONEY_SCALE:
        return "inr-money"
    return nu


def detect_conflicts(facts: list[Fact]) -> list[str]:
    conflicts: list[str] = []
    by_metric: dict[str, list[Fact]] = {}
    for idx, f in enumerate(facts):
        # Facts with an explicit metric compare only within that metric.
        # Facts without one compare within slot+normalized-unit so genuine
        # divergences (100 vs 200 subscribers) are still surfaced.
        if f.metric:
            key = f.slot + "\x00" + f.metric
        else:
            key = f.slot + "\x00" + "__slot__" + "\x00" + _conflict_group(f.unit)
        by_metric.setdefault(key, []).append(f)
    for key, items in by_metric.items():
        if len(items) < 2:
            continue
        slot = key.split("\x00")[0]
        nums = [(f, _fact_numbers(f)) for f in items]
        nums = [(f, ns) for f, ns in nums if ns]
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                a, na = nums[i]
                b, nb = nums[j]
                va, vb = na[0], nb[0]
                if va == 0 or vb == 0:
                    continue
                # Units already grouped by normalized family; only skip when
                # both are non-empty and families genuinely differ — except
                # INR money scales, which compare by scaled value ("₹325
                # crore" vs "₹3.25 billion" is the same figure restated).
                if _norm_unit(a.unit) != _norm_unit(b.unit) and a.unit and b.unit:
                    sca, scb = _MONEY_SCALE.get(_norm_unit(a.unit)), \
                        _MONEY_SCALE.get(_norm_unit(b.unit))
                    if sca is None or scb is None:
                        # Different metric, not a conflict.
                        continue
                    va, vb = va * sca, vb * scb
                denom = max(abs(va), abs(vb))
                if denom == 0:
                    continue
                if abs(va - vb) / denom >= CONFLICT_PCT:
                    if "CONFLICT" not in a.flags:
                        a.flags.append("CONFLICT")
                    if "CONFLICT" not in b.flags:
                        b.flags.append("CONFLICT")
                    conflicts.append(
                        "CONFLICT slot=%s: '%s' (%s) vs '%s' (%s) - "
                        "report both, do not resolve." % (slot, a.value, a.source_date, b.value, b.source_date)
                    )
    return conflicts


def coverage_gaps(facts: list[Fact], required: dict[str, list[str]]) -> dict[str, list[str]]:
    have = {f.slot for f in facts if f.claim.strip()}
    return {sec: [s for s in slots if s not in have] for sec, slots in required.items()}


_TRUNCATED_MONEY = re.compile(r"^[₹$\s]*[\d,\.]+$", re.I)
_TRUNCATED_MONEY_RS = re.compile(r"^(?:rs\.?|inr)\s?[\d,\.]+$", re.I)
_MONEY_TAIL = re.compile(
    r"([₹$]\s?[\d,\.]+|(?:rs\.?|inr)\s?[\d,\.]+)\s*(billion|million|crore|lakh|bn|mn|trillion|m\b|b\b)", re.I)


def repair_value(value: str, claim: str) -> str:
    """Heal truncated money values ('$110' where the claim carries
    '$110 Billion'). The claim is verbatim store, so extending the value
    from it keeps validator grounding intact."""
    if not value:
        return value
    v = value.strip()
    if _TRUNCATED_MONEY.match(v) or _TRUNCATED_MONEY_RS.match(v):
        m = _MONEY_TAIL.search(claim or "")
        if m:
            digits_v = re.sub(r"\D", "", v)
            digits_m = re.sub(r"\D", "", m.group(1))
            if digits_v and digits_v == digits_m:
                return m.group(0)
    return value
