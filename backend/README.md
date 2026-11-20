# SEO Content Intelligence backend

Python 3.12, FastAPI, SQLAlchemy, LangGraph and a database-backed queue. Local, single-operator MVP;
no authentication is included: bind to loopback only. Do not expose this service on the Internet.

## Run

From `backend/`, install [uv](https://docs.astral.sh/uv/) then:

```sh
uv sync --python 3.12
uv run alembic upgrade head
uv run uvicorn seoci.api.main:app --host 127.0.0.1 --port 8000
# In a separate terminal, same directory and environment:
uv run python -m seoci.worker
# One queued job (useful for diagnostics):
uv run python -m seoci.worker --once
```

No credentials are needed. SQLite data lives in `data/seoci.db`; LangGraph checkpoints live in
`data/seoci.db.checkpoints`. Keep both for resumability. `uv run ruff check . && uv run pytest -q`
runs the offline acceptance suite. OpenAPI request schemas are at `/openapi.json`, interactive docs at `/docs`.

## Configuration

Environment variables or a local ignored `.env`:

| Variable | Default | Meaning |
|---|---|---|
| DATABASE_URL | sqlite:///./data/seoci.db | SQLAlchemy URL; PostgreSQL: `postgresql+psycopg://user:pass@localhost/seoci` |
| LLM_MODEL | empty | Empty selects deterministic mock; otherwise LiteLLM model identifier. Set the provider's usual API key environment variable, e.g. OPENAI_API_KEY. |
| SERP_PROVIDER | mock | `mock` or `dataforseo`; real keyword and research adapters follow the same setting |
| DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD | empty | DataForSEO credentials, never stored in project records |
| MAX_REVISION_CYCLES | 2 | Maximum automatic QA revisions |
| RUN_BUDGET_USD | 2 | Refuse the next LLM task once recorded spend reaches this cap |
| CACHE_TTL_SECONDS | 3600 | Provider response cache lifetime |
| NETWORK_TIMEOUT | 20 | Per-request network timeout in seconds |
| WORKER_POLL_SECONDS | 0.5 | Queue poll interval |

Mock mode intentionally leaves volume/competition unavailable. SERP entries are explicitly labeled demo
results. Its long-form articles contain qualitative guidance, a comparison table, hypothetical worked
example, checklist, references and SEO metadata, in Indonesian or English. Gardening and savings topics
include curated, topic-specific guidance and authoritative research starting points. Other topics use
general decision guidance. Mock source URLs are **not** live-verified evidence. The source note and unresolved evidence
remain visible in the article/package; publication requires a real editorial source check. Other project
languages require a real LLM. Sources and SERP text are untrusted data, not agent instructions.

Real provider locale uses language-country (e.g. `id-ID`, `en-US`). DataForSEO adapters resolve ISO
country codes to provider location codes through their cached locations endpoint. Explicit provider
location names also work. No synthetic fallback occurs on provider error.

Budget checks occur before tasks; the last call may exceed the cap (provider billing is post-response).
Network operations have bounded timeouts and transport/status retries; cache uses provider/query/locale/device.
Sitemap downloads are bounded to the project host and public HTTP(S), without redirects; per-URL errors
are returned. Public-host validation is defense in depth, not a substitute for a production egress firewall
(DNS rebinding protection belongs there). Optional source text fetching is off by default.

## Frontend API contract

JSON unless noted. All ids are UUID strings; times are ISO-8601 UTC strings. Errors:
`{"detail":"message"}`; validation 422 uses FastAPI's standard `detail` array. 404 missing object,
409 invalid state/active job/idempotency conflict. Collection endpoints return arrays, not envelopes.
Mutating workflow endpoints enqueue a job and return immediately; poll detail every two seconds.
`POST /approve` still returns the **current** gate state, not an optimistic next state.

### Project and inventory

- `GET /api/health` -> `{status:"ok",pipeline:"separate-worker"}`.
- `GET /api/projects` -> `Project[]`.
- `POST /api/projects` (201), `PUT /api/projects/{id}` -> `Project`.
  Input: `{name,domain,niche,audience,language?:"id",country?:"ID",voice_profile?:string,
  rules?:object,business_objective?:string}`. First four required; a bare domain defaults to HTTPS.
  The web form stores plain-text editorial rules in `rules.instructions`.
  Project adds `{id,version,created_at}`. PUT is full replacement, increments profile version;
  runs retain their own project snapshot.
- `GET /api/projects/{id}` -> `Project`; `DELETE /api/projects/{id}` -> 204.
  Deletion cascades application data, refuses active jobs. LangGraph checkpoints are operational
  records outside this cascade; purge checkpoint DB separately for complete local data removal.
- `GET /api/projects/{id}/content-items` -> `ContentItem[]`.
- `POST /api/projects/{id}/content-items` input `{items:[{url,title?,slug?,status?,metadata_json?}]}`
  -> `{items:ContentItem[],failures:[{url,error}]}`. Upsert by project/url, maximum 200 per request.
  ContentItem adds `{id,project_id,last_seen_at}`; malformed or off-site URLs are rejected per item.
  Omitted fields are preserved when a known URL is reimported.
- `POST /api/projects/{id}/sitemap` (202) input `{url}` -> same import result shape. Bounded synchronous
  connector import (not article pipeline work), supports sitemap indexes and same-site redirects,
  including the bare domain and its `www` variant. Import failures do not abort siblings.
  URL-level `lastmod` metadata is saved as `metadata_json.sitemap_lastmod`; pages are not fetched.

### Runs

- `GET /api/runs?project_id=...` -> `Run[]`.
- `POST /api/runs` (201), optional `Idempotency-Key` header:
  `{project_id,mode?:"selected"|"discovery",primary_keyword,locale?:"id-ID"}` -> `Run`.
  In discovery, `primary_keyword` is the seed. Same key + body returns existing run; different body -> 409.
- `Run`: `{id,project_id,mode,primary_keyword,locale,state,context,error,resume_state,
  revision_count,created_at,updated_at,idempotency_key,request_fingerprint}`.
- `GET /api/runs/{id}` -> Run plus `revision_limit`, `mock_revision` and:
  - `artifacts:[{id,run_id,stage,version,data,created_at}]`: context, keyword research (`data.shortlist`),
    strategy (`data.overlap_warnings`, `ymyl`, `expert_review_label`), brief, evidence, drafting, SEO, QA and export.
  - `keywords:[{id,run_id,version,keyword,locale,intent,score,confidence,selected,data,created_at}]`.
    `data={intent:{label,reason,confidence},metrics:{volume:null|number,competition:null|string,
    provider,status,locale,period,captured_at},opportunity:{score,confidence,dimensions,
    not_a_ranking_prediction},serp_snapshot_id}`. Each dimension: `{score:null|number,weight,reason,confidence}`.
  - `serp_snapshots:[{id,run_id,version,query,locale,provider,created_at,data}]`;
    `data={query,locale,device,provider,captured_at,mock?,results:[{rank,url,title,snippet}]}`.
  - `briefs:[{id,run_id,version,status,data,created_at}]`; data is
    `{angle,audience,intent,outline:[{level,heading,purpose}],questions,exclusions,internal_links,source_plan}`.
  - `sources:[{id,run_id,version,url,title,publisher,published_at,retrieved_at,source_type,data,created_at}]`;
    data has untrusted snippet and mock flag.
  - `evidence:[{id,run_id,version,source_id,claim,supporting_note,confidence,review_status,data,created_at}]`;
    data links to `url` and evidence `scope`.
  - `drafts:[{id,run_id,version,body_md,body_html,metadata_json,status,data,created_at}]`;
    data contains change_log. SEO metadata: `{title,h1,slug,meta_description,excerpt,tags,category,
    image_guidance:{concept,alt,caption},primary_keyword,locale}`.
  - `qa_reviews:[{id,run_id,version,draft_id,data,created_at}]`; data contains
    `{dimensions,findings:[{dimension,severity,location,finding,action}],status,summary,
    expert_review_required,human_resolution?}`. Severity: blocker/major/minor.
  - `approvals:[{id,run_id,version,stage,actor_id,decision,comment,data,created_at}]`.
  - `audit:[{id,run_id,version,actor,action,data,created_at}]`; transitions have
    `data={from,to,reason,artifact_ref}`, usage and stage events include model/cost/latency.
  - `jobs:[{id,run_id,status,payload,attempts,error,created_at,started_at}]`.
  - `usage:{calls:[{task,model,prompt_tokens,completion_tokens,cost_usd,latency_ms,prompt_version}],
    cost_usd,tokens}`, `exports:["md","html","json"]` (empty until generated).

### Commands and export

- `POST /api/runs/{id}/approve` (202):
  `{stage:"keyword"|"brief"|"final",decision?:"approve"|"request_revision",payload?:object,comment?:string}`
  -> `{run_id,job_id,state,queued:true}`.
  Keyword payload `{keyword?:shortlist string,intent?:string}` records intent override.
  Brief payload `{edits?:Partial<Brief>}` creates a new approved version, retaining the original.
  Final approve requires `payload:{draft_id,draft_version}` identifying the reviewed latest draft;
  missing or stale identifiers return 409. QA must have no unresolved hard content issues. YMYL additionally requires
  `expert_reviewed:true` in that payload and nonempty comment identifying the human review. This explicitly
  routes expert/source flags to human accountability; original QA findings are retained with resolution.
  Final `request_revision` creates another draft and returns to QA/final review. It shares the configured
  revision cap with automatic revisions. Mock mode keeps the current Markdown and asks the editor to apply
  feedback manually. Keyword/brief edits use approve.
- `PUT /api/runs/{id}/draft` (202): `{body_md,metadata_json?:SEO}` -> `{draft_id,version,job_id,state}`.
  Only final_review/blocked; creates a version, syncs the SEO H1 and queues QA. A failed check leaves
  the edited version available for correction instead of triggering an automatic rewrite. Approved/exported articles are immutable.
- `POST /api/runs/{id}/retry` (202), no body -> `{run_id,job_id,state}`.
  Resumes failed checkpoint, including approval payload if its job failed. Blocked drafts use manual edit.
- `POST /api/runs/{id}/cancel`, no body -> `{run_id,state:"cancelled"}`. Refuses active worker or terminal states.
- `GET /api/runs/{id}/drafts/diff?a=1&b=2` -> `{a,b,diff:unified_diff_string}`.
- `GET /api/runs/{id}/export/{md|html|json}` -> attachment with corresponding content type.
  Only after final approval and worker export completion; otherwise 409. Markdown preserves body formatting;
  HTML disables embedded HTML for safe previews; JSON includes stable ids, metadata, briefs, sources,
  evidence_ledger, qa_report, versions, and article Markdown/HTML (`schema_version:"1.0"`).

## Architecture and PRD mapping

`api` validates commands and queues jobs. `worker` claims with SQLite write lock or PostgreSQL
`FOR UPDATE SKIP LOCKED`, then executes LangGraph using thread id = run id. Each stage commits typed
records, a uniquely keyed artifact and audit events in one transaction. LangGraph checkpoints before
and after stages; committed artifacts are reused on replay. Stale running jobs can be reclaimed after
ten minutes; operate one worker per local SQLite DB. PostgreSQL supports concurrent run claims.
Retry never recreates a run; explicit create idempotency prevents double-click duplication.

State progression: draft → ready_for_research → researching → keyword_review → strategy → brief_review
→ evidence_research → drafting → optimizing → qa → final_review → article_ready → exported.
QA may return revision_required → drafting, or blocked after the revision cap. interrupt()/Command(resume)
implement the three review gates. Every transition uses the PRD table, with explicit completion of its
omitted technical edges: ready_for_research→researching, technical failure from any active node→failed,
and resumed→saved checkpoint stage. These extensions are audited, never direct state assignments.

FR-001–004: projects, versioned snapshots, inventory/import; FR-010–016: selected/discovery, providers,
missing-data semantics, intent override, dimensional scoring, overlap warnings; FR-020–024: strategy,
editable versioned briefs and inventory links; FR-030–035: untrusted research, ledger, long-form bilingual
demo drafting; FR-040–045: SEO, six QA dimensions, deterministic checks and capped revision;
FR-050–053: gated portable exports, stable package ids, immutable versions and manual editing/diff.
Tests cover every design-listed PRD §11 case plus full API→worker→approval→export execution.

Production hardening still needed: authentication/authorization,
verified topic research/claim extraction beyond the conservative numeric-claim rules, per-provider quota
scheduling, strict pre-flight token budget reservation, migrations with frozen historical table definitions,
and retention tooling for application plus checkpoint data. Initial Alembic revision creates all initial
SQLAlchemy tables; subsequent schema changes should use normal frozen Alembic operations.
