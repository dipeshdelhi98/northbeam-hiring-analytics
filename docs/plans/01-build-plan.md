# Build plan v1 — handed to the agent after profiling

Written 2026-11-10 after a profiling pass over all seven files (findings in CLAUDE.md).
Time cap 16h. Order is by marks-per-hour, not by layer.

## Scope decisions

| Item | Decision | Why |
|---|---|---|
| Bronze/Silver/Gold | Build, DuckDB single file | Brief allows it; zero infra; SQL-first |
| Star schema + stage history | Build | Core of the assessment |
| Reconciliation as tests | Build | Numbers that tie must *stay* tied |
| Metric layer | Build, one Python module of SQL | "This is the point of the exercise" |
| API + auth + RLS | Build, FastAPI + HS256 JWT, scope via temp views | Thinnest thing that's genuinely non-bypassable |
| Frontend | One static HTML file, no build step | Visual design not scored |
| Deployment | **Not deployed — local + written plan + Dockerfile** | No free host is needed to demonstrate reasoning; avoids any risk of a bill and avoids publishing PII-shaped data |
| CRUD | Drop | Carries no marks |
| Extension | C (security review) only if core done with time left | Reuses the RLS tests already written |
| Orchestration (Airflow/dbt) | Drop | One `python -m pipeline.run` is enough at this size |

## Steps

1. Repo skeleton, CLAUDE.md, this plan. Commit.
2. Bronze: land each file as VARCHAR columns + lineage (`_load_id`, `_source_file`, `_source_sha256`,
   `_source_row`, `_loaded_at`). Skip a file whose SHA-256 is already in `bronze._load_log`. Commit.
3. Silver: typing, trimming, identity resolution (phone), salary unit fix, open-offer decided_at,
   orphan flags. Commit.
4. Gold: dims (date, candidate=person, candidate_record bridge, requisition with -1 member, user,
   stage), facts (application, stage_event, stage_history intervals, offer, interview). Commit.
5. Metric layer with the five controls + time to hire, stage conversion, acceptance rate,
   period-over-period. Control tests. Commit.
6. Idempotency test (run twice, row counts identical, load log shows skip). Commit.
7. API: login, /me, /metrics, /requisitions, /requisitions/{id}/applications. Scope by construction.
   Access-control tests including tampered tokens and id-guessing. Commit.
8. Frontend. Commit.
9. Docs: README, RECONCILIATION, DEPLOYMENT, WORKLOG, ESTIMATES. Commit.

## Acceptance

- `pytest` green; five controls tie from Gold via the metric layer.
- `grep` finds no metric arithmetic outside `metrics/`.
- A hiring manager editing a req id in the URL gets 404, not data.
