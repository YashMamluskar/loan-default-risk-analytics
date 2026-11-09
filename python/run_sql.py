"""Phase 7: run every SQL file against MySQL and record results and timings.

Connection settings come from environment variables only (never stored in the project):
    MYSQL_HOST (default 127.0.0.1), MYSQL_PORT (3306), MYSQL_USER (root), MYSQL_PASSWORD (empty)

Usage: python run_sql.py [--skip-load]
Writes data/aggregate/sql_results/Qnn.csv, query_log.csv and dq_results.csv, then reconciles
vw_kpi_portfolio with the Python KPIs and raises if they differ.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

import mysql.connector
import pandas as pd

from config import AGGREGATE_DIR, PROJECT_ROOT, ensure_dirs, get_logger

log = get_logger("run_sql")
SQL_DIR = PROJECT_ROOT / "sql"
OUT = AGGREGATE_DIR / "sql_results"


def connect(database: str | None = None):
    return mysql.connector.connect(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"), port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "root"), password=os.environ.get("MYSQL_PASSWORD", ""),
        database=database, allow_local_infile=True, connection_timeout=30, use_pure=True,
    )


def statements(path) -> list[tuple[str, str]]:
    """Split a script into (leading comment, statement) pairs. Scripts hold no ';' inside strings."""
    text = path.read_text(encoding="utf-8")
    chunks = [c.strip() for c in text.split(";\n")]
    pairs = []
    for chunk in chunks:
        lines = chunk.splitlines()
        comments = [l for l in lines if l.strip().startswith("--")]
        body = "\n".join(l for l in lines if not l.strip().startswith("--")).strip().rstrip(";")
        if body:
            pairs.append(("\n".join(comments), body))
    return pairs


def run_file(cur, name: str, query_log: list, dq: list) -> None:
    for comment, body in statements(SQL_DIR / name):
        start = time.time()
        cur.execute(body)
        rows = cur.fetchall() if cur.with_rows else None
        elapsed = time.time() - start
        match = re.search(r"--\s*(Q\d+)\.", comment)
        if rows is not None and match:
            frame = pd.DataFrame(rows, columns=[d[0] for d in cur.description])
            frame.to_csv(OUT / f"{match.group(1)}.csv", index=False)
            query_log.append({"file": name, "query": match.group(1), "purpose": comment.split(". ", 1)[-1].splitlines()[0],
                              "rows": len(frame), "seconds": round(elapsed, 2)})
            log.info("%s rows=%d %.1fs", match.group(1), len(frame), elapsed)
        elif rows is not None and name.startswith("03"):
            dq.append({"check_name": rows[0][0], "failures": int(rows[0][1]), "seconds": round(elapsed, 2)})
            log.info("DQ %s failures=%s", rows[0][0], rows[0][1])
        else:
            log.info("%s: %s (%.1fs)", name, " ".join(body.split())[:70], elapsed)


def reconcile(cur) -> pd.DataFrame:
    cur.execute("SELECT * FROM vw_kpi_portfolio")
    sql_row = dict(zip([d[0] for d in cur.description], cur.fetchone()))
    kpi = json.loads((AGGREGATE_DIR / "portfolio_kpis.json").read_text())
    fin = json.loads((AGGREGATE_DIR / "financial_totals.json").read_text())
    expected = {
        "total_loans": kpi["loans"], "total_funded": kpi["funded"], "avg_funded": kpi["avg_funded"], "avg_int_rate": kpi["avg_rate"],
        "fully_paid": kpi["fully_paid"], "charged_off": kpi["charged_off"], "resolved": kpi["resolved"], "default_rate": kpi["default_rate"],
        "principal_weighted_rate": kpi["principal_weighted_rate"], "mature_default_rate": kpi["mature_default_rate"],
        "total_payments": fin["total_payments"], "principal_received": fin["principal_received"],
        "unpaid_principal_at_chargeoff": fin["unpaid_principal"], "recoveries": fin["co_recoveries"],
        "recovery_fees": fin["co_fees"], "est_net_principal_loss": fin["est_net_loss"],
    }
    rows = []
    for key, python_value in expected.items():
        sql_value = float(sql_row[key])
        tolerance = 1e-5 if abs(python_value) < 100 else 5.0  # ratios vs dollars (DECIMAL rounding)
        rows.append({"kpi": key, "python": python_value, "mysql": sql_value, "difference": sql_value - python_value,
                     "tolerance": tolerance, "match": abs(sql_value - python_value) <= tolerance})
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "kpi_reconciliation_python_mysql.csv", index=False)
    log.info("Reconciliation:\n%s", frame.to_string())
    return frame


def main() -> int:
    ensure_dirs()
    OUT.mkdir(parents=True, exist_ok=True)
    os.chdir(PROJECT_ROOT)  # 02_data_loading.sql uses project-relative paths
    skip_load = "--skip-load" in sys.argv
    con = connect()
    con.autocommit = True
    cur = con.cursor()
    query_log: list[dict] = []
    dq: list[dict] = []
    files = ["01_database_schema.sql", "02_data_loading.sql"] if not skip_load else []
    files += ["03_data_quality_checks.sql", "06_kpi_views.sql", "04_business_analysis.sql", "05_advanced_analysis.sql"]
    if skip_load:
        cur.execute("USE loan_default_analytics")
    for name in files:
        log.info("=== %s ===", name)
        run_file(cur, name, query_log, dq)
    pd.DataFrame(query_log).to_csv(OUT / "query_log.csv", index=False)
    pd.DataFrame(dq).to_csv(OUT / "dq_results.csv", index=False)
    frame = reconcile(cur)
    con.close()
    bad_dq = [d for d in dq if d["failures"]]
    if bad_dq or not frame.match.all():
        log.error("Failed DQ: %s; KPI mismatches: %s", bad_dq, frame[~frame.match].kpi.tolist())
        return 1
    log.info("All %d DQ checks passed; %d queries ran; KPIs reconciled", len(dq), len(query_log))
    return 0


if __name__ == "__main__":
    sys.exit(main())
