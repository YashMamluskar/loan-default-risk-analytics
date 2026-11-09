-- 03_data_quality_checks.sql
-- Every check returns check_name and failures; a correct load returns failures = 0
-- except the row-count check, which reports the expected 2,260,668 loans as loaded.

USE loan_default_analytics;

-- DQ1. Confirms the full population loaded into each loan table without truncation.
SELECT 'row_count_loan_details' AS check_name, ABS(COUNT(*) - 2260668) AS failures FROM loan_details;
SELECT 'row_count_borrower_profiles' AS check_name, ABS(COUNT(*) - 2260668) AS failures FROM borrower_profiles;
SELECT 'row_count_loan_performance' AS check_name, ABS(COUNT(*) - 2260668) AS failures FROM loan_performance;

-- DQ2. Finds performance rows whose loan does not exist (orphaned financial records).
SELECT 'orphan_performance' AS check_name, COUNT(*) AS failures
FROM loan_performance p LEFT JOIN loan_details d ON d.loan_id = p.loan_id WHERE d.loan_id IS NULL;

-- DQ3. Finds borrower rows whose loan does not exist.
SELECT 'orphan_borrower' AS check_name, COUNT(*) AS failures
FROM borrower_profiles b LEFT JOIN loan_details d ON d.loan_id = b.loan_id WHERE d.loan_id IS NULL;

-- DQ4. Finds loans whose issue month is missing from the calendar.
SELECT 'missing_issue_date_key' AS check_name, COUNT(*) AS failures
FROM loan_details d LEFT JOIN date_dimension c ON c.date_key = d.issue_date WHERE c.date_key IS NULL;

-- DQ5. Finds loans without a risk-segment parent.
SELECT 'missing_risk_segment' AS check_name, COUNT(*) AS failures
FROM loan_details d LEFT JOIN loan_risk_segments s ON s.risk_segment = d.risk_segment WHERE s.risk_segment IS NULL;

-- DQ6. Confirms a resolved loan is exactly one of Fully Paid or Charged Off.
SELECT 'resolved_flag_consistency' AS check_name, COUNT(*) AS failures
FROM loan_performance WHERE is_resolved <> is_fully_paid + is_charged_off;

-- DQ7. Confirms Current and Late loans never count as charged off.
SELECT 'unresolved_counted_as_default' AS check_name, COUNT(*) AS failures
FROM loan_performance WHERE status_group = 'Unresolved' AND is_charged_off = 1;

-- DQ8. Confirms the reported cash identity holds on every loan.
SELECT 'cash_identity' AS check_name, COUNT(*) AS failures
FROM loan_performance
WHERE ABS(total_rec_prncp + total_rec_int + total_rec_late_fee + recoveries - total_pymnt) > 1;

-- DQ9. Confirms principal received never exceeds the funded amount.
SELECT 'principal_gt_funded' AS check_name, COUNT(*) AS failures
FROM loan_performance p JOIN loan_details d ON d.loan_id = p.loan_id
WHERE p.total_rec_prncp > d.funded_amnt + 1;

-- DQ10. Confirms recovery fees never exceed recoveries.
SELECT 'fee_gt_recoveries' AS check_name, COUNT(*) AS failures
FROM loan_performance WHERE collection_recovery_fee > recoveries + 1;

-- DQ11. Confirms calculated loss fields exist only on charged-off loans.
SELECT 'loss_field_scope' AS check_name, COUNT(*) AS failures
FROM loan_performance
WHERE (is_charged_off = 1 AND unpaid_principal_at_chargeoff IS NULL)
   OR (is_charged_off = 0 AND unpaid_principal_at_chargeoff IS NOT NULL);

-- DQ12. Confirms cleaned DTI and income have no placeholder or zero values.
SELECT 'clean_field_range' AS check_name, COUNT(*) AS failures
FROM borrower_profiles WHERE dti_clean < 0 OR dti_clean >= 999 OR annual_inc_clean <= 0;
