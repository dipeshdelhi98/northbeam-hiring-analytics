"""Reconciliation against data/landing/CONTROL_TOTALS.txt, through the metric layer only.

The parametrised `params` are the control's own wording translated into metric parameters;
the arithmetic lives in metrics/definitions.py. See docs/RECONCILIATION.md for the traps.
"""
import pytest

from metrics import compute

CONTROLS = [
    ("1 unique people", "candidate_pool", {}, 560),
    ("2 at Offer close of 2026-03-31", "applications_in_stage_as_of",
     {"stage": "Offer", "as_of": "2026-03-31"}, 32),
    ("3 median days to hire H1 2026", "time_to_hire_median_days",
     {"start": "2026-01-01", "end": "2026-06-30"}, 58),
    ("4 Engineering offered salary INR", "offered_salary_total_inr",
     {"department": "Engineering"}, 200_700_000),
    ("5 offer acceptance rate %", "offer_acceptance_rate", {}, 51.2),
]


@pytest.mark.parametrize("label,metric,params,expected", CONTROLS, ids=[c[0] for c in CONTROLS])
def test_control_total_ties(admin_con, label, metric, params, expected):
    assert compute(admin_con, metric, **params).value == expected


def test_as_of_is_history_not_todays_column(admin_con):
    """The stale current_stage column gives a different (wrong) answer; we must not be using it."""
    stale = admin_con.execute(
        "SELECT count(*) FROM fact_application WHERE is_valid_requisition AND reported_current_stage = 'Offer'"
    ).fetchone()[0]
    assert stale != compute(admin_con, "applications_in_stage_as_of").value


def test_every_candidate_record_maps_to_exactly_one_person(admin_con):
    n_records, n_mapped = admin_con.execute(
        "SELECT count(*), count(DISTINCT candidate_id) FROM bridge_candidate_record"
    ).fetchone()
    assert n_records == n_mapped == 601
