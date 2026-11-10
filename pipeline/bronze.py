"""Bronze: data exactly as landed, every value as text, plus lineage.

Idempotency: a file is identified by its SHA-256. If the same bytes have already been
loaded, the load is recorded as `skipped_duplicate` and no rows are appended. A changed
file is appended as a new load; Silver always reads the latest load of each source.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import openpyxl

from pipeline.config import LANDING_DIR, SOURCES

LINEAGE_COLS = ["_load_id", "_source_file", "_source_sha256", "_source_row", "_loaded_at"]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _as_text(v) -> str | None:
    """Stringify without interpretation. None stays NULL; everything else is str()."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat(sep=" ")
    return str(v)


def _read_rows(path: Path) -> tuple[list[str], list[list[str | None]]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            # Empty string in a CSV is as-landed; Silver decides whether it means NULL.
            return header, [list(r) for r in reader]
    if suffix == ".json":
        records = json.loads(path.read_text(encoding="utf-8"))
        header: list[str] = []
        for r in records:
            for k in r:
                if k not in header:
                    header.append(k)
        return header, [[_as_text(r.get(k)) for k in header] for r in records]
    if suffix == ".xlsx":
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.worksheets[0]
        it = ws.iter_rows(values_only=True)
        header = [str(h) for h in next(it)]
        rows = [[_as_text(v) for v in row] for row in it if any(v is not None for v in row)]
        wb.close()
        return header, rows
    raise ValueError(f"Unsupported file type: {path}")


def _ensure_log(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS bronze._load_log (
            load_id       INTEGER,
            source        VARCHAR,
            source_file   VARCHAR,
            source_sha256 VARCHAR,
            row_count     INTEGER,
            loaded_at     TIMESTAMP,
            status        VARCHAR  -- loaded | skipped_duplicate
        )
        """
    )


def load_source(con: duckdb.DuckDBPyConnection, source: str, path: Path) -> dict:
    sha = _sha256(path)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    next_id = con.execute("SELECT coalesce(max(load_id), 0) + 1 FROM bronze._load_log").fetchone()[0]

    already = con.execute(
        "SELECT 1 FROM bronze._load_log WHERE source = ? AND source_sha256 = ? AND status = 'loaded'",
        [source, sha],
    ).fetchone()
    if already:
        con.execute(
            "INSERT INTO bronze._load_log VALUES (?, ?, ?, ?, 0, ?, 'skipped_duplicate')",
            [next_id, source, path.name, sha, now],
        )
        return {"source": source, "status": "skipped_duplicate", "rows": 0}

    header, rows = _read_rows(path)
    table = f"bronze.{source}"
    cols_ddl = ", ".join(f'"{c}" VARCHAR' for c in header)
    con.execute(
        f"""CREATE TABLE IF NOT EXISTS {table} ({cols_ddl},
            _load_id INTEGER, _source_file VARCHAR, _source_sha256 VARCHAR,
            _source_row INTEGER, _loaded_at TIMESTAMP)"""
    )
    existing = [r[0] for r in con.execute(f"DESCRIBE {table}").fetchall()]
    for c in header:  # schema drift: new columns are added, never dropped
        if c not in existing:
            con.execute(f'ALTER TABLE {table} ADD COLUMN "{c}" VARCHAR')

    payload = [r + [next_id, path.name, sha, i + 1, now] for i, r in enumerate(rows)]
    col_list = ", ".join(f'"{c}"' for c in header + LINEAGE_COLS)
    placeholders = ", ".join("?" for _ in header + LINEAGE_COLS)
    con.begin()
    try:
        con.executemany(f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})", payload)
        con.execute(
            "INSERT INTO bronze._load_log VALUES (?, ?, ?, ?, ?, ?, 'loaded')",
            [next_id, source, path.name, sha, len(rows), now],
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    return {"source": source, "status": "loaded", "rows": len(rows)}


def run(con: duckdb.DuckDBPyConnection, landing_dir: Path = LANDING_DIR) -> list[dict]:
    _ensure_log(con)
    results = [load_source(con, src, landing_dir / fname) for src, fname in SOURCES.items()]
    # Silver reads only the latest successful load of each source.
    for src in SOURCES:
        con.execute(
            f"""CREATE OR REPLACE VIEW bronze.{src}_latest AS
                SELECT * FROM bronze.{src}
                WHERE _load_id = (SELECT max(load_id) FROM bronze._load_log
                                  WHERE source = '{src}' AND status = 'loaded')"""
        )
    return results
