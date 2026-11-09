# Data Quality Report

All results are measured. Treatments are in [cleaning_log.md](cleaning_log.md).

## Overall assessment

Structure and financial integrity are strong: unique ids, no duplicates, valid dates, and on every loan total payments equal principal + interest + late fees + recoveries. The issues are limited borrower-field placeholders and fields introduced part-way through the program, plus 33 non-loan rows.

## Issues found

| Issue | Records | Handling |
|---|---:|---|
| Non-loan summary rows | 33 | Removed |
| `dti` placeholders (-1, 999) | 137 | `dti_clean` is NULL |
| `dti` missing | 1,711 | Stays NULL |
| `dti` above 100 | 2,426 | Kept and flagged |
| `annual_inc` zero | 1,667 | `annual_inc_clean` is NULL |
| `annual_inc` above $1M | 583 | Kept and flagged |
| `revol_util` above 150% | 28 | Kept and flagged |
| `emp_length` missing | 146,907 | Label "Unknown" |
| 999 placeholder in `mo_sin_*` | 3 | `*_clean` is NULL |
| Whitespace-only `emp_title` | 3 | Treated as blank |

## Validation rules

Executed by `python/data_validation.py`.

| Rule | Measured | Result |
|---|---:|---|
| Staging rows == 2,260,701 documented source records | 2260701.0 | Pass |
| Clean rows == raw rows - 33 footers | 2260668.0 | Pass |
| Loan id unique | 2260668.0 | Pass |
| Loan id never null | 0.0 | Pass |
| No value lost in type conversion (non-null counts equal, all columns) | 0.0 | Pass |
| SUM(loan_amnt) unchanged by cleaning | 34016115925.0 | Pass |
| SUM(funded_amnt) unchanged by cleaning | 34004208600.0 | Pass |
| SUM(total_pymnt) unchanged by cleaning | 27314649582.62 | Pass |
| SUM(total_rec_prncp) unchanged by cleaning | 21489393643.58 | Pass |
| SUM(recoveries) unchanged by cleaning | 325262956.86 | Pass |
| loan_status distribution unchanged | 9.0 | Pass |
| Resolved == Fully Paid + Charged Off | 1345310.0 | Pass |
| Primary default rate is Charged Off / Resolved | 0.199626 | Pass |
| Current loans never counted as charged off | 0.0 | Pass |
| Late loans never counted as resolved | 0.0 | Pass |
| Funded amount within $500-$40,000 | 0.0 | Pass |
| Investor funding never exceeds funded amount | 0.0 | Pass |
| Principal received never exceeds funded amount | 0.0 | Pass |
| Cash identity: principal+interest+late fees+recoveries == total payments | 0.0 | Pass |
| Recovery fees never exceed recoveries | 0.0 | Pass |
| Recoveries only on charged-off/policy charged-off loans | 0.0 | Pass |
| Fully Paid has no outstanding principal | 0.0 | Pass |
| Charged Off has no outstanding principal | 0.0 | Pass |
| Issue date within 2007-2018 | 0.0 | Pass |
| Credit line opened on or before issue | 0.0 | Pass |
| Interest rate within 0-40% | 0.0 | Pass |
| dti_clean within 0-999 | 0.0 | Pass |
| annual_inc_clean is positive | 0.0 | Pass |
| term_months is 36 or 60 | 0.0 | Pass |
| Grade A-G | 0.0 | Pass |
| Subgrade starts with grade | 0.0 | Pass |

## Source characteristics (documented, not errors)

| Characteristic | Records |
|---|---:|
| Fully Paid with principal shortfall above $1 | 4.0 |
| Fully Paid flagged as debt settlement | 5.0 |
| Charged Off with zero recoveries | 83875.0 |
| Charged Off where net recoveries exceed unpaid principal | 86.0 |
| Loan amount differs from funded amount | 2065.0 |
| Zero total payments | 949.0 |

## Missingness by period

Fields such as `open_acc_6m` and `all_util` have about 38% missing because they begin later in the program, so analysis of them covers later cohorts only. They are not used in the primary KPIs.
