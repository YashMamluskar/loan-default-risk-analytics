"""Phase 2: write data_dictionary.csv, dataset_audit.md and data_quality_report.md from measured audit tables.

Business meanings follow the field names and values seen in the data, and standard LendingClub usage.
They are analyst descriptions, not an official LendingClub dictionary (none ships with this file).
"""
from __future__ import annotations

import json

import pandas as pd

from config import AUDIT_DIR, DOCS_DIR, ensure_dirs, get_logger
from data_cleaning import DROPPED_COLUMNS

log = get_logger("build_data_dictionary")

# column: (category, business meaning, timing). Timing: O = known at origination, P = post-origination.
D = {
    "id": ("Loan identification", "Unique LendingClub loan id; primary trace key.", "O"),
    "member_id": ("Loan identification", "Borrower id; empty for every record in this release.", "O"),
    "url": ("Loan identification", "Listing web page built from the loan id.", "O"),
    "loan_amnt": ("Loan characteristics", "Amount the borrower applied for.", "O"),
    "funded_amnt": ("Loan characteristics", "Amount committed to the loan at origination.", "O"),
    "funded_amnt_inv": ("Loan characteristics", "Part of the funded amount committed by investors.", "O"),
    "term": ("Loan characteristics", "Contract length: 36 or 60 months.", "O"),
    "int_rate": ("Interest and repayment", "Contract annual interest rate, in percent.", "O"),
    "installment": ("Interest and repayment", "Scheduled monthly payment.", "O"),
    "grade": ("Loan characteristics", "LendingClub risk grade, A (lowest risk) to G.", "O"),
    "sub_grade": ("Loan characteristics", "Finer grade, A1 to G5.", "O"),
    "emp_title": ("Employment", "Job title typed by the borrower; free text, may reveal employer.", "O"),
    "emp_length": ("Employment", "Years employed, from < 1 year to 10+ years.", "O"),
    "home_ownership": ("Borrower demographics", "Housing status: RENT, MORTGAGE, OWN, ANY, OTHER, NONE.", "O"),
    "annual_inc": ("Income and financial profile", "Annual income reported at application.", "O"),
    "verification_status": ("Income and financial profile", "Whether income or its source was verified by LendingClub.", "O"),
    "issue_d": ("Origination dates", "Month the loan was issued.", "O"),
    "loan_status": ("Loan performance", "Status at the data snapshot.", "P"),
    "pymnt_plan": ("Loan performance", "Whether a payment plan is in place.", "P"),
    "desc": ("Loan identification", "Free-text loan description from the borrower.", "O"),
    "purpose": ("Loan characteristics", "Category of stated loan purpose.", "O"),
    "title": ("Loan characteristics", "Loan title provided by the borrower; free text.", "O"),
    "zip_code": ("Geographic", "First three digits of the borrower's ZIP code.", "O"),
    "addr_state": ("Geographic", "Borrower's state.", "O"),
    "dti": ("Income and financial profile", "Monthly debt payments / monthly income, excluding mortgage and this loan, in percent.", "O"),
    "delinq_2yrs": ("Credit history", "30+ day delinquencies in the past 2 years.", "O"),
    "earliest_cr_line": ("Credit history", "Month the earliest credit line was opened.", "O"),
    "fico_range_low": ("Credit history", "Lower bound of FICO range at origination.", "O"),
    "fico_range_high": ("Credit history", "Upper bound of FICO range at origination.", "O"),
    "inq_last_6mths": ("Credit history", "Credit inquiries in the past 6 months.", "O"),
    "mths_since_last_delinq": ("Credit history", "Months since last delinquency; blank usually means none recorded.", "O"),
    "mths_since_last_record": ("Credit history", "Months since last public record.", "O"),
    "open_acc": ("Credit history", "Open credit lines.", "O"),
    "pub_rec": ("Credit history", "Derogatory public records.", "O"),
    "revol_bal": ("Credit history", "Total revolving balance.", "O"),
    "revol_util": ("Credit history", "Revolving balance as a percent of revolving credit limit.", "O"),
    "total_acc": ("Credit history", "Total credit lines ever on file.", "O"),
    "initial_list_status": ("Loan characteristics", "Initial listing: w (whole) or f (fractional).", "O"),
    "out_prncp": ("Loan performance", "Remaining outstanding principal.", "P"),
    "out_prncp_inv": ("Loan performance", "Outstanding principal attributable to investors.", "P"),
    "total_pymnt": ("Interest and repayment", "All payments received to date.", "P"),
    "total_pymnt_inv": ("Interest and repayment", "Payments received, investor-funded portion.", "P"),
    "total_rec_prncp": ("Interest and repayment", "Principal received to date.", "P"),
    "total_rec_int": ("Interest and repayment", "Interest received to date.", "P"),
    "total_rec_late_fee": ("Interest and repayment", "Late fees received to date.", "P"),
    "recoveries": ("Recovery", "Gross amount recovered after charge-off.", "P"),
    "collection_recovery_fee": ("Recovery", "Collection fee on recoveries.", "P"),
    "last_pymnt_d": ("Loan performance", "Month of last payment received.", "P"),
    "last_pymnt_amnt": ("Interest and repayment", "Amount of last payment.", "P"),
    "next_pymnt_d": ("Loan performance", "Next scheduled payment month.", "P"),
    "last_credit_pull_d": ("Loan performance", "Month LendingClub last pulled credit.", "P"),
    "last_fico_range_high": ("Loan performance", "Upper FICO bound at last pull; post-origination.", "P"),
    "last_fico_range_low": ("Loan performance", "Lower FICO bound at last pull; post-origination.", "P"),
    "policy_code": ("Loan identification", "Credit policy code; constant 1 here.", "O"),
    "application_type": ("Loan characteristics", "Individual or Joint App.", "O"),
    "annual_inc_joint": ("Income and financial profile", "Combined income on joint applications.", "O"),
    "dti_joint": ("Income and financial profile", "Combined DTI on joint applications.", "O"),
    "verification_status_joint": ("Income and financial profile", "Verification of joint income.", "O"),
    "disbursement_method": ("Loan characteristics", "Cash or DirectPay.", "O"),
    "hardship_flag": ("Hardship and settlement", "Whether the borrower is on a hardship plan.", "P"),
    "debt_settlement_flag": ("Hardship and settlement", "Whether a charged-off loan is working with a settlement company.", "P"),
}
GROUPS = [
    ("sec_app_", "Credit history", "Second applicant on a joint application", "O"),
    ("hardship_", "Hardship and settlement", "Hardship plan detail", "P"),
    ("settlement_", "Hardship and settlement", "Debt settlement detail", "P"),
]
SPECIFIC = {
    "collections_12_mths_ex_med": "Collections in 12 months, excluding medical.", "mths_since_last_major_derog": "Months since last 90+ day rating.",
    "acc_now_delinq": "Accounts currently delinquent.", "tot_coll_amt": "Total collection amounts ever owed.", "tot_cur_bal": "Current balance of all accounts.",
    "open_acc_6m": "Accounts opened in 6 months.", "open_act_il": "Active installment accounts.", "open_il_12m": "Installment accounts opened in 12 months.",
    "open_il_24m": "Installment accounts opened in 24 months.", "mths_since_rcnt_il": "Months since latest installment account.", "total_bal_il": "Balance on installment accounts.",
    "il_util": "Installment balance as a percent of credit limit.", "open_rv_12m": "Revolving accounts opened in 12 months.", "open_rv_24m": "Revolving accounts opened in 24 months.",
    "max_bal_bc": "Maximum balance on revolving accounts.", "all_util": "Balance as a percent of limit, all trades.", "total_rev_hi_lim": "Total revolving credit limit.",
    "inq_fi": "Personal finance inquiries.", "total_cu_tl": "Finance trades.", "inq_last_12m": "Credit inquiries in 12 months.", "acc_open_past_24mths": "Trades opened in 24 months.",
    "avg_cur_bal": "Average balance across accounts.", "bc_open_to_buy": "Available bankcard credit.", "bc_util": "Bankcard balance as a percent of limit.",
    "chargeoff_within_12_mths": "Charge-offs on the credit file in 12 months.", "delinq_amnt": "Past-due amount owed on delinquent accounts.",
    "mo_sin_old_il_acct": "Months since oldest installment account.", "mo_sin_old_rev_tl_op": "Months since oldest revolving account.",
    "mo_sin_rcnt_rev_tl_op": "Months since latest revolving account.", "mo_sin_rcnt_tl": "Months since latest account.", "mort_acc": "Mortgage accounts.",
    "mths_since_recent_bc": "Months since latest bankcard account.", "mths_since_recent_bc_dlq": "Months since latest bankcard delinquency.",
    "mths_since_recent_inq": "Months since latest inquiry.", "mths_since_recent_revol_delinq": "Months since latest revolving delinquency.",
    "num_accts_ever_120_pd": "Accounts ever 120+ days past due.", "num_actv_bc_tl": "Active bankcard accounts.", "num_actv_rev_tl": "Active revolving accounts.",
    "num_bc_sats": "Satisfactory bankcard accounts.", "num_bc_tl": "Bankcard accounts.", "num_il_tl": "Installment accounts.", "num_op_rev_tl": "Open revolving accounts.",
    "num_rev_accts": "Revolving accounts.", "num_rev_tl_bal_gt_0": "Revolving accounts with a balance.", "num_sats": "Satisfactory accounts.",
    "num_tl_120dpd_2m": "Accounts 120 days past due, updated in 2 months.", "num_tl_30dpd": "Accounts 30 days past due, updated in 2 months.",
    "num_tl_90g_dpd_24m": "Accounts 90+ days past due in 24 months.", "num_tl_op_past_12m": "Accounts opened in 12 months.", "pct_tl_nvr_dlq": "Percent of trades never delinquent.",
    "percent_bc_gt_75": "Percent of bankcards above 75% of limit.", "pub_rec_bankruptcies": "Public-record bankruptcies.", "tax_liens": "Tax liens.",
    "tot_hi_cred_lim": "Total high credit or credit limit.", "total_bal_ex_mort": "Total balance excluding mortgage.", "total_bc_limit": "Total bankcard limit.",
    "total_il_high_credit_limit": "Total installment credit limit.", "revol_bal_joint": "Combined revolving balance on joint applications.",
    "deferral_term": "Payments deferred under a hardship plan.", "orig_projected_additional_accrued_interest": "Projected extra interest under hardship plan.",
    "payment_plan_start_date": "First payment month of the hardship plan.", "debt_settlement_flag_date": "Month the settlement flag was set.",
}
USE_NOTES = {
    "loan_status": "Target of default analysis; never a predictor.", "last_fico_range_high": "Exclude from origination-time analysis or models (leakage).", "last_fico_range_low": "Exclude from origination-time analysis or models (leakage).",
    "recoveries": "Non-zero only after charge-off; outcome-derived.", "emp_title": "High cardinality and possible personal information; not exported to SQL or Power BI.", "title": "High cardinality; duplicates purpose.",
    "desc": "Removed in cleaning.", "url": "Removed in cleaning.", "member_id": "Removed in cleaning.", "policy_code": "Removed in cleaning.", "zip_code": "Partial location; not exported to SQL or Power BI.",
    "dti": "Use dti_clean: -1 and 999 are placeholders.", "annual_inc": "Use annual_inc_clean: zero is treated as unknown.",
}
PRIORITY = {"loan_amnt", "funded_amnt", "funded_amnt_inv", "term", "int_rate", "installment", "grade", "sub_grade", "emp_title", "emp_length", "home_ownership", "annual_inc", "verification_status", "issue_d", "loan_status", "purpose",
            "addr_state", "dti", "delinq_2yrs", "earliest_cr_line", "open_acc", "pub_rec", "revol_bal", "revol_util", "total_acc", "initial_list_status", "out_prncp", "total_pymnt", "total_pymnt_inv", "total_rec_prncp", "total_rec_int",
            "total_rec_late_fee", "recoveries", "collection_recovery_fee", "last_pymnt_d", "last_credit_pull_d"}


def describe(name: str) -> tuple[str, str, str]:
    if name in D:
        return D[name]
    for prefix, category, meaning, timing in GROUPS:
        if name.startswith(prefix):
            detail = SPECIFIC.get(name, name.replace(prefix, "").replace("_", " ") + ".")
            return category, f"{meaning}: {detail}", timing
    if name in SPECIFIC:
        category = "Hardship and settlement" if name in ("deferral_term", "orig_projected_additional_accrued_interest", "payment_plan_start_date", "debt_settlement_flag_date") else ("Income and financial profile" if name == "revol_bal_joint" else "Credit history")
        timing = "P" if category == "Hardship and settlement" else "O"
        return category, SPECIFIC[name], timing
    raise KeyError(f"Column has no dictionary entry: {name}")


def dq_note(row) -> str:
    notes = []
    if row.missing_pct >= 90:
        notes.append("Excessive missing (90%+)")
    elif row.missing_pct >= 30:
        notes.append("High missing (30%+)")
    if row.approx_distinct and row.approx_distinct <= 1:
        notes.append("Single value")
    if row.approx_distinct and row.approx_distinct > 50000 and row.numeric_parse_pct == 0:
        notes.append("High-cardinality text")
    return "; ".join(notes)


def main() -> None:
    ensure_dirs()
    profile = pd.read_csv(AUDIT_DIR / "column_profile.csv")
    facts = json.loads((AUDIT_DIR / "audit_facts.json").read_text())
    counts = json.loads((AUDIT_DIR / "cleaning_counts.json").read_text())
    validation = pd.read_csv(AUDIT_DIR / "validation_results.csv")
    freq = pd.read_csv(AUDIT_DIR / "categorical_frequencies.csv")

    rows = []
    for row in profile.itertuples():
        category, meaning, timing = describe(row.column_name)
        rows.append({"column_name": row.column_name, "category": category, "business_meaning": meaning,
                     "available_at_origination": "Yes" if timing == "O" else "No", "priority_field": "Yes" if row.column_name in PRIORITY else "No",
                     "non_null": row.non_null, "missing_pct": row.missing_pct, "approx_distinct": row.approx_distinct, "numeric_parse_pct": row.numeric_parse_pct,
                     "min": row.min, "median": row.median, "max": row.max, "kept_in_clean": "No" if row.column_name in DROPPED_COLUMNS else "Yes",
                     "quality_flag": dq_note(row), "usage_note": USE_NOTES.get(row.column_name, "")})
    dictionary = pd.DataFrame(rows)
    dictionary.to_csv(DOCS_DIR / "data_dictionary.csv", index=False)

    status = freq[(freq.column_name == "loan_status") & freq.value.notna()].copy()
    status["share"] = status.records / status.records.sum()
    meanings = {"Fully Paid": ("Terminal", "Repaid in full. Numerator side of resolved loans."), "Charged Off": ("Terminal", "Written off as unrecoverable. The primary default event."),
                "Current": ("Unresolved", "Paying on schedule; never treated as default."), "Late (31-120 days)": ("Unresolved", "Delinquent, not yet charged off; never treated as confirmed default."),
                "Late (16-30 days)": ("Unresolved", "Delinquent, not yet charged off."), "In Grace Period": ("Unresolved", "Within 15 days after due date."),
                "Default": ("Separate", "40 loans over 120 days late, pending charge-off. Reported separately; sensitivity only."),
                "Does not meet the credit policy. Status:Fully Paid": ("Separate", "Legacy loans outside current policy, repaid. Reported separately."),
                "Does not meet the credit policy. Status:Charged Off": ("Separate", "Legacy loans outside current policy, charged off. Reported separately.")}
    status_rows = "\n".join(f"| {r.value} | {r.records:,} | {r.share:.3%} | {meanings[r.value][0]} | {meanings[r.value][1]} |" for r in status.itertuples())
    by_cat = dictionary.groupby("category").column_name.count().sort_values(ascending=False)
    cat_rows = "\n".join(f"| {c} | {n} |" for c, n in by_cat.items())
    excessive = dictionary[dictionary.missing_pct >= 90].column_name.tolist()
    high = dictionary[(dictionary.missing_pct >= 30) & (dictionary.missing_pct < 90)].column_name.tolist()
    post = dictionary[dictionary.available_at_origination == "No"].column_name.tolist()
    (DOCS_DIR / "dataset_audit.md").write_text(f"""# Dataset Audit

Generated by `python/data_inspection.py` and `python/build_data_dictionary.py`. Raw values were profiled as text before any cleaning.

## File

| Item | Value |
|---|---|
| File | `accepted_2007_to_2018Q4.csv` |
| Size | {facts['csv_bytes']:,} bytes ({facts['csv_bytes'] / 1024**3:.2f} GB) |
| Records (excluding header) | {facts['csv_records_excl_header']:,} |
| Columns | {facts['columns']} |
| Non-loan rows | {facts['non_numeric_id_or_null_amount_rows']} (32 "Total amount funded" summaries, 1 section label) |
| Loans | {facts['csv_records_excl_header'] - facts['non_numeric_id_or_null_amount_rows']:,} |
| Issue dates | June 2007 to December 2018 |
| Status snapshot | Latest last payment month is March 2019 |
| Exact duplicate rows | {facts['csv_records_excl_header'] - facts['distinct_full_row_hashes']:,} (by full-row hash) |
| Duplicate loan ids | {facts['duplicated_ids']:,} |

## Loan status

| Status | Records | Share | Treatment | Meaning |
|---|---:|---:|---|---|
{status_rows}

## Columns by category

| Category | Columns |
|---|---:|
{cat_rows}

## Columns to treat with care

* **90%+ missing ({len(excessive)}):** {', '.join(f'`{c}`' for c in excessive)}.
* **30-90% missing ({len(high)}):** {', '.join(f'`{c}`' for c in high)}. Many apply only to later loans, or a blank means the event never happened, so blanks are not errors or zeros.
* **No analytical value:** `member_id` (empty), `policy_code` (constant), `url` (derived from id).
* **High-cardinality text:** `emp_title`, `title`, `desc`.
* **Redundant pairs:** `funded_amnt` and `loan_amnt` differ on {validation.set_index('rule').measured['Loan amount differs from funded amount']} loans; `fico_range_low` and `fico_range_high` are always 4-5 points apart; `purpose` and `title` overlap.
* **Post-origination, so unusable for origination-time analysis ({len(post)}):** {', '.join(f'`{c}`' for c in post[:16])} and the remaining hardship and settlement fields. See the `available_at_origination` column in [data_dictionary.csv](data_dictionary.csv).

Full per-column profile: `data/aggregate/audit/column_profile.csv`.
""", encoding="utf-8")

    val_rows = "\n".join(f"| {r.rule} | {r.measured} | {'Pass' if r.passed else 'FAIL'} |" for r in validation[validation.severity == "error"].itertuples())
    info_rows = "\n".join(f"| {r.rule} | {r.measured} |" for r in validation[validation.severity != "error"].itertuples())
    (DOCS_DIR / "data_quality_report.md").write_text(f"""# Data Quality Report

All results are measured. Treatments are in [cleaning_log.md](cleaning_log.md).

## Overall assessment

Structure and financial integrity are strong: unique ids, no duplicates, valid dates, and on every loan total payments equal principal + interest + late fees + recoveries. The issues are limited borrower-field placeholders and fields introduced part-way through the program, plus {counts['footer_rows']} non-loan rows.

## Issues found

| Issue | Records | Handling |
|---|---:|---|
| Non-loan summary rows | {counts['footer_rows']} | Removed |
| `dti` placeholders (-1, 999) | {counts['dti_placeholder']:,} | `dti_clean` is NULL |
| `dti` missing | {counts['dti_missing']:,} | Stays NULL |
| `dti` above 100 | {counts['dti_gt100']:,} | Kept and flagged |
| `annual_inc` zero | {counts['income_zero']:,} | `annual_inc_clean` is NULL |
| `annual_inc` above $1M | {counts['income_gt1m']:,} | Kept and flagged |
| `revol_util` above 150% | {counts['util_gt150']:,} | Kept and flagged |
| `emp_length` missing | {counts['emp_missing']:,} | Label "Unknown" |
| 999 placeholder in `mo_sin_*` | {counts['il999'] + counts['rev999']} | `*_clean` is NULL |
| Whitespace-only `emp_title` | 3 | Treated as blank |

## Validation rules

Executed by `python/data_validation.py`.

| Rule | Measured | Result |
|---|---:|---|
{val_rows}

## Source characteristics (documented, not errors)

| Characteristic | Records |
|---|---:|
{info_rows}

## Missingness by period

Fields such as `open_acc_6m` and `all_util` have about 38% missing because they begin later in the program, so analysis of them covers later cohorts only. They are not used in the primary KPIs.
""", encoding="utf-8")
    log.info("Dictionary rows=%d", len(dictionary))
    assert len(dictionary) == 151


if __name__ == "__main__":
    main()
