"""Gold: star schema. Rebuilt in full from Silver on every run.

Fact grains (one sentence each):
- fact_application:                one row per application submitted.
- fact_stage_event:                one row per recorded stage transition of an application.
- fact_application_stage_history:  one row per application per contiguous period it spent in a stage
                                   (valid_from inclusive, valid_to exclusive, NULL = still there).
- fact_offer:                      one row per offer extended.
- fact_interview:                  one row per scheduled interview.

Surrogate keys are integers assigned by ordering on the natural key. Because Gold is a full
rebuild they are deterministic for identical inputs; they are NOT promised stable across source
changes (a new candidate can shift keys). That is acceptable while nothing outside this warehouse
stores them — see README "What I'd change".

Unknown members: requisition_sk = -1 ("Unknown requisition") and application_sk = -1 absorb
orphan references so facts never silently drop rows on an inner join.
"""
import duckdb

SQL = """
CREATE SCHEMA IF NOT EXISTS gold;

-- dim_date ----------------------------------------------------------------------
CREATE OR REPLACE TABLE gold.dim_date AS
SELECT
    CAST(strftime(d, '%Y%m%d') AS INTEGER) AS date_key,
    CAST(d AS DATE)                        AS date,
    year(d)                                AS year,
    quarter(d)                             AS quarter,
    month(d)                               AS month,
    strftime(d, '%Y-%m')                   AS year_month,
    isodow(d)                              AS iso_day_of_week
FROM range(DATE '2025-01-01', DATE '2027-12-31', INTERVAL 1 DAY) t(d);

-- dim_stage ----------------------------------------------------------------------
CREATE OR REPLACE TABLE gold.dim_stage AS
SELECT * FROM (VALUES
    (1, 'Applied',   1, FALSE, FALSE),
    (2, 'Screen',    2, FALSE, FALSE),
    (3, 'Interview', 3, FALSE, FALSE),
    (4, 'Offer',     4, FALSE, FALSE),
    (5, 'Hired',     5, TRUE,  TRUE),
    (6, 'Rejected', 90, TRUE,  FALSE),
    (7, 'Withdrawn',91, TRUE,  FALSE)
) t(stage_sk, stage_name, stage_order, is_terminal, is_success);

-- dim_user -----------------------------------------------------------------------
CREATE OR REPLACE TABLE gold.dim_user AS
SELECT row_number() OVER (ORDER BY user_id) AS user_sk, user_id, name, email, role, department
FROM silver.users;

-- dim_requisition ----------------------------------------------------------------
CREATE OR REPLACE TABLE gold.dim_requisition AS
SELECT
    row_number() OVER (ORDER BY r.req_id) AS requisition_sk,
    r.req_id, r.title, r.department, r.location,
    r.hiring_manager_id, hm.user_sk AS hiring_manager_user_sk,
    r.recruiter_id,      rc.user_sk AS recruiter_user_sk,
    r.headcount, r.opened_date, r.closed_date, r.status,
    TRUE AS is_valid
FROM silver.requisitions r
LEFT JOIN gold.dim_user hm ON hm.user_id = r.hiring_manager_id
LEFT JOIN gold.dim_user rc ON rc.user_id = r.recruiter_id
UNION ALL
SELECT -1, 'UNKNOWN', 'Unknown requisition', 'Unknown', NULL,
       NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, FALSE;

-- dim_candidate (grain: one resolved PERSON) + record bridge ------------------------
CREATE OR REPLACE TABLE gold.dim_candidate AS
SELECT row_number() OVER (ORDER BY person_id) AS candidate_sk,
       person_id, full_name, primary_email, phone_norm, first_seen_at, record_count
FROM silver.persons;

CREATE OR REPLACE TABLE gold.bridge_candidate_record AS
SELECT cr.candidate_id, d.candidate_sk, cr.source, cr.created_at, cr.email,
       cr.is_duplicate_record
FROM silver.candidate_records cr
JOIN gold.dim_candidate d USING (person_id);

-- fact_stage_event ------------------------------------------------------------------
CREATE OR REPLACE TABLE gold._app_keys AS
SELECT row_number() OVER (ORDER BY a.application_id) AS application_sk,
       a.application_id,
       b.candidate_sk,
       coalesce(r.requisition_sk, -1) AS requisition_sk,
       a.req_id AS source_req_id,
       a.is_valid_requisition
FROM silver.applications a
JOIN gold.bridge_candidate_record b USING (candidate_id)
LEFT JOIN gold.dim_requisition r ON r.req_id = a.req_id AND r.requisition_sk > 0;

CREATE OR REPLACE TABLE gold.fact_stage_event AS
SELECT
    row_number() OVER (ORDER BY e.application_id, e.changed_at, e.event_seq) AS stage_event_sk,
    e.event_id,
    k.application_sk, k.candidate_sk, k.requisition_sk, k.is_valid_requisition,
    fs.stage_sk AS from_stage_sk,
    ts.stage_sk AS to_stage_sk,
    e.changed_at,
    CAST(strftime(e.changed_at, '%Y%m%d') AS INTEGER) AS changed_date_key,
    u.user_sk AS changed_by_user_sk,
    e.event_seq
FROM silver.stage_events e
JOIN gold._app_keys k USING (application_id)
LEFT JOIN gold.dim_stage fs ON fs.stage_name = e.from_stage
JOIN gold.dim_stage ts      ON ts.stage_name = e.to_stage
LEFT JOIN gold.dim_user u   ON u.user_id = e.changed_by;

-- fact_application_stage_history: the stage as a history -------------------------------
-- Each event opens a period in its to_stage; the next event for the same application closes it.
CREATE OR REPLACE TABLE gold.fact_application_stage_history AS
SELECT
    application_sk, candidate_sk, requisition_sk, is_valid_requisition,
    to_stage_sk AS stage_sk,
    changed_at  AS valid_from,
    lead(changed_at) OVER w AS valid_to,
    lead(changed_at) OVER w IS NULL AS is_current,
    stage_event_sk AS opened_by_stage_event_sk
FROM gold.fact_stage_event
WINDOW w AS (PARTITION BY application_sk ORDER BY changed_at, event_seq);

-- fact_application ----------------------------------------------------------------------
CREATE OR REPLACE TABLE gold.fact_application AS
SELECT
    k.application_sk, k.application_id, k.candidate_sk, k.requisition_sk, k.source_req_id,
    k.is_valid_requisition,
    a.applied_at,
    CAST(strftime(a.applied_at, '%Y%m%d') AS INTEGER) AS applied_date_key,
    hired.changed_at AS hired_at,
    CAST(strftime(hired.changed_at, '%Y%m%d') AS INTEGER) AS hired_date_key,
    cur.stage_sk AS current_stage_sk,                    -- derived from history
    a.reported_current_stage,                            -- as the source claims; audit only
    a.reported_current_stage IS DISTINCT FROM s.stage_name AS dq_reported_stage_stale
FROM gold._app_keys k
JOIN silver.applications a USING (application_id)
LEFT JOIN gold.fact_application_stage_history cur
       ON cur.application_sk = k.application_sk AND cur.is_current
LEFT JOIN gold.dim_stage s ON s.stage_sk = cur.stage_sk
LEFT JOIN (
    SELECT application_sk, min(changed_at) AS changed_at
    FROM gold.fact_stage_event WHERE to_stage_sk = 5 GROUP BY 1
) hired ON hired.application_sk = k.application_sk;

-- fact_offer ------------------------------------------------------------------------------
CREATE OR REPLACE TABLE gold.fact_offer AS
SELECT
    row_number() OVER (ORDER BY o.offer_id) AS offer_sk,
    o.offer_id,
    coalesce(k.application_sk, -1) AS application_sk,
    k.candidate_sk,
    coalesce(k.requisition_sk, -1) AS requisition_sk,
    coalesce(k.is_valid_requisition, FALSE) AS is_valid_requisition,
    o.offered_at,
    CAST(strftime(o.offered_at, '%Y%m%d') AS INTEGER) AS offered_date_key,
    o.decided_at,
    CAST(strftime(o.decided_at, '%Y%m%d') AS INTEGER) AS decided_date_key,
    o.status,
    o.currency,
    o.annual_salary_inr,
    o.annual_salary_raw,
    o.salary_unit_corrected,
    o.reported_department
FROM silver.offers o
LEFT JOIN gold._app_keys k USING (application_id);

-- fact_interview ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE gold.fact_interview AS
SELECT
    row_number() OVER (ORDER BY i.interview_id) AS interview_sk,
    i.interview_id,
    coalesce(k.application_sk, -1) AS application_sk,
    k.candidate_sk,
    coalesce(k.requisition_sk, -1) AS requisition_sk,
    coalesce(k.is_valid_requisition, FALSE) AS is_valid_requisition,
    i.application_id AS source_application_id,
    u.user_sk AS interviewer_user_sk,
    i.scheduled_at,
    CAST(strftime(i.scheduled_at, '%Y%m%d') AS INTEGER) AS scheduled_date_key,
    i.interview_type, i.outcome, i.score, i.dq_score_without_outcome
FROM silver.interviews i
LEFT JOIN gold._app_keys k USING (application_id)
LEFT JOIN gold.dim_user u ON u.user_id = i.interviewer_id;

DROP TABLE gold._app_keys;
"""


def run(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(SQL)
