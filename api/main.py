"""HTTP API over the Gold layer. Run: uvicorn api.main:app

Every data endpoint obtains its connection from `scoped()` — the only way into the data from here.
Endpoints contain no metric arithmetic: numbers come from metrics.compute / period_over_period;
row listings are plain selects of attributes.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterator

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from api.auth import authenticate, current_user_id, issue_token
from api.scope import Principal, UnknownUser, scoped_connection
from metrics import METRICS, compute, period_over_period

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="Northbeam hiring analytics", docs_url="/api/docs", openapi_url="/api/openapi.json")

# Headline cards, in display order. Parameters are the metric layer's defaults unless given here.
DASHBOARD = [
    ("candidate_pool", {}),
    ("applications_in_stage_as_of", {}),
    ("time_to_hire_median_days", {}),
    ("offered_salary_total_inr", {}),
    ("offer_acceptance_rate", {}),
]
DASHBOARD_POP = ("time_to_hire_median_days", "2026-04-01", "2026-06-30")


class Scoped:
    def __init__(self, con, principal: Principal):
        self.con, self.principal = con, principal


def scoped(user_id: str = Depends(current_user_id)) -> Iterator[Scoped]:
    try:
        con, principal = scoped_connection(user_id)
    except UnknownUser:
        # valid signature but the user no longer exists: treat as unauthenticated
        raise HTTPException(401, "Not authenticated")
    try:
        yield Scoped(con, principal)
    finally:
        con.close()


class LoginIn(BaseModel):
    email: str
    password: str


@app.post("/api/login")
def login(body: LoginIn):
    uid = authenticate(body.email, body.password)
    if not uid:
        raise HTTPException(401, "Invalid email or password")
    return {"access_token": issue_token(uid), "token_type": "bearer"}


@app.get("/api/me")
def me(s: Scoped = Depends(scoped)):
    reqs = [r[0] for r in s.con.execute("SELECT req_id FROM dim_requisition WHERE is_valid ORDER BY 1").fetchall()]
    return {**s.principal.__dict__, "requisitions": reqs}


@app.get("/api/dashboard")
def dashboard(s: Scoped = Depends(scoped)):
    return {
        "cards": [compute(s.con, n, **p).to_dict() for n, p in DASHBOARD],
        "period_over_period": period_over_period(s.con, *DASHBOARD_POP),
        "stage_conversion": compute(s.con, "stage_conversion").to_dict(),
        "pipeline_by_requisition": compute(s.con, "pipeline_by_requisition").to_dict(),
    }


@app.get("/api/metrics")
def list_metrics():
    return [
        {"name": m.name, "label": m.label, "unit": m.unit, "description": m.description,
         "parameters": m.defaults, "supports_period_over_period": m.supports_period}
        for m in METRICS.values()
    ]


def _iso(v: str | None, name: str) -> str | None:
    if v is None:
        return None
    try:
        return date.fromisoformat(v).isoformat()
    except ValueError:
        raise HTTPException(422, f"{name} must be YYYY-MM-DD")


@app.get("/api/metrics/{name}")
def metric(
    name: str,
    s: Scoped = Depends(scoped),
    stage: str | None = None,
    as_of: str | None = None,
    start: str | None = None,
    end: str | None = None,
    department: str | None = Query(None),
):
    if name not in METRICS:
        raise HTTPException(404, "Unknown metric")
    given = {"stage": stage, "as_of": _iso(as_of, "as_of"), "start": _iso(start, "start"),
             "end": _iso(end, "end"), "department": department}
    params = {k: v for k, v in given.items() if v is not None}
    try:
        return compute(s.con, name, **params).to_dict()
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/api/metrics/{name}/period-over-period")
def metric_pop(name: str, start: str, end: str, s: Scoped = Depends(scoped)):
    if name not in METRICS:
        raise HTTPException(404, "Unknown metric")
    try:
        return period_over_period(s.con, name, _iso(start, "start"), _iso(end, "end"))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/api/requisitions/{req_id}/applications")
def requisition_applications(req_id: str, s: Scoped = Depends(scoped)):
    # Out-of-scope and non-existent look identical (404) so ids cannot be probed.
    if not s.con.execute("SELECT 1 FROM dim_requisition WHERE req_id = ?", [req_id]).fetchone():
        raise HTTPException(404, "Requisition not found")
    rows = s.con.execute(
        """
        SELECT a.application_id, c.full_name, CAST(a.applied_at AS DATE), st.stage_name,
               CAST(a.hired_at AS DATE)
        FROM fact_application a
        JOIN dim_requisition r USING (requisition_sk)
        JOIN dim_candidate c USING (candidate_sk)
        LEFT JOIN dim_stage st ON st.stage_sk = a.current_stage_sk
        WHERE r.req_id = ?
        ORDER BY a.applied_at
        """,
        [req_id],
    ).fetchall()
    # Deliberately no email / phone: nobody on this screen needs them (data minimisation).
    keys = ("application_id", "candidate_name", "applied_on", "current_stage", "hired_on")
    return [dict(zip(keys, (str(v) if isinstance(v, date) else v for v in r))) for r in rows]


@app.get("/api/applications/{application_id}/history")
def application_history(application_id: str, s: Scoped = Depends(scoped)):
    rows = s.con.execute(
        """
        SELECT st.stage_name, h.valid_from, h.valid_to
        FROM fact_application_stage_history h
        JOIN fact_application a USING (application_sk)
        JOIN dim_stage st USING (stage_sk)
        WHERE a.application_id = ?
        ORDER BY h.valid_from
        """,
        [application_id],
    ).fetchall()
    if not rows:
        raise HTTPException(404, "Application not found")
    return [{"stage": r[0], "from": str(r[1]), "to": None if r[2] is None else str(r[2])} for r in rows]


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")
