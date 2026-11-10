# CLAUDE.md — agent context for this repository

Northbeam ATS analytics: Bronze → Silver → Gold (DuckDB) + one metric layer + FastAPI + static frontend.
This file is the standing brief for any coding agent working here. Read it before changing anything.

## Non-negotiables (from the client brief)

1. **Metrics are defined once, in `metrics/definitions.py`.** Nowhere else may compute a metric —
   not the API, not the frontend, not tests. Tests *call* the metric layer; they never re-derive a number.
   If you find yourself writing `median(`, `count(distinct`, a ratio, or a date difference outside
   `metrics/`, stop — it belongs in a metric definition.
2. **The frontend does no arithmetic on metric values.** The API returns a pre-formatted `display`
   string; `frontend/` and `web/` render it verbatim. If the UI needs a new number (a label, a
   delta, a direction), add it to the metric layer's output — never compute it in TypeScript.
3. **Stage is history, not a column.** Any "what stage was X in at time T" question is answered from
   `gold.fact_application_stage_history` (valid_from / valid_to). `applications.current_stage` is a
   stale denormalised column — it is kept in Gold only as `reported_current_stage` for auditing,
   and must never feed a metric.
4. **Row-level security lives in `api/scope.py` and is applied by construction**: every request gets
   an in-memory DuckDB connection holding *copies of Gold tables already filtered to the caller's
   scope*, with the warehouse detached.
   Metric SQL refers to bare table names (`fact_offer`, not `wh.gold.fact_offer`). A test enforces
   this. Scope is derived server-side from the user id in a signed token — never from request
   params and never from role claims in the token.
5. **Re-running the pipeline must not duplicate data.** Bronze is append-only keyed by file SHA-256;
   Silver and Gold are rebuilt deterministically from the latest Bronze load.
6. Control totals in `data/landing/CONTROL_TOTALS.txt` must tie. `tests/test_controls.py` is the
   reconciliation; if it goes red, explain the cause in `docs/RECONCILIATION.md` — never tune a
   number to make it pass.

## Data rules discovered during profiling (do not "simplify" these away)

- **Person identity** = normalised phone (last 10 digits). 41 people have two candidate records
  (same phone, same name modulo case/whitespace, different email). Email is *not* an identity key:
  different people share generated emails (e.g. two "Aarav Kapoor"s with different phones).
- **Orphan requisitions**: 23 applications point at `REQ-2xxx` ids that do not exist. They map to the
  unknown-requisition member (`requisition_sk = -1`) and are excluded from metrics by
  `is_valid_requisition`.
- **Engineering offer salaries are stored ×100 (paise)**. Rule in Silver: salary > ₹5 crore → ÷100,
  flagged `salary_unit_corrected`.
- **Open offers carry a meaningless `decided_at`** — nulled in Silver.
- **Time to hire** = whole calendar days between application date and Hired date (date difference,
  not fractional days — fractional median is 58.54, which rounds to the wrong answer 59).
- 9 interviews reference applications that do not exist → `application_sk = -1`.
- Interview scores recorded against `pending` / `no_show` outcomes are nulled in Gold.

## Layout

```
pipeline/   bronze.py silver.py gold.py run.py   (python -m pipeline.run)
metrics/    definitions.py  ← the only place metrics live
api/        main.py auth.py scope.py
frontend/   Next.js 16 app (static export → frontend/out, served by the API). Read
            frontend/AGENTS.md first: this Next version differs from training data.
web/        index.html (zero-build fallback, served when frontend/out is absent)
tests/      controls, idempotency, access control, single-definition guard
docs/       RECONCILIATION.md, WORKLOG.md, ESTIMATES.md, DEPLOYMENT.md, plans/
```

## Commands

```
py -3.12 -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m pipeline.run          # builds warehouse/northbeam.duckdb
.venv/Scripts/python -m pytest -q
.venv/Scripts/uvicorn api.main:app --reload   # http://127.0.0.1:8000
```

## Working style for agents

- Small commits, one concern each, imperative subject line.
- Profile before you transform: run a query and look at the data before writing a cleaning rule.
- Do not add dependencies without a reason written in the commit message.
- Prefer SQL in DuckDB over pandas for transformations; pandas only for reading xlsx/json.
- Never write a number, count or package version into a committed file without having just
  queried it (`pip freeze`, a SQL count). Memory of earlier output is not a source.
- Anything with calendar semantics (as-of, periods, day counts) gets a boundary example checked
  by hand before it is called done.
- A test suite that passes first time is unproven: break the code on purpose and watch it fail.
