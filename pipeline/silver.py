"""Silver: typed, trimmed, deduplicated, conformed. Rebuilt in full from the latest Bronze load.

Every correction is *flagged*, not silently applied, so Gold and the reconciliation note can
point at exactly which rows a rule touched.
"""
import duckdb

# Above this an annual salary is not credible for any role in the pack (the highest
# non-Engineering offer is ₹30 lakh). Every value above it divides by 100 onto the same
# 7-step salary ladder the other departments use, i.e. it was stored in paise.
SALARY_PAISE_THRESHOLD_INR = 50_000_000

SQL = f"""
CREATE SCHEMA IF NOT EXISTS silver;

-- Users --------------------------------------------------------------------
CREATE OR REPLACE TABLE silver.users AS
SELECT DISTINCT ON (user_id)
    trim(user_id)                         AS user_id,
    trim(name)                            AS name,
    lower(trim(email))                    AS email,
    lower(trim(role))                     AS role,
    nullif(trim(department), '')          AS department
FROM bronze.users_latest
ORDER BY user_id, _source_row;

-- Requisitions --------------------------------------------------------------
CREATE OR REPLACE TABLE silver.requisitions AS
SELECT DISTINCT ON (req_id)
    trim(req_id)                          AS req_id,
    trim(title)                           AS title,
    trim(department)                      AS department,
    trim(location)                        AS location,
    trim(hiring_manager_id)               AS hiring_manager_id,
    trim(recruiter_id)                    AS recruiter_id,
    CAST(headcount AS INTEGER)            AS headcount,
    CAST(opened_date AS DATE)             AS opened_date,
    CAST(nullif(closed_date, '') AS DATE) AS closed_date,
    lower(trim(status))                   AS status
FROM bronze.requisitions_latest
ORDER BY req_id, _source_row;

-- Candidate records + identity resolution ------------------------------------
-- A *record* is a row in candidates.csv. A *person* is resolved by normalised phone
-- (last 10 digits). Name is normalised only to verify the match, never used as the key.
CREATE OR REPLACE TABLE silver.candidate_records AS
WITH typed AS (
    SELECT DISTINCT ON (candidate_id)
        trim(candidate_id)                                         AS candidate_id,
        regexp_replace(trim(full_name), '\\s+', ' ', 'g')          AS full_name_clean,
        lower(trim(email))                                         AS email,
        right(regexp_replace(phone, '[^0-9]', '', 'g'), 10)        AS phone_norm,
        trim(source)                                               AS source,
        CAST(created_at AS TIMESTAMP)                              AS created_at,
        full_name <> regexp_replace(trim(full_name), '\\s+', ' ', 'g') AS dq_name_whitespace
    FROM bronze.candidates_latest
    ORDER BY candidate_id, _source_row
)
SELECT
    *,
    'P' || phone_norm AS person_id,
    -- earliest record for the person is the survivor; later ones are duplicates
    row_number() OVER (PARTITION BY phone_norm ORDER BY created_at, candidate_id) > 1
        AS is_duplicate_record
FROM typed;

CREATE OR REPLACE TABLE silver.persons AS
SELECT
    person_id,
    -- surviving name: the earliest record's, title-cased where the source shouted it
    arg_min(CASE WHEN full_name_clean = upper(full_name_clean)
                   OR full_name_clean = lower(full_name_clean)
                 THEN list_aggr(list_transform(string_split(lower(full_name_clean), ' '),
                                lambda x: upper(x[1]) || x[2:]), 'string_agg', ' ')
                 ELSE full_name_clean END,
            created_at)                                  AS full_name,
    arg_min(email, created_at)                           AS primary_email,
    any_value(phone_norm)                                AS phone_norm,
    min(created_at)                                      AS first_seen_at,
    count(*)                                             AS record_count,
    count(DISTINCT lower(full_name_clean))               AS distinct_names  -- QA: expect 1
FROM silver.candidate_records
GROUP BY person_id;

-- Applications ---------------------------------------------------------------
CREATE OR REPLACE TABLE silver.applications AS
SELECT DISTINCT ON (a.application_id)
    trim(a.application_id)                       AS application_id,
    trim(a.candidate_id)                         AS candidate_id,
    cr.person_id,
    trim(a.req_id)                               AS req_id,
    r.req_id IS NOT NULL                         AS is_valid_requisition,
    CAST(a.applied_at AS TIMESTAMP)              AS applied_at,
    trim(a.current_stage)                        AS reported_current_stage,  -- stale; audit only
    lower(trim(a.is_active)) = 'true'            AS reported_is_active
FROM bronze.applications_latest a
LEFT JOIN silver.candidate_records cr ON cr.candidate_id = trim(a.candidate_id)
LEFT JOIN silver.requisitions r       ON r.req_id = trim(a.req_id)
ORDER BY a.application_id, a._source_row;

-- Stage events ----------------------------------------------------------------
-- Deduplicate on content as well as id: a re-exported transition must not count twice.
CREATE OR REPLACE TABLE silver.stage_events AS
SELECT DISTINCT ON (application_id, from_stage, to_stage, changed_at)
    trim(event_id)                               AS event_id,
    trim(application_id)                         AS application_id,
    nullif(trim(from_stage), '')                 AS from_stage,
    trim(to_stage)                               AS to_stage,
    CAST(changed_at AS TIMESTAMP)                AS changed_at,
    CAST(event_seq AS INTEGER)                   AS event_seq,
    nullif(trim(changed_by), '')                 AS changed_by
FROM bronze.stage_events_latest
ORDER BY application_id, from_stage, to_stage, changed_at, event_seq;

-- Interviews --------------------------------------------------------------------
CREATE OR REPLACE TABLE silver.interviews AS
SELECT DISTINCT ON (i.interview_id)
    trim(i.interview_id)                         AS interview_id,
    trim(i.application_id)                       AS application_id,
    a.application_id IS NOT NULL                 AS is_known_application,
    CAST(i.scheduled_at AS TIMESTAMP)            AS scheduled_at,
    nullif(trim(i.interviewer_id), '')           AS interviewer_id,
    trim(i.type)                                 AS interview_type,
    lower(trim(i.outcome))                       AS outcome,
    -- a score only means something once the interview has a pass/fail outcome
    CASE WHEN lower(trim(i.outcome)) IN ('pass', 'fail')
         THEN CAST(CAST(i.score AS DOUBLE) AS INTEGER) END AS score,
    i.score IS NOT NULL AND lower(trim(i.outcome)) NOT IN ('pass', 'fail')
                                                 AS dq_score_without_outcome
FROM bronze.interviews_latest i
LEFT JOIN silver.applications a ON a.application_id = trim(i.application_id)
ORDER BY i.interview_id, i._source_row;

-- Offers --------------------------------------------------------------------------
CREATE OR REPLACE TABLE silver.offers AS
WITH typed AS (
    SELECT DISTINCT ON (offer_id)
        trim(offer_id)                           AS offer_id,
        trim(application_id)                     AS application_id,
        trim(department)                         AS reported_department,
        CAST(offered_at AS DATE)                 AS offered_at,
        CAST(annual_salary AS BIGINT)            AS annual_salary_raw,
        upper(trim(currency))                    AS currency,
        lower(trim(status))                      AS status,
        CAST(nullif(decided_at, '') AS DATE)     AS decided_at_raw
    FROM bronze.offers_latest
    ORDER BY offer_id, _source_row
)
SELECT
    offer_id, application_id, reported_department, offered_at, currency, status,
    annual_salary_raw,
    CASE WHEN annual_salary_raw > {SALARY_PAISE_THRESHOLD_INR}
         THEN annual_salary_raw // 100 ELSE annual_salary_raw END AS annual_salary_inr,
    annual_salary_raw > {SALARY_PAISE_THRESHOLD_INR}              AS salary_unit_corrected,
    -- an open offer has not been decided; a decided_at on it is noise
    CASE WHEN status = 'open' THEN NULL ELSE decided_at_raw END   AS decided_at,
    status = 'open' AND decided_at_raw IS NOT NULL                AS dq_open_with_decided_at
FROM typed;
"""


def run(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(SQL)
