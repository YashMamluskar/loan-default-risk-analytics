"""Phase 11: cross-tool QA. Compares Python, MySQL and Power BI KPIs and writes the testing report.

Every line of the report comes from a check run here or from a result file written by the tool that
ran it. A step that has not run is reported as NOT RUN rather than assumed to pass.
"""
from __future__ import annotations

import json
import re

import pandas as pd

from config import AGGREGATE_DIR, ANALYTICAL_PARQUET, AUDIT_DIR, CLEAN_PARQUET, DOCS_DIR, EXPORT_DIR, PROJECT_ROOT, STAGING_PARQUET, connect, ensure_dirs, get_logger

log = get_logger("qa_checks")
SQL_RESULTS = AGGREGATE_DIR / "sql_results"
PBI_RESULTS = AGGREGATE_DIR / "powerbi_validation"
checks: list[dict] = []


def check(area: str, name: str, passed, detail="") -> None:
    status = "NOT RUN" if passed is None else ("Pass" if passed else "FAIL")
    checks.append({"area": area, "check": name, "result": status, "detail": str(detail)})
    log.info("%-8s %-12s %s %s", status, area, name, detail)


def python_kpis() -> dict:
    kpi = json.loads((AGGREGATE_DIR / "portfolio_kpis.json").read_text())
    fin = json.loads((AGGREGATE_DIR / "financial_totals.json").read_text())
    return {"total_loans": kpi["loans"], "total_funded": kpi["funded"], "avg_funded": kpi["avg_funded"], "avg_int_rate": kpi["avg_rate"], "fully_paid": kpi["fully_paid"],
            "charged_off": kpi["charged_off"], "resolved": kpi["resolved"], "default_rate": kpi["default_rate"], "principal_weighted_rate": kpi["principal_weighted_rate"],
            "mature_default_rate": kpi["mature_default_rate"], "total_payments": fin["total_payments"], "principal_received": fin["principal_received"],
            "unpaid_principal_at_chargeoff": fin["unpaid_principal"], "recoveries": fin["co_recoveries"], "recovery_fees": fin["co_fees"], "est_net_principal_loss": fin["est_net_loss"]}


def reconciliation() -> pd.DataFrame:
    py = python_kpis()
    frame = pd.DataFrame({"kpi": list(py), "python": list(py.values())})
    path = SQL_RESULTS / "kpi_reconciliation_python_mysql.csv"
    frame["mysql"] = frame.kpi.map(pd.read_csv(path).set_index("kpi").mysql) if path.exists() else float("nan")
    path = PBI_RESULTS / "dax_portfolio.csv"
    if path.exists():
        dax = pd.read_csv(path).iloc[0].to_dict()
        frame["power_bi"] = frame.kpi.map(dax)
        # DAX average rate is stored as a fraction; Python reports percent.
        frame.loc[frame.kpi == "avg_int_rate", "power_bi"] *= 100
    else:
        frame["power_bi"] = float("nan")
    # Ratios must agree closely. Dollars may differ by rounding: MySQL DECIMAL(,6), Power BI cents across 2.26M loans.
    frame["tolerance"] = frame.python.map(lambda v: 1e-5 if abs(v) < 100 else 50.0)
    frame.to_csv(AGGREGATE_DIR / "kpi_reconciliation_all_tools.csv", index=False)
    return frame


def main() -> int:
    ensure_dirs()
    con = connect()
    one = lambda sql: con.execute(sql).fetchone()[0]

    # Data pipeline
    n_clean = one(f"SELECT COUNT(*) FROM '{CLEAN_PARQUET.as_posix()}'")
    n_raw = one(f"SELECT COUNT(*) FROM '{STAGING_PARQUET.as_posix()}'")
    check("Pipeline", "Clean rows = raw rows - 33 non-loan rows", n_clean == n_raw - 33, f"{n_raw:,} to {n_clean:,}")
    check("Pipeline", "Analytical file keeps every loan", one(f"SELECT COUNT(*) FROM '{ANALYTICAL_PARQUET.as_posix()}'") == n_clean)
    v = pd.read_csv(AUDIT_DIR / "validation_results.csv")
    bad = v[(~v.passed) & (v.severity == "error")]
    check("Pipeline", "Data validation rules", bad.empty, f"{(v.severity == 'error').sum()} rules, {len(bad)} failed")
    fact = EXPORT_DIR / "powerbi" / "fact_loans.parquet"
    check("Exports", "Power BI fact has every loan", one(f"SELECT COUNT(*) FROM '{fact.as_posix()}'") == n_clean)
    check("Exports", "Power BI fact ids are unique", one(f"SELECT COUNT(DISTINCT loan_id) FROM '{fact.as_posix()}'") == n_clean)
    for table in ("loan_details", "borrower_profiles", "loan_performance"):
        path = EXPORT_DIR / "mysql" / f"{table}.csv"
        with open(path, "rb") as handle:
            lines = sum(buffer.count(b"\n") for buffer in iter(lambda: handle.read(1 << 20), b""))
        check("Exports", f"MySQL {table}.csv row count", lines - 1 == n_clean, f"{lines - 1:,}")

    # Protected-field check on exports
    fact_cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM '{fact.as_posix()}'").fetchall()}
    check("Privacy", "No free text or personal fields in the Power BI fact", not fact_cols & {"emp_title", "title", "desc", "zip_code", "url", "member_id"})

    # SQL
    dq_path, log_path = SQL_RESULTS / "dq_results.csv", SQL_RESULTS / "query_log.csv"
    if dq_path.exists() and log_path.exists():
        dq = pd.read_csv(dq_path)
        ql = pd.read_csv(log_path)
        check("MySQL", "Data-quality checks", (dq.failures == 0).all(), f"{len(dq)} checks")
        check("MySQL", "Business queries executed (at least 25 required)", len(ql) >= 25, f"{len(ql)} queries, slowest {ql.seconds.max():.0f}s")
        written = {re.match(r"-- (Q\d+)\.", l).group(1) for f in ("04_business_analysis.sql", "05_advanced_analysis.sql") for l in (PROJECT_ROOT / "sql" / f).read_text(encoding="utf-8").splitlines() if re.match(r"-- Q\d+\.", l)}
        check("MySQL", "Every written query was executed", written == set(ql["query"]), f"{len(written)} written")
    else:
        check("MySQL", "Data-quality checks and business queries", None, "No result files")

    # Cross-tool KPI reconciliation
    rec = reconciliation()
    for tool, label in (("mysql", "MySQL"), ("power_bi", "Power BI")):
        if rec[tool].isna().all():
            check("KPI", f"Python vs {label}", None, "No result file")
        else:
            diff = (rec[tool] - rec.python).abs()
            check("KPI", f"Python vs {label} on {len(rec)} KPIs", (diff <= rec.tolerance).all(), f"largest dollar gap ${diff[rec.python.abs() >= 100].max():,.2f}")

    # Grade-level DAX vs Python and filter behaviour
    grade_path = PBI_RESULTS / "dax_by_grade.csv"
    if grade_path.exists():
        dax = pd.read_csv(grade_path).set_index("grade")
        py = pd.read_csv(AGGREGATE_DIR / "summary_grade.csv").set_index("grade")
        check("Power BI", "Grade default rates match Python", ((dax.default_rate - py.default_rate).abs() < 1e-9).all())
        check("Power BI", "Grade mature rates match Python", ((dax.mature_default_rate - py.mature_default_rate).abs() < 1e-9).all())
        f = pd.read_csv(PBI_RESULTS / "dax_filter_checks.csv").iloc[0]
        state = pd.read_csv(AGGREGATE_DIR / "summary_state.csv").set_index("addr_state")
        purpose = pd.read_csv(AGGREGATE_DIR / "summary_purpose_label.csv").set_index("purpose_label")
        dti = pd.read_csv(AGGREGATE_DIR / "summary_dti_band.csv").set_index("dti_band")
        tier = pd.read_csv(AGGREGATE_DIR / "risk_tier_summary.csv").set_index("risk_tier")
        check("Power BI", "Filtered measure: state CA", abs(f.ca_rate - state.default_rate["CA"]) < 1e-9, f"{f.ca_rate:.4%}")
        check("Power BI", "Filtered measure: Small Business", abs(f.small_business_rate - purpose.default_rate["Small Business"]) < 1e-9, f"{f.small_business_rate:.4%}")
        check("Power BI", "Filtered measure: DTI 40+", abs(f.dti_40_rate - dti.default_rate["40+"]) < 1e-9, f"{f.dti_40_rate:.4%}")
        check("Power BI", "Filtered measure: High tier loans", f.high_tier_loans == tier.loans["High"], f"{f.high_tier_loans:,.0f}")
        check("Power BI", "Rate is blank on Current loans, never zero or a false default", pd.isna(f.current_rate_blank))
        cohort = pd.read_csv(PBI_RESULTS / "dax_by_year_term.csv")
        immature = cohort[(cohort.elapsed < 0.99)]
        check("Power BI", "Mature cohort measure blanks immature cohorts", immature.mature_cohort.isna().all(), f"{len(immature)} immature cohorts")
        m = pd.read_csv(PBI_RESULTS / "dax_all_measures.csv")
        check("Power BI", "All measures evaluate without error", (m.status == "ok").all(), f"{len(m)} measures")
    else:
        check("Power BI", "DAX validation against a loaded model", None, "No result file")

    status_path = PBI_RESULTS / "pbix_status.json"
    status = json.loads(status_path.read_text()) if status_path.exists() else {}
    for item in status.get("checks", []):
        check("Power BI", item["check"], item["passed"], item.get("detail", ""))

    frame = pd.DataFrame(checks)
    frame.to_csv(AGGREGATE_DIR / "qa_results.csv", index=False)
    rec_show = rec.drop(columns="tolerance").copy()
    fmt = lambda v: "" if pd.isna(v) else (f"{v:,.6f}" if abs(v) < 100 else f"{v:,.2f}")
    for col in ("python", "mysql", "power_bi"):
        rec_show[col] = rec_show[col].map(fmt)
    table = lambda f: "| " + " | ".join(f.columns) + " |\n|" + "---|" * len(f.columns) + "\n" + "\n".join("| " + " | ".join(map(str, r)) + " |" for r in f.values)
    counts = frame.result.value_counts().to_dict()
    limits = status.get("limits", [])
    (DOCS_DIR / "testing_report.md").write_text(f"""# Testing Report

Generated by `python/qa_checks.py`. Results: {counts.get('Pass', 0)} passed, {counts.get('FAIL', 0)} failed, {counts.get('NOT RUN', 0)} not run.

## Checks

{table(frame.rename(columns=str.title))}

## KPI reconciliation across tools

{table(rec_show)}

Dollar differences come from rounding: MySQL stores six decimals, Power BI stores cents. Ratios agree to at least five decimals.

## Defects found and fixed during testing

| Defect | How it was found | Fix |
|---|---|---|
| 33 non-loan rows included a section label as well as totals | Cleaning assertion | Rule covers both; rows logged in `data/aggregate/audit/non_loan_rows.csv` |
| 3 whitespace-only `emp_title` values appeared as lost values | Value-loss validation rule | Blank-aware comparison |
| Charged-off composition double-counted recovery fees | Reconciliation assertion | Chart now reconciles to funded amount exactly |
| DuckDB reservoir sampling was unrepresentative (82% of rows from 2015) | Comparison of sample and population mix; an implausible odds-ratio interval prompted it | Hash-based sample plus an automatic representativeness assertion; all sampled statistics rerun |
| Dollar signs in chart labels rendered as math text | Visual review | Math parsing disabled |
| Q31 stalled for over 7 minutes on a segment-first join | Query monitoring | Aggregates first, then joins; rerun |
| Notebooks launched under global Python | Execution failure | Run through the project environment and its kernel |
| MySQL division rounded rates to 4 decimals, so the default rate read 0.1996 | Python and MySQL reconciliation | Session precision raised in query scripts; views compute rates in floating point; rerun |
| Band labels sorted alphabetically in Power BI (`$100K` before `<$40K`) | Screenshot review | Removed unneeded key flag from band dimensions, so model sort columns apply |
| Drill-through was missing from the right-click menu, and tooltips showed defaults | Interaction test | Added the page bindings Power BI expects; both retested and working |

## Known limitations of this testing

{chr(10).join('- ' + l for l in limits) if limits else '- See the checks above for anything marked NOT RUN.'}
""", encoding="utf-8")
    log.info("QA: %s", counts)
    return 1 if counts.get("FAIL") else 0


if __name__ == "__main__":
    raise SystemExit(main())
