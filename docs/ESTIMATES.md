# Estimate vs actual

**Honest caveat first:** no per-section estimate was written before the build started. The whole
core was built in one Claude Code session started from a single prompt, so the "Estimate" column
below is the split I'd have planned for a 16-hour cap, written *after* the fact. I'm not presenting
it as a pre-commitment. Actuals are wall-clock from the commit timestamps (session started ≈12:17,
last commit 13:23 on 2026-11-10), plus my own review time afterwards.

| Section | Estimate for a 16h cap (h) | Actual, agent session (h) | Notes |
|---|---|---|---|
| Profiling the raw data | 1.5 | 0.15 | 7 profiling scripts; all 5 controls computed before any table design |
| 1. Pipeline Bronze/Silver/Gold | 3.0 | 0.25 | One failed run (DuckDB 2.0 lambda syntax) |
| 2. Dimensional model | 1.5 | (in the above) | Designed together with Gold SQL |
| 3. Reconciliation + note | 2.0 | 0.2 | Tie was established during profiling; note took the time |
| 4. Metric layer | 2.0 | 0.1 | Plus the PoP fix |
| 5. API + auth + RLS + frontend | 3.0 | 0.2 | |
| Tests incl. mutation checks | (in 5) | 0.1 | |
| 6. Deployment (write-up, no deploy) | 0.5 | 0.05 | |
| 7. Worklog + agent artefacts | 1.0 | 0.1 | |
| 8. This table | 0.25 | 0.05 | |
| My review of the output | 1.25 | _add yours_ | |
| **Total** | **16** | **≈1.2 + review** | |

## Where I was most wrong

1. Build time: I'd have budgeted ~12 hours of building; with the agent it was ~1 hour, so the
   real cost moved almost entirely into *reviewing and being able to defend* what was built.
2. Reconciliation: I expected it to be the slow end of the work; it was the fast start — computing
   every control under competing rules *before* modelling made the traps visible immediately.
