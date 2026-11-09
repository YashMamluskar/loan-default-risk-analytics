# Power BI Data Model

Star schema: one fact table of all 2,260,668 loans at loan grain and 17 dimensions, plus `ref_statistical_findings`, an unrelated reference table for the insights page.

| Dimension | Key | Fact column | Relationship |
|---|---|---|---|
| `dim_date` | `date` | `fact_loans[issue_date]` | 1:many, single direction |
| `dim_grade` | `sub_grade` | `fact_loans[sub_grade]` | 1:many, single direction |
| `dim_term` | `term_months` | `fact_loans[term_months]` | 1:many, single direction |
| `dim_purpose` | `purpose_label` | `fact_loans[purpose_label]` | 1:many, single direction |
| `dim_state` | `addr_state` | `fact_loans[addr_state]` | 1:many, single direction |
| `dim_status` | `status_clean` | `fact_loans[status_clean]` | 1:many, single direction |
| `dim_risk_segment` | `risk_segment` | `fact_loans[risk_segment]` | 1:many, single direction |
| `dim_income_band` | `income_band` | `fact_loans[income_band]` | 1:many, single direction |
| `dim_dti_band` | `dti_band` | `fact_loans[dti_band]` | 1:many, single direction |
| `dim_amount_band` | `amount_band` | `fact_loans[amount_band]` | 1:many, single direction |
| `dim_rate_band` | `rate_band` | `fact_loans[rate_band]` | 1:many, single direction |
| `dim_fico_band` | `fico_band` | `fact_loans[fico_band]` | 1:many, single direction |
| `dim_emp_length` | `emp_length_label` | `fact_loans[emp_length_label]` | 1:many, single direction |
| `dim_credit_history_band` | `credit_history_band` | `fact_loans[credit_history_band]` | 1:many, single direction |
| `dim_delinq_band` | `delinq_band` | `fact_loans[delinq_band]` | 1:many, single direction |
| `dim_home_ownership` | `home_ownership_group` | `fact_loans[home_ownership_group]` | 1:many, single direction |
| `dim_verification` | `verification_status` | `fact_loans[verification_status]` | 1:many, single direction |

## Design decisions

* **Grain and scope.** All loans are imported with no sampling. Only the columns the report uses are included, so 186 cleaned columns become 37 in the fact table.
* **Source.** Parquet files in `data/exports/powerbi/`, read through the `DataFolder` Power Query parameter. Change it under Transform data to move the project.
* **Date table.** `dim_date` holds every day from 2007 to 2019 and is marked as a date table. Issue dates are stored as the first of the month, which is all the source records. Auto date/time is off.
* **Bands.** Each band has a hidden sort column, so `<$40K` sorts before `$40K-$60K`.
* **Filter direction.** All relationships are single direction from dimension to fact, so totals stay predictable.
* **Hidden fact columns.** Fact columns are hidden; users work through dimensions and measures.
* **Maps.** State visuals are ranked bars and a table instead of a map. State codes are clean, but map visuals send data to an online service and a ranked view reads sample sizes more easily.
* **Boxplots.** Power BI has no native box plot, so distributions use P25, median and P75 measures on one axis.
