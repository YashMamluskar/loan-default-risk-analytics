"""Phase 3: independent validation of the cleaned dataset.

Each check is a named rule with a measured result. The script writes
data/aggregate/audit/validation_results.csv and exits non-zero on any failed rule.
"Warning" rules describe source-data characteristics that are documented, not errors.
"""
from __future__ import annotations

import sys

import pandas as pd

from config import AUDIT_DIR, CLEAN_PARQUET, STAGING_PARQUET, connect, ensure_dirs, get_logger
from data_cleaning import DROPPED_COLUMNS

log = get_logger("data_validation")
results: list[dict] = []


def record(rule: str, measured, passed: bool, severity: str = "error") -> None:
    results.append({"rule": rule, "measured": measured, "passed": bool(passed), "severity": severity})
    log.info("%-4s %-70s %s", "OK" if passed else severity.upper()[:4], rule, measured)


def main() -> int:
    ensure_dirs()
    con = connect()
    raw = f"'{STAGING_PARQUET.as_posix()}'"
    clean = f"'{CLEAN_PARQUET.as_posix()}'"
    one = lambda sql: con.execute(sql).fetchone()[0]

    raw_rows = one(f"SELECT COUNT(*) FROM {raw}")
    record("Staging rows == 2,260,701 documented source records", raw_rows, raw_rows == 2260701)

    rows = one(f"SELECT COUNT(*) FROM {clean}")
    record("Clean rows == raw rows - 33 footers", rows, rows == raw_rows - 33)
    record("Loan id unique", one(f"SELECT COUNT(DISTINCT id) FROM {clean}"), one(f"SELECT COUNT(DISTINCT id) FROM {clean}") == rows)
    record("Loan id never null", one(f"SELECT COUNT(*) FROM {clean} WHERE id IS NULL"), one(f"SELECT COUNT(*) FROM {clean} WHERE id IS NULL") == 0)

    # Conversions must not lose any value: non-null count per column identical before/after.
    raw_cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {raw}").fetchall()]
    keep = [c for c in raw_cols if c not in DROPPED_COLUMNS]
    # Whitespace-only text is intentionally blank, so raw counts are compared after trimming.
    raw_nn = con.execute("SELECT " + ",".join(f"COUNT(NULLIF(TRIM(\"{c}\"), ''))" for c in keep) + f" FROM {raw} WHERE regexp_matches(id,'^[0-9]+$')").fetchone()
    clean_nn = con.execute("SELECT " + ",".join(f'COUNT("{c}")' for c in keep) + f" FROM {clean}").fetchone()
    lost = [c for c, a, b in zip(keep, raw_nn, clean_nn) if a != b]
    record("No value lost in type conversion (non-null counts equal, all columns)", len(lost), not lost)

    # Financial totals must survive cleaning exactly.
    for col in ("loan_amnt", "funded_amnt", "total_pymnt", "total_rec_prncp", "recoveries"):
        a = one(f"SELECT SUM(TRY_CAST({col} AS DOUBLE)) FROM {raw}")
        b = one(f"SELECT SUM({col}) FROM {clean}")
        record(f"SUM({col}) unchanged by cleaning", round(b, 2), abs(a - b) < 0.01)

    # Status taxonomy
    status = con.execute(f"SELECT loan_status, COUNT(*) FROM {raw} WHERE regexp_matches(id,'^[0-9]+$') GROUP BY 1").df()
    status2 = con.execute(f"SELECT loan_status, COUNT(*) FROM {clean} GROUP BY 1").df()
    record("loan_status distribution unchanged", len(status), status.sort_values("loan_status").values.tolist() == status2.sort_values("loan_status").values.tolist())
    fp, co, res = con.execute(f"SELECT SUM(is_fully_paid), SUM(is_charged_off), SUM(is_resolved) FROM {clean}").fetchone()
    record("Resolved == Fully Paid + Charged Off", res, res == fp + co)
    rate = co / res
    record("Primary default rate is Charged Off / Resolved", round(rate, 6), 0 < rate < 1)
    record("Current loans never counted as charged off", one(f"SELECT COUNT(*) FROM {clean} WHERE loan_status='Current' AND is_charged_off=1"), one(f"SELECT COUNT(*) FROM {clean} WHERE loan_status='Current' AND is_charged_off=1") == 0)
    record("Late loans never counted as resolved", one(f"SELECT COUNT(*) FROM {clean} WHERE loan_status LIKE 'Late%' AND is_resolved=1"), one(f"SELECT COUNT(*) FROM {clean} WHERE loan_status LIKE 'Late%' AND is_resolved=1") == 0)

    # Business rules on reported cash
    rules = {
        "Funded amount within $500-$40,000": "funded_amnt < 500 OR funded_amnt > 40000",
        "Investor funding never exceeds funded amount": "funded_amnt_inv > funded_amnt + 1",
        "Principal received never exceeds funded amount": "total_rec_prncp > funded_amnt + 1",
        "Cash identity: principal+interest+late fees+recoveries == total payments": "ABS(total_rec_prncp + total_rec_int + total_rec_late_fee + recoveries - total_pymnt) > 1",
        "Recovery fees never exceed recoveries": "collection_recovery_fee > recoveries + 1",
        "Recoveries only on charged-off/policy charged-off loans": "recoveries > 0 AND status_clean NOT IN ('Charged Off','Policy Exception - Charged Off')",
        "Fully Paid has no outstanding principal": "loan_status='Fully Paid' AND out_prncp > 0.01",
        "Charged Off has no outstanding principal": "loan_status='Charged Off' AND out_prncp > 0.01",
        "Issue date within 2007-2018": "issue_year NOT BETWEEN 2007 AND 2018",
        "Credit line opened on or before issue": "earliest_cr_line > issue_d",
        "Interest rate within 0-40%": "int_rate <= 0 OR int_rate > 40",
        "dti_clean within 0-999": "dti_clean < 0 OR dti_clean >= 999",
        "annual_inc_clean is positive": "annual_inc_clean <= 0",
        "term_months is 36 or 60": "term_months NOT IN (36,60)",
        "Grade A-G": "grade NOT IN ('A','B','C','D','E','F','G')",
        "Subgrade starts with grade": "left(sub_grade,1) <> grade",
    }
    for rule, bad in rules.items():
        n = one(f"SELECT COUNT(*) FROM {clean} WHERE {bad}")
        record(rule, n, n == 0)

    # Source characteristics that are documented rather than failed.
    warnings = {
        "Fully Paid with principal shortfall above $1": "loan_status='Fully Paid' AND total_rec_prncp < funded_amnt - 1",
        "Fully Paid flagged as debt settlement": "loan_status='Fully Paid' AND debt_settlement_flag='Y'",
        "Charged Off with zero recoveries": "loan_status='Charged Off' AND recoveries = 0",
        "Charged Off where net recoveries exceed unpaid principal": "est_net_principal_loss < 0",
        "Loan amount differs from funded amount": "loan_amnt <> funded_amnt",
        "Zero total payments": "total_pymnt = 0",
    }
    for rule, cond in warnings.items():
        n = one(f"SELECT COUNT(*) FROM {clean} WHERE {cond}")
        record(rule, n, True, severity="info")

    frame = pd.DataFrame(results)
    frame.to_csv(AUDIT_DIR / "validation_results.csv", index=False)
    failed = frame[(~frame.passed) & (frame.severity == "error")]
    log.info("Rules=%d failed=%d", len(frame), len(failed))
    return 1 if len(failed) else 0


if __name__ == "__main__":
    sys.exit(main())
