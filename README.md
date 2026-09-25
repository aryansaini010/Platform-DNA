# Platform DNA Report Generator

Implements `platform_dna_report_plan.md`: takes an Indian OTT platform name and
produces a Platform DNA report with the same structure, depth and scoring
behaviour as the JioHotstar example.

> The JioHotstar example is a **format and depth benchmark, not a fact source**.
> Never copy its facts, titles, figures or phrasing into another platform's report.
> Every figure in the output must trace to the fact store or a computed stat.

## Pipeline (mirrors plan §2)

```
platform + aliases
   │ 
   ▼
A. Research (SearXNG → Firecrawl, cached)  ──►  pages cache (.cache/)
   ▼
B. Fact extraction → facts table, tagged by SLOT
   ▼
C. Title dataset (TMDB + Wikipedia + trade press) ──► titles + computed stats
   ▼
D. Coverage check: required slots filled? if not, targeted re-search
   ▼
E. Section writer x6 (facts + stats + rubric) ──► JSON (sections/*.json)
   ▼
F. Top-of-report writer (summary, positioning, tag), wishlist, pitch, identity
   ▼
G. Validator → regenerate failing parts only (max 2 retries)
   ▼
H. Renderer (Jinja2 template) ──► Markdown
```

Key invariants (from the plan, enforced in code):

- `overall = round(mean(6 section scores))`. The model never chooses it (`scores.py`).
- Header count is honest: `~N named titles` + sampling disclaimer when N < 150.
- Counts are fixed: 6 score rows, 6 standout titles, 8 wishlist, 8 yes, 8 no.
- Conflicts (>~25% divergence in one slot) are surfaced, not hidden.
- Facts older than 18 months are auto-flagged stale.
- Every ₹/$/%/date must match the fact store or a computed stat (validator).

## Layout

```
config/platforms.json      aliases + per-platform hints
data/catalog/              platforms.json (129 services, each with ≥1 region)
                           + regions.json (197 ISO codes)
scripts/check_catalog.py   invariant check: every platform has a region
                           (run after any catalog edit)
src/platform_dna/
  config.py                slot checklist, query templates, rubric, anchors
  research.py              SearXNG + Firecrawl clients (cached, retry)
  facts.py                 fact dataclass, conflict + staleness (code, not model)
  titles.py                title dataset + computed stats
  scores.py                overall + rubric + blind-rescore check
  writer.py                deterministic section/top/pitch builders
  validator.py             structure, numbers, grounding, contamination
  renderer.py              Jinja2 → Markdown
templates/report.md.j2     layout (model never controls layout)
data/fact_packs/           <platform_slug>.json  (facts + titles + meta)
outputs/                   generated reports
main.py                    CLI
```

## Setup (local stack, plan §3)

SearXNG needs JSON enabled (`settings.yml`):

```yaml
use_default_settings: true
server:
  secret_key: "change-me"
  limiter: false
search:
  formats: [html, json]
```

```bash
pip install -r requirements.txt
# optional (enables live research + TMDB + LLM polish):
set SEARXNG_URL=http://localhost:8080
set FIRECRAWL_URL=http://localhost:3002
set TMDB_API_KEY=...
set ANTHROPIC_API_KEY=...
```

Without those env vars the pipeline runs in **fact-pack mode**
(no network needed): it builds the report purely from
`data/fact_packs/<slug>.json`. That is how the bundled outputs were made.

## Usage

```bash
# 1. Generate from a hand-verified fact pack (deterministic, no keys needed)
python main.py --platform "Netflix India" --fact-pack data/fact_packs/netflix_in.json

# 2. Generic slug form
python main.py --platform "ZEE5" --fact-pack data/fact_packs/zee5.json --output outputs/ZEE5_Platform_DNA_Report.md

# 3. Validate only
python main.py --platform "Netflix India" --fact-pack data/fact_packs/netflix_in.json --validate-only
```

To add a new platform:

1. Copy `data/fact_packs/netflix_in.json` → `data/fact_packs/<slug>.json`.
2. Fill `facts` (slot, claim, value, unit, source_url, source_date, tier,
   confidence) and `titles` (name, year, type, language, genres, is_original...).
3. Add aliases in `config/platforms.json`.
4. Run the CLI. Fix validator errors (it tells you which section failed).

## Writing stage: system prompt + optional AI polish

- `prompts/system_prompt.md` — the analyst brief, verbatim (`[[OTT_PLATFORM_NAME]]` /
  `[[REGION]]` filled per run). `prompts/pipeline_addendum.md` adds the three
  machine rules: sampling disclaimer, conflict surfacing, example-is-format-only.
- Without a key, sections are composed deterministically (`composer.py`) — every
  figure traces to the fact store.
- With a key, Auto DNA offers **Enhance draft prose with AI**: each section is
  rewritten under the system prompt with facts + stats + the matching JioHotstar
  section as format reference (`src/platform_dna/llm.py`). Scores, validation
  and layout stay in code; invented figures still fail validation.

```powershell
$env:ANTHROPIC_API_KEY = "..."   # optional; ANTHROPIC_MODEL overrides default
```

## Web UI (Vite React + FastAPI)

```powershell
pip install -r requirements.txt
# terminal 1 — API on :8001 (loads GROQ_API_KEY from .env)
python -m uvicorn api:app --host 127.0.0.1 --port 8001
# terminal 2 — app on :5173
cd frontend; npm install; npm run dev -- --port 5173 --host 127.0.0.1 --strictPort
# open http://127.0.0.1:5173/
```

- **Platform DNA:** pick any of 129 platforms + 197 regions → full research
  (query pack + top-N scraping + fact extraction + Wikipedia title mining)
  → Groq-polished draft (scores stay computed, never chosen) → validated
  report, download **.md / .pdf / fact-pack JSON**.
- **Recently ready:** every validated report is stored in `data/library/`,
  viewable and deletable from the UI.
- (The legacy Streamlit workbench `app.py` was retired; do not run it.)

## Docker: SearXNG + Firecrawl (plan §3)

Requires Docker Engine running (Docker Desktop on Windows).

**1. SearXNG** — already wired in this repo:

```powershell
# optional: put a real secret in docker/searxng/settings.yml first
docker compose up -d searxng
# JSON check (must return results, otherwise format=json 403s):
Invoke-RestMethod "http://localhost:8080/search?q=netflix+india&format=json" |
  Select-Object -ExpandProperty results | Select-Object -First 3 title, url
```

**2. Firecrawl** — use the official self-host stack (it needs API + worker +
Playwright + Redis + Postgres, so cloning upstream avoids drift):

```powershell
git clone https://github.com/firecrawl/firecrawl
cd firecrawl
# follow its README for the .env, then:
docker compose up -d --build
# scrape check (Wikipedia):
Invoke-RestMethod -Method Post -Uri "http://localhost:3002/v1/scrape" `
  -ContentType "application/json" `
  -Body '{"url":"https://en.wikipedia.org/wiki/List_of_Netflix_India_original_programming","formats":["markdown"],"onlyMainContent":true}'
```

**3. Point the pipeline at them** (PowerShell; app runs on host, so
`localhost` ports are correct — service names only matter container-to-container):

```powershell
$env:SEARXNG_URL = "http://localhost:8080"
$env:FIRECRAWL_URL = "http://localhost:3002"
$env:TMDB_API_KEY = "..."   # optional, for the title dataset
```

**4. Put both on one network** (so containerised callers can use
`http://searxng:8080` and `http://firecrawl-api:3002`):

```powershell
docker network connect dna-net firecrawl-api
docker network connect dna-net firecrawl-worker 2>$null
```

Known limits (plan §7, already handled in code): self-hosted Firecrawl has
no managed anti-bot layer — expect Cloudflare/JS-heavy failures
(`research.scrape` treats <500-char pages as failures, retries with
backoff, caches by URL hash); keep SearXNG concurrency at 2–4 and rely on
the `.cache/` query cache.

## Fact slots (plan §4 Step 1)

content_hours, language_count, originals_investment, hub_deals,
named_originals, franchises, mau, subscribers, segment_skews, diaspora,
genre_mix, regulatory_ctx, downloads, telecom_bundles, devices, linear_share,
ctv_share, dubbing, windows, revenue_annual, revenue_quarterly, ebitda,
pricing, ad_products, sports_rights, mission, leadership, campaigns,
share_trends, rival_gains, ownership, ceo_structure, approval_chain, data_sharing.

Each slot wants 2–3 queries; see `config.py:QUERY_TEMPLATES`.
Source tiers: T1 official/investor, T2 trade press, T3 Wikipedia/aggregators.
