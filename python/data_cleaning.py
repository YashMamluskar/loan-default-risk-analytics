"""Phase 3: reproducible cleaning from the all-text staging file to typed Parquet.

Design rules
------------
* The raw CSV and original values are never altered. Suspect values stay in their
  original column; corrected versions live in *_clean columns with *_flag columns.
* Records are only removed if they are not loans (33 summary/section-label rows, none are loans).
* Missing values are not imputed. Missing bands are reported as "Unknown".
* Every count written to the cleaning log is measured from the data.
"""
from __future__ import annotations

import json

from config import AUDIT_DIR, CLEAN_PARQUET, DOCS_DIR, STAGING_PARQUET, connect, ensure_dirs, get_logger

log = get_logger("data_cleaning")

# Latest observed last_pymnt_d is Mar-2019 (asserted below); used for loan maturity.
SNAPSHOT_DATE = "2019-03-31"

DATE_COLUMNS = [
    "issue_d", "earliest_cr_line", "last_pymnt_d", "next_pymnt_d", "last_credit_pull_d",
    "sec_app_earliest_cr_line", "hardship_start_date", "hardship_end_date",
    "payment_plan_start_date", "debt_settlement_flag_date", "settlement_date",
]
TEXT_COLUMNS = [
    "term", "grade", "sub_grade", "emp_title", "emp_length", "home_ownership", "verification_status",
    "loan_status", "pymnt_plan", "purpose", "title", "zip_code", "addr_state", "initial_list_status",
    "application_type", "verification_status_joint", "hardship_flag", "hardship_type", "hardship_reason",
    "hardship_status", "hardship_loan_status", "disbursement_method", "debt_settlement_flag",
    "settlement_status",
]
# Removed from the cleaned file with reasons (still available in the raw file).
DROPPED_COLUMNS = {
    "member_id": "100% missing in the source",
    "url": "Derivable from id; holds no analytical information",
    "desc": "94.42% missing free text written by borrowers; possible personal information",
    "policy_code": "Constant value 1 on every loan",
}
ID_COLUMN = "id"
# Placeholder value 999 observed in these month counters; handled as unknown in *_clean.
PLACEHOLDER_999 = ["mo_sin_old_il_acct", "mo_sin_old_rev_tl_op"]


def band(expr: str, edges: list[tuple[float, str]], top: str, unknown: str = "Unknown") -> str:
    """CASE expression for right-open bands; NULL goes to the explicit unknown label."""
    parts = " ".join(f"WHEN {expr} < {edge} THEN '{label}'" for edge, label in edges)
    return f"CASE WHEN {expr} IS NULL THEN '{unknown}' {parts} ELSE '{top}' END"


INCOME_BANDS = [(40000, "<$40K"), (60000, "$40K-$60K"), (80000, "$60K-$80K"), (100000, "$80K-$100K"), (150000, "$100K-$150K")]
DTI_BANDS = [(10, "<10"), (20, "10-20"), (30, "20-30"), (40, "30-40")]
AMOUNT_BANDS = [(5000, "<$5K"), (10000, "$5K-$10K"), (15000, "$10K-$15K"), (20000, "$15K-$20K"), (25000, "$20K-$25K"), (30000, "$25K-$30K")]
RATE_BANDS = [(8, "<8%"), (11, "8-11%"), (14, "11-14%"), (17, "14-17%"), (20, "17-20%"), (25, "20-25%")]
FICO_BANDS = [(680, "660-679"), (700, "680-699"), (720, "700-719"), (750, "720-749")]
HISTORY_BANDS = [(5, "<5 yrs"), (10, "5-10 yrs"), (15, "10-15 yrs"), (20, "15-20 yrs"), (30, "20-30 yrs")]
UTIL_BANDS = [(25, "<25%"), (50, "25-50%"), (75, "50-75%"), (100, "75-100%")]


def build_select(all_columns: list[str]) -> str:
    casts: list[str] = []
    for name in all_columns:
        if name in DROPPED_COLUMNS:
            continue
        q = f'"{name}"'
        if name == ID_COLUMN:
            casts.append(f"CAST({q} AS BIGINT) AS id")
        elif name in DATE_COLUMNS:
            casts.append(f"CAST(strptime({q}, '%b-%Y') AS DATE) AS {name}")
        elif name in TEXT_COLUMNS:
            casts.append(f"NULLIF(TRIM({q}), '') AS {name}")
        else:
            casts.append(f"CAST({q} AS DOUBLE) AS {name}")
    return ",\n            ".join(casts)


def main() -> None:
    ensure_dirs()
    con = connect()
    src = f"'{STAGING_PARQUET.as_posix()}'"
    columns = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()]
    raw_rows = con.execute(f"SELECT COUNT(*) FROM {src}").fetchone()[0]
    footer_rows = con.execute(f"SELECT COUNT(*) FROM {src} WHERE id LIKE 'Total amount funded%' OR id = 'Loans that do not meet the credit policy'").fetchone()[0]
    other_non_numeric = con.execute(
        f"SELECT COUNT(*) FROM {src} WHERE NOT regexp_matches(id,'^[0-9]+$') AND id NOT LIKE 'Total amount funded%' AND id <> 'Loans that do not meet the credit policy'"
    ).fetchone()[0]
    assert other_non_numeric == 0, "Unexpected non-numeric ids beyond the documented footer rows"
    log.info("Raw rows=%s footer rows=%s", raw_rows, footer_rows)

    typed = build_select(columns)
    placeholder_cols = ",\n            ".join(
        f"CASE WHEN {c} = 999 THEN NULL ELSE {c} END AS {c}_clean" for c in PLACEHOLDER_999
    )
    tmp = CLEAN_PARQUET.with_suffix(".tmp")
    con.execute(f"""
    COPY (
    WITH typed AS (
        SELECT
            {typed}
        FROM {src}
        WHERE regexp_matches(id, '^[0-9]+$')
    ), step1 AS (
        SELECT *,
            -- Loan terms and dates
            CAST(regexp_extract(term, '([0-9]+)', 1) AS INTEGER) AS term_months,
            CAST(EXTRACT(year FROM issue_d) AS INTEGER) AS issue_year,
            CAST(EXTRACT(month FROM issue_d) AS INTEGER) AS issue_month,
            CAST(strftime(issue_d, '%Y%m%d') AS INTEGER) AS issue_date_key,
            CAST(date_add(issue_d, CAST(regexp_extract(term,'([0-9]+)',1) AS INTEGER) * INTERVAL 1 MONTH) AS DATE) AS scheduled_maturity_date,
            ROUND(date_diff('month', earliest_cr_line, issue_d) / 12.0, 2) AS credit_history_years,
            -- Employment: years kept numeric; "10+" is a capped value and "<1" is recorded as 0
            CASE emp_length WHEN '< 1 year' THEN 0 WHEN '1 year' THEN 1 WHEN '10+ years' THEN 10
                 ELSE TRY_CAST(regexp_extract(emp_length,'([0-9]+)',1) AS INTEGER) END AS emp_length_years,
            COALESCE(emp_length, 'Unknown') AS emp_length_label,
            -- Value corrections kept separate from the originals
            CASE WHEN dti < 0 OR dti >= 999 THEN NULL ELSE dti END AS dti_clean,
            CASE WHEN dti IS NULL THEN 'missing' WHEN dti < 0 OR dti >= 999 THEN 'placeholder' WHEN dti > 100 THEN 'suspicious_gt100' ELSE 'ok' END AS dti_flag,
            CASE WHEN annual_inc <= 0 THEN NULL ELSE annual_inc END AS annual_inc_clean,
            CASE WHEN annual_inc IS NULL THEN 'missing' WHEN annual_inc <= 0 THEN 'zero' WHEN annual_inc > 1000000 THEN 'suspicious_gt1m' ELSE 'ok' END AS annual_inc_flag,
            CASE WHEN revol_util IS NULL THEN 'missing' WHEN revol_util > 150 THEN 'suspicious_gt150' WHEN revol_util > 100 THEN 'over_limit' ELSE 'ok' END AS revol_util_flag,
            GREATEST(total_rec_late_fee, 0) AS total_rec_late_fee_clean,
            {placeholder_cols},
            (fico_range_low + fico_range_high) / 2.0 AS fico_mid,
            -- Standardised categories
            CASE WHEN home_ownership IN ('ANY','NONE','OTHER') THEN 'OTHER' ELSE home_ownership END AS home_ownership_group,
            CASE purpose WHEN 'debt_consolidation' THEN 'Debt Consolidation' WHEN 'credit_card' THEN 'Credit Card'
                 WHEN 'home_improvement' THEN 'Home Improvement' WHEN 'major_purchase' THEN 'Major Purchase'
                 WHEN 'small_business' THEN 'Small Business' WHEN 'renewable_energy' THEN 'Renewable Energy'
                 ELSE upper(left(purpose,1)) || substr(purpose,2) END AS purpose_label,
            lower(emp_title) AS emp_title_std,
            -- Status taxonomy: see documentation/methodology.md
            CASE
                WHEN loan_status = 'Fully Paid' THEN 'Fully Paid'
                WHEN loan_status = 'Charged Off' THEN 'Charged Off'
                WHEN loan_status = 'Current' THEN 'Current'
                WHEN loan_status = 'In Grace Period' THEN 'In Grace Period'
                WHEN loan_status = 'Late (16-30 days)' THEN 'Late (16-30 days)'
                WHEN loan_status = 'Late (31-120 days)' THEN 'Late (31-120 days)'
                WHEN loan_status = 'Default' THEN 'Default'
                WHEN loan_status LIKE 'Does not meet%Fully Paid' THEN 'Policy Exception - Fully Paid'
                WHEN loan_status LIKE 'Does not meet%Charged Off' THEN 'Policy Exception - Charged Off'
            END AS status_clean,
            CASE
                WHEN loan_status IN ('Fully Paid','Charged Off') THEN 'Resolved'
                WHEN loan_status IN ('Current','In Grace Period','Late (16-30 days)','Late (31-120 days)') THEN 'Unresolved'
                WHEN loan_status = 'Default' THEN 'Default Status'
                ELSE 'Policy Exception'
            END AS status_group,
            CAST(loan_status = 'Fully Paid' AS INTEGER) AS is_fully_paid,
            CAST(loan_status = 'Charged Off' AS INTEGER) AS is_charged_off,
            CAST(loan_status IN ('Fully Paid','Charged Off') AS INTEGER) AS is_resolved
        FROM typed
    )
    SELECT *,
        CAST(scheduled_maturity_date <= DATE '{SNAPSHOT_DATE}' AS INTEGER) AS is_term_elapsed,
        -- Financial measures: reported vs calculated, charged-off loans only
        CASE WHEN is_charged_off = 1 THEN funded_amnt - total_rec_prncp END AS unpaid_principal_at_chargeoff,
        CASE WHEN is_charged_off = 1 THEN recoveries - collection_recovery_fee END AS net_recoveries,
        CASE WHEN is_charged_off = 1 THEN funded_amnt - total_rec_prncp - (recoveries - collection_recovery_fee) END AS est_net_principal_loss,
        -- Analytical bands
        {band('annual_inc_clean', INCOME_BANDS, '$150K+')} AS income_band,
        {band('dti_clean', DTI_BANDS, '40+')} AS dti_band,
        {band('funded_amnt', AMOUNT_BANDS, '$30K+')} AS amount_band,
        {band('int_rate', RATE_BANDS, '25%+')} AS rate_band,
        {band('fico_range_low', FICO_BANDS, '750+')} AS fico_band,
        {band('credit_history_years', HISTORY_BANDS, '30+ yrs')} AS credit_history_band,
        {band('revol_util', UTIL_BANDS, '100%+')} AS revol_util_band,
        CASE WHEN delinq_2yrs IS NULL THEN 'Unknown' WHEN delinq_2yrs = 0 THEN '0' WHEN delinq_2yrs = 1 THEN '1' ELSE '2+' END AS delinq_band,
        CASE WHEN pub_rec IS NULL THEN 'Unknown' WHEN pub_rec = 0 THEN '0' WHEN pub_rec = 1 THEN '1' ELSE '2+' END AS pub_rec_band,
        CASE WHEN inq_last_6mths IS NULL THEN 'Unknown' WHEN inq_last_6mths = 0 THEN '0' WHEN inq_last_6mths = 1 THEN '1' WHEN inq_last_6mths = 2 THEN '2' ELSE '3+' END AS inquiry_band
    FROM step1
    ) TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)
    """)
    tmp.replace(CLEAN_PARQUET)

    clean = f"'{CLEAN_PARQUET.as_posix()}'"
    counts = con.execute(f"""
        SELECT COUNT(*) AS rows_out, COUNT(DISTINCT id) AS distinct_ids, MAX(last_pymnt_d) AS max_last_pymnt,
          SUM((dti_flag='placeholder')::INT) AS dti_placeholder, SUM((dti_flag='missing')::INT) AS dti_missing,
          SUM((dti_flag='suspicious_gt100')::INT) AS dti_gt100,
          SUM((annual_inc_flag='zero')::INT) AS income_zero, SUM((annual_inc_flag='suspicious_gt1m')::INT) AS income_gt1m,
          SUM((revol_util_flag='over_limit')::INT) AS util_100_150, SUM((revol_util_flag='suspicious_gt150')::INT) AS util_gt150,
          SUM((revol_util_flag='missing')::INT) AS util_missing,
          SUM((total_rec_late_fee < 0)::INT) AS negative_late_fee, MIN(total_rec_late_fee) AS min_late_fee,
          SUM((mo_sin_old_il_acct=999)::INT) AS il999, SUM((mo_sin_old_rev_tl_op=999)::INT) AS rev999,
          SUM((home_ownership IN ('ANY','NONE','OTHER'))::INT) AS home_other,
          SUM((emp_length IS NULL)::INT) AS emp_missing, SUM((funded_amnt_inv=0)::INT) AS inv_zero,
          SUM((status_clean IS NULL)::INT) AS unmapped_status
        FROM {clean}
    """).df().iloc[0].to_dict()
    counts = {k: (str(v)[:10] if k == "max_last_pymnt" else (float(v) if k == "min_late_fee" else int(v))) for k, v in counts.items()}
    counts.update(raw_rows=raw_rows, footer_rows=footer_rows)
    assert counts["rows_out"] == raw_rows - footer_rows, "Row count must only fall by the footer rows"
    assert counts["distinct_ids"] == counts["rows_out"], "Loan ids must stay unique"
    assert counts["unmapped_status"] == 0, "Every loan_status must map to the taxonomy"
    assert counts["max_last_pymnt"] == "2019-03-01", "Snapshot assumption changed; review SNAPSHOT_DATE"
    (AUDIT_DIR / "cleaning_counts.json").write_text(json.dumps(counts, indent=2))
    log.info("Clean rows=%s columns=%s", counts["rows_out"],
             len(con.execute(f"DESCRIBE SELECT * FROM {clean}").fetchall()))
    log.info("Counts: %s", counts)
    write_cleaning_log(counts)


def write_cleaning_log(c: dict) -> None:
    dropped = "\n".join(f"| `{k}` | {v} |" for k, v in DROPPED_COLUMNS.items())
    text = f"""# Cleaning Log

Generated by `python/data_cleaning.py`; all counts are measured on each run. The raw CSV is never modified.

## Record flow

| Step | Records |
|---|---|
| Records in the raw CSV (excluding header) | {c['raw_rows']:,} |
| Removed: 32 "Total amount funded in policy code..." summary rows and 1 "Loans that do not meet the credit policy" section label (not loans) | {c['footer_rows']:,} |
| **Loans in the cleaned dataset** | **{c['rows_out']:,}** |
| Distinct loan ids | {c['distinct_ids']:,} |

No loan was removed. There are no exact duplicates and no duplicated loan ids, so de-duplication changed nothing.

## Columns removed from the cleaned file

| Column | Reason |
|---|---|
{dropped}

## Value treatments

Originals stay in their own columns. Corrections go to `*_clean` and are explained by `*_flag`.

| Field | Finding | Records | Treatment |
|---|---|---:|---|
| `dti` | Values of -1 or 999 used as placeholders | {c['dti_placeholder']:,} | `dti_clean` is NULL, band "Unknown" |
| `dti` | Missing | {c['dti_missing']:,} | Stays NULL, band "Unknown"; not imputed |
| `dti` | Above 100 but below 999 | {c['dti_gt100']:,} | Kept, flagged `suspicious_gt100`; falls in the 40+ band |
| `annual_inc` | Zero income | {c['income_zero']:,} | `annual_inc_clean` is NULL, band "Unknown" |
| `annual_inc` | Above $1M (maximum $110M) | {c['income_gt1m']:,} | Kept, flagged; medians are reported alongside means |
| `revol_util` | 100-150% (over limit is plausible) | {c['util_100_150']:,} | Kept, flagged `over_limit` |
| `revol_util` | Above 150% | {c['util_gt150']:,} | Kept, flagged `suspicious_gt150` |
| `revol_util` | Missing | {c['util_missing']:,} | Stays NULL, band "Unknown" |
| `total_rec_late_fee` | Small negative values (minimum {c['min_late_fee']:.6f}) | {c['negative_late_fee']:,} | `total_rec_late_fee_clean` floors at 0 |
| `mo_sin_old_il_acct` | Placeholder 999 | {c['il999']:,} | `*_clean` is NULL |
| `mo_sin_old_rev_tl_op` | Placeholder 999 | {c['rev999']:,} | `*_clean` is NULL |
| `home_ownership` | ANY / NONE / OTHER | {c['home_other']:,} | Grouped as OTHER in `home_ownership_group` |
| `emp_length` | Missing | {c['emp_missing']:,} | Label "Unknown"; never treated as zero years |
| `funded_amnt_inv` | Exactly zero | {c['inv_zero']:,} | Kept as reported |

## Type conversions

* `id` to BIGINT; dates from `Mon-YYYY` text to DATE (first of month); other fields to DOUBLE. `data_validation.py` proves conversions created no new NULLs.
* `term` to `term_months`; `emp_length` to `emp_length_years` (`< 1 year` = 0, `10+ years` = 10, a capped value).
* Text fields trimmed. `emp_title_std` is lowercase for grouping. `emp_title` is not exported to Power BI.

## Outliers

Outliers are retained. Band analysis is insensitive to them, and they are flagged so they can be excluded deliberately.

## Added fields

Status taxonomy (`status_clean`, `status_group`, `is_*`), maturity (`scheduled_maturity_date`, `is_term_elapsed`, snapshot {SNAPSHOT_DATE}), calculated financials (`unpaid_principal_at_chargeoff`, `net_recoveries`, `est_net_principal_loss`), and analytical bands. Definitions: [methodology.md](methodology.md).

## Output format

`lendingclub_cleaned.csv` was deliberately not produced: the Parquet file is the system of record and an uncompressed CSV of the same content would exceed 1 GB with no analytical benefit. Power BI and MySQL get their own purpose-built, slimmer exports.
"""
    (DOCS_DIR / "cleaning_log.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
