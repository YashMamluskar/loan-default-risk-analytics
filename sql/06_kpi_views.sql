-- 06_kpi_views.sql
-- Reusable views. vw_kpi_portfolio is the SQL value that reconciles to Python and Power BI.

USE loan_default_analytics;
-- Rates multiply by 1E0 so they stay exact whatever the caller's div_precision_increment is.

-- Loan-level analytical view: joins the three loan tables for ad hoc analysis.
CREATE OR REPLACE VIEW vw_loan_fact AS
SELECT d.loan_id, d.issue_date, d.issue_year, d.grade, d.sub_grade, d.term_months, d.int_rate, d.funded_amnt,
       d.funded_amnt_inv, d.purpose_label, d.addr_state, d.risk_segment, d.amount_band, d.rate_band,
       b.income_band, b.dti_band, b.fico_band, b.emp_length_label, b.home_ownership_group, b.verification_status,
       b.annual_inc_clean, b.dti_clean, p.status_clean, p.status_group, p.is_fully_paid, p.is_charged_off,
       p.is_resolved, p.is_term_elapsed, p.total_pymnt, p.total_rec_prncp, p.total_rec_int, p.recoveries,
       p.collection_recovery_fee, p.out_prncp, p.unpaid_principal_at_chargeoff, p.net_recoveries, p.est_net_principal_loss
FROM loan_details d
INNER JOIN borrower_profiles b ON b.loan_id = d.loan_id
INNER JOIN loan_performance p ON p.loan_id = d.loan_id;

-- Portfolio KPIs in one row.
CREATE OR REPLACE VIEW vw_kpi_portfolio AS
SELECT COUNT(*) AS total_loans,
       SUM(d.funded_amnt) AS total_funded,
       AVG(d.funded_amnt) AS avg_funded,
       AVG(d.int_rate) AS avg_int_rate,
       SUM(p.is_fully_paid) AS fully_paid,
       SUM(p.is_charged_off) AS charged_off,
       SUM(p.is_resolved) AS resolved,
       1E0 * SUM(p.is_charged_off) / SUM(p.is_resolved) AS default_rate,
       1E0 * SUM(CASE WHEN p.is_charged_off = 1 THEN d.funded_amnt END) / SUM(CASE WHEN p.is_resolved = 1 THEN d.funded_amnt END) AS principal_weighted_rate,
       1E0 * SUM(CASE WHEN p.is_term_elapsed = 1 THEN p.is_charged_off END) / SUM(CASE WHEN p.is_term_elapsed = 1 THEN p.is_resolved END) AS mature_default_rate,
       SUM(p.total_pymnt) AS total_payments,
       SUM(p.total_rec_prncp) AS principal_received,
       SUM(p.unpaid_principal_at_chargeoff) AS unpaid_principal_at_chargeoff,
       SUM(CASE WHEN p.is_charged_off = 1 THEN p.recoveries END) AS recoveries,
       SUM(CASE WHEN p.is_charged_off = 1 THEN p.collection_recovery_fee END) AS recovery_fees,
       SUM(p.est_net_principal_loss) AS est_net_principal_loss
FROM loan_details d
INNER JOIN loan_performance p ON p.loan_id = d.loan_id;

-- Grade summary.
CREATE OR REPLACE VIEW vw_kpi_grade AS
SELECT d.grade, COUNT(*) AS loans, SUM(d.funded_amnt) AS funded,
       SUM(p.is_resolved) AS resolved, SUM(p.is_charged_off) AS charged_off,
       1E0 * SUM(p.is_charged_off) / SUM(p.is_resolved) AS default_rate,
       SUM(p.unpaid_principal_at_chargeoff) AS unpaid_principal,
       1E0 * SUM(p.recoveries) / SUM(p.unpaid_principal_at_chargeoff) AS recovery_ratio
FROM loan_details d
INNER JOIN loan_performance p ON p.loan_id = d.loan_id
GROUP BY d.grade;

-- Annual cohort summary, with term-elapsed coverage shown beside the rates.
CREATE OR REPLACE VIEW vw_kpi_cohort AS
SELECT d.issue_year, d.term_months, COUNT(*) AS loans, SUM(d.funded_amnt) AS funded,
       AVG(p.is_term_elapsed) AS pct_term_elapsed,
       1E0 * SUM(p.is_charged_off) / NULLIF(SUM(p.is_resolved), 0) AS resolved_default_rate,
       1E0 * SUM(CASE WHEN p.is_term_elapsed = 1 THEN p.is_charged_off END)
           / NULLIF(SUM(CASE WHEN p.is_term_elapsed = 1 THEN p.is_resolved END), 0) AS mature_default_rate
FROM loan_details d
INNER JOIN loan_performance p ON p.loan_id = d.loan_id
GROUP BY d.issue_year, d.term_months;

-- State summary. Descriptive; not a basis for geographic lending restrictions.
CREATE OR REPLACE VIEW vw_kpi_state AS
SELECT d.addr_state, COUNT(*) AS loans, SUM(d.funded_amnt) AS funded,
       SUM(p.is_resolved) AS resolved,
       1E0 * SUM(p.is_charged_off) / NULLIF(SUM(p.is_resolved), 0) AS default_rate,
       SUM(p.unpaid_principal_at_chargeoff) AS unpaid_principal
FROM loan_details d
INNER JOIN loan_performance p ON p.loan_id = d.loan_id
GROUP BY d.addr_state;
