# Methodology

## Population

All 2,260,668 accepted loans issued June 2007 to December 2018. Status and cash reflect the data snapshot: the latest last-payment month is March 2019, and maturity logic uses 2019-03-31.

## Status taxonomy

| `status_clean` | `status_group` | In primary default rate? |
|---|---|---|
| Fully Paid | Resolved | Yes, denominator |
| Charged Off | Resolved | Yes, numerator and denominator |
| Current | Unresolved | No |
| In Grace Period | Unresolved | No |
| Late (16-30 days) | Unresolved | No |
| Late (31-120 days) | Unresolved | No |
| Default | Default Status | No, reported separately (40 loans) |
| Policy Exception - Fully Paid | Policy Exception | No, reported separately |
| Policy Exception - Charged Off | Policy Exception | No, reported separately |

## Default metrics

These are separate metrics with different denominators, and they are never combined.

| Metric | Definition | Use |
|---|---|---|
| Historical Default Rate (primary) | Charged Off loans / (Fully Paid + Charged Off loans) | Headline, by loan count |
| Principal-weighted charge-off rate | Funded $ of Charged Off / funded $ of resolved loans | Dollar-weighted view |
| Charged-off share of originated | Funded $ of Charged Off / all funded $ | Scale only; understates young loans |
| Term-elapsed (mature) rate | Primary definition on loans whose issue date + term is on or before 2019-03-31 | Cohort comparison |
| Alternative rate | (Charged Off + Default + Policy Charged Off) / (those + Fully Paid + Policy Fully Paid) | Sensitivity only |

### Why a maturity view is needed

A 60-month loan issued in 2017 can charge off quickly, but mostly cannot be Fully Paid yet unless it prepays. Resolved loans in young cohorts therefore over-represent failures. Term-elapsed loans remove most of this bias.

A cohort is compared only when at least 99% of its loans have reached scheduled maturity. For 60-month loans that ends at March 2014, so the mature view omits later credit conditions.

## Financial measures

| Measure | Type | Definition |
|---|---|---|
| `funded_amnt`, `funded_amnt_inv` | Reported | Original funded amount, investor portion |
| `total_pymnt` | Reported | Equals principal + interest + late fees + recoveries (validated on every loan) |
| `total_rec_prncp`, `total_rec_int`, `total_rec_late_fee` | Reported | Cash received by type |
| `recoveries`, `collection_recovery_fee` | Reported | Post-charge-off cash, and the fee on it |
| `out_prncp` | Reported | Principal outstanding at the snapshot |
| Charged-off principal exposure (`unpaid_principal_at_chargeoff`) | Calculated | `funded_amnt - total_rec_prncp`, Charged Off loans only |
| `net_recoveries` | Calculated | `recoveries - collection_recovery_fee` |
| Estimated net principal loss | Calculated | Exposure minus net recoveries |
| Recovery ratio | Calculated | Gross recoveries / exposure |

**Assumptions and limits.** Principal lost is not simply loan amount minus recoveries: repayments before charge-off are subtracted first. Recoveries may include amounts other than principal, because the data does not split them. Estimated net loss ignores interest income, funding and servicing costs, tax, discounting, and investor share. It is not an accounting loss.

## Risk segmentation

Each loan's segment is grade x term, both known at origination.

Relative Risk Index (RRI) = segment term-elapsed rate / portfolio term-elapsed rate.

| Tier | Rule |
|---|---|
| Low | RRI under 0.75 |
| Medium | RRI from 0.75 to under 1.25 |
| High | RRI of 1.25 or more |
| Insufficient data | Fewer than 500 term-elapsed resolved loans |

The thresholds were chosen for transparency: within 25% of the portfolio rate counts as typical. They are retrospective portfolio classifications, not approved underwriting rules or individual credit decisions. No protected characteristic is used.

## Statistics

* **Large samples.** With over a million loans, tiny differences reach significance, so readings use effect sizes (Cramer's V, odds ratios, Cohen's d) and Bonferroni across the test family.
* **Confidence intervals.** Wilson score intervals, which behave well in small segments.
* **Confounding.** Cochran-Mantel-Haenszel stratifies by grade, because term and verification are tied to grade.
* **Sampling.** Tests needing ranks or models use a repeatable sample selected by hashing the loan id, with an automated representativeness check. DuckDB's reservoir sampling was tested and rejected: under a parallel scan it drew 82% of rows from 2015.

Correlation and association here are not causation.

## Consistency across tools

Metric logic lives in `python/analysis_common.py`, SQL views in `sql/06_kpi_views.sql`, and DAX in `powerbi/model_definition.py`. Results are reconciled in `data/aggregate/sql_results/kpi_reconciliation_python_mysql.csv` and in the testing report.
