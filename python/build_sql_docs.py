"""Write documentation/sql_documentation.md from the SQL comments and the measured query log."""
from __future__ import annotations

import pandas as pd

from config import AGGREGATE_DIR, DOCS_DIR


def main() -> None:
    log = pd.read_csv(AGGREGATE_DIR / "sql_results" / "query_log.csv")
    dq = pd.read_csv(AGGREGATE_DIR / "sql_results" / "dq_results.csv")
    rec = pd.read_csv(AGGREGATE_DIR / "sql_results" / "kpi_reconciliation_python_mysql.csv")
    rows = "\n".join(f"| {r.query} | `{r.file}` | {r.purpose} | {r.rows} | {r.seconds:.1f} |" for r in log.itertuples())
    dq_rows = "\n".join(f"| {r.check_name} | {r.failures} |" for r in dq.itertuples())
    (DOCS_DIR / "sql_documentation.md").write_text(f"""# SQL Documentation

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
{rows}

## Data-quality results

| Check | Failures |
|---|---:|
{dq_rows}

## Python reconciliation

{int(rec['match'].sum())} of {len(rec)} KPIs in `vw_kpi_portfolio` match Python within tolerance. See `data/aggregate/sql_results/kpi_reconciliation_python_mysql.csv`.

## Verification environment

The scripts were verified end to end against a separate local MySQL 8.0.40 instance created only for testing, because credentials for the installed `MySQL80` service were not shared. To load the installed service, run the commands above with its port and credentials.

## Division precision

MySQL keeps only 4 extra decimal places on integer division by default, which rounds a default rate to 0.1996. Query scripts set `div_precision_increment = 10`, and views multiply by `1E0` so they stay exact in any session.

## Performance note

Pre-aggregate before joining to small dimension tables. Q31's first version drove from the segment table and made millions of random lookups, stalling for over 7 minutes. The rewrite finished in under a minute.
""", encoding="utf-8")


if __name__ == "__main__":
    main()
