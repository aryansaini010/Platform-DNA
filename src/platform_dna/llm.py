"""LLM writing stage (plan Steps 4 & 6).

System = prompts/system_prompt.md ([[OTT_PLATFORM_NAME]] / [[REGION]] filled)
+ prompts/pipeline_addendum.md. Each call writes ONE section from the evidence
pack plus the matching JioHotstar section as format reference (prompt caching
recommended: the system + example prefix is stable across calls).

Deterministic pipeline stays in charge: scores, overall, header counts,
layout and validation are all computed in code. The model only upgrades
prose — and the validator still rejects any invented figure.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import httpx

from .composer import (audience_fields, content_fields, distribution_fields,
                       editorial_fields, emotional_fields, ranked,
                       revenue_fields)

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"


def _load_dotenv() -> None:
    """Backend-only keys live in repo-root .env (never in the frontend)."""
    env = Path(__file__).resolve().parents[2] / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip("\"'")
        if k and k not in os.environ:
            os.environ[k] = v


_load_dotenv()

BUILDERS = {"content": content_fields, "audience": audience_fields,
            "emotional": emotional_fields, "distribution": distribution_fields,
            "revenue": revenue_fields, "editorial": editorial_fields}

SECTION_KEYS: dict[str, list[str]] = {
    sec: [k for k, v in fn("P", [], []).items()
          if isinstance(v, str) and k not in ("evidence", "tiers_label")]
    for sec, fn in BUILDERS.items()
}

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
# 429-only fallback on a separate TPM bucket (primary stays 120b).
# Enable the fallback once at console.groq.com -> settings -> project ->
# limits, else it 403s and the section keeps deterministic text.
# NOTE: gpt-oss-20b / qwen models are project-blocked on some Groq accounts
# (403 model_permission_blocked_project) — llama-3.1-8b-instant is the safe
# default fallback; validator still gates every fallback output.
GROQ_FALLBACK_MODEL = os.environ.get("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
# Ollama-primary (local GPU, e.g. RTX 5090 via SSH tunnel or on-server).
# OLLAMA_URL must be set explicitly to opt in (no silent localhost default
# that would mask a missing tunnel as "configured"). When set, auto mode
# prefers Ollama and keeps Groq/Anthropic only as fallback.
OLLAMA_URL = os.environ.get("OLLAMA_URL", "").strip().rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gpt-oss:20b")
OLLAMA_NUM_CTX = int(os.environ.get("OLLAMA_NUM_CTX", "8192") or 8192)
OLLAMA_TIMEOUT_S = float(os.environ.get("OLLAMA_TIMEOUT_S", "180") or 180)


def llm_provider_mode() -> str:
    return (os.environ.get("LLM_PROVIDER", "auto") or "auto").strip().lower()
# Portable: repo-root example if present, else no example (never a hard-coded
# developer-machine path).
_EXAMPLE_CANDIDATES = (
    Path(__file__).resolve().parents[2] / "outputs" / "JioHotstar_Platform_DNA_Report.md",
    Path(__file__).resolve().parents[2] / "data" / "library",
)
EXAMPLE_DEFAULT = str(_EXAMPLE_CANDIDATES[0])


def load_system(platform: str, region: str) -> str:
    sys = (PROMPTS / "system_prompt.md").read_text(encoding="utf-8")
    add = (PROMPTS / "pipeline_addendum.md").read_text(encoding="utf-8")
    sys = sys.replace("[[OTT_PLATFORM_NAME]]", platform).replace(
        "[[REGION — default \"India, all language markets\"]]", region)
    sys = sys.replace("[[OTT_PLATFORM_NAME]]", platform).replace("[[REGION]]", region)
    return sys + "\n\n" + add


def split_example(path: str | None = None) -> dict[str, str]:
    """Split the JioHotstar reference report into its six section texts."""
    candidates: list[Path] = []
    if path:
        candidates.append(Path(path))
    candidates.append(_EXAMPLE_CANDIDATES[0])
    # Fall back to the newest library report that parses into sections.
    try:
        lib = _EXAMPLE_CANDIDATES[1]
        if lib.exists():
            for p in sorted(lib.glob("*.md"), reverse=True)[:5]:
                candidates.append(p)
    except Exception:
        pass
    for cand in candidates:
        try:
            text = cand.read_text(encoding="utf-8")
        except Exception:
            continue
        parts = re.split(r"(?m)^### \d+\. \w+ DNA", text)
        names = [n.lower() for n in re.findall(r"(?m)^### \d+\. (\w+) DNA", text)]
        if not names:
            continue
        out = dict(zip(names, parts[1:]))
        shaped = {k: v.strip()[:6000] for k, v in out.items() if v.strip()}
        if shaped:
            return shaped
    return {}


def has_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def has_groq_key() -> bool:
    return bool(os.environ.get("GROQ_API_KEY"))


def has_ollama() -> bool:
    mode = llm_provider_mode()
    if mode in ("groq", "anthropic", "deterministic"):
        return False
    if mode == "ollama":
        return bool(OLLAMA_URL)
    return bool(OLLAMA_URL)


def has_any_key() -> bool:
    return has_groq_key() or has_key() or has_ollama()


def active_provider() -> str:
    mode = llm_provider_mode()
    if mode == "ollama":
        return "ollama" if has_ollama() else "deterministic"
    if mode == "groq":
        return "groq" if has_groq_key() else "deterministic"
    if mode == "anthropic":
        return "anthropic" if has_key() else "deterministic"
    if mode == "deterministic":
        return "deterministic"
    # auto: Ollama-primary when configured, else legacy Groq-first.
    if has_ollama():
        return "ollama"
    if has_groq_key():
        return "groq"
    if has_key():
        return "anthropic"
    return "deterministic"


def anthropic_complete(system: str, user: str, max_tokens: int = 3000,
                       temperature: float = 0.2) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": os.environ.get("ANTHROPIC_MODEL", MODEL),
              "max_tokens": max_tokens, "temperature": temperature,
              "system": system,
              "messages": [{"role": "user", "content": user}]},
        timeout=180)
    r.raise_for_status()
    blocks = r.json().get("content", [])
    return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")


def enhance_section(platform: str, region: str, sec: str, draft_fields: dict,
                    facts: list[dict], stats: dict, example_text: str) -> dict:
    """Rewrite one section's prose fields via LLM. Returns {key: text}.

    Provider priority: Ollama first when OLLAMA_URL is set (LLM_PROVIDER
    auto/ollama), then Groq (GROQ_API_KEY), then Anthropic fallback.
    """
    if has_ollama():
        try:
            return enhance_section_ollama(platform, region, sec, draft_fields,
                                          facts, stats, example_text)
        except Exception:
            if llm_provider_mode() == "ollama":
                raise
            # auto mode: fall through to Groq/Anthropic.
    if has_groq_key():
        try:
            return enhance_section_groq(platform, region, sec, draft_fields,
                                        facts, stats, example_text)
        except Exception:
            if not has_key():
                raise
    keys = SECTION_KEYS[sec]
    # Lean prompts (free-tier TPM): top-12 facts only.
    fact_lines = [f"[{f['slot']}] {f.get('value', '')} :: {f['claim']} "
                  f"({f.get('source_date', '')}, tier {f.get('tier', 3)})"
                  for f in ranked(facts)[:12]]
    user = json.dumps({
        "task": f"Rewrite the {sec.upper()} DNA section prose for {platform} ({region}).",
        "score_assigned": draft_fields.get("score"),
        "evidence_pack_facts": fact_lines,
        "computed_stats": stats,
        "current_draft_fields": {k: draft_fields.get(k, "") for k in keys},
        "format_reference_section_JioHotstar_STRUCTURE_AND_TONE_ONLY": example_text,
        "return_json_keys": keys,
    }, ensure_ascii=False)
    system = load_system(platform, region)
    raw = anthropic_complete(system, user)
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    data = json.loads(cleaned)
    missing = [k for k in keys if k not in data]
    if missing:
        raise ValueError(f"LLM response missing keys: {missing}")
    return {k: str(data[k]) for k in keys}


def groq_complete(system: str, user: str, max_tokens: int = 1800,
                  temperature: float = 0.2,
                  model: str | None = None) -> str:
    """OpenAI-compatible chat call to Groq with strict JSON object mode.

    Free-tier aware: honors Retry-After on 429 (capped) with jitter and
    retries the same model once before falling to the 429-only fallback
    model on a separate TPM bucket. Raises with Groq's real error body.
    """
    import random as _rnd
    import time as _time

    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY is not set.")
    models = [model or os.environ.get("GROQ_MODEL", GROQ_MODEL), GROQ_FALLBACK_MODEL]
    # Quality-first 429 policy: one capped wait then same-model retry, then
    # fallback model (429-only). Cap keeps p90 inside the 3-4 min budget.
    RETRY_AFTER_CAP = float(os.environ.get("GROQ_RETRY_AFTER_CAP", "25"))
    last_err: Exception | None = None
    for i, m in enumerate(dict.fromkeys(models)):
        if i:
            _time.sleep(3)  # transient gateway blips (incl. stray 403s)
        waits = 0
        while waits < 2:
            try:
                r = httpx.post(
                    GROQ_API_URL,
                    headers={"Authorization": f"Bearer {key}",
                             "Content-Type": "application/json"},
                    json={"model": m,
                          "max_tokens": max_tokens, "temperature": temperature,
                          "response_format": {"type": "json_object"},
                          "messages": [{"role": "system", "content": system},
                                       {"role": "user", "content": user}]},
                    timeout=60)
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"] or "{}"
            except Exception as e:  # noqa: BLE001
                # Surface Groq's real error body (permission blocks, key
                # issues, rate-limit codes) instead of a bare HTTP status.
                detail = ""
                retry_after: float | None = None
                try:
                    import httpx as _hx
                    if isinstance(e, _hx.HTTPStatusError) and e.response is not None:
                        detail = " | groq says: %s" % (e.response.text or "")[:400]
                        if e.response.status_code == 429:
                            try:
                                retry_after = min(
                                    RETRY_AFTER_CAP, float(e.response.headers.get("retry-after", "25")))
                            except Exception:
                                retry_after = min(RETRY_AFTER_CAP, 25.0)
                except Exception:
                    pass
                if retry_after is not None and waits == 0:
                    waits += 1
                    _time.sleep(retry_after + _rnd.uniform(0, 2))
                    continue
                last_err = RuntimeError(f"Groq call failed ({m}): {e}{detail}")
                break
    raise RuntimeError(f"Groq call failed: {last_err}")


def ollama_complete(system: str, user: str, max_tokens: int = 1800,
                      temperature: float = 0.1,
                      model: str | None = None,
                      num_ctx: int | None = None) -> str:
    """OpenAI-compatible chat call to local Ollama (GPU server).

    No API key, no TPM/429 handling — local inference only. Connection
    failures (dead SSH tunnel / Ollama down) trip a per-process cooldown
    so the remaining calls in a generate fail fast (~0s) instead of each
    paying connect timeouts + retries. Other errors keep one immediate
    retry, then raise for fallback (auto) or enhance_errors (ollama-only).
    """
    import time as _time

    base = (os.environ.get("OLLAMA_URL", "") or "").strip().rstrip("/")
    if not base:
        raise RuntimeError("OLLAMA_URL is not set.")
    global _OLLAMA_DEAD_UNTIL
    try:
        if _time.time() < _OLLAMA_DEAD_UNTIL:
            raise RuntimeError(
                f"Ollama unreachable (cooldown): {base} refused recently; "
                "restart the SSH tunnel, then retry.")
    except NameError:
        _OLLAMA_DEAD_UNTIL = 0.0
    m = model or os.environ.get("OLLAMA_MODEL", OLLAMA_MODEL) or "gpt-oss:20b"
    ctx = int(num_ctx or OLLAMA_NUM_CTX)
    url = base + "/v1/chat/completions"
    payload = {"model": m,
               "max_tokens": max_tokens, "temperature": temperature,
               "response_format": {"type": "json_object"},
               "options": {"num_ctx": ctx, "temperature": temperature},
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user}]}
    last_err: Exception | None = None
    for _ in range(2):
        try:
            r = httpx.post(url, json=payload, timeout=OLLAMA_TIMEOUT_S)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"] or "{}"
        except Exception as e:  # noqa: BLE001
            last_err = e
            if isinstance(e, httpx.ConnectError):
                # Dead tunnel / Ollama down: cool down, no retry sleep.
                _OLLAMA_DEAD_UNTIL = _time.time() + 120.0
                break
            _time.sleep(2)
    raise RuntimeError(f"Ollama call failed ({m} via {base}): {last_err}")


def ollama_reachable(timeout_s: float = 3.0) -> bool:
    """Fast liveness ping for the configured OLLAMA_URL (tags endpoint).

    Called once per generate: when the SSH tunnel is down the whole
    enhance phase skips Ollama immediately instead of letting call #1
    burn connect timeouts. Result is NOT cached across generates — a
    restarted tunnel is picked up on the next run. Model-load state is
    irrelevant here (first inference loads it on demand).
    """
    import time as _time

    base = (os.environ.get("OLLAMA_URL", "") or "").strip().rstrip("/")
    if not base:
        return False
    try:
        if _time.time() < globals().get("_OLLAMA_DEAD_UNTIL", 0.0):
            return False
    except Exception:
        pass
    try:
        r = httpx.get(base + "/api/tags", timeout=timeout_s)
        return r.status_code < 500
    except Exception:
        return False


def is_ollama_unreachable(e: Exception) -> bool:
    """True when e is an Ollama transport failure (dead tunnel/down server).

    Lets api._try skip its 10s outer retry: retrying a refused socket on
    a fixed per-generate cooldown can never succeed, so record and move on.
    """
    s = f"{e}"
    if "OLLAMA_URL is not set" in s or "Ollama unreachable (cooldown)" in s:
        return True
    return "Ollama call failed" in s and (
        "ConnectError" in s or "refused" in s.lower()
        or "Failed to establish" in s)


def _parse_json_object(raw: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(), flags=re.M).strip()
    return json.loads(cleaned)


def _is_groq_json_400(e: Exception) -> bool:
    """True for Groq constrained-decoding failures ('Failed to generate /
    validate JSON'). These are prompt-sensitive, not rate limits: retrying
    the identical prompt usually 400s again, so callers retry once with a
    slimmed prompt (halved example + top-6 facts)."""
    s = f"{e}"
    return "Groq call failed" in s and (
        "Failed to generate JSON" in s or "Failed to validate JSON" in s)


def enhance_section_groq(platform: str, region: str, sec: str, draft_fields: dict,
                         facts: list[dict], stats: dict, example_text: str) -> dict:
    """Groq rewrite of one section. Figures must stay verbatim from facts."""
    keys = SECTION_KEYS[sec]
    # Lean prompts (free-tier TPM): top-12 facts only.
    fact_lines = [f"[{f['slot']}] {f.get('value', '')} :: {f['claim']} "
                  f"({f.get('source_date', '')}, tier {f.get('tier', 3)})"
                  for f in ranked(facts)[:12]]
    extra_keys: dict = {}
    if sec == "content" and isinstance(draft_fields.get("standout_titles"), list):
        # Standout whys are template-y ("2018 Hindi Comedy series original
        # from the mined list"); let the model rewrite WHY only. Titles must
        # come back identical (validator-safe) or the item is reverted.
        extra_keys["standout_titles"] = draft_fields["standout_titles"][:6]
    user = json.dumps({
        "task": f"Rewrite the {sec.upper()} DNA section prose for {platform} ({region}) in JioHotstar density and tone.",
        "rules": [
            "Use ONLY figures already present in evidence_pack_facts values/claims or computed_stats.",
            "Never invent Rs/$/%/year figures. Never reuse JioHotstar facts.",
            "Percentages: reuse ONLY % figures already written with % in evidence_pack_facts, "
            "OR shares exactly computed from computed_stats title counts (e.g. 9 of 10 series titles = 90%) — "
            "always state the basis ('9 of 10 mined titles'). Never estimate other shares.",
            "Keep the same keys and order as current_draft_fields.",
            "JioHotstar reference is STRUCTURE_AND_TONE_ONLY.",
            "standout_titles: keep every title string IDENTICAL; rewrite only each why as one editorial clause on why it matters (named, dated, specific).",
            "Sample fractions like '5 of 6 standout titles' stay as fractions; never convert them into % (no '≈83%').",
            "Return a JSON object only, no thinking trace, no markdown fences.",
        ],
        "score_assigned": draft_fields.get("score"),
        "evidence_pack_facts": fact_lines,
        "computed_stats": stats,
        "current_draft_fields": {k: draft_fields.get(k, "") for k in keys},
        **({"current_standout_titles": extra_keys["standout_titles"]} if extra_keys else {}),
        "format_reference_section_JioHotstar_STRUCTURE_AND_TONE_ONLY": (example_text or "")[:2500],
        "return_json_keys": keys + (["standout_titles"] if extra_keys else []),
    }, ensure_ascii=False)
    system = load_system(platform, region)
    try:
        raw = groq_complete(system, user)
    except Exception as e:  # noqa: BLE001
        if not _is_groq_json_400(e):
            raise
        slim = json.loads(user)
        slim["evidence_pack_facts"] = fact_lines[:6]
        slim["format_reference_section_JioHotstar_STRUCTURE_AND_TONE_ONLY"] = (example_text or "")[:1200]
        raw = groq_complete(system, json.dumps(slim, ensure_ascii=False))
    data = _parse_json_object(raw)
    missing = [k for k in keys if k not in data]
    if missing:
        raise ValueError(f"Groq response missing keys: {missing}")
    out = {k: str(data[k]) for k in keys}
    if extra_keys:
        kept = []
        orig = {str(s.get("title", "")): s for s in extra_keys["standout_titles"]}
        for item in data.get("standout_titles", []) or []:
            t = str((item or {}).get("title", ""))
            why = str((item or {}).get("why", ""))
            if t in orig and why.strip():
                kept.append({"title": t, "why": why.strip()[:300]})
            elif t in orig:
                kept.append(orig[t])
        if len(kept) == len(extra_keys["standout_titles"]):
            out["standout_titles"] = kept
    return out


def enhance_section_ollama(platform: str, region: str, sec: str, draft_fields: dict,
                           facts: list[dict], stats: dict, example_text: str) -> dict:
    """Ollama rewrite of one section. Same prompts/rules as Groq path."""
    keys = SECTION_KEYS[sec]
    fact_lines = [f"[{f['slot']}] {f.get('value', '')} :: {f['claim']} "
                  f"({f.get('source_date', '')}, tier {f.get('tier', 3)})"
                  for f in ranked(facts)[:12]]
    extra_keys: dict = {}
    if sec == "content" and isinstance(draft_fields.get("standout_titles"), list):
        extra_keys["standout_titles"] = draft_fields["standout_titles"][:6]
    user = json.dumps({
        "task": f"Rewrite the {sec.upper()} DNA section prose for {platform} ({region}) in JioHotstar density and tone.",
        "rules": [
            "Use ONLY figures already present in evidence_pack_facts values/claims or computed_stats.",
            "Never invent Rs/$/%/year figures. Never reuse JioHotstar facts.",
            "Percentages: reuse ONLY % figures already written with % in evidence_pack_facts, "
            "OR shares exactly computed from computed_stats title counts (e.g. 9 of 10 series titles = 90%) — "
            "always state the basis ('9 of 10 mined titles'). Never estimate other shares.",
            "Keep the same keys and order as current_draft_fields.",
            "JioHotstar reference is STRUCTURE_AND_TONE_ONLY.",
            "standout_titles: keep every title string IDENTICAL; rewrite only each why as one editorial clause on why it matters (named, dated, specific).",
            "Return a JSON object only, no thinking trace, no markdown fences.",
            "Sample fractions like '5 of 6 standout titles' stay as fractions; never convert them into % (no '≈83%').",
        ],
        "score_assigned": draft_fields.get("score"),
        "evidence_pack_facts": fact_lines,
        "computed_stats": stats,
        "current_draft_fields": {k: draft_fields.get(k, "") for k in keys},
        **({"current_standout_titles": extra_keys["standout_titles"]} if extra_keys else {}),
        "format_reference_section_JioHotstar_STRUCTURE_AND_TONE_ONLY": (example_text or "")[:2500],
        "return_json_keys": keys + (["standout_titles"] if extra_keys else []),
    }, ensure_ascii=False)
    raw = ollama_complete(load_system(platform, region), user)
    data = _parse_json_object(raw)
    missing = [k for k in keys if k not in data]
    if missing:
        raise ValueError(f"Ollama response missing keys: {missing}")
    out = {k: str(data[k]) for k in keys}
    if extra_keys:
        kept = []
        orig = {str(s.get("title", "")): s for s in extra_keys["standout_titles"]}
        for item in data.get("standout_titles", []) or []:
            t = str((item or {}).get("title", ""))
            why = str((item or {}).get("why", ""))
            if t in orig and why.strip():
                kept.append({"title": t, "why": why.strip()[:300]})
            elif t in orig:
                kept.append(orig[t])
        if len(kept) == len(extra_keys["standout_titles"]):
            out["standout_titles"] = kept
    return out


def enhance_top_groq(platform: str, region: str, kind: str,
                     facts: list[dict], current: dict | list | str) -> dict | list | str:
    """Groq polish for summary/positioning/wishlist/pitch/identity.

    kind: summary | positioning | wishlist | pitch | identity.
    Returns same shape as `current`. All figures stay verbatim from facts.
    JioHotstar reference rules per kind are enforced (structure/tone only).
    """
    fact_lines = [f"[{f['slot']}] {f.get('value', '')} :: {f['claim'][:220]}"
                  for f in ranked(facts)[:12]]
    format_rules = {
        "summary": ("2-4 sentences: what the platform does well, its structural "
                    "vulnerabilities, and the medium-term risk if nothing changes."),
        "positioning": ("One paragraph: role in the viewer's stack (default vs deliberate "
                        "choice), conviction vs narrowness, what it is a deliberate "
                        "alternative to."),
        "wishlist": ("Exactly 8 items, each a concrete buy with a bold lead: "
                     "'**Lead** — detail naming genres, territories, or comparable "
                     "titles plus why the gap exists. Keep plain-text figures only."),
        "pitch": ("Keep exact keys angle/ideal_profile/yes/no/negotiation; "
                  "yes and no stay exactly 8 items each; negotiation covers rights, "
                  "deal structure, approval chain, and performance-data transparency."),
        "identity": "One italic-ready sentence, concrete and specific, not marketing copy.",
    }
    user = json.dumps({
        "task": f"Polish the {kind} for {platform} ({region}) to JioHotstar density.",
        "rules": ["Figures verbatim from evidence only.", "No JioHotstar fact reuse.",
                  "Percentages: reuse ONLY % figures already written with % in evidence, "
                  "OR shares exactly computed from title counts in evidence (state the basis).",
                  "Return JSON object with single key 'result'.",
                  "Format: " + format_rules.get(kind, "Keep the input shape.")],
        "evidence_pack_facts": fact_lines,
        "current": current,
    }, ensure_ascii=False)
    raw = groq_complete(load_system(platform, region), user, max_tokens=900)
    data = _parse_json_object(raw)
    return data.get("result", current)


def enhance_voice_groq(platform: str, region: str, facts: list[dict],
                       identity: str, summary: str, positioning: str) -> dict:
    """One call for identity+summary+positioning (token-saving merge)."""
    fact_lines = [f"[{f['slot']}] {f.get('value', '')} :: {f['claim'][:220]}"
                  for f in ranked(facts)[:12]]
    user = json.dumps({
        "task": f"Polish identity, summary and positioning for {platform} ({region}) to JioHotstar density.",
        "rules": ["Figures verbatim from evidence only.", "No JioHotstar fact reuse.",
                  "Percentages: reuse ONLY % figures already written with % in evidence, "
                  "OR shares exactly computed from title counts in evidence (state the basis).",
                  "identity_line: one concrete sentence, not marketing copy.",
                  "summary: 2-4 sentences (strengths, vulnerabilities, medium-term risk).",
                  "positioning: one paragraph (stack role, conviction vs narrowness).",
                  "Return JSON object with EXACTLY keys identity_line, summary, positioning. No thinking trace, no markdown fences."],
        "evidence_pack_facts": fact_lines,
        "current": {"identity_line": identity, "summary": summary, "positioning": positioning},
    }, ensure_ascii=False)
    system = load_system(platform, region)
    try:
        raw = groq_complete(system, user, max_tokens=900)
    except Exception as e:  # noqa: BLE001
        if not _is_groq_json_400(e):
            raise
        slim = json.loads(user)
        slim["evidence_pack_facts"] = fact_lines[:6]
        raw = groq_complete(system, json.dumps(slim, ensure_ascii=False), max_tokens=900)
    data = _parse_json_object(raw)
    for k in ("identity_line", "summary", "positioning"):
        if k not in data:
            raise ValueError(f"Groq voice response missing key: {k}")
    return {k: str(data[k]).strip() for k in ("identity_line", "summary", "positioning")}


def enhance_deal_groq(platform: str, region: str, facts: list[dict],
                      wishlist: list, pitch: dict) -> dict:
    """One call for wishlist+pitch (token-saving merge)."""
    fact_lines = [f"[{f['slot']}] {f.get('value', '')} :: {f['claim'][:220]}"
                  for f in ranked(facts)[:12]]
    user = json.dumps({
        "task": f"Polish wishlist and pitch playbook for {platform} ({region}) to JioHotstar density.",
        "rules": ["Figures verbatim from evidence only.", "No JioHotstar fact reuse.",
                  "Percentages: reuse ONLY % figures already written with % in evidence, "
                  "OR shares exactly computed from title counts in evidence (state the basis).",
                  "wishlist: exactly 8 items, each '**Lead** — detail' with genres/territories/comparables.",
                  "pitch: keep exact keys angle/ideal_profile/yes/no/negotiation; yes and no exactly 8 each.",
                  "Return JSON object with EXACTLY keys wishlist, pitch. No thinking trace, no markdown fences."],
        "evidence_pack_facts": fact_lines,
        "current": {"wishlist": wishlist, "pitch": pitch},
    }, ensure_ascii=False)
    system = load_system(platform, region)
    try:
        raw = groq_complete(system, user, max_tokens=1200)
    except Exception as e:  # noqa: BLE001
        if not _is_groq_json_400(e):
            raise
        slim = json.loads(user)
        slim["evidence_pack_facts"] = fact_lines[:6]
        raw = groq_complete(system, json.dumps(slim, ensure_ascii=False), max_tokens=1200)
    data = _parse_json_object(raw)
    if not isinstance(data.get("wishlist"), list) or len(data["wishlist"]) != 8:
        raise ValueError("Groq deal response: wishlist must be 8 items")
    p = data.get("pitch", {})
    if len(p.get("yes", [])) != 8 or len(p.get("no", [])) != 8:
        raise ValueError("Groq deal response: pitch yes/no must be 8 each")
    return {"wishlist": [str(x) for x in data["wishlist"]], "pitch": p}


def enhance_voice_ollama(platform: str, region: str, facts: list[dict],
                         identity: str, summary: str, positioning: str) -> dict:
    """Ollama one-call polish for identity+summary+positioning."""
    fact_lines = [f"[{f['slot']}] {f.get('value', '')} :: {f['claim'][:220]}"
                  for f in ranked(facts)[:12]]
    user = json.dumps({
        "task": f"Polish identity, summary and positioning for {platform} ({region}) to JioHotstar density.",
        "rules": ["Figures verbatim from evidence only.", "No JioHotstar fact reuse.",
                  "Percentages: reuse ONLY % figures already written with % in evidence, "
                  "OR shares exactly computed from title counts in evidence (state the basis).",
                  "identity_line: one concrete sentence, not marketing copy.",
                  "summary: 2-4 sentences (strengths, vulnerabilities, medium-term risk).",
                  "positioning: one paragraph (stack role, conviction vs narrowness).",
                  "Return JSON object with EXACTLY keys identity_line, summary, positioning. No thinking trace."],
        "evidence_pack_facts": fact_lines,
        "current": {"identity_line": identity, "summary": summary, "positioning": positioning},
    }, ensure_ascii=False)
    raw = ollama_complete(load_system(platform, region), user, max_tokens=900)
    data = _parse_json_object(raw)
    for k in ("identity_line", "summary", "positioning"):
        if k not in data:
            raise ValueError(f"Ollama voice response missing key: {k}")
    return {k: str(data[k]).strip() for k in ("identity_line", "summary", "positioning")}


def enhance_deal_ollama(platform: str, region: str, facts: list[dict],
                        wishlist: list, pitch: dict) -> dict:
    """Ollama one-call polish for wishlist+pitch."""
    fact_lines = [f"[{f['slot']}] {f.get('value', '')} :: {f['claim'][:220]}"
                  for f in ranked(facts)[:12]]
    user = json.dumps({
        "task": f"Polish wishlist and pitch playbook for {platform} ({region}) to JioHotstar density.",
        "rules": ["Figures verbatim from evidence only.", "No JioHotstar fact reuse.",
                  "Percentages: reuse ONLY % figures already written with % in evidence, "
                  "OR shares exactly computed from title counts in evidence (state the basis).",
                  "wishlist: exactly 8 items, each '**Lead** — detail' with genres/territories/comparables.",
                  "pitch: keep exact keys angle/ideal_profile/yes/no/negotiation; yes and no exactly 8 each.",
                  "Return JSON object with EXACTLY keys wishlist, pitch. No thinking trace."],
        "evidence_pack_facts": fact_lines,
        "current": {"wishlist": wishlist, "pitch": pitch},
    }, ensure_ascii=False)
    raw = ollama_complete(load_system(platform, region), user, max_tokens=1200)
    data = _parse_json_object(raw)
    if not isinstance(data.get("wishlist"), list) or len(data["wishlist"]) != 8:
        raise ValueError("Ollama deal response: wishlist must be 8 items")
    p = data.get("pitch", {})
    if len(p.get("yes", [])) != 8 or len(p.get("no", [])) != 8:
        raise ValueError("Ollama deal response: pitch yes/no must be 8 each")
    return {"wishlist": [str(x) for x in data["wishlist"]], "pitch": p}


def enhance_voice(platform: str, region: str, facts: list[dict],
                  identity: str, summary: str, positioning: str) -> dict:
    """Router: Ollama first when configured, else Groq. No Anthropic voice path."""
    if has_ollama():
        try:
            return enhance_voice_ollama(platform, region, facts, identity, summary, positioning)
        except Exception:
            if llm_provider_mode() == "ollama":
                raise
    return enhance_voice_groq(platform, region, facts, identity, summary, positioning)


def enhance_deal(platform: str, region: str, facts: list[dict],
                 wishlist: list, pitch: dict) -> dict:
    """Router: Ollama first when configured, else Groq."""
    if has_ollama():
        try:
            return enhance_deal_ollama(platform, region, facts, wishlist, pitch)
        except Exception:
            if llm_provider_mode() == "ollama":
                raise
    return enhance_deal_groq(platform, region, facts, wishlist, pitch)


def polish_fact_claims(facts: list[dict], limit: int = 40) -> list[dict]:
    """Router: Ollama copy-edit when configured, else Groq path."""
    if has_ollama() and facts:
        import time as _time
        out = []
        for f in facts[:limit]:
            try:
                user = json.dumps({
                    "task": "Fix grammar and trim to <=320 chars without changing any figure, name, or meaning.",
                    "claim": f.get("claim", ""),
                    "return_json_keys": ["claim"],
                })
                raw = ollama_complete("You are a copy editor. Return JSON only.", user,
                                      max_tokens=500)
                new_claim = _parse_json_object(raw).get("claim", f.get("claim", ""))
                g = dict(f)
                if new_claim and len(str(new_claim)) > 20:
                    g["claim"] = str(new_claim)[:320]
                out.append(g)
            except Exception:
                out.append(f)
        out += facts[limit:]
        return out
    return polish_fact_claims_groq(facts, limit=limit)


def polish_fact_claims_groq(facts: list[dict], limit: int = 40) -> list[dict]:
    """Grammar/dedupe polish for fact claims. value/unit/slot/sources immutable."""
    if not has_groq_key() or not facts:
        return facts
    import time as _time
    pacing = 0.0
    try:
        pacing = float(os.environ.get("GROQ_PACING_S", "2"))
    except Exception:
        pacing = 2.0
    out = []
    for f in facts[:limit]:
        try:
            user = json.dumps({
                "task": "Fix grammar and trim to <=320 chars without changing any figure, name, or meaning.",
                "claim": f.get("claim", ""),
                "return_json_keys": ["claim"],
            })
            raw = groq_complete("You are a copy editor. Return JSON only.", user,
                                max_tokens=500)
            new_claim = _parse_json_object(raw).get("claim", f.get("claim", ""))
            g = dict(f)
            if new_claim and len(str(new_claim)) > 20:
                g["claim"] = str(new_claim)[:320]
            out.append(g)
        except Exception:
            out.append(f)
        if pacing > 0:
            _time.sleep(min(pacing, 4.0))
    out += facts[limit:]
    return out
