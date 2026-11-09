# SQL Documentation

MySQL 8.0 database `loan_default_analytics`. All 2,260,668 loans are loaded with no sampling or truncation.

## Schema

| Table | Grain | Role |
|---|---|---|
| `loan_details` | Loan | Contract terms at origination; parent of the loan tables |
| `borrower_profiles` | Loan | Borrower attributes at origination (no borrower id exists in the source) |
| `loan_performance` | Loan | Status, reported cash and calculated exposure at the snapshot |
| `loan_risk_segments` | Grade x term | Retrospective tiers |
| `date_dimension` | Month | Calendar for issue months |

`loan_details` links to `date_dimension` and `loan_risk_segments`. `borrower_profiles` and `loan_performance` link 1:1 to `loan_details` by `loan_id`. Attributes are stored once. `emp_title`, `zip_code`, `title` and `desc` are not loaded.

## Scripts

| File | Purpose |
|---|---|
| `01_database_schema.sql` | Database, tables, keys, indexes |
| `02_data_loading.sql` | Bulk load from `data/exports/mysql/` |
| `03_data_quality_checks.sql` | Integrity and business-rule checks |
| `04_business_analysis.sql` | KPI and segment queries (Q01-Q22) |
| `05_advanced_analysis.sql` | CTEs, windows, subqueries (Q23-Q35) |
| `06_kpi_views.sql` | Reusable views, including `vw_kpi_portfolio` |

## How to run

Export the CSV files first:

```bash
python python/mysql_export.py
```

Then from the project root, with `local_infile` enabled on the server and connection details in `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER` and `MYSQL_PASSWORD`:

```bash
python python/run_sql.py
```

## SQL capabilities shown

SELECT and filtering, GROUP BY and HAVING, INNER and LEFT JOIN, CASE, scalar and derived-table subqueries, CTEs, RANK, DENSE_RANK, ROW_NUMBER, NTILE, LAG, running totals, rolling averages, partitioned shares, and year-over-year change.

## Queries

Times come from the verification run on a memory-limited test instance, on this machine, under memory pressure. They indicate relative cost only.

| Query | File | Business purpose | Rows | Seconds |
|---|---|---|---:|---:|
| Q01 | `04_business_analysis.sql` | How large is the portfolio, and what are its headline averages? | 1 | 9.4 |
| Q02 | `04_business_analysis.sql` | How is the portfolio distributed across loan statuses? | 9 | 42.3 |
| Q03 | `04_business_analysis.sql` | What share of resolved loans charged off, by count and by principal? Keeps the rates separate. | 1 | 28.1 |
| Q04 | `04_business_analysis.sql` | Sensitivity: does adding the Default status and policy-exception loans change the rate? | 1 | 11.0 |
| Q05 | `04_business_analysis.sql` | Which grades have the highest historical charge-off rates? | 7 | 86.6 |
| Q06 | `04_business_analysis.sql` | Which subgrades exceed a 40% charge-off rate, with enough resolved loans to trust? | 12 | 28.7 |
| Q07 | `04_business_analysis.sql` | How do 36- and 60-month loans compare on rate, size and outcome? | 2 | 27.5 |
| Q08 | `04_business_analysis.sql` | Which loan purposes default most? Uses CASE to label small purposes. | 14 | 31.9 |
| Q09 | `04_business_analysis.sql` | How does charge-off vary across income bands? | 7 | 30.1 |
| Q10 | `04_business_analysis.sql` | How does debt-to-income ratio relate to loan performance? | 6 | 35.6 |
| Q11 | `04_business_analysis.sql` | Does employment length separate risk, and how do unknown values behave? | 12 | 33.0 |
| Q12 | `04_business_analysis.sql` | How do home ownership and income verification combine? | 9 | 32.9 |
| Q13 | `04_business_analysis.sql` | How do credit-history signals (FICO, delinquency) relate to outcomes? | 20 | 33.6 |
| Q14 | `04_business_analysis.sql` | How are interest rates set across grades and terms? | 14 | 9.8 |
| Q15 | `04_business_analysis.sql` | Do higher contract rates accompany weaker outcomes? | 7 | 26.8 |
| Q16 | `04_business_analysis.sql` | Where did the cash go, by status? These are reported cash flows, not accounting profit. | 9 | 41.0 |
| Q17 | `04_business_analysis.sql` | How much principal was recovered from charged-off loans? Also gives the estimated net loss. | 1 | 17.9 |
| Q18 | `04_business_analysis.sql` | Which grades contribute most to charged-off principal relative to their originations? | 7 | 22.8 |
| Q19 | `04_business_analysis.sql` | Which purposes hold the largest charged-off principal? | 11 | 15.8 |
| Q20 | `04_business_analysis.sql` | How do origination volumes and mature outcomes vary by year? | 12 | 25.6 |
| Q21 | `04_business_analysis.sql` | Which states carry the most exposure, and how do their rates compare? Descriptive only. | 51 | 22.8 |
| Q22 | `04_business_analysis.sql` | Which calendar months had no originations? LEFT JOIN keeps months without loans. | 17 | 3.9 |
| Q23 | `05_advanced_analysis.sql` | How does each subgrade rank overall and within its grade? RANK and DENSE_RANK. | 35 | 21.2 |
| Q24 | `05_advanced_analysis.sql` | How did funded originations accumulate? Running total by month. | 139 | 20.6 |
| Q25 | `05_advanced_analysis.sql` | Year-over-year change in originations. 2018 versus 2017 compares full calendar years. | 12 | 17.4 |
| Q26 | `05_advanced_analysis.sql` | Year-over-year change in mature 36-month cohorts. Only years with all terms elapsed compare fairly. | 9 | 20.6 |
| Q27 | `05_advanced_analysis.sql` | How biased is the resolved-only rate for recent years compared with term-elapsed loans? | 21 | 27.6 |
| Q28 | `05_advanced_analysis.sql` | Which grade-purpose segments make up 80% of charged-off principal? Pareto with a window total. | 11 | 14.7 |
| Q29 | `05_advanced_analysis.sql` | How has grade mix shifted? Share of each year's loans, with a partitioned window. | 84 | 5.9 |
| Q30 | `05_advanced_analysis.sql` | Which states exceed the portfolio rate? Scalar subquery for the benchmark, minimum sample applied. | 23 | 28.6 |
| Q31 | `05_advanced_analysis.sql` | Which grade-term segments take more loss share than funding share? Concentration index. | 14 | 21.5 |
| Q32 | `05_advanced_analysis.sql` | How do the retrospective risk tiers perform? LEFT JOIN keeps a tier even if it were empty. | 3 | 20.6 |
| Q33 | `05_advanced_analysis.sql` | Does default rise evenly across DTI deciles? NTILE on resolved loans with valid DTI. | 10 | 31.8 |
| Q34 | `05_advanced_analysis.sql` | How much do debt-settled loans recover compared with others? | 2 | 2.9 |
| Q35 | `05_advanced_analysis.sql` | What are the worst grade and DTI combinations with a meaningful sample? | 10 | 59.7 |

## Data-quality results

| Check | Failures |
|---|---:|
| row_count_loan_details | 0 |
| row_count_borrower_profiles | 0 |
| row_count_loan_performance | 0 |
| orphan_performance | 0 |
| orphan_borrower | 0 |
| missing_issue_date_key | 0 |
| missing_risk_segment | 0 |
| resolved_flag_consistency | 0 |
| unresolved_counted_as_default | 0 |
| cash_identity | 0 |
| principal_gt_funded | 0 |
| fee_gt_recoveries | 0 |
| loss_field_scope | 0 |
| clean_field_range | 0 |

## Python reconciliation

16 of 16 KPIs in `vw_kpi_portfolio` match Python within tolerance. See `data/aggregate/sql_results/kpi_reconciliation_python_mysql.csv`.

## Verification environment

The scripts were verified end to end against a separate local MySQL 8.0.40 instance created only for testing, because credentials for the installed `MySQL80` service were not shared. To load the installed service, run the commands above with its port and credentials.

## Division precision

MySQL keeps only 4 extra decimal places on integer division by default, which rounds a default rate to 0.1996. Query scripts set `div_precision_increment = 10`, and views multiply by `1E0` so they stay exact in any session.

## Performance note

Pre-aggregate before joining to small dimension tables. Q31's first version drove from the segment table and made millions of random lookups, stalling for over 7 minutes. The rewrite finished in under a minute.
