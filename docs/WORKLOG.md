# Agent worklog

Tool: **Claude Code** (VS Code extension, model Claude Opus 5.5), one session on 2026-11-10.
Context file: [`CLAUDE.md`](../CLAUDE.md). Plans handed to / produced with the agent:
[`docs/plans/`](plans/). Commit history is the build in order.

---

## 1. What I delegated that worked

I delegated the whole build from one prompt. What made that work was not the prompt but the order
the agent was held to: **profile and compute all five control totals under competing rules before
designing a single table.** That one step surfaced every trap (email vs phone identity, stale
`current_stage`, paise salaries, fractional-day rounding to 59, orphan requisitions) while they were
still cheap. The other delegations that paid off:

- Writing the profiling findings into `CLAUDE.md` as rules, so later steps could not "simplify"
  them away (e.g. revert to deduping on email).
- Turning the reconciliation into tests, so the five numbers stay tied rather than being checked once.
- Access-control tests written as attacks (URL edits, forged/`alg:none`/swapped-payload tokens,
  injected `role` claim) rather than as happy paths.
- Mutation-checking the suite: 28/28 passing first time was treated as unproven until scope was
  deliberately widened and 4 tests went red.

## 2. What I did not delegate — and what I should not have

Being straight about it: in this session very little was withheld from the agent. The decisions
that are mine to own, and that I have re-checked myself rather than taken on trust:

- **Control 1 vs the footnote.** The footnote says exclude anything not tied to a valid
  requisition; applied literally to people that gives 559, not 560. Counting all resolved people is
  a business-definition call, not a technical one — I'd confirm it with the data owner rather than
  let either me or an agent decide it silently.
- **Not deploying publicly.** A public login page over personal-data-shaped records with a password
  in the README is a judgement about risk to the client, which is not something to hand off.
- **The paise rule.** A ">₹5 crore ÷100" threshold is a heuristic; the real fix is asking the ATS
  vendor when and why the unit changed. An agent can find the pattern; it can't make that call.

What I'd change next time: write the section estimates and a v0 plan myself *before* the first
prompt, and review each layer's commit before the next one is built, instead of reviewing at the end.

## 3. One thing the agent got wrong, and what changed afterwards

**Period-over-period compared Q2 against the wrong quarter.** The first implementation defined the
previous window as "the same number of days immediately before". For Q2 2026 (1 Apr–30 Jun, 91
days) that produced a baseline of **31 Dec 2025 → 31 Mar 2026**. Nothing errored; the number looked
plausible. It was caught by reading the actual output of the metric — the printed comparison window
— rather than trusting that the code ran. Fix: `previous_period()` now shifts whole-month windows
by whole months (Q2 → Q1) and only falls back to equal-length days for arbitrary windows.

The same pattern showed up three more times (dependency versions written from memory, "27 email
pairs" when it was 24 groups / 51 records, "~3 MB" when the file is 7 MB). The prompting change
that came out of it is now in `CLAUDE.md`: never commit a number or version without having just
queried it, and anything with calendar semantics gets a hand-checked boundary example before it is
called done.

---

## 4. Session record (factual, as it happened)

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
