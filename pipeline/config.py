import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANDING_DIR = Path(os.environ.get("NB_LANDING_DIR", ROOT / "data" / "landing"))
WAREHOUSE_PATH = Path(os.environ.get("NB_WAREHOUSE", ROOT / "warehouse" / "northbeam.duckdb"))

# source name -> file in the landing directory
SOURCES = {
    "candidates": "candidates.csv",
    "applications": "applications.csv",
    "stage_events": "stage_events.csv",
    "requisitions": "requisitions.json",
    "users": "users.json",
    "interviews": "interviews.json",
    "offers": "offers.xlsx",
}
