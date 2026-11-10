import shutil

import duckdb

from pipeline.config import LANDING_DIR
from pipeline.run import build


def _counts(path):
    con = duckdb.connect(str(path), read_only=True)
    try:
        tables = con.execute(
            """SELECT table_schema || '.' || table_name FROM information_schema.tables
               WHERE table_schema IN ('bronze','silver','gold') AND table_type = 'BASE TABLE'
                 AND table_name <> '_load_log'"""
        ).fetchall()
        return {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for (t,) in tables}
    finally:
        con.close()


def test_rerun_does_not_duplicate(tmp_path):
    wh = tmp_path / "wh.duckdb"
    build(wh, LANDING_DIR, verbose=False)
    first = _counts(wh)
    loads = build(wh, LANDING_DIR, verbose=False)
    assert {l["status"] for l in loads} == {"skipped_duplicate"}
    assert _counts(wh) == first


def test_reexported_file_with_repeated_rows_does_not_duplicate(tmp_path):
    """A changed file is a new Bronze load; Silver reads only the latest and dedupes on id."""
    landing = tmp_path / "landing"
    shutil.copytree(LANDING_DIR, landing)
    wh = tmp_path / "wh.duckdb"
    build(wh, landing, verbose=False)
    before = _counts(wh)

    csv = landing / "stage_events.csv"
    lines = csv.read_bytes().splitlines(keepends=True)
    csv.write_bytes(b"".join(lines + lines[1:51]))  # same 50 events exported twice
    build(wh, landing, verbose=False)
    after = _counts(wh)

    assert after["bronze.stage_events"] == before["bronze.stage_events"] + len(lines) - 1 + 50
    assert {k: v for k, v in after.items() if not k.startswith("bronze.")} == \
           {k: v for k, v in before.items() if not k.startswith("bronze.")}
