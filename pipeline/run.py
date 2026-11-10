"""Entry point: python -m pipeline.run"""
import time

import duckdb

from pipeline import bronze, gold, silver
from pipeline.config import LANDING_DIR, WAREHOUSE_PATH


def build(warehouse_path=WAREHOUSE_PATH, landing_dir=LANDING_DIR, verbose=True) -> list[dict]:
    warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(warehouse_path))
    try:
        t0 = time.perf_counter()
        loads = bronze.run(con, landing_dir)
        silver.run(con)
        gold.run(con)
        if verbose:
            for l in loads:
                print(f"bronze  {l['source']:<14} {l['status']:<18} rows={l['rows']}")
            for (t,) in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='gold' ORDER BY 1"
            ).fetchall():
                n = con.execute(f"SELECT count(*) FROM gold.{t}").fetchone()[0]
                print(f"gold    {t:<32} rows={n}")
            print(f"built {warehouse_path} in {time.perf_counter() - t0:.2f}s")
        return loads
    finally:
        con.close()


if __name__ == "__main__":
    build()
