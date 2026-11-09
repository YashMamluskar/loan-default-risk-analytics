"""Phase 7: write the full population as CSV files for sql/02_data_loading.sql.

NULL is written as \\N, which LOAD DATA reads as SQL NULL. No rows are sampled.
"""
from __future__ import annotations

import pandas as pd

from analysis_common import analytical_src
from config import AGGREGATE_DIR, EXPORT_DIR, connect, ensure_dirs, get_logger

log = get_logger("mysql_export")
OUT = EXPORT_DIR / "mysql"

TABLES = {
    "loan_details": """id AS loan_id, issue_d AS issue_date, issue_year, loan_amnt, funded_amnt, ROUND(funded_amnt_inv, 6) AS funded_amnt_inv,
        term_months, int_rate, installment, grade, sub_grade, purpose_label, addr_state, application_type, initial_list_status,
        amount_band, rate_band, risk_segment""",
    "borrower_profiles": """id AS loan_id, emp_length_label, emp_length_years, home_ownership_group, annual_inc, annual_inc_clean, annual_inc_flag,
        verification_status, dti, dti_clean, dti_flag, fico_range_low::INT AS fico_range_low, fico_range_high::INT AS fico_range_high, earliest_cr_line,
        credit_history_years, delinq_2yrs::INT AS delinq_2yrs, inq_last_6mths::INT AS inq_last_6mths, open_acc::INT AS open_acc, pub_rec::INT AS pub_rec,
        revol_bal, revol_util, total_acc::INT AS total_acc, income_band, dti_band, fico_band, credit_history_band, delinq_band, pub_rec_band""",
    "loan_performance": """id AS loan_id, loan_status, status_clean, status_group, is_fully_paid, is_charged_off, is_resolved, is_term_elapsed,
        scheduled_maturity_date, ROUND(out_prncp, 6) AS out_prncp, ROUND(total_pymnt, 6) AS total_pymnt, ROUND(total_pymnt_inv, 6) AS total_pymnt_inv,
        ROUND(total_rec_prncp, 6) AS total_rec_prncp, ROUND(total_rec_int, 6) AS total_rec_int, ROUND(total_rec_late_fee_clean, 6) AS total_rec_late_fee,
        ROUND(recoveries, 6) AS recoveries, ROUND(collection_recovery_fee, 6) AS collection_recovery_fee, last_pymnt_d, last_credit_pull_d,
        debt_settlement_flag, ROUND(unpaid_principal_at_chargeoff, 6) AS unpaid_principal_at_chargeoff, ROUND(net_recoveries, 6) AS net_recoveries,
        ROUND(est_net_principal_loss, 6) AS est_net_principal_loss""",
}


def main() -> None:
    ensure_dirs()
    OUT.mkdir(parents=True, exist_ok=True)
    con = connect()
    src = analytical_src()
    options = r"(HEADER, DELIMITER ',', NULLSTR '\N')"

    for table, cols in TABLES.items():
        target = (OUT / f"{table}.csv").as_posix()
        con.execute(f"COPY (SELECT {cols} FROM {src}) TO '{target}' {options}")
        log.info("%s: %.0f MB", table, (OUT / f"{table}.csv").stat().st_size / 1024**2)

    dates = pd.date_range("2007-01-01", "2019-12-01", freq="MS")
    pd.DataFrame({"date_key": dates.strftime("%Y-%m-%d"), "year_num": dates.year, "quarter_num": dates.quarter, "month_num": dates.month,
                  "month_name": dates.strftime("%b"), "year_month_label": dates.strftime("%Y-%m")}).to_csv(OUT / "date_dimension.csv", index=False, lineterminator="\n")

    seg = pd.read_csv(AGGREGATE_DIR / "risk_segments_grade_term.csv")
    seg = seg[["risk_segment", "grade", "term_months", "mature_resolved", "mature_charged_off", "mature_default_rate", "relative_risk_index", "risk_tier"]].copy()
    seg["mature_resolved"] = seg.mature_resolved.astype(int)
    seg["mature_charged_off"] = seg.mature_charged_off.astype(int)
    seg["mature_default_rate"] = seg.mature_default_rate.round(6)
    seg["relative_risk_index"] = seg.relative_risk_index.round(4)
    seg.to_csv(OUT / "loan_risk_segments.csv", index=False, na_rep="\\N", lineterminator="\n")
    log.info("MySQL export complete")


if __name__ == "__main__":
    main()
