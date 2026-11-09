-- 05_advanced_analysis.sql
-- CTEs, subqueries and window functions on the same metric definitions as 04_business_analysis.sql.

USE loan_default_analytics;
-- MySQL keeps only 4 extra decimal places on division by default, which would round a rate to 0.1996.
SET SESSION div_precision_increment = 10;

-- Q23. How does each subgrade rank overall and within its grade? RANK and DENSE_RANK.
WITH sub AS (
    SELECT d.grade, d.sub_grade,
           SUM(p.is_resolved) AS resolved,
           SUM(p.is_charged_off) / SUM(p.is_resolved) AS default_rate
    FROM loan_details d
    INNER JOIN loan_performance p ON p.loan_id = d.loan_id
    GROUP BY d.grade, d.sub_grade
)
SELECT sub_grade, resolved, ROUND(default_rate, 6) AS default_rate,
       RANK() OVER (ORDER BY default_rate DESC) AS overall_rank,
       DENSE_RANK() OVER (PARTITION BY grade ORDER BY default_rate DESC) AS rank_within_grade
FROM sub
ORDER BY overall_rank;

-- Q24. How did funded originations accumulate? Running total by month.
WITH monthly AS (
    SELECT issue_date, SUM(funded_amnt) AS funded FROM loan_details GROUP BY issue_date
)
SELECT issue_date, funded,
       SUM(funded) OVER (ORDER BY issue_date) AS cumulative_funded,
       ROUND(AVG(funded) OVER (ORDER BY issue_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS rolling_3m_avg_funded
FROM monthly
ORDER BY issue_date;

-- Q25. Year-over-year change in originations. 2018 versus 2017 compares full calendar years.
WITH yearly AS (
    SELECT issue_year, COUNT(*) AS loans, SUM(funded_amnt) AS funded FROM loan_details GROUP BY issue_year
)
SELECT issue_year, loans, funded,
       LAG(funded) OVER (ORDER BY issue_year) AS prior_year_funded,
       ROUND(100 * (funded / LAG(funded) OVER (ORDER BY issue_year) - 1), 2) AS funded_yoy_pct
FROM yearly
ORDER BY issue_year;

-- Q26. Year-over-year change in mature 36-month cohorts. Only years with all terms elapsed compare fairly.
WITH cohort AS (
    SELECT d.issue_year,
           SUM(p.is_resolved) AS resolved,
           SUM(p.is_charged_off) / SUM(p.is_resolved) AS default_rate
    FROM loan_details d
    INNER JOIN loan_performance p ON p.loan_id = d.loan_id
    WHERE d.term_months = 36
    GROUP BY d.issue_year
    HAVING MIN(p.is_term_elapsed) = 1
)
SELECT issue_year, resolved, ROUND(default_rate, 6) AS default_rate,
       ROUND(100 * (default_rate - LAG(default_rate) OVER (ORDER BY issue_year)), 3) AS change_in_pct_points
FROM cohort
ORDER BY issue_year;

-- Q27. How biased is the resolved-only rate for recent years compared with term-elapsed loans?
SELECT d.issue_year, d.term_months,
       ROUND(AVG(p.is_term_elapsed), 4) AS pct_term_elapsed,
       ROUND(AVG(p.is_resolved), 4) AS pct_resolved,
       ROUND(SUM(p.is_charged_off) / NULLIF(SUM(p.is_resolved), 0), 6) AS resolved_only_rate,
       ROUND(SUM(CASE WHEN p.is_term_elapsed = 1 THEN p.is_charged_off END)
             / NULLIF(SUM(CASE WHEN p.is_term_elapsed = 1 THEN p.is_resolved END), 0), 6) AS term_elapsed_rate
FROM loan_details d
INNER JOIN loan_performance p ON p.loan_id = d.loan_id
GROUP BY d.issue_year, d.term_months
ORDER BY d.issue_year, d.term_months;

-- Q28. Which grade-purpose segments make up 80% of charged-off principal? Pareto with a window total.
WITH seg AS (
    SELECT d.grade, d.purpose_label, SUM(p.unpaid_principal_at_chargeoff) AS unpaid
    FROM loan_details d
    INNER JOIN loan_performance p ON p.loan_id = d.loan_id AND p.is_charged_off = 1
    GROUP BY d.grade, d.purpose_label
), ranked AS (
    SELECT grade, purpose_label, unpaid,
           SUM(unpaid) OVER (ORDER BY unpaid DESC, grade, purpose_label) / SUM(unpaid) OVER () AS cum_share,
           ROW_NUMBER() OVER (ORDER BY unpaid DESC, grade, purpose_label) AS seg_rank
    FROM seg
)
SELECT seg_rank, grade, purpose_label, ROUND(unpaid, 2) AS unpaid_principal, ROUND(cum_share, 4) AS cumulative_share
FROM ranked
WHERE cum_share - unpaid / (SELECT SUM(unpaid) FROM seg) < 0.80
ORDER BY seg_rank;

-- Q29. How has grade mix shifted? Share of each year's loans, with a partitioned window.
SELECT issue_year, grade,
       COUNT(*) AS loans,
       ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY issue_year), 2) AS pct_of_year
FROM loan_details
GROUP BY issue_year, grade
ORDER BY issue_year, grade;

-- Q30. Which states exceed the portfolio rate? Scalar subquery for the benchmark, minimum sample applied.
SELECT d.addr_state,
       SUM(p.is_resolved) AS resolved,
       ROUND(SUM(p.is_charged_off) / SUM(p.is_resolved), 6) AS default_rate,
       ROUND(SUM(p.is_charged_off) / SUM(p.is_resolved)
             - (SELECT SUM(is_charged_off) / SUM(is_resolved) FROM loan_performance), 6) AS gap_to_portfolio
FROM loan_details d
INNER JOIN loan_performance p ON p.loan_id = d.loan_id
GROUP BY d.addr_state
HAVING SUM(p.is_resolved) >= 1000
   AND SUM(p.is_charged_off) / SUM(p.is_resolved) > (SELECT SUM(is_charged_off) / SUM(is_resolved) FROM loan_performance)
ORDER BY gap_to_portfolio DESC;

-- Q31. Which grade-term segments take more loss share than funding share? Concentration index.
-- Loan totals are aggregated first, so the small segment table joins to about 14 rows.
WITH loan_totals AS (
    SELECT d.risk_segment,
           SUM(d.funded_amnt) AS funded,
           SUM(p.unpaid_principal_at_chargeoff) AS unpaid
    FROM loan_details d
    INNER JOIN loan_performance p ON p.loan_id = d.loan_id
    GROUP BY d.risk_segment
)
SELECT s.risk_segment, s.risk_tier, s.relative_risk_index,
       ROUND(100 * t.funded / SUM(t.funded) OVER (), 2) AS pct_of_funded,
       ROUND(100 * t.unpaid / SUM(t.unpaid) OVER (), 2) AS pct_of_unpaid_principal,
       ROUND((t.unpaid / SUM(t.unpaid) OVER ()) / (t.funded / SUM(t.funded) OVER ()), 2) AS loss_concentration_index
FROM loan_risk_segments s
INNER JOIN loan_totals t ON t.risk_segment = s.risk_segment
ORDER BY loss_concentration_index DESC;

-- Q32. How do the retrospective risk tiers perform? LEFT JOIN keeps a tier even if it were empty.
WITH loan_totals AS (
    SELECT d.risk_segment,
           COUNT(*) AS loans,
           SUM(d.funded_amnt) AS funded,
           SUM(p.is_charged_off) AS charged_off,
           SUM(p.is_resolved) AS resolved,
           SUM(p.unpaid_principal_at_chargeoff) AS unpaid
    FROM loan_details d
    INNER JOIN loan_performance p ON p.loan_id = d.loan_id
    GROUP BY d.risk_segment
)
SELECT s.risk_tier,
       COUNT(DISTINCT s.risk_segment) AS segments,
       SUM(t.loans) AS loans,
       SUM(t.funded) AS funded,
       ROUND(SUM(t.charged_off) / SUM(t.resolved), 6) AS default_rate,
       ROUND(SUM(t.unpaid), 2) AS unpaid_principal
FROM loan_risk_segments s
LEFT JOIN loan_totals t ON t.risk_segment = s.risk_segment
GROUP BY s.risk_tier
ORDER BY default_rate;

-- Q33. Does default rise evenly across DTI deciles? NTILE on resolved loans with valid DTI.
WITH ranked AS (
    SELECT b.dti_clean, p.is_charged_off,
           NTILE(10) OVER (ORDER BY b.dti_clean) AS dti_decile
    FROM borrower_profiles b
    INNER JOIN loan_performance p ON p.loan_id = b.loan_id
    WHERE p.is_resolved = 1 AND b.dti_clean IS NOT NULL
)
SELECT dti_decile, COUNT(*) AS resolved, MIN(dti_clean) AS min_dti, MAX(dti_clean) AS max_dti,
       ROUND(AVG(is_charged_off), 6) AS default_rate
FROM ranked
GROUP BY dti_decile
ORDER BY dti_decile;

-- Q34. How much do debt-settled loans recover compared with others?
SELECT debt_settlement_flag,
       COUNT(*) AS charged_off_loans,
       ROUND(100 * AVG(recoveries = 0), 2) AS pct_with_zero_recovery,
       ROUND(SUM(recoveries), 2) AS recoveries,
       ROUND(SUM(recoveries) / SUM(unpaid_principal_at_chargeoff), 4) AS recovery_ratio
FROM loan_performance
WHERE is_charged_off = 1
GROUP BY debt_settlement_flag;

-- Q35. What are the worst grade and DTI combinations with a meaningful sample?
SELECT *
FROM (
    SELECT d.grade, b.dti_band,
           SUM(p.is_resolved) AS resolved,
           ROUND(SUM(p.is_charged_off) / SUM(p.is_resolved), 6) AS default_rate,
           RANK() OVER (ORDER BY SUM(p.is_charged_off) / SUM(p.is_resolved) DESC) AS risk_rank
    FROM loan_details d
    INNER JOIN borrower_profiles b ON b.loan_id = d.loan_id
    INNER JOIN loan_performance p ON p.loan_id = d.loan_id
    WHERE b.dti_band <> 'Unknown'
    GROUP BY d.grade, b.dti_band
    HAVING SUM(p.is_resolved) >= 500
) ranked
WHERE risk_rank <= 10
ORDER BY risk_rank;
