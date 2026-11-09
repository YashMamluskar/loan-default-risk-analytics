"""Semantic model definition: tables, relationships and documented DAX measures.

This file is the single source for the generated template, dax_measures.md and data_model.md.
"""
from __future__ import annotations

F = "fact_loans"

# name, description, DAX, format string, display folder
MEASURES = [
    ("Total Loans", "All loans in the current filter context, any status.", f"COUNTROWS({F})", "#,0", "Portfolio"),
    ("Total Funded Amount", "Original principal funded (reported).", f"SUM({F}[funded_amnt])", "$#,0", "Portfolio"),
    ("Investor Funded Amount", "Portion of funded principal committed by investors (reported).", f"SUM({F}[funded_amnt_inv])", "$#,0", "Portfolio"),
    ("Average Loan Amount", "Mean funded amount per loan.", f"AVERAGE({F}[funded_amnt])", "$#,0", "Portfolio"),
    ("Median Loan Amount", "Median funded amount per loan.", f"MEDIAN({F}[funded_amnt])", "$#,0", "Portfolio"),
    ("Average Interest Rate", "Unweighted mean contract rate, in percent.", f"DIVIDE(AVERAGE({F}[int_rate]), 100)", "0.00%", "Portfolio"),
    ("Average Loan Term", "Mean contract term in months.", f"AVERAGE({F}[term_months])", "0.0", "Portfolio"),
    ("Loan Origination Count", "Loans originated; follows the issue-date context.", "[Total Loans]", "#,0", "Portfolio"),
    ("Loan Origination Amount", "Principal originated; follows the issue-date context.", "[Total Funded Amount]", "$#,0", "Portfolio"),

    ("Fully Paid Loans", "Terminal status Fully Paid. Excludes policy-exception loans.", f"SUM({F}[is_fully_paid])", "#,0", "Default"),
    ("Charged-Off Loans", "Terminal status Charged Off. Excludes policy-exception and Default-status loans.", f"SUM({F}[is_charged_off])", "#,0", "Default"),
    ("Resolved Loans", "Fully Paid + Charged Off: the denominator of the primary default rate.", f"SUM({F}[is_resolved])", "#,0", "Default"),
    ("Unresolved Loans", "Current, In Grace Period and Late loans. Never counted as defaults.", 'CALCULATE([Total Loans], dim_status[status_group] = "Unresolved")', "#,0", "Default"),
    ("Historical Default Rate", "PRIMARY KPI. Charged Off / (Fully Paid + Charged Off), by loan count.", "DIVIDE([Charged-Off Loans], [Resolved Loans])", "0.00%", "Default"),
    ("Mature Default Rate", "Primary definition restricted to loans whose full term has elapsed by March 2019. Removes the bias from young loans that default early but repay late.", f"VAR co = CALCULATE([Charged-Off Loans], {F}[is_term_elapsed] = 1)\nVAR res = CALCULATE([Resolved Loans], {F}[is_term_elapsed] = 1)\nRETURN DIVIDE(co, res)", "0.00%", "Default"),
    ("Pct Term Elapsed", "Share of loans whose full term has elapsed by March 2019.", f"DIVIDE(SUM({F}[is_term_elapsed]), [Total Loans])", "0.0%", "Default"),
    ("Mature Cohort Default Rate", "Charge-off rate shown only where at least 99% of the loans in context have reached maturity; otherwise blank, so immature cohorts are not compared.", "IF([Pct Term Elapsed] >= 0.99, [Historical Default Rate])", "0.00%", "Default"),
    ("Resolved Funded Amount", "Funded principal of resolved loans.", f"CALCULATE([Total Funded Amount], {F}[is_resolved] = 1)", "$#,0", "Default"),
    ("Charged-Off Funded Amount", "Original funded principal of charged-off loans, before any repayment. Not a loss figure.", f"CALCULATE([Total Funded Amount], {F}[is_charged_off] = 1)", "$#,0", "Default"),
    ("Principal-Weighted Charge-Off Rate", "Funded $ charged off / funded $ resolved. Separate from the loan-count rate.", "DIVIDE([Charged-Off Funded Amount], [Resolved Funded Amount])", "0.00%", "Default"),
    ("Charged-Off Share of Originated", "Funded $ charged off / all funded $, including unresolved loans. Understates eventual loss on young loans.", "DIVIDE([Charged-Off Funded Amount], [Total Funded Amount])", "0.00%", "Default"),
    ("Default Rate CI Low", "Lower 95% Wilson bound of the Historical Default Rate.", "VAR n = [Resolved Loans]\nVAR p = [Historical Default Rate]\nVAR z = 1.959964\nRETURN DIVIDE(p + z*z/(2*n) - z*SQRT(p*(1-p)/n + z*z/(4*n*n)), 1 + z*z/n)", "0.00%", "Default"),
    ("Default Rate CI High", "Upper 95% Wilson bound of the Historical Default Rate.", "VAR n = [Resolved Loans]\nVAR p = [Historical Default Rate]\nVAR z = 1.959964\nRETURN DIVIDE(p + z*z/(2*n) + z*SQRT(p*(1-p)/n + z*z/(4*n*n)), 1 + z*z/n)", "0.00%", "Default"),
    ("Default Rate vs Selection", "Gap to the rate of everything currently selected, in percentage points.", "[Historical Default Rate] - CALCULATE([Historical Default Rate], ALLSELECTED())", "+0.0%;-0.0%;0.0%", "Default"),
    ("Rate Color", "Conditional format: red at 1.25x or more of the selection rate, teal under 0.75x, navy otherwise.", 'VAR r = DIVIDE([Historical Default Rate], CALCULATE([Historical Default Rate], ALLSELECTED()))\nRETURN SWITCH(TRUE(), r >= 1.25, "#C8452F", r < 0.75, "#14A098", "#1F4E79")', None, "Format"),

    ("Average Annual Income", "Mean of annual_inc_clean (zero incomes excluded). Very skewed; read with the median.", f"AVERAGE({F}[annual_inc_clean])", "$#,0", "Borrower"),
    ("Median Annual Income", "Median of annual_inc_clean.", f"MEDIAN({F}[annual_inc_clean])", "$#,0", "Borrower"),
    ("Average DTI", "Mean of dti_clean (placeholders -1 and 999 excluded).", f"AVERAGE({F}[dti_clean])", "0.00", "Borrower"),
    ("Average Employment Length", "Mean years employed. Unknown excluded; '10+ years' is capped at 10, so this is a lower bound.", f"AVERAGE({F}[emp_length_years])", "0.0", "Borrower"),
    ("Average FICO", "Mean midpoint of the FICO range at origination.", f"AVERAGE({F}[fico_mid])", "0", "Borrower"),

    ("Total Payments Received", "Reported cash: principal + interest + late fees + recoveries.", f"SUM({F}[total_pymnt])", "$#,0", "Financial"),
    ("Total Principal Received", "Reported principal repaid, all statuses.", f"SUM({F}[total_rec_prncp])", "$#,0", "Financial"),
    ("Total Interest Received", "Reported interest received. Cash flow, not profit.", f"SUM({F}[total_rec_int])", "$#,0", "Financial"),
    ("Outstanding Principal", "Reported principal still outstanding at the snapshot.", f"SUM({F}[out_prncp])", "$#,0", "Financial"),
    ("Charged-Off Principal Exposure", "Calculated: funded principal minus principal repaid, charged-off loans only. Estimate, not an accounting loss.", f"SUM({F}[unpaid_principal_at_chargeoff])", "$#,0", "Financial"),
    ("Total Recoveries", "Reported post-charge-off recoveries on Charged Off loans (gross of fees).", f"CALCULATE(SUM({F}[recoveries]), {F}[is_charged_off] = 1)", "$#,0", "Financial"),
    ("Total Recovery Fees", "Reported collection fees on Charged Off loans.", f"CALCULATE(SUM({F}[collection_recovery_fee]), {F}[is_charged_off] = 1)", "$#,0", "Financial"),
    ("Net Recoveries", "Calculated: recoveries minus collection fees.", "[Total Recoveries] - [Total Recovery Fees]", "$#,0", "Financial"),
    ("Recovery Ratio", "Gross recoveries / Charged-Off Principal Exposure.", "DIVIDE([Total Recoveries], [Charged-Off Principal Exposure])", "0.0%", "Financial"),
    ("Estimated Net Principal Loss", "Calculated: exposure minus net recoveries. Excludes interest income, funding and servicing costs; not an accounting loss.", f"SUM({F}[est_net_principal_loss])", "$#,0", "Financial"),
    ("Share of Exposure", "Share of Charged-Off Principal Exposure in the selection.", "DIVIDE([Charged-Off Principal Exposure], CALCULATE([Charged-Off Principal Exposure], ALLSELECTED()))", "0.0%", "Financial"),
    ("Share of Funded", "Share of Total Funded Amount in the selection.", "DIVIDE([Total Funded Amount], CALCULATE([Total Funded Amount], ALLSELECTED()))", "0.0%", "Financial"),
    ("Loss Concentration Index", "Share of Exposure / Share of Funded. Above 1 means the segment takes more than its proportional share.", "DIVIDE([Share of Exposure], [Share of Funded])", "0.00", "Financial"),

    ("Risk Segment Distribution", "Share of selected loans in each risk segment or tier.", "DIVIDE([Total Loans], CALCULATE([Total Loans], ALLSELECTED(dim_risk_segment)))", "0.0%", "Risk"),

    ("Rate P25", "25th percentile of contract rate, in percent.", f"PERCENTILE.INC({F}[int_rate], 0.25) / 100", "0.0%", "Distribution"),
    ("Rate Median", "Median contract rate, in percent.", f"MEDIAN({F}[int_rate]) / 100", "0.0%", "Distribution"),
    ("Rate P75", "75th percentile of contract rate, in percent.", f"PERCENTILE.INC({F}[int_rate], 0.75) / 100", "0.0%", "Distribution"),
    ("Amount P25", "25th percentile of funded amount.", f"PERCENTILE.INC({F}[funded_amnt], 0.25)", "$#,0", "Distribution"),
    ("Amount Median", "Median funded amount.", f"MEDIAN({F}[funded_amnt])", "$#,0", "Distribution"),
    ("Amount P75", "75th percentile of funded amount.", f"PERCENTILE.INC({F}[funded_amnt], 0.75)", "$#,0", "Distribution"),

    ("Scope Label", "Population label shown in every page header.", '"Population: " & FORMAT([Total Loans], "#,0") & " of " & FORMAT(CALCULATE([Total Loans], ALL()), "#,0") & " loans issued Jun 2007-Dec 2018 | Status snapshot: Mar 2019"', None, "Format"),
    ("Drill Title", "Heading of the drill-through page.", '"Grade " & SELECTEDVALUE(dim_grade[grade], "(multiple)") & " detail"', None, "Format"),
]

# (dimension table, dimension key, fact column, sort-by mapping {column: sort column})
DIMENSIONS = [
    ("dim_date", "date", "issue_date", {"year_month": "year_month_sort", "issue_month": "issue_month_num"}),
    ("dim_grade", "sub_grade", "sub_grade", {"sub_grade": "sub_grade_sort"}),
    ("dim_term", "term_months", "term_months", {"term_label": "term_sort"}),
    ("dim_purpose", "purpose_label", "purpose_label", {}),
    ("dim_state", "addr_state", "addr_state", {}),
    ("dim_status", "status_clean", "status_clean", {"status_clean": "status_sort"}),
    ("dim_risk_segment", "risk_segment", "risk_segment", {"risk_tier": "risk_tier_sort"}),
    ("dim_income_band", "income_band", "income_band", {"income_band": "income_band_sort"}),
    ("dim_dti_band", "dti_band", "dti_band", {"dti_band": "dti_band_sort"}),
    ("dim_amount_band", "amount_band", "amount_band", {"amount_band": "amount_band_sort"}),
    ("dim_rate_band", "rate_band", "rate_band", {"rate_band": "rate_band_sort"}),
    ("dim_fico_band", "fico_band", "fico_band", {"fico_band": "fico_band_sort"}),
    ("dim_emp_length", "emp_length_label", "emp_length_label", {"emp_length_label": "emp_length_label_sort"}),
    ("dim_credit_history_band", "credit_history_band", "credit_history_band", {"credit_history_band": "credit_history_band_sort"}),
    ("dim_delinq_band", "delinq_band", "delinq_band", {"delinq_band": "delinq_band_sort"}),
    ("dim_home_ownership", "home_ownership_group", "home_ownership_group", {}),
    ("dim_verification", "verification_status", "verification_status", {"verification_status": "verification_sort"}),
]
REFERENCE_TABLES = ["ref_statistical_findings"]
