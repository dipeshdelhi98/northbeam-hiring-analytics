import pytest

from pipeline.config import WAREHOUSE_PATH
from pipeline.run import build


@pytest.fixture(scope="session", autouse=True)
def warehouse():
    """Build the warehouse once per test session (idempotent, so safe on an existing file)."""
    build(WAREHOUSE_PATH, verbose=False)
    return WAREHOUSE_PATH


@pytest.fixture(scope="session")
def admin_con(warehouse):
    from api.scope import scoped_connection

    con, _ = scoped_connection("U013")  # Simran Jain, admin
    yield con
    con.close()
