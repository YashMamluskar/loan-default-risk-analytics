"""Phase 8: build the Power BI star schema and the reporting summaries.

The fact table holds all 2,260,668 loans (no sampling) but only the 31 of 186 cleaned
columns the dashboard uses, with money rounded to cents to compress better in VertiPaq.
Text attributes move to small dimensions. Summaries are written as CSV for review and reuse.
"""
from __future__ import annotations

import json
import shutil

import pandas as pd

from analysis_common import ORDERS, analytical_src, segment_metrics
from config import AGGREGATE_DIR, EXPORT_DIR, STATS_DIR, connect, ensure_dirs, get_logger

log = get_logger("powerbi_export")
OUT = EXPORT_DIR / "powerbi"
SUMMARY_OUT = AGGREGATE_DIR / "powerbi_summaries"

STATE_NAMES = {
    "AK": "Alaska", "AL": "Alabama", "AR": "Arkansas", "AZ": "Arizona", "CA": "California", "CO": "Colorado", "CT": "Connecticut",
    "DC": "District of Columbia", "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "IA": "Iowa", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "MA": "Massachusetts", "MD": "Maryland",
    "ME": "Maine", "MI": "Michigan", "MN": "Minnesota", "MO": "Missouri", "MS": "Mississippi", "MT": "Montana", "NC": "North Carolina",
    "ND": "North Dakota", "NE": "Nebraska", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NV": "Nevada", "NY": "New York",
    "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VA": "Virginia", "VT": "Vermont", "WA": "Washington", "WI": "Wisconsin",
    "WV": "West Virginia", "WY": "Wyoming",
}

FACT_SQL = """
    id AS loan_id, issue_d AS issue_date, sub_grade, term_months, purpose_label, addr_state, status_clean, risk_segment,
    income_band, dti_band, amount_band, rate_band, fico_band, emp_length_label, home_ownership_group, verification_status,
    credit_history_band, delinq_band,
    funded_amnt, ROUND(funded_amnt_inv, 2) AS funded_amnt_inv, int_rate, annual_inc_clean, dti_clean, emp_length_years, fico_mid,
    is_fully_paid, is_charged_off, is_resolved, is_term_elapsed,
    ROUND(total_pymnt, 2) AS total_pymnt, ROUND(total_rec_prncp, 2) AS total_rec_prncp, ROUND(total_rec_int, 2) AS total_rec_int,
    ROUND(recoveries, 2) AS recoveries, ROUND(collection_recovery_fee, 2) AS collection_recovery_fee, ROUND(out_prncp, 2) AS out_prncp,
    ROUND(unpaid_principal_at_chargeoff, 2) AS unpaid_principal_at_chargeoff, ROUND(est_net_principal_loss, 2) AS est_net_principal_loss
"""

STATUS_ORDER = ["Fully Paid", "Current", "In Grace Period", "Late (16-30 days)", "Late (31-120 days)", "Default", "Charged Off",
                "Policy Exception - Fully Paid", "Policy Exception - Charged Off"]
STATUS_GROUP = {"Fully Paid": "Resolved", "Charged Off": "Resolved", "Current": "Unresolved", "In Grace Period": "Unresolved",
                "Late (16-30 days)": "Unresolved", "Late (31-120 days)": "Unresolved", "Default": "Default Status",
                "Policy Exception - Fully Paid": "Policy Exception", "Policy Exception - Charged Off": "Policy Exception"}


def write_dim(frame: pd.DataFrame, name: str, con) -> None:
    con.register("dim_frame", frame)
    con.execute(f"COPY dim_frame TO '{(OUT / f'{name}.parquet').as_posix()}' (FORMAT PARQUET)")
    con.unregister("dim_frame")
    log.info("%s rows=%d", name, len(frame))


def band_dim(values: list, key: str) -> pd.DataFrame:
    return pd.DataFrame({key: values, f"{key}_sort": range(1, len(values) + 1)})


def build_dimensions(con, src) -> None:
    distinct = lambda col: [r[0] for r in con.execute(f'SELECT DISTINCT "{col}" FROM {src} ORDER BY 1').fetchall()]

    days = pd.date_range("2007-01-01", "2019-12-31", freq="D")
    dim_date = pd.DataFrame({"date": days.date, "issue_year": days.year, "issue_quarter": "Q" + days.quarter.astype(str), "issue_month_num": days.month,
                             "issue_month": days.strftime("%b"), "year_month": days.strftime("%Y-%m"), "year_month_sort": days.year * 100 + days.month})
    write_dim(dim_date, "dim_date", con)

    subgrades = distinct("sub_grade")
    write_dim(pd.DataFrame({"sub_grade": subgrades, "sub_grade_sort": range(1, len(subgrades) + 1), "grade": [s[0] for s in subgrades]}), "dim_grade", con)
    write_dim(pd.DataFrame({"term_months": [36, 60], "term_label": ["36 months", "60 months"], "term_sort": [1, 2]}), "dim_term", con)
    write_dim(pd.DataFrame({"purpose_label": distinct("purpose_label")}), "dim_purpose", con)
    states = distinct("addr_state")
    missing = set(states) - set(STATE_NAMES)
    assert not missing, f"Unmapped states: {missing}"
    write_dim(pd.DataFrame({"addr_state": states, "state_name": [STATE_NAMES[s] for s in states]}), "dim_state", con)
    found = set(distinct("status_clean"))
    assert found == set(STATUS_ORDER), f"Status taxonomy mismatch: {found ^ set(STATUS_ORDER)}"
    write_dim(pd.DataFrame({"status_clean": STATUS_ORDER, "status_group": [STATUS_GROUP[s] for s in STATUS_ORDER], "status_sort": range(1, 10)}), "dim_status", con)

    seg = pd.read_csv(AGGREGATE_DIR / "risk_segments_grade_term.csv")
    tier_sort = {"Low": 1, "Medium": 2, "High": 3, "Insufficient data": 4}
    write_dim(pd.DataFrame({"risk_segment": seg.risk_segment, "risk_tier": seg.risk_tier, "risk_tier_sort": seg.risk_tier.map(tier_sort),
                            "relative_risk_index": seg.relative_risk_index.round(3)}), "dim_risk_segment", con)

    bands = {"dim_income_band": ("income_band", ORDERS["income_band"]), "dim_dti_band": ("dti_band", ORDERS["dti_band"]),
             "dim_amount_band": ("amount_band", ORDERS["amount_band"]), "dim_rate_band": ("rate_band", ORDERS["rate_band"]),
             "dim_fico_band": ("fico_band", ORDERS["fico_band"]), "dim_emp_length": ("emp_length_label", ORDERS["emp_length_label"]),
             "dim_credit_history_band": ("credit_history_band", ORDERS["credit_history_band"]), "dim_delinq_band": ("delinq_band", ORDERS["delinq_band"])}
    for name, (key, order) in bands.items():
        actual = set(distinct(key))
        values = [v for v in order if v in actual]
        assert set(values) == actual, f"{key}: unexpected values {actual - set(values)}"
        write_dim(band_dim(values, key), name, con)
    write_dim(pd.DataFrame({"home_ownership_group": distinct("home_ownership_group")}), "dim_home_ownership", con)
    write_dim(pd.DataFrame({"verification_status": ["Not Verified", "Source Verified", "Verified"], "verification_sort": [1, 2, 3]}), "dim_verification", con)


def build_summaries(con, src) -> None:
    """Validated summaries required by the brief; each is traceable to analysis_common.segment_metrics."""
    dims = {"grade": "grade", "subgrade": "sub_grade", "purpose": "purpose_label", "income": "income_band", "dti": "dti_band", "employment": "emp_length_label",
            "home_ownership": "home_ownership_group", "verification": "verification_status", "fico": "fico_band", "term": "term_months", "state": "addr_state",
            "annual_cohort": "issue_year", "risk_segment": "risk_segment"}
    for name, dim in dims.items():
        segment_metrics(con, dim, src).to_csv(SUMMARY_OUT / f"summary_{name}.csv", index=False)
    segment_metrics(con, "status_clean", src).to_csv(SUMMARY_OUT / "summary_status.csv", index=False)
    recov = segment_metrics(con, ["issue_year", "grade"], src)[["issue_year", "grade", "charged_off", "unpaid_principal_at_chargeoff", "recoveries", "recovery_fees", "recovery_ratio", "est_net_principal_loss"]]
    recov.to_csv(SUMMARY_OUT / "summary_recoveries.csv", index=False)
    shutil.copy(AGGREGATE_DIR / "portfolio_kpis.json", SUMMARY_OUT / "summary_portfolio.json")


def build_reference_tables(con) -> None:
    """Statistical findings for the insights page."""
    tests = pd.read_csv(STATS_DIR / "hypothesis_tests.csv")
    t = tests[["test_name", "test", "p_value_display", "effect_size", "business_reading"]].copy()
    t.insert(0, "finding_sort", range(1, len(t) + 1))
    write_dim(t, "ref_statistical_findings", con)


def main() -> None:
    ensure_dirs()
    OUT.mkdir(parents=True, exist_ok=True)
    SUMMARY_OUT.mkdir(parents=True, exist_ok=True)
    con = connect()
    src = analytical_src()
    con.execute(f"COPY (SELECT {FACT_SQL} FROM {src}) TO '{(OUT / 'fact_loans.parquet').as_posix()}' (FORMAT PARQUET, COMPRESSION SNAPPY, ROW_GROUP_SIZE 200000)")
    fact = f"'{(OUT / 'fact_loans.parquet').as_posix()}'"
    n, funded, charged = con.execute(f"SELECT COUNT(*), SUM(funded_amnt), SUM(is_charged_off) FROM {fact}").fetchone()
    kpi = json.loads((AGGREGATE_DIR / "portfolio_kpis.json").read_text())
    assert n == kpi["loans"] and funded == kpi["funded"] and charged == kpi["charged_off"], "Fact export does not reconcile"
    log.info("fact_loans rows=%d, %.0f MB", n, (OUT / "fact_loans.parquet").stat().st_size / 1024**2)
    build_dimensions(con, src)
    build_summaries(con, src)
    build_reference_tables(con)
    log.info("Power BI export complete")


if __name__ == "__main__":
    main()
