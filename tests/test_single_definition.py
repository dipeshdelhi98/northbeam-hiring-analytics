"""Guards for 'define a metric once'. Crude on purpose: a grep that fails loudly beats a convention.

1. Metric-shaped SQL (aggregates, date maths, offer-status logic) appears only in metrics/.
2. Metric SQL refers to bare table names, so it always runs against the scoped connection.
3. The frontend does no arithmetic on numbers it receives.
"""
import re
from pathlib import Path

from metrics import METRICS

ROOT = Path(__file__).resolve().parent.parent
METRIC_PATTERNS = [
    r"\bmedian\s*\(", r"\bquantile", r"\bdate_diff\s*\(", r"\bdatediff\s*\(",
    r"\bavg\s*\(", r"\bsum\s*\(", r"count\s*\(\s*\*\s*\)\s*filter", r"'accepted'", r"'declined'",
]
# Places allowed to contain metric-shaped SQL:
ALLOWED = {
    ROOT / "metrics" / "definitions.py",
    ROOT / "pipeline" / "gold.py",       # builds tables, computes no metric
    ROOT / "pipeline" / "silver.py",
}


SKIP_DIRS = {".venv", "tests", "node_modules", ".next", "out", ".git"}


def _code_files():
    for p in ROOT.rglob("*"):
        if p.suffix in {".py", ".html", ".js", ".sql", ".ts", ".tsx"} and not SKIP_DIRS & set(p.parts):
            yield p


def test_metric_logic_lives_only_in_metric_layer():
    offenders = []
    for p in _code_files():
        if p in ALLOWED:
            continue
        text = p.read_text(encoding="utf-8").lower()
        offenders += [f"{p.relative_to(ROOT)}: {pat}" for pat in METRIC_PATTERNS if re.search(pat, text)]
    assert not offenders, "metric logic outside metrics/: " + ", ".join(offenders)


def test_silver_and_gold_compute_no_metrics():
    for p in (ROOT / "pipeline" / "gold.py", ROOT / "pipeline" / "silver.py"):
        text = p.read_text(encoding="utf-8").lower()
        for pat in (r"\bmedian\s*\(", r"\bavg\s*\(", r"'accepted'", r"date_diff"):
            assert not re.search(pat, text), f"{p.name} contains {pat}"


def test_metric_sql_uses_only_scoped_bare_tables():
    for m in METRICS.values():
        assert not re.search(r"\b(gold|silver|bronze|wh)\.", m.sql, re.I), m.name


def test_frontend_does_no_arithmetic_on_values():
    js = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = js[js.index("<script>"):]
    assert "Math." not in script and "toFixed" not in script and "parseFloat" not in script
    # numbers on cards are only ever the API's display strings
    assert ".value)" not in script and "c.value" not in script


def test_next_frontend_does_no_arithmetic_on_values():
    """The React app may filter, sort and lay out rows, but never derive or reformat a number:
    no maths library, no numeric parsing, no aggregation, no locale number formatting."""
    forbidden = [r"\bMath\.", r"toFixed", r"parseFloat", r"parseInt", r"\bNumber\(", r"\.reduce\(",
                 r"Intl\.NumberFormat", r"toLocaleString", r"toPrecision"]
    offenders = []
    for p in (ROOT / "frontend" / "src").rglob("*.ts*"):
        text = p.read_text(encoding="utf-8")
        offenders += [f"{p.relative_to(ROOT)}: {pat}" for pat in forbidden if re.search(pat, text)]
    assert not offenders, offenders
