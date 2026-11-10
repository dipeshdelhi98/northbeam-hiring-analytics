# Agent worklog

Tool: **Claude Code** (VS Code extension, model Claude Opus 5.5), one session on 2026-11-10.
Context file: [`CLAUDE.md`](../CLAUDE.md). Plans handed to / produced with the agent:
[`docs/plans/`](plans/). Commit history is the build in order.

---

> **Candidate: the three reflective sections below must be written by you, in your words.**
> The brief says a generic worklog scores zero and that it will be read line by line in the
> interview. The agent has filled in only the factual session record (section 4) as raw material.
> Delete this box when done.

## 1. What I delegated that worked

_…your words. Candidates from the session record: profiling scripts; Bronze/Silver/Gold SQL;
the access-control attack tests; mutation-checking the tests…_

## 2. What I deliberately did not delegate, and why

_…your words. Think about: which metric definitions you checked by hand against the control
file; the decision not to deploy publicly; the reading of the control-file footnote for
control 1 (560 vs 559); accepting/rejecting the paise threshold rule…_

## 3. One thing the agent got wrong that I caught — how, and what I changed in my prompting

_…your words. Real candidates from section 4, pick the one you actually noticed/would defend:
the period-over-period window (Q2 compared against 31 Dec–31 Mar), or the reconciliation note
quoting "27 pairs share an email" when it was 24 groups / 51 records…_

---

## 4. Session record (factual, written by the agent as it worked)

**Prompt given:** the OpenBI email + "Implement this" with the path to the brief
([plans/00-initial-prompt.md](plans/00-initial-prompt.md)).

| # | Step | What happened |
|---|---|---|
| 1 | Read brief, README, CONTROL_TOTALS | Noted the exclusion footnote applies to all five figures. |
| 2 | Environment | `python` on PATH was the Windows Store stub; found 3.12 via `py`. venv created. |
| 3 | Profiling (before any pipeline code) | Ran 7 throwaway profiling scripts. Found: phone gives exactly 560 people, email 574; 23 orphan-requisition applications; `current_stage` disagrees with events on 96 rows; Engineering salaries ×100; open offers with `decided_at`; 9 interviews on non-existent applications. Computed every control under competing rules **before** designing tables, which surfaced that fractional-day median (58.54) would round to 59. |
| 4 | Plan + CLAUDE.md | Wrote profiling findings into CLAUDE.md as rules so later steps (and later sessions) can't "simplify" them away. Plan v1 committed before code. |
| 5 | **Agent error** — dependency pins | Agent first wrote `requirements.txt` from memory (duckdb 1.4.1, fastapi 0.118 …) while the venv actually had duckdb 2.0.0 etc. Caught by running `pip freeze` before committing; replaced with real versions. |
| 6 | Git line endings | Noticed `autocrlf` would rewrite landed CSVs on clone → different SHA-256 → Bronze would think they were new files. Added `.gitattributes` `-text` for `data/landing/**`. |
| 7 | **Agent error** — DuckDB 2.0 lambda | Silver used the deprecated `x -> …` lambda; DuckDB 2.0 rejects it. Pipeline run failed loudly; fixed to `lambda x: …`. |
| 8 | Pipeline QA | Second run: all 7 sources `skipped_duplicate`, Bronze row counts unchanged. Every merged person has exactly one normalised name. |
| 9 | **Agent error** — period-over-period | First PoP implementation used "previous N days". Output showed Q2 2026 compared with **2025-12-31 → 2026-03-31**. Not a crash — a plausible-looking wrong baseline. Changed `previous_period()` to shift whole-month windows by whole months. |
| 10 | Scope design | Chose "copy scoped rows into an in-memory DB, then DETACH the warehouse" over WHERE-clauses-per-endpoint so a missed filter is impossible rather than unlikely. Measured cost: ~70 ms per request. |
| 11 | Tests passed first time → distrusted | 28/28 green on first run. Mutation-checked: widen HM scope to `TRUE` (4 access tests fail), fractional-day time-to-hire (control 3 fails at 58.5), a `median()` added to `api/main.py` (guard fails). |
| 12 | **Agent error** — numbers in prose | The first draft of RECONCILIATION.md said "27 pairs share an email" and "13 names" from memory of earlier output. Re-queried before committing: actually 24 email groups / 51 records (up to 4 per email), 20 whitespace-flagged names. Corrected. Also corrected warehouse size claim in DEPLOYMENT (said ~3 MB; actual 7 MB). |
| 13 | Deployment | Decided not to publish a public URL (PII-shaped data, shared demo password). Dockerfile written; **not built** — Docker not installed on this machine, stated as such in DEPLOYMENT.md. |

### Prompting changes that came out of the errors

- After #5 and #12: "never state a number or a version in a committed file without having just
  queried it" — added to the working style in CLAUDE.md.
- After #9: definitions with calendar semantics (period, as-of, day counts) get an explicit
  boundary example in the docstring and a check against a hand-picked case.
