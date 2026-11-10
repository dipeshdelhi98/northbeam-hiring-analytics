"""Authentication: email + password -> short-lived HS256 JWT carrying only the user id.

Demo credentials: every user in users.json can sign in with NB_DEMO_PASSWORD (default below).
This is a stand-in for SSO — in production the IdP (Entra ID / Google Workspace via OIDC) would
assert identity and this module would verify *its* token instead. Everything downstream only
needs a trusted user id, so that swap does not touch scoping.

Deliberate choices
- The token carries `sub` (user id) and nothing used for authorisation. Role and scope are
  re-read from Gold on every request, so a revoked role takes effect immediately and editing
  claims achieves nothing even if the signature were somehow valid.
- `algorithms=["HS256"]` is pinned on decode: `alg: none` and algorithm-confusion tokens fail.
- Login failure is the same response for unknown email and wrong password.
"""
from __future__ import annotations

import hmac
import os
import secrets
import time

import duckdb
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pipeline.config import WAREHOUSE_PATH

JWT_SECRET = os.environ.get("NB_JWT_SECRET") or secrets.token_urlsafe(48)
JWT_ALG = "HS256"
TOKEN_TTL_SECONDS = int(os.environ.get("NB_TOKEN_TTL", "3600"))
DEMO_PASSWORD = os.environ.get("NB_DEMO_PASSWORD", "northbeam-demo")

_bearer = HTTPBearer(auto_error=False)
_UNAUTHORISED = HTTPException(
    status.HTTP_401_UNAUTHORIZED, "Not authenticated", headers={"WWW-Authenticate": "Bearer"}
)


def authenticate(email: str, password: str) -> str | None:
    """Return the user id for valid credentials, else None."""
    con = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
    try:
        row = con.execute(
            "SELECT user_id FROM gold.dim_user WHERE email = lower(trim(?))", [email]
        ).fetchone()
    finally:
        con.close()
    ok = hmac.compare_digest(password.encode(), DEMO_PASSWORD.encode())
    return row[0] if (row and ok) else None


def issue_token(user_id: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": user_id, "iat": now, "exp": now + TOKEN_TTL_SECONDS}, JWT_SECRET, algorithm=JWT_ALG
    )


def current_user_id(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    if creds is None or creds.scheme.lower() != "bearer":
        raise _UNAUTHORISED
    try:
        claims = jwt.decode(
            creds.credentials, JWT_SECRET, algorithms=[JWT_ALG], options={"require": ["sub", "exp"]}
        )
    except jwt.PyJWTError:
        raise _UNAUTHORISED
    return str(claims["sub"])
