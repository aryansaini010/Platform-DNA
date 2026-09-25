"""Scoring: overall is half-up round(mean(sections)); blind-rescore guard (plan §4 Step 5)."""
from __future__ import annotations

import math as _math


def overall(scores: dict[str, int]) -> int:
    if not scores:
        return 0
    vals: list[int] = []
    for v in scores.values():
        try:
            vals.append(int(v))
        except Exception:
            continue
    if not vals:
        return 0
    # Half-up to match human math (bankers round(58.5)=58 surprises analysts).
    return int(_math.floor(sum(vals) / len(vals) + 0.5))


def blind_rescore_ok(writer_score: int, blind_score: int, tol: int = 8) -> bool:
    return abs(writer_score - blind_score) <= tol
