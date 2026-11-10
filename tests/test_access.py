"""Access control, attacked the way a curious user with dev tools would.

Satisfies the brief's "tell us how you satisfied yourself it cannot be bypassed": every test
here sends a request a real client could send, and asserts on what comes back.
"""
import time

import jwt
import pytest
from fastapi.testclient import TestClient

from api import auth
from api.main import app
from api.scope import scoped_connection

client = TestClient(app)
PW = auth.DEMO_PASSWORD

UDAY = "uday.varma@northbeam.example"        # U005 hiring manager: REQ-1003, 1010, 1024
NAVEEN = "naveen.malhotra@northbeam.example"  # U001 recruiter
ADMIN = "simran.jain@northbeam.example"       # U013 admin


def login(email, password=PW):
    r = client.post("/api/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_hiring_manager_sees_only_own_requisitions():
    h = login(UDAY)
    assert client.get("/api/me", headers=h).json()["requisitions"] == ["REQ-1003", "REQ-1010", "REQ-1024"]
    reqs = {r["req_id"] for r in client.get("/api/dashboard", headers=h).json()["pipeline_by_requisition"]["value"]}
    assert reqs == {"REQ-1003", "REQ-1010", "REQ-1024"}


def test_recruiter_sees_only_owned_requisitions():
    h = login(NAVEEN)
    con, _ = scoped_connection("U001")
    expected = {r[0] for r in con.execute("SELECT req_id FROM dim_requisition WHERE recruiter_id='U001'").fetchall()}
    assert set(client.get("/api/me", headers=h).json()["requisitions"]) == expected


def test_editing_the_url_to_another_requisition_returns_404():
    h = login(UDAY)
    assert client.get("/api/requisitions/REQ-1003/applications", headers=h).status_code == 200
    # REQ-1011 belongs to U010; exists but out of scope -> identical to non-existent
    assert client.get("/api/requisitions/REQ-1011/applications", headers=h).status_code == 404
    assert client.get("/api/requisitions/REQ-9999/applications", headers=h).status_code == 404


def test_guessing_an_application_id_outside_scope_returns_404():
    con, _ = scoped_connection("U010")
    other = con.execute("SELECT application_id FROM fact_application LIMIT 1").fetchone()[0]
    assert client.get(f"/api/applications/{other}/history", headers=login(UDAY)).status_code == 404
    assert client.get(f"/api/applications/{other}/history", headers=login(ADMIN)).status_code == 200


def test_metrics_are_scoped_and_query_params_cannot_widen_them():
    h = login(UDAY)
    mine = client.get("/api/metrics/candidate_pool", headers=h).json()["value"]
    assert 0 < mine < 560
    # parameters a metric does not take are rejected, not silently honoured
    r = client.get("/api/metrics/candidate_pool?department=Sales", headers=h)
    assert r.status_code == 422
    # department filter can only narrow within scope: U005 has no Sales requisitions
    assert client.get("/api/metrics/offered_salary_total_inr?department=Sales", headers=h).json()["value"] == 0


def test_scoped_connection_has_no_path_to_the_warehouse():
    con, _ = scoped_connection("U005")
    assert [r[0] for r in con.execute("SELECT database_name FROM duckdb_databases() WHERE NOT internal").fetchall()] == ["memory"]
    assert con.execute("SELECT count(*) FROM fact_application WHERE requisition_sk NOT IN (SELECT requisition_sk FROM dim_requisition)").fetchone()[0] == 0


@pytest.mark.parametrize("path", ["/api/me", "/api/dashboard", "/api/metrics/candidate_pool",
                                  "/api/requisitions/REQ-1003/applications"])
def test_no_token_is_401(path):
    assert client.get(path).status_code == 401


def test_wrong_password_and_unknown_user_look_the_same():
    a = client.post("/api/login", json={"email": UDAY, "password": "nope"})
    b = client.post("/api/login", json={"email": "nobody@x.example", "password": PW})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def _forge(claims, key=auth.JWT_SECRET, alg="HS256"):
    return {"Authorization": "Bearer " + jwt.encode(claims, key, algorithm=alg)}


def test_tampered_tokens_are_rejected():
    now = int(time.time())
    # signed with the wrong key, claiming to be the admin
    assert client.get("/api/me", headers=_forge({"sub": "U013", "exp": now + 60}, key="guess")).status_code == 401
    # expired
    assert client.get("/api/me", headers=_forge({"sub": "U005", "exp": now - 1})).status_code == 401
    # alg=none
    unsigned = jwt.encode({"sub": "U013", "exp": now + 60}, None, algorithm="none")
    assert client.get("/api/me", headers={"Authorization": "Bearer " + unsigned}).status_code == 401
    # payload edited after signing (sub swapped), signature kept
    h, p, s = jwt.encode({"sub": "U005", "exp": now + 60}, auth.JWT_SECRET, algorithm="HS256").split(".")
    _, p2, _ = jwt.encode({"sub": "U013", "exp": now + 60}, "x", algorithm="HS256").split(".")
    assert client.get("/api/me", headers={"Authorization": f"Bearer {h}.{p2}.{s}"}).status_code == 401


def test_role_claim_in_token_is_ignored():
    now = int(time.time())
    h = _forge({"sub": "U005", "role": "admin", "exp": now + 60})
    assert client.get("/api/me", headers=h).json()["role"] == "hiring_manager"


def test_token_for_deleted_user_is_401():
    assert client.get("/api/me", headers=_forge({"sub": "U999", "exp": int(time.time()) + 60})).status_code == 401


def test_listings_do_not_expose_contact_details():
    rows = client.get("/api/requisitions/REQ-1003/applications", headers=login(UDAY)).json()
    assert rows and not any(k in rows[0] for k in ("email", "phone", "primary_email", "phone_norm"))
