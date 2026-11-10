# Northbeam hiring analytics

A data layer that settles Northbeam's hiring numbers, and a thin app over it.
Bronze → Silver → Gold in DuckDB, one metric layer, a FastAPI backend with row-level scope,
and a one-file frontend.

**All five control totals tie** (560 · 32 · 58 · ₹200,700,000 · 51.2%) — see
[docs/RECONCILIATION.md](docs/RECONCILIATION.md) for what each trap was.

## Run it (≈2 minutes)

Requires Python 3.12. Windows paths shown; on macOS/Linux use `.venv/bin/`.

```bash
py -3.12 -m venv .venv            # or: python3.12 -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m pipeline.run     # builds warehouse/northbeam.duckdb (~4 s)
.venv/Scripts/python -m pytest -q        # 29 tests: controls, idempotency, access, guards
.venv/Scripts/uvicorn api.main:app       # http://127.0.0.1:8000
```

**The full UI (Next.js)** — optional, needs Node 20+:

```bash
cd frontend && npm install && npm run build && cd ..   # static export → frontend/out
.venv/Scripts/uvicorn api.main:app                    # now serves the Next.js app at /
# or, while developing the UI: (cd frontend && npm run dev) → http://localhost:3000
```

Without the build, `/` serves a single-file fallback page from `web/` over the same API.
The Next.js app has three sections: **Overview** (headline metrics, hires by month, stage
funnel, pipeline on any date), **Requisitions** (filter/search; open a role to see its candidates
and each one's stage history), **Team** (per-recruiter / hiring-manager results). Light and dark
themes, and it works at phone width.

Sign in with any email from `data/landing/users.json` (the login page has one-click demo
accounts); demo password **`northbeam-demo`**
(override with `NB_DEMO_PASSWORD`). Useful logins:

| Email | Role | Sees |
|---|---|---|
| `simran.jain@northbeam.example` | admin | everything — the control totals |
| `uday.varma@northbeam.example` | hiring manager | REQ-1003, 1010, 1024 only |
| `naveen.malhotra@northbeam.example` | recruiter | the 7 requisitions they own |

API docs: http://127.0.0.1:8000/api/docs

## Where things are

| Path | What |
|---|---|
| `pipeline/bronze.py` | Land files as text + lineage (`_load_id`, `_source_sha256`, `_source_row`, `_loaded_at`). Same bytes twice → skipped. |
| `pipeline/silver.py` | Typing, cleaning, identity resolution, salary unit fix. Every correction is flagged. |
| `pipeline/gold.py` | Star schema. Grain of every fact table in the module docstring. |
| `metrics/definitions.py` | **Every metric, once.** Change time-to-hire here and nowhere else. |
| `api/scope.py` | Row-level security. |
| `api/main.py`, `api/auth.py` | Endpoints, JWT auth. |
| `frontend/` | Next.js app (static export served by FastAPI). Renders API values; no arithmetic. |
| `web/index.html` | Zero-build fallback page, served when `frontend/out` doesn't exist. |
| `docs/` | Reconciliation, deployment, worklog, estimates, plans given to the agent. |
| `CLAUDE.md` | Context file for the coding agent (Claude Code). |

## Gold model

```
                       dim_date          dim_stage
                          │                  │
dim_candidate ── fact_application ── fact_application_stage_history   (stage as history)
   (person)    │      │          └── fact_stage_event
bridge_candidate_record│
   (601 records→560)   ├── fact_offer
                       └── fact_interview
                  dim_requisition (+ sk -1 "Unknown")   dim_user (role-plays HM / recruiter / interviewer)
```

| Fact | Grain |
|---|---|
| `fact_application` | One row per application submitted. |
| `fact_stage_event` | One row per recorded stage transition of an application. |
| `fact_application_stage_history` | One row per application per contiguous period spent in a stage (`valid_from` inclusive, `valid_to` exclusive, NULL = still there). |
| `fact_offer` | One row per offer extended. |
| `fact_interview` | One row per scheduled interview. |

- **Stage is history.** "How many sat at Offer on 31 March" is a range predicate on
  `fact_application_stage_history`. The source's `current_stage` survives only as
  `reported_current_stage` for audit; it is wrong on 96 applications.
- **Orphan requisitions** (23 applications to `REQ-2xxx`) point to the `requisition_sk = -1`
  unknown member instead of being dropped, and every metric filters `is_valid_requisition`.
- **People who appear more than once** (41) are one `dim_candidate` row; `bridge_candidate_record`
  maps all 601 source records to it.
- Surrogate keys are integers, deterministic per build; see DEPLOYMENT for when that must change.

## The metric layer

`metrics/definitions.py` holds: candidate pool, applications in stage as-of, hires, **median time
to hire**, offered salary, **offer acceptance rate**, **stage conversion**, pipeline by requisition,
hires by month, team performance (per recruiter / hiring manager),
and a generic **period-over-period** (calendar-aligned: Q2 compares with Q1) over any metric that
takes a date window.

How "defined once" is enforced, not just intended (`tests/test_single_definition.py`):
- metric-shaped SQL (`median(`, `date_diff(`, `sum(`, `'accepted'` …) anywhere outside
  `metrics/` fails the build;
- neither frontend may use `Math.`, `toFixed`, `parseFloat`, `.reduce(`, `Intl.NumberFormat`…
  — the API sends display strings (including period-over-period direction and whether the change
  is favourable), so the UI never decides anything numeric;
- shared formula fragments (`TIME_TO_HIRE_DAYS`, `ACCEPTANCE_RATE_PCT`) are reused by the
  per-person and per-month metrics, so changing time to hire is a one-line edit everywhere;
- metric SQL may only use bare table names, so it can only ever run against a scoped connection.

## Access control — and how I satisfied myself it can't be bypassed

**Mechanism.** `api/scope.py` gives each request its own in-memory DuckDB connection. It attaches
the warehouse read-only, copies in only the rows for the caller's requisitions (hiring manager:
`hiring_manager_id = me`; recruiter: `recruiter_id = me`; admin: all), copies only the candidates
against those requisitions, then **detaches the warehouse**. Every query a request runs, whether a
metric, a listing or a future bug, executes against a database that does not contain other
people's rows. Scope is not a `WHERE` clause that each endpoint has to remember.

The user id comes only from a signed JWT (`HS256` pinned, `exp` required). Role and scope are
re-read from Gold on every request; a `role` claim in the token is ignored.

**Evidence** (`tests/test_access.py`, all run as HTTP requests):
- HM / recruiter see exactly their requisitions in `/me`, the dashboard and the pipeline table.
- Editing the URL to another manager's requisition → **404**, the same as a non-existent id (no
  existence oracle). Guessing another team's application id → 404.
- Query parameters can't widen scope: unknown metric params → 422; `department=Sales` for an
  Engineering HM → 0.
- No token, expired token, wrong-key token, `alg: none`, payload swapped under a valid signature,
  `role: admin` injected, token for a deleted user → all 401 / ignored.
- The scoped connection has no attached database other than memory.
- Listings never return email or phone.
- **The tests were mutation-checked:** widening the HM predicate to `TRUE` turns 4 access tests red.

## What I left out, and why

| Left out | Why |
|---|---|
| Public deployment | Deliberate: see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Dockerfile provided (not built — no Docker on this machine). |
| Real SSO / password storage | Demo shared password stands in; `api/auth.py` is the single swap point. |
| CRUD screens | No marks; not needed to demonstrate anything. |
| Orchestration (Airflow/dbt) | One command builds everything in ~4 s; a scheduler adds nothing at this size. |
| Incremental Silver/Gold | Full rebuild is deterministic and sub-second; incremental logic would be risk without benefit here. |
| Extensions A/B/C | Not started — core first. (C would be the cheapest, given the access tests already exist.) |
| Charts | Visual design not scored. |

## Known limitations / what I'd do differently

- Surrogate keys are rebuild-assigned (not stable across source changes).
- The salary paise rule is a threshold heuristic; the real fix is to ask the ATS vendor which field
  changed units and when, then key the rule on that instead.
- Per-request scoped copy is ~70 ms; fine here, would need caching at scale.
- `candidate_pool` counts all resolved people including the 53 with no valid application — see the
  footnote discussion in RECONCILIATION.md. A business owner should confirm that's the intended
  definition.
