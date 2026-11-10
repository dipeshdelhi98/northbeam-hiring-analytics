"""THE metric layer. Every metric in this repository is defined here and nowhere else.

Rules
- Metric SQL references Gold tables by *bare* name (`fact_offer`, never `gold.fact_offer`).
  The caller supplies a connection in which those names hold only the rows the user may see
  (see api/scope.py). A metric therefore cannot accidentally escape row-level security, and
  the same definition serves an admin, a recruiter and a hiring manager.
- Every metric excludes records not tied to a valid requisition (`is_valid_requisition`), as
  the control totals require. Admins see orphan rows in tables, never in numbers.
- Formatting for display happens here too, so the frontend renders strings and does no maths.

To change a definition, change this file only. tests/test_single_definition.py guards that.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Callable

import duckdb

STAGES = ("Applied", "Screen", "Interview", "Offer", "Hired", "Rejected", "Withdrawn")
FUNNEL = ("Applied", "Screen", "Interview", "Offer", "Hired")


@dataclass(frozen=True)
class Metric:
    name: str
    label: str
    description: str
    unit: str  # count | days | inr | percent | table
    sql: str
    defaults: dict[str, Any] = field(default_factory=dict)
    # optional post-processing of the fetched rows into the value (kept beside the SQL)
    shape: Callable[[list[tuple]], Any] | None = None
    supports_period: bool = False  # True if the metric takes start/end and can do PoP


@dataclass
class MetricResult:
    name: str
    label: str
    unit: str
    value: Any
    display: str
    params: dict[str, Any]
    description: str

    def to_dict(self) -> dict:
        return self.__dict__.copy()


# --------------------------------------------------------------------------------------------
# Definitions
# --------------------------------------------------------------------------------------------

_DEFS = [
    Metric(
        name="candidate_pool",
        label="People in candidate pool",
        description="Distinct people (not candidate records). Identity is resolved in Silver by "
        "normalised phone number; two records with the same phone are one person.",
        unit="count",
        sql="SELECT count(DISTINCT candidate_sk) FROM dim_candidate",
    ),
    Metric(
        name="applications_in_stage_as_of",
        label="Applications in stage (as at close of day)",
        description="Applications whose stage history places them in $stage at the close of "
        "$as_of: a period that opened on or before that day and had not closed by the end of it.",
        unit="count",
        sql="""
            SELECT count(DISTINCT h.application_sk)
            FROM fact_application_stage_history h
            JOIN dim_stage s USING (stage_sk)
            WHERE h.is_valid_requisition
              AND s.stage_name = $stage
              AND h.valid_from <  CAST($as_of AS DATE) + INTERVAL 1 DAY
              AND (h.valid_to IS NULL OR h.valid_to >= CAST($as_of AS DATE) + INTERVAL 1 DAY)
        """,
        defaults={"stage": "Offer", "as_of": "2026-03-31"},
    ),
    Metric(
        name="hires",
        label="Hires",
        description="Applications that reached Hired with a hire date in [$start, $end].",
        unit="count",
        sql="""
            SELECT count(*) FROM fact_application
            WHERE is_valid_requisition AND hired_at IS NOT NULL
              AND CAST(hired_at AS DATE) BETWEEN CAST($start AS DATE) AND CAST($end AS DATE)
        """,
        defaults={"start": "2026-01-01", "end": "2026-06-30"},
        supports_period=True,
    ),
    Metric(
        name="time_to_hire_median_days",
        label="Median time to hire (days)",
        description="Median of whole calendar days from application date to Hired date, for "
        "hires dated in [$start, $end]. Calendar-day difference, not elapsed 24h periods.",
        unit="days",
        sql="""
            SELECT median(date_diff('day', CAST(applied_at AS DATE), CAST(hired_at AS DATE)))
            FROM fact_application
            WHERE is_valid_requisition AND hired_at IS NOT NULL
              AND CAST(hired_at AS DATE) BETWEEN CAST($start AS DATE) AND CAST($end AS DATE)
        """,
        defaults={"start": "2026-01-01", "end": "2026-06-30"},
        supports_period=True,
    ),
    Metric(
        name="offered_salary_total_inr",
        label="Total annual offered salary (INR)",
        description="Sum of annual offered salary, any offer status, for requisitions in "
        "$department (the requisition's department, not the offer row's). NULL = all.",
        unit="inr",
        sql="""
            SELECT coalesce(sum(o.annual_salary_inr), 0)
            FROM fact_offer o
            JOIN dim_requisition r USING (requisition_sk)
            WHERE o.is_valid_requisition
              AND ($department IS NULL OR r.department = $department)
        """,
        defaults={"department": "Engineering"},
    ),
    Metric(
        name="offer_acceptance_rate",
        label="Offer acceptance rate",
        description="Accepted ÷ (accepted + declined). Open offers have not reached a decision "
        "and are excluded. Optional window on offer date [$start, $end].",
        unit="percent",
        sql="""
            SELECT 100.0 * count(*) FILTER (WHERE status = 'accepted')
                   / nullif(count(*) FILTER (WHERE status IN ('accepted', 'declined')), 0)
            FROM fact_offer
            WHERE is_valid_requisition
              AND ($start IS NULL OR offered_at >= CAST($start AS DATE))
              AND ($end   IS NULL OR offered_at <= CAST($end AS DATE))
        """,
        defaults={"start": None, "end": None},
        supports_period=True,
    ),
    Metric(
        name="stage_conversion",
        label="Stage conversion",
        description="For each funnel step, applications that ever reached the next stage ÷ "
        "applications that ever reached this stage. Reached = has a stage-history period in it.",
        unit="table",
        sql="""
            WITH reached AS (
                SELECT s.stage_name, s.stage_order, count(DISTINCT h.application_sk) AS n
                FROM fact_application_stage_history h
                JOIN dim_stage s USING (stage_sk)
                WHERE h.is_valid_requisition
                  AND s.stage_name IN ('Applied','Screen','Interview','Offer','Hired')
                GROUP BY ALL
            )
            SELECT stage_name AS from_stage,
                   lead(stage_name) OVER (ORDER BY stage_order) AS to_stage,
                   n AS reached_from,
                   lead(n) OVER (ORDER BY stage_order) AS reached_to,
                   100.0 * lead(n) OVER (ORDER BY stage_order) / nullif(n, 0) AS rate_pct
            FROM reached
            ORDER BY stage_order
        """,
        shape=lambda rows: [
            {
                "from_stage": r[0],
                "to_stage": r[1],
                "reached_from": r[2],
                "reached_to": r[3],
                "rate_pct": None if r[4] is None else round(r[4], 1),
                "display": "–" if r[4] is None else f"{r[4]:.1f}%",
            }
            for r in rows
            if r[1] is not None
        ],
    ),
    Metric(
        name="pipeline_by_requisition",
        label="Pipeline by requisition",
        description="Per requisition: applications currently in each stage (current = the open "
        "period in stage history, not the source's current_stage column).",
        unit="table",
        sql="""
            SELECT r.req_id, r.title, r.department, r.status,
                   count(a.application_sk) AS applications,
                   count(*) FILTER (WHERE s.stage_name IN ('Applied','Screen','Interview','Offer'))
                       AS in_progress,
                   count(*) FILTER (WHERE s.stage_name = 'Offer') AS at_offer,
                   count(*) FILTER (WHERE s.stage_name = 'Hired') AS hired
            FROM dim_requisition r
            LEFT JOIN fact_application a USING (requisition_sk)
            LEFT JOIN dim_stage s ON s.stage_sk = a.current_stage_sk
            WHERE r.is_valid
            GROUP BY ALL
            ORDER BY r.req_id
        """,
        shape=lambda rows: [
            dict(zip(("req_id", "title", "department", "status", "applications",
                      "in_progress", "at_offer", "hired"), r))
            for r in rows
        ],
    ),
]

METRICS: dict[str, Metric] = {m.name: m for m in _DEFS}


# --------------------------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------------------------

def _format(unit: str, v: Any) -> str:
    if v is None:
        return "–"
    if unit == "count":
        return f"{int(v):,}"
    if unit == "days":
        return f"{v:g} days" if float(v).is_integer() else f"{v:.1f} days"
    if unit == "inr":
        return f"₹{int(v):,}"
    if unit == "percent":
        return f"{v:.1f}%"
    return ""


def _value(unit: str, v: Any) -> Any:
    if v is None:
        return None
    if unit in ("count", "inr"):
        return int(v)
    if unit in ("days", "percent"):
        return round(float(v), 1)
    return v


def compute(con: duckdb.DuckDBPyConnection, name: str, **params: Any) -> MetricResult:
    m = METRICS[name]
    unknown = set(params) - set(m.defaults)
    if unknown:
        raise ValueError(f"{name} does not take {sorted(unknown)}")
    p = {**m.defaults, **params}
    if "stage" in p and p["stage"] not in STAGES:
        raise ValueError(f"stage must be one of {STAGES}")
    rows = con.execute(m.sql, p).fetchall() if p else con.execute(m.sql).fetchall()
    if m.shape:
        value = m.shape(rows)
        display = ""
    else:
        value = _value(m.unit, rows[0][0])
        display = _format(m.unit, value)
    return MetricResult(m.name, m.label, m.unit, value, display, p, m.description)


def _add_months(d: date, months: int) -> date:
    y, m = divmod(d.year * 12 + d.month - 1 + months, 12)
    return date(y, m + 1, 1)


def previous_period(s: date, e: date) -> tuple[date, date]:
    """The comparison window for [s, e].

    Whole calendar months (s is the 1st, e is a month end) compare against the same number of
    whole months immediately before — so Q2 compares with Q1, not with 91 days ending 31 Mar.
    Any other window compares against the immediately preceding window of equal length in days.
    """
    if e < s:
        raise ValueError("end must be on or after start")
    if s.day == 1 and (e + timedelta(days=1)).day == 1:
        n_months = (e.year - s.year) * 12 + (e.month - s.month) + 1
        return _add_months(s, -n_months), s - timedelta(days=1)
    length = (e - s).days + 1
    return s - timedelta(days=length), s - timedelta(days=1)


def period_over_period(
    con: duckdb.DuckDBPyConnection, name: str, start: str, end: str
) -> dict:
    """The metric over [start, end] against previous_period(start, end)."""
    m = METRICS[name]
    if not m.supports_period:
        raise ValueError(f"{name} has no period parameters")
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    ps, pe = previous_period(s, e)
    cur = compute(con, name, start=s.isoformat(), end=e.isoformat())
    prev = compute(con, name, start=ps.isoformat(), end=pe.isoformat())
    change = None if cur.value is None or prev.value is None else cur.value - prev.value
    change_pct = None if change is None or not prev.value else 100.0 * change / prev.value
    delta_unit = "pp" if m.unit == "percent" else ("days" if m.unit == "days" else "")
    return {
        "name": name,
        "label": f"{m.label} — period over period",
        "current": cur.to_dict(),
        "previous": prev.to_dict(),
        "change": None if change is None else round(change, 1),
        "change_pct": None if change_pct is None else round(change_pct, 1),
        "display": "–" if change is None else
        f"{change:+g}{(' ' + delta_unit) if delta_unit else ''}"
        + ("" if change_pct is None else f" ({change_pct:+.1f}%)")
        + f" vs {ps.isoformat()} → {pe.isoformat()}",
    }
