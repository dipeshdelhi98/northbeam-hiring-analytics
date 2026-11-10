"""Row-level security by construction.

`scoped_connection(user_id)` returns an in-memory DuckDB connection that contains *copies* of the
Gold tables filtered to what that user may see, and nothing else: the warehouse file is attached
read-only, the filtered copies are taken, and the warehouse is DETACHED before the connection is
handed back. Any SQL run on the returned connection — metric definitions, endpoint queries, a
future bug — physically cannot read rows outside the user's scope, because they are not there.

Scope rules (from the brief):
- hiring_manager: requisitions where they are the hiring manager, and the candidates against them
- recruiter:      requisitions they own (recruiter_id)
- admin:          everything, including the unknown-requisition member
- anyone else / unknown user: nothing

The role and scope are read from Gold on every request, keyed only by the user id from the
verified token. Nothing in the request body, query string or token claims can widen it.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb

from pipeline.config import WAREHOUSE_PATH

# Gold tables filtered by requisition scope
_REQ_SCOPED = [
    "fact_application",
    "fact_stage_event",
    "fact_application_stage_history",
    "fact_offer",
    "fact_interview",
]
# Reference dimensions with no candidate data
_UNSCOPED = ["dim_stage", "dim_date"]


@dataclass(frozen=True)
class Principal:
    user_id: str
    name: str
    role: str
    email: str


class UnknownUser(Exception):
    pass


def lookup_user(con: duckdb.DuckDBPyConnection, user_id: str, schema: str = "wh.gold") -> Principal:
    row = con.execute(
        f"SELECT user_id, name, role, email FROM {schema}.dim_user WHERE user_id = ?", [user_id]
    ).fetchone()
    if not row:
        raise UnknownUser(user_id)
    return Principal(*row)


def _scope_predicate(role: str) -> str:
    if role == "admin":
        return "TRUE"
    if role == "hiring_manager":
        return "hiring_manager_id = $uid"
    if role == "recruiter":
        return "recruiter_id = $uid"
    return "FALSE"


def scoped_connection(
    user_id: str, warehouse: Path = WAREHOUSE_PATH
) -> tuple[duckdb.DuckDBPyConnection, Principal]:
    con = duckdb.connect(":memory:")
    try:
        con.execute(f"ATTACH '{Path(warehouse).as_posix()}' AS wh (READ_ONLY)")
        principal = lookup_user(con, user_id)
        pred = _scope_predicate(principal.role)
        uid = {"uid": principal.user_id}

        con.execute(
            f"CREATE TABLE dim_requisition AS SELECT * FROM wh.gold.dim_requisition WHERE {pred}",
            uid if "$uid" in pred else None,
        )
        for t in _REQ_SCOPED:
            con.execute(
                f"""CREATE TABLE {t} AS SELECT * FROM wh.gold.{t}
                    WHERE requisition_sk IN (SELECT requisition_sk FROM dim_requisition)"""
            )
        if principal.role == "admin":
            con.execute("CREATE TABLE dim_candidate AS SELECT * FROM wh.gold.dim_candidate")
            con.execute(
                "CREATE TABLE bridge_candidate_record AS SELECT * FROM wh.gold.bridge_candidate_record"
            )
        else:
            # candidates against the user's requisitions only
            con.execute(
                """CREATE TABLE dim_candidate AS SELECT * FROM wh.gold.dim_candidate
                   WHERE candidate_sk IN (SELECT candidate_sk FROM fact_application)"""
            )
            con.execute(
                """CREATE TABLE bridge_candidate_record AS SELECT * FROM wh.gold.bridge_candidate_record
                   WHERE candidate_sk IN (SELECT candidate_sk FROM dim_candidate)"""
            )
        # colleagues: names and roles only, no candidate data
        con.execute("CREATE TABLE dim_user AS SELECT user_sk, user_id, name, role, department FROM wh.gold.dim_user")
        for t in _UNSCOPED:
            con.execute(f"CREATE TABLE {t} AS SELECT * FROM wh.gold.{t}")

        con.execute("DETACH wh")
        return con, principal
    except Exception:
        con.close()
        raise
