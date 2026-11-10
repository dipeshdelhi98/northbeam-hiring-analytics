# Reconciliation note

All five control totals tie from Gold, through the metric layer, as the admin user.
They are asserted on every test run (`tests/test_controls.py`), so they stay tied.

| # | Control | Control figure | Ours | Plausible wrong answer we avoided | Where the rule lives |
|---|---|---|---|---|---|
| 1 | Unique people in candidate pool | 560 | **560** | 601 (records) · 574 (dedupe on email) | `pipeline/silver.py` → `candidate_records.person_id` |
| 2 | Applications at Offer, close of 2026-03-31 | 32 | **32** | 146 (`current_stage = 'Offer'`) · 43 (incl. orphan reqs) | `metrics/definitions.py` → `applications_in_stage_as_of` |
| 3 | Median time to hire, days (hires 1 Jan–30 Jun 2026) | 58 | **58** | 59 (fractional days: median 58.54, rounded) | `time_to_hire_median_days` |
| 4 | Total annual offered salary, Engineering, INR | 200,700,000 | **200,700,000** | 20,070,000,000 (raw: Engineering stored in paise) | `silver.offers.annual_salary_inr` + `offered_salary_total_inr` |
| 5 | Offer acceptance rate | 51.2% | **51.2%** | 52.1% (orphan reqs included) | `offer_acceptance_rate` |

Nothing differed in the end. Below is what in the data would have produced each wrong answer
and what the pipeline does about it.

## 1. People, not records — 560

- `candidates.csv` has 601 rows with 601 distinct `candidate_id`s; there are no literal duplicates.
- 41 people have two records: **same phone, same name** (modulo case and whitespace —
  `SHREYA REDDY`, `Divya  Verma`) but **different email** (`shreya.reddy@yahoo.in` vs
  `shreya.reddy92@outlook.com`) and a different source, created later. A typical "re-applied
  through an agency" pattern.
- The trap the other way: **email is not identity**. 24 email addresses are shared by 51 records
  (up to 4 records on one address), and within every one of those groups the phones differ — they
  are different people with generated `firstname.lastname@` collisions (two Aarav Kapoors).
  Deduping on email gives 574; on email *or* phone over-merges.
- Rule: person = last 10 digits of phone. Verified: every merged group has exactly one
  normalised name (`silver.persons.distinct_names = 1` for all 560).
- Modelled as `gold.dim_candidate` (one row per person) + `gold.bridge_candidate_record`
  (601 records → person). Applications from either record land on the same person.

**Tension with the footnote.** The control file says figures exclude records that cannot be tied
to a valid requisition. 52 people have no application at all, and 1 person applied only to
non-existent requisitions. Excluding that person would give 559; excluding everyone without a
valid application gives 507. 560 counts them all, so I read the footnote as applying to
application-derived records (applications, events, offers), not to the person register: a person
is not *untied* from a requisition, they simply have not been tied to one yet. I flagged this rather
than picked silently; if the business means "people in an active pipeline" that is a different,
second metric, not a redefinition of this one.

## 2. Offer at close of 31 March — 32

- `applications.current_stage` is a denormalised column that is **stale on 96 of 1,450
  applications** compared with the event history (e.g. 24 say `Offer` but have a later `Hired`
  event; 19 say `Screen` but were rejected). More importantly it only knows *today*: it cannot
  answer an as-at question at all. Using it gives 146.
- Rule: `gold.fact_application_stage_history` holds one row per stage period with
  `valid_from` (inclusive) / `valid_to` (exclusive). "At close of 31 March" = period opened before
  `2026-04-01 00:00` and not closed before `2026-04-01 00:00`.
- 11 more applications were at Offer that night against `REQ-2xxx` requisitions that do not exist
  → excluded (43 → 32).
- Checked: the event log itself is clean — no duplicate ids, no duplicate transitions, `event_seq`
  agrees with `changed_at` ordering, and every `from_stage` equals the previous `to_stage`. Silver
  still dedupes on (application, from, to, timestamp) so a re-export cannot double-count.

## 3. Median time to hire — 58

- 97 hires dated 1 Jan–30 Jun 2026 on valid requisitions; `applied_at` equals the `Applied`
  event timestamp on every application, so "submitted" is unambiguous.
- Calendar-day difference (`hire date − application date`) → median **58**.
- Elapsed time in fractional days → median **58.54**, which displays as 58.5 or rounds to **59**.
  Integer-flooring elapsed time also gives 58, but by accident. Calendar days is what "days to
  hire" means to a recruiter, so the definition says so explicitly.
- Window boundary: hires are filtered on hire **date** between the two dates inclusive. Filtering on
  timestamp `<= '2026-06-30'` silently drops hires on 30 June after midnight (97 → 95 hires; the
  median happens to survive, which is exactly why it would go unnoticed).

## 4. Engineering offered salary — ₹200,700,000

- Every Engineering offer (111 rows) is 100× every other department's: values are 90,000,000 …
  300,000,000 where others are 900,000 … 3,000,000 — **the same seven-step salary ladder with two
  extra zeros**. A ₹30 crore salary for a Backend Engineer is not credible; the values were stored in
  paise.
- Rule (Silver): annual salary > ₹5 crore → ÷100, flagged `salary_unit_corrected`, raw value kept
  as `annual_salary_raw`. Threshold-based rather than "if department = Engineering" so it describes
  the defect, not the symptom, and will catch a paise value in any department.
- "Engineering requisitions" means the requisition's department. Note that requisition titles do not
  imply department (e.g. `REQ-1019 Financial Analyst` is Engineering) — do not filter on title.
  The offer sheet's own `department` column agrees with the requisition on all valid rows; we use
  the requisition anyway, as the control specifies.
- 1 Engineering-labelled offer sits on an orphan requisition → excluded.

## 5. Offer acceptance rate — 51.2%

- 164 accepted / 320 decided (accepted + declined) on valid requisitions = 51.25% → 51.2.
  Including orphan requisitions: 172 / 330 = 52.1%.
- 91 offers are `open` **but carry a `decided_at`**. Treating "has a decided_at" as "decided"
  would pull them into the denominator. Status is authoritative; `decided_at` is nulled on open
  offers in Silver and flagged `dq_open_with_decided_at`.
- Cross-check against events: every accepted offer's application has a Hired event and no
  declined/open offer's does.

## Other defects found and handled (do not affect the controls)

| Defect | Rows | Handling |
|---|---|---|
| Applications to non-existent requisitions (`REQ-2xxx`) | 23 | `requisition_sk = -1` (unknown member); excluded from all metrics; visible to admins |
| Interviews referencing non-existent applications | 9 | `application_sk = -1`; kept for audit |
| Interview scores on `pending` / `no_show` outcomes | 456 | score nulled in Gold, flagged `dq_score_without_outcome` |
| Candidate names with leading/trailing/double whitespace | 20 | trimmed/collapsed, flagged `dq_name_whitespace` |
| Candidate names in ALL CAPS / all lower case | (in duplicate records) | survivor name title-cased |
| `current_stage` disagrees with event history | 96 | kept as `reported_current_stage`, flagged `dq_reported_stage_stale`; never used |
