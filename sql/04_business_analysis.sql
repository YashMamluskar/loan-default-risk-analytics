-- 04_business_analysis.sql
-- Business KPI queries. Default rate = Charged Off / (Fully Paid + Charged Off), by loan count,
-- unless a query names another definition. Each query answers one management question.

USE loan_default_analytics;
-- MySQL keeps only 4 extra decimal places on division by default, which would round a rate to 0.1996.
SET SESSION div_precision_increment = 10;

-- Q01. How large is the portfolio, and what are its headline averages?
SELECT COUNT(*) AS total_loans,
       SUM(funded_amnt) AS total_funded,
       SUM(funded_amnt_inv) AS total_investor_funded,
       ROUND(AVG(funded_amnt), 2) AS avg_funded,
       ROUND(AVG(int_rate), 4) AS avg_int_rate,
       MIN(issue_date) AS first_issue_month,
       MAX(issue_date) AS last_issue_month
FROM loan_details;

-- Q02. How is the portfolio distributed across loan statuses?
SELECT p.status_clean, p.status_group,
       COUNT(*) AS loans,
       ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 3) AS pct_of_loans,
       SUM(d.funded_amnt) AS funded,
       ROUND(SUM(p.out_prncp), 2) AS outstanding_principal
FROM loan_performance p
INNER JOIN loan_details d ON d.loan_id = p.loan_id
GROUP BY p.status_clean, p.status_group
ORDER BY loans DESC;

-- Q03. What share of resolved loans charged off, by count and by principal? Keeps the rates separate.
SELECT SUM(p.is_charged_off) AS charged_off,
       SUM(p.is_resolved) AS resolved,
       ROUND(SUM(p.is_charged_off) / SUM(p.is_resolved), 6) AS default_rate_count,
       ROUND(SUM(CASE WHEN p.is_charged_off = 1 THEN d.funded_amnt ELSE 0 END)
             / SUM(CASE WHEN p.is_resolved = 1 THEN d.funded_amnt ELSE 0 END), 6) AS default_rate_principal_weighted,
       ROUND(SUM(CASE WHEN p.is_charged_off = 1 THEN d.funded_amnt ELSE 0 END) / SUM(d.funded_amnt), 6) AS charged_off_share_of_all_originated
FROM loan_performance p
INNER JOIN loan_details d ON d.loan_id = p.loan_id;

-- Q04. Sensitivity: does adding the Default status and policy-exception loans change the rate?
SELECT ROUND(SUM(status_clean IN ('Charged Off', 'Default', 'Policy Exception - Charged Off'))
             / SUM(status_clean IN ('Fully Paid', 'Charged Off', 'Default', 'Policy Exception - Charged Off', 'Policy Exception - Fully Paid')), 6) AS alt_default_rate,
       ROUND(SUM(is_charged_off) / SUM(is_resolved), 6) AS primary_default_rate
FROM loan_performance;

-- Q05. Which grades have the highest historical charge-off rates?
SELECT d.grade,
       COUNT(*) AS loans,
       SUM(p.is_resolved) AS resolved,
       SUM(p.is_charged_off) AS charged_off,
       ROUND(SUM(p.is_charged_off) / SUM(p.is_resolved), 6) AS default_rate,
       ROUND(SUM(CASE WHEN p.is_term_elapsed = 1 THEN p.is_charged_off END)
             / SUM(CASE WHEN p.is_term_elapsed = 1 THEN p.is_resolved END), 6) AS mature_default_rate
FROM loan_details d
INNER JOIN loan_performance p ON p.loan_id = d.loan_id
GROUP BY d.grade
ORDER BY d.grade;

-- Q06. Which subgrades exceed a 40% charge-off rate, with enough resolved loans to trust?
SELECT d.sub_grade,
       SUM(p.is_resolved) AS resolved,
       ROUND(SUM(p.is_charged_off) / SUM(p.is_resolved), 6) AS default_rate
FROM loan_details d
INNER JOIN loan_performance p ON p.loan_id = d.loan_id
GROUP BY d.sub_grade
HAVING SUM(p.is_resolved) >= 500 AND SUM(p.is_charged_off) / SUM(p.is_resolved) > 0.40
ORDER BY default_rate DESC;

-- Q07. How do 36- and 60-month loans compare on rate, size and outcome?
SELECT d.term_months,
       COUNT(*) AS loans,
       ROUND(AVG(d.int_rate), 3) AS avg_int_rate,
       ROUND(AVG(d.funded_amnt), 2) AS avg_funded,
       ROUND(SUM(p.is_charged_off) / SUM(p.is_resolved), 6) AS default_rate,
       ROUND(SUM(CASE WHEN p.is_term_elapsed = 1 THEN p.is_charged_off END)
             / SUM(CASE WHEN p.is_term_elapsed = 1 THEN p.is_resolved END), 6) AS mature_default_rate
FROM loan_details d
INNER JOIN loan_performance p ON p.loan_id = d.loan_id
GROUP BY d.term_months;

-- Q08. Which loan purposes default most? Uses CASE to label small purposes.
SELECT d.purpose_label,
       SUM(p.is_resolved) AS resolved,
       ROUND(SUM(p.is_charged_off) / SUM(p.is_resolved), 6) AS default_rate,
       CASE WHEN SUM(p.is_resolved) < 1000 THEN 'Small sample' ELSE 'Reliable' END AS sample_note
FROM loan_details d
INNER JOIN loan_performance p ON p.loan_id = d.loan_id
GROUP BY d.purpose_label
ORDER BY default_rate DESC;

-- Q09. How does charge-off vary across income bands?
SELECT b.income_band,
       SUM(p.is_resolved) AS resolved,
       ROUND(SUM(p.is_charged_off) / SUM(p.is_resolved), 6) AS default_rate
FROM borrower_profiles b
INNER JOIN loan_performance p ON p.loan_id = b.loan_id
GROUP BY b.income_band
ORDER BY FIELD(b.income_band, '<$40K', '$40K-$60K', '$60K-$80K', '$80K-$100K', '$100K-$150K', '$150K+', 'Unknown');

-- Q10. How does debt-to-income ratio relate to loan performance?
SELECT b.dti_band,
       SUM(p.is_resolved) AS resolved,
       ROUND(SUM(p.is_charged_off) / SUM(p.is_resolved), 6) AS default_rate,
       ROUND(AVG(b.dti_clean), 2) AS avg_dti
FROM borrower_profiles b
INNER JOIN loan_performance p ON p.loan_id = b.loan_id
GROUP BY b.dti_band
ORDER BY FIELD(b.dti_band, '<10', '10-20', '20-30', '30-40', '40+', 'Unknown');

-- Q11. Does employment length separate risk, and how do unknown values behave?
SELECT b.emp_length_label,
       SUM(p.is_resolved) AS resolved,
       ROUND(SUM(p.is_charged_off) / SUM(p.is_resolved), 6) AS default_rate
FROM borrower_profiles b
INNER JOIN loan_performance p ON p.loan_id = b.loan_id
GROUP BY b.emp_length_label, b.emp_length_years
ORDER BY b.emp_length_years IS NULL, b.emp_length_years;

-- Q12. How do home ownership and income verification combine?
SELECT b.home_ownership_group, b.verification_status,
       SUM(p.is_resolved) AS resolved,
       ROUND(SUM(p.is_charged_off) / SUM(p.is_resolved), 6) AS default_rate
FROM borrower_profiles b
INNER JOIN loan_performance p ON p.loan_id = b.loan_id
GROUP BY b.home_ownership_group, b.verification_status
HAVING SUM(p.is_resolved) >= 1000
ORDER BY b.home_ownership_group, default_rate DESC;

-- Q13. How do credit-history signals (FICO, delinquency) relate to outcomes?
SELECT b.fico_band, b.delinq_band,
       SUM(p.is_resolved) AS resolved,
       ROUND(SUM(p.is_charged_off) / SUM(p.is_resolved), 6) AS default_rate
FROM borrower_profiles b
INNER JOIN loan_performance p ON p.loan_id = b.loan_id
GROUP BY b.fico_band, b.delinq_band
ORDER BY FIELD(b.fico_band, '660-679', '680-699', '700-719', '720-749', '750+'), b.delinq_band;

-- Q14. How are interest rates set across grades and terms?
SELECT grade, term_months,
       COUNT(*) AS loans,
       ROUND(AVG(int_rate), 3) AS avg_int_rate,
       MIN(int_rate) AS min_int_rate,
       MAX(int_rate) AS max_int_rate
FROM loan_details
GROUP BY grade, term_months
ORDER BY grade, term_months;

-- Q15. Do higher contract rates accompany weaker outcomes?
SELECT d.rate_band,
       SUM(p.is_resolved) AS resolved,
       ROUND(SUM(p.is_charged_off) / SUM(p.is_resolved), 6) AS default_rate
FROM loan_details d
INNER JOIN loan_performance p ON p.loan_id = d.loan_id
GROUP BY d.rate_band
ORDER BY FIELD(d.rate_band, '<8%', '8-11%', '11-14%', '14-17%', '17-20%', '20-25%', '25%+');

-- Q16. Where did the cash go, by status? These are reported cash flows, not accounting profit.
SELECT p.status_clean,
       SUM(d.funded_amnt) AS funded,
       ROUND(SUM(p.total_pymnt), 2) AS total_payments,
       ROUND(SUM(p.total_rec_prncp), 2) AS principal_received,
       ROUND(SUM(p.total_rec_int), 2) AS interest_received,
       ROUND(SUM(p.recoveries), 2) AS recoveries,
       ROUND(SUM(p.out_prncp), 2) AS outstanding_principal
FROM loan_performance p
INNER JOIN loan_details d ON d.loan_id = p.loan_id
GROUP BY p.status_clean
ORDER BY funded DESC;

-- Q17. How much principal was recovered from charged-off loans? Also gives the estimated net loss.
SELECT COUNT(*) AS charged_off_loans,
       SUM(d.funded_amnt) AS funded_on_charged_off,
       ROUND(SUM(p.total_rec_prncp), 2) AS principal_repaid_before_chargeoff,
       ROUND(SUM(p.unpaid_principal_at_chargeoff), 2) AS unpaid_principal_at_chargeoff,
       ROUND(SUM(p.recoveries), 2) AS gross_recoveries,
       ROUND(SUM(p.collection_recovery_fee), 2) AS recovery_fees,
       ROUND(SUM(p.net_recoveries), 2) AS net_recoveries,
       ROUND(SUM(p.est_net_principal_loss), 2) AS est_net_principal_loss,
       ROUND(SUM(p.recoveries) / SUM(p.unpaid_principal_at_chargeoff), 6) AS gross_recovery_ratio
FROM loan_performance p
INNER JOIN loan_details d ON d.loan_id = p.loan_id
WHERE p.is_charged_off = 1;

-- Q18. Which grades contribute most to charged-off principal relative to their originations?
SELECT d.grade,
       SUM(d.funded_amnt) AS funded,
       ROUND(SUM(p.unpaid_principal_at_chargeoff), 2) AS unpaid_principal,
       ROUND(SUM(p.recoveries), 2) AS recoveries,
       ROUND(100 * SUM(d.funded_amnt) / SUM(SUM(d.funded_amnt)) OVER (), 2) AS pct_of_funded,
       ROUND(100 * SUM(p.unpaid_principal_at_chargeoff) / SUM(SUM(p.unpaid_principal_at_chargeoff)) OVER (), 2) AS pct_of_unpaid_principal
FROM loan_details d
INNER JOIN loan_performance p ON p.loan_id = d.loan_id
GROUP BY d.grade
ORDER BY d.grade;

-- Q19. Which purposes hold the largest charged-off principal?
SELECT d.purpose_label,
       ROUND(SUM(p.unpaid_principal_at_chargeoff), 2) AS unpaid_principal,
       ROUND(SUM(p.recoveries) / SUM(p.unpaid_principal_at_chargeoff), 4) AS recovery_ratio
FROM loan_details d
INNER JOIN loan_performance p ON p.loan_id = d.loan_id AND p.is_charged_off = 1
GROUP BY d.purpose_label
HAVING SUM(p.unpaid_principal_at_chargeoff) > 10000000
ORDER BY unpaid_principal DESC;

-- Q20. How do origination volumes and mature outcomes vary by year?
SELECT d.issue_year,
       COUNT(*) AS loans,
       SUM(d.funded_amnt) AS funded,
       ROUND(AVG(d.int_rate), 3) AS avg_int_rate,
       ROUND(AVG(p.is_term_elapsed), 4) AS pct_term_elapsed,
       ROUND(SUM(p.is_charged_off) / SUM(p.is_resolved), 6) AS resolved_default_rate,
       ROUND(SUM(CASE WHEN p.is_term_elapsed = 1 THEN p.is_charged_off END)
             / NULLIF(SUM(CASE WHEN p.is_term_elapsed = 1 THEN p.is_resolved END), 0), 6) AS mature_default_rate
FROM loan_details d
INNER JOIN loan_performance p ON p.loan_id = d.loan_id
GROUP BY d.issue_year
ORDER BY d.issue_year;

-- Q21. Which states carry the most exposure, and how do their rates compare? Descriptive only.
SELECT d.addr_state,
       COUNT(*) AS loans,
       SUM(d.funded_amnt) AS funded,
       SUM(p.is_resolved) AS resolved,
       ROUND(SUM(p.is_charged_off) / NULLIF(SUM(p.is_resolved), 0), 6) AS default_rate,
       ROUND(SUM(p.unpaid_principal_at_chargeoff), 2) AS unpaid_principal
FROM loan_details d
INNER JOIN loan_performance p ON p.loan_id = d.loan_id
GROUP BY d.addr_state
ORDER BY funded DESC;

-- Q22. Which calendar months had no originations? LEFT JOIN keeps months without loans.
SELECT c.date_key, c.year_num, c.month_name, COUNT(d.loan_id) AS loans
FROM date_dimension c
LEFT JOIN loan_details d ON d.issue_date = c.date_key
GROUP BY c.date_key, c.year_num, c.month_name
HAVING COUNT(d.loan_id) = 0
ORDER BY c.date_key;
