# DAX Measures

Generated from `powerbi/model_definition.py`. All measures live on `fact_loans` in display folders.

## Portfolio

### Total Loans

All loans in the current filter context, any status.

Format: `#,0`

```dax
Total Loans =
COUNTROWS(fact_loans)
```

### Total Funded Amount

Original principal funded (reported).

Format: `$#,0`

```dax
Total Funded Amount =
SUM(fact_loans[funded_amnt])
```

### Investor Funded Amount

Portion of funded principal committed by investors (reported).

Format: `$#,0`

```dax
Investor Funded Amount =
SUM(fact_loans[funded_amnt_inv])
```

### Average Loan Amount

Mean funded amount per loan.

Format: `$#,0`

```dax
Average Loan Amount =
AVERAGE(fact_loans[funded_amnt])
```

### Median Loan Amount

Median funded amount per loan.

Format: `$#,0`

```dax
Median Loan Amount =
MEDIAN(fact_loans[funded_amnt])
```

### Average Interest Rate

Unweighted mean contract rate, in percent.

Format: `0.00%`

```dax
Average Interest Rate =
DIVIDE(AVERAGE(fact_loans[int_rate]), 100)
```

### Average Loan Term

Mean contract term in months.

Format: `0.0`

```dax
Average Loan Term =
AVERAGE(fact_loans[term_months])
```

### Loan Origination Count

Loans originated; follows the issue-date context.

Format: `#,0`

```dax
Loan Origination Count =
[Total Loans]
```

### Loan Origination Amount

Principal originated; follows the issue-date context.

Format: `$#,0`

```dax
Loan Origination Amount =
[Total Funded Amount]
```

## Default

### Fully Paid Loans

Terminal status Fully Paid. Excludes policy-exception loans.

Format: `#,0`

```dax
Fully Paid Loans =
SUM(fact_loans[is_fully_paid])
```

### Charged-Off Loans

Terminal status Charged Off. Excludes policy-exception and Default-status loans.

Format: `#,0`

```dax
Charged-Off Loans =
SUM(fact_loans[is_charged_off])
```

### Resolved Loans

Fully Paid + Charged Off: the denominator of the primary default rate.

Format: `#,0`

```dax
Resolved Loans =
SUM(fact_loans[is_resolved])
```

### Unresolved Loans

Current, In Grace Period and Late loans. Never counted as defaults.

Format: `#,0`

```dax
Unresolved Loans =
CALCULATE([Total Loans], dim_status[status_group] = "Unresolved")
```

### Historical Default Rate

PRIMARY KPI. Charged Off / (Fully Paid + Charged Off), by loan count.

Format: `0.00%`

```dax
Historical Default Rate =
DIVIDE([Charged-Off Loans], [Resolved Loans])
```

### Mature Default Rate

Primary definition restricted to loans whose full term has elapsed by March 2019. Removes the bias from young loans that default early but repay late.

Format: `0.00%`

```dax
Mature Default Rate =
VAR co = CALCULATE([Charged-Off Loans], fact_loans[is_term_elapsed] = 1)
VAR res = CALCULATE([Resolved Loans], fact_loans[is_term_elapsed] = 1)
RETURN DIVIDE(co, res)
```

### Pct Term Elapsed

Share of loans whose full term has elapsed by March 2019.

Format: `0.0%`

```dax
Pct Term Elapsed =
DIVIDE(SUM(fact_loans[is_term_elapsed]), [Total Loans])
```

### Mature Cohort Default Rate

Charge-off rate shown only where at least 99% of the loans in context have reached maturity; otherwise blank, so immature cohorts are not compared.

Format: `0.00%`

```dax
Mature Cohort Default Rate =
IF([Pct Term Elapsed] >= 0.99, [Historical Default Rate])
```

### Resolved Funded Amount

Funded principal of resolved loans.

Format: `$#,0`

```dax
Resolved Funded Amount =
CALCULATE([Total Funded Amount], fact_loans[is_resolved] = 1)
```

### Charged-Off Funded Amount

Original funded principal of charged-off loans, before any repayment. Not a loss figure.

Format: `$#,0`

```dax
Charged-Off Funded Amount =
CALCULATE([Total Funded Amount], fact_loans[is_charged_off] = 1)
```

### Principal-Weighted Charge-Off Rate

Funded $ charged off / funded $ resolved. Separate from the loan-count rate.

Format: `0.00%`

```dax
Principal-Weighted Charge-Off Rate =
DIVIDE([Charged-Off Funded Amount], [Resolved Funded Amount])
```

### Charged-Off Share of Originated

Funded $ charged off / all funded $, including unresolved loans. Understates eventual loss on young loans.

Format: `0.00%`

```dax
Charged-Off Share of Originated =
DIVIDE([Charged-Off Funded Amount], [Total Funded Amount])
```

### Default Rate CI Low

Lower 95% Wilson bound of the Historical Default Rate.

Format: `0.00%`

```dax
Default Rate CI Low =
VAR n = [Resolved Loans]
VAR p = [Historical Default Rate]
VAR z = 1.959964
RETURN DIVIDE(p + z*z/(2*n) - z*SQRT(p*(1-p)/n + z*z/(4*n*n)), 1 + z*z/n)
```

### Default Rate CI High

Upper 95% Wilson bound of the Historical Default Rate.

Format: `0.00%`

```dax
Default Rate CI High =
VAR n = [Resolved Loans]
VAR p = [Historical Default Rate]
VAR z = 1.959964
RETURN DIVIDE(p + z*z/(2*n) + z*SQRT(p*(1-p)/n + z*z/(4*n*n)), 1 + z*z/n)
```

### Default Rate vs Selection

Gap to the rate of everything currently selected, in percentage points.

Format: `+0.0%;-0.0%;0.0%`

```dax
Default Rate vs Selection =
[Historical Default Rate] - CALCULATE([Historical Default Rate], ALLSELECTED())
```

## Format

### Rate Color

Conditional format: red at 1.25x or more of the selection rate, teal under 0.75x, navy otherwise.

Format: `text`

```dax
Rate Color =
VAR r = DIVIDE([Historical Default Rate], CALCULATE([Historical Default Rate], ALLSELECTED()))
RETURN SWITCH(TRUE(), r >= 1.25, "#C8452F", r < 0.75, "#14A098", "#1F4E79")
```

### Scope Label

Population label shown in every page header.

Format: `text`

```dax
Scope Label =
"Population: " & FORMAT([Total Loans], "#,0") & " of " & FORMAT(CALCULATE([Total Loans], ALL()), "#,0") & " loans issued Jun 2007-Dec 2018 | Status snapshot: Mar 2019"
```

### Drill Title

Heading of the drill-through page.

Format: `text`

```dax
Drill Title =
"Grade " & SELECTEDVALUE(dim_grade[grade], "(multiple)") & " detail"
```

## Borrower

### Average Annual Income

Mean of annual_inc_clean (zero incomes excluded). Very skewed; read with the median.

Format: `$#,0`

```dax
Average Annual Income =
AVERAGE(fact_loans[annual_inc_clean])
```

### Median Annual Income

Median of annual_inc_clean.

Format: `$#,0`

```dax
Median Annual Income =
MEDIAN(fact_loans[annual_inc_clean])
```

### Average DTI

Mean of dti_clean (placeholders -1 and 999 excluded).

Format: `0.00`

```dax
Average DTI =
AVERAGE(fact_loans[dti_clean])
```

### Average Employment Length

Mean years employed. Unknown excluded; '10+ years' is capped at 10, so this is a lower bound.

Format: `0.0`

```dax
Average Employment Length =
AVERAGE(fact_loans[emp_length_years])
```

### Average FICO

Mean midpoint of the FICO range at origination.

Format: `0`

```dax
Average FICO =
AVERAGE(fact_loans[fico_mid])
```

## Financial

### Total Payments Received

Reported cash: principal + interest + late fees + recoveries.

Format: `$#,0`

```dax
Total Payments Received =
SUM(fact_loans[total_pymnt])
```

### Total Principal Received

Reported principal repaid, all statuses.

Format: `$#,0`

```dax
Total Principal Received =
SUM(fact_loans[total_rec_prncp])
```

### Total Interest Received

Reported interest received. Cash flow, not profit.

Format: `$#,0`

```dax
Total Interest Received =
SUM(fact_loans[total_rec_int])
```

### Outstanding Principal

Reported principal still outstanding at the snapshot.

Format: `$#,0`

```dax
Outstanding Principal =
SUM(fact_loans[out_prncp])
```

### Charged-Off Principal Exposure

Calculated: funded principal minus principal repaid, charged-off loans only. Estimate, not an accounting loss.

Format: `$#,0`

```dax
Charged-Off Principal Exposure =
SUM(fact_loans[unpaid_principal_at_chargeoff])
```

### Total Recoveries

Reported post-charge-off recoveries on Charged Off loans (gross of fees).

Format: `$#,0`

```dax
Total Recoveries =
CALCULATE(SUM(fact_loans[recoveries]), fact_loans[is_charged_off] = 1)
```

### Total Recovery Fees

Reported collection fees on Charged Off loans.

Format: `$#,0`

```dax
Total Recovery Fees =
CALCULATE(SUM(fact_loans[collection_recovery_fee]), fact_loans[is_charged_off] = 1)
```

### Net Recoveries

Calculated: recoveries minus collection fees.

Format: `$#,0`

```dax
Net Recoveries =
[Total Recoveries] - [Total Recovery Fees]
```

### Recovery Ratio

Gross recoveries / Charged-Off Principal Exposure.

Format: `0.0%`

```dax
Recovery Ratio =
DIVIDE([Total Recoveries], [Charged-Off Principal Exposure])
```

### Estimated Net Principal Loss

Calculated: exposure minus net recoveries. Excludes interest income, funding and servicing costs; not an accounting loss.

Format: `$#,0`

```dax
Estimated Net Principal Loss =
SUM(fact_loans[est_net_principal_loss])
```

### Share of Exposure

Share of Charged-Off Principal Exposure in the selection.

Format: `0.0%`

```dax
Share of Exposure =
DIVIDE([Charged-Off Principal Exposure], CALCULATE([Charged-Off Principal Exposure], ALLSELECTED()))
```

### Share of Funded

Share of Total Funded Amount in the selection.

Format: `0.0%`

```dax
Share of Funded =
DIVIDE([Total Funded Amount], CALCULATE([Total Funded Amount], ALLSELECTED()))
```

### Loss Concentration Index

Share of Exposure / Share of Funded. Above 1 means the segment takes more than its proportional share.

Format: `0.00`

```dax
Loss Concentration Index =
DIVIDE([Share of Exposure], [Share of Funded])
```

## Risk

### Risk Segment Distribution

Share of selected loans in each risk segment or tier.

Format: `0.0%`

```dax
Risk Segment Distribution =
DIVIDE([Total Loans], CALCULATE([Total Loans], ALLSELECTED(dim_risk_segment)))
```

## Distribution

### Rate P25

25th percentile of contract rate, in percent.

Format: `0.0%`

```dax
Rate P25 =
PERCENTILE.INC(fact_loans[int_rate], 0.25) / 100
```

### Rate Median

Median contract rate, in percent.

Format: `0.0%`

```dax
Rate Median =
MEDIAN(fact_loans[int_rate]) / 100
```

### Rate P75

75th percentile of contract rate, in percent.

Format: `0.0%`

```dax
Rate P75 =
PERCENTILE.INC(fact_loans[int_rate], 0.75) / 100
```

### Amount P25

25th percentile of funded amount.

Format: `$#,0`

```dax
Amount P25 =
PERCENTILE.INC(fact_loans[funded_amnt], 0.25)
```

### Amount Median

Median funded amount.

Format: `$#,0`

```dax
Amount Median =
MEDIAN(fact_loans[funded_amnt])
```

### Amount P75

75th percentile of funded amount.

Format: `$#,0`

```dax
Amount P75 =
PERCENTILE.INC(fact_loans[funded_amnt], 0.75)
```
