"""Write README.md, project_overview.md and the portfolio summary from measured outputs."""
from __future__ import annotations

import json
import sys

import pandas as pd

from config import AGGREGATE_DIR, DOCS_DIR, PROJECT_ROOT

sys.path.insert(0, str(PROJECT_ROOT / "powerbi"))
from insights import build_insights  # noqa: E402


def main() -> None:
    k = json.loads((AGGREGATE_DIR / "portfolio_kpis.json").read_text())
    f = json.loads((AGGREGATE_DIR / "financial_totals.json").read_text())
    ins = build_insights()
    ql = pd.read_csv(AGGREGATE_DIR / "sql_results" / "query_log.csv")
    qa = pd.read_csv(AGGREGATE_DIR / "qa_results.csv") if (AGGREGATE_DIR / "qa_results.csv").exists() else None
    qa_line = ""
    if qa is not None:
        counts = qa.result.value_counts().to_dict()
        qa_line = f"{counts.get('Pass', 0)} checks passed, {counts.get('FAIL', 0)} failed, {counts.get('NOT RUN', 0)} not run."
    bullet = lambda items: "\n".join(f"- {i}" for i in items)

    (PROJECT_ROOT / "README.md").write_text(f"""# Loan Default Risk Intelligence & Credit Portfolio Analytics

End-to-end analysis of {k['loans']:,.0f} LendingClub loans ({k['funded'] / 1e9:,.2f} billion dollars funded), from a raw 1.6 GB CSV to a validated MySQL database and an interactive Power BI dashboard.

![Executive overview](visuals/dashboard_screenshots/01_executive_overview.png)

## Business problem

A lender needs to know how its portfolio performed, which segments drove charge-offs, how much was recovered, and which actions merit testing. Getting this right depends on careful definitions: counting unresolved loans or using the wrong denominator produces misleading default rates.

## Key results

| KPI | Value | Definition |
|---|---:|---|
| Loans | {k['loans']:,.0f} | Issued Jun 2007 to Dec 2018 |
| Funded principal | ${k['funded'] / 1e9:,.2f}B | Original funded amount |
| Historical default rate | {k['default_rate']:.2%} | Charged Off / (Fully Paid + Charged Off) |
| Principal-weighted rate | {k['principal_weighted_rate']:.2%} | Same, weighted by funded dollars |
| Term-elapsed default rate | {k['mature_default_rate']:.2%} | Loans past scheduled maturity by Mar 2019 |
| Charged-off principal | ${f['unpaid_principal'] / 1e9:,.2f}B | Funded minus principal repaid; an estimate |
| Recovery ratio | {f['recovery_ratio_gross']:.1%} | Gross recoveries / charged-off principal |

## Key findings

{bullet(ins['findings'])}

## Recommendations to test

{bullet(ins['recommendations'])}

Full evidence is in [the final report](documentation/final_project_report.md).

## Technology

Python (pandas, DuckDB, SciPy, statsmodels, Matplotlib, seaborn), MySQL 8, Power BI Desktop (Power Query, DAX), Jupyter.

## Architecture

```text
Raw CSV (2,260,701 rows, 151 columns)
  -> data_inspection.py    all-text staging Parquet and column audit
  -> data_cleaning.py      typed, flagged, cleaned Parquet (186 columns)
  -> data_validation.py    37 rules
  -> risk_segmentation.py  analytical Parquet with retrospective tiers
  -> eda / borrower / financial / statistical analysis
  -> mysql_export + run_sql      MySQL schema, checks, queries, views
  -> powerbi_export + build_template      star schema and report template
  -> qa_checks.py          Python, MySQL and Power BI reconciliation
```

## Analytical approach

- **Careful definitions.** Current and Late loans are never counted as defaults. The Default status (40 loans) and legacy policy-exception loans are reported separately.
- **Separate denominators.** Count-based, principal-weighted and share-of-originated rates stay separate.
- **Maturity awareness.** Recent resolved loans over-represent early failures, so cohorts are compared only after their terms have elapsed.
- **Reported versus calculated.** Cash fields are distinguished from estimates, and nothing is presented as an accounting loss.
- **Effect sizes.** With over a million loans nearly everything is significant, so readings use effect sizes and stratified tests.
- **Transparent segmentation.** Retrospective grade x term tiers use published thresholds, with no protected characteristics.

Details: [methodology](documentation/methodology.md).

## SQL

{len(ql)} documented business queries plus data-quality checks and KPI views: joins, CTEs, subqueries, CASE, RANK, DENSE_RANK, NTILE, LAG, running totals and year-over-year change. See [SQL documentation](documentation/sql_documentation.md).

## Dashboard

Six pages plus a drill-through page and a report-page tooltip, with synced slicers, cross-filtering, conditional formatting and {len(__import__('model_definition').MEASURES)} documented [DAX measures](powerbi/dax_measures.md).

| | |
|---|---|
| ![Borrower risk](visuals/dashboard_screenshots/02_borrower_risk.png) | ![Loan performance](visuals/dashboard_screenshots/03_loan_performance.png) |
| ![Exposure](visuals/dashboard_screenshots/04_exposure_recovery.png) | ![Time and geography](visuals/dashboard_screenshots/05_time_geography.png) |
| ![Insights](visuals/dashboard_screenshots/06_risk_insights.png) | ![Drill-through](visuals/dashboard_screenshots/07_drill_through_grade_g.png) |

## Testing

{qa_line} See the [testing report](documentation/testing_report.md), including the defects that testing caught and how they were fixed.

## Run it

Download `accepted_2007_to_2018Q4.csv` from [Kaggle](https://www.kaggle.com/datasets/wordsforthewise/lending-club) into `data/raw/`. Then from the project root:

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python -m pip install -r requirements.txt
```

```bash
.venv/Scripts/python python/run_pipeline.py
```

MySQL (set `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`; the server needs `local_infile` enabled):

```bash
.venv/Scripts/python python/run_sql.py
```

Power BI: run `python powerbi/build_template.py`, open `powerbi/Loan_Default_Risk_Dashboard.pbit`, confirm the `DataFolder` path and choose Load.

## Limitations

{bullet(ins['limitations'])}

More in [limitations](documentation/limitations.md).
""", encoding="utf-8")

    (DOCS_DIR / "project_overview.md").write_text(f"""# Project Overview

**Goal.** Help a lender understand portfolio performance, default patterns and financial exposure, using a reproducible analysis of real loan data.

**Scope.** {k['loans']:,.0f} accepted LendingClub loans issued June 2007 to December 2018, status as of March 2019.

**Deliverables**

| Deliverable | Location |
|---|---|
| Data pipeline | `python/` |
| Notebooks | `notebooks/` |
| SQL scripts | `sql/` |
| Power BI report and template | `powerbi/` |
| Charts and screenshots | `visuals/` |
| Documentation | `documentation/` |

**Reading order.** [Business understanding](business_understanding.md), [dataset audit](dataset_audit.md), [methodology](methodology.md), [final report](final_project_report.md), [testing report](testing_report.md).

**Headline.** {k['default_rate']:.2%} of resolved loans charged off ({k['mature_default_rate']:.2%} once terms have elapsed), leaving ${f['unpaid_principal'] / 1e9:,.2f}B of principal unpaid at charge-off, of which {f['recovery_ratio_gross']:.1%} was recovered.
""", encoding="utf-8")

    (DOCS_DIR / "portfolio_summary.md").write_text(f"""# Portfolio Summary

## LinkedIn

Built an end-to-end credit risk analytics project on {k['loans'] / 1e6:.2f} million LendingClub loans (${k['funded'] / 1e9:,.0f}B funded): a Python and DuckDB pipeline, a full-population MySQL database with {len(ql)} business queries, and an interactive Power BI dashboard, with KPIs reconciled across all three tools.

The most useful finding was about measurement. The resolved-loan default rate is {k['default_rate']:.1%}, but it falls to {k['mature_default_rate']:.1%} on loans whose full term has elapsed, because recent resolved loans over-represent early failures. The High risk tier holds {pd.read_csv(AGGREGATE_DIR / 'risk_tier_summary.csv').set_index('risk_tier').share_of_funded['High']:.0%} of funding but {pd.read_csv(AGGREGATE_DIR / 'risk_tier_summary.csv').set_index('risk_tier').share_of_unpaid_principal['High']:.0%} of charged-off principal.

## Resume

**Loan Default Risk Intelligence & Credit Portfolio Analytics** | Python, DuckDB, MySQL, Power BI, DAX
- Built a memory-efficient pipeline for a 1.6 GB, {k['loans'] / 1e6:.2f}M-loan dataset, with 37 automated validation rules on 7 GB of RAM.
- Designed a MySQL schema and wrote {len(ql)} documented queries using CTEs and window functions; reconciled KPIs across Python, MySQL and Power BI.
- Delivered a six-page Power BI dashboard with {len(__import__('model_definition').MEASURES)} DAX measures, drill-through and report-page tooltips over a star schema.
- Identified a High risk tier holding {pd.read_csv(AGGREGATE_DIR / 'risk_tier_summary.csv').set_index('risk_tier').share_of_unpaid_principal['High']:.0%} of charged-off principal on {pd.read_csv(AGGREGATE_DIR / 'risk_tier_summary.csv').set_index('risk_tier').share_of_funded['High']:.0%} of funding, and quantified resolved-only bias in default rates.
""", encoding="utf-8")
    print("README written")


if __name__ == "__main__":
    main()
