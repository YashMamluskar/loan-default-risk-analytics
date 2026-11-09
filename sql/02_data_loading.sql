-- 02_data_loading.sql
-- Purpose : Load the full population (all 2,260,668 loans, no sampling or truncation).
-- Input   : CSV files written by python/mysql_export.py, with \N meaning NULL.
-- Run from the project root so the relative paths resolve, with local_infile enabled on
-- the server and the client:   mysql --local-infile=1 -u <user> -p < sql/02_data_loading.sql
-- Parent tables load first. FK and unique checks are off only for this bulk session;
-- 03_data_quality_checks.sql then proves referential integrity explicitly.

USE loan_default_analytics;
SET SESSION foreign_key_checks = 0;
SET SESSION unique_checks = 0;

LOAD DATA LOCAL INFILE 'data/exports/mysql/date_dimension.csv' INTO TABLE date_dimension
    FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' LINES TERMINATED BY '\n' IGNORE 1 LINES;

LOAD DATA LOCAL INFILE 'data/exports/mysql/loan_risk_segments.csv' INTO TABLE loan_risk_segments
    FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' LINES TERMINATED BY '\n' IGNORE 1 LINES;

LOAD DATA LOCAL INFILE 'data/exports/mysql/loan_details.csv' INTO TABLE loan_details
    FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' LINES TERMINATED BY '\n' IGNORE 1 LINES;

LOAD DATA LOCAL INFILE 'data/exports/mysql/borrower_profiles.csv' INTO TABLE borrower_profiles
    FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' LINES TERMINATED BY '\n' IGNORE 1 LINES;

LOAD DATA LOCAL INFILE 'data/exports/mysql/loan_performance.csv' INTO TABLE loan_performance
    FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' LINES TERMINATED BY '\n' IGNORE 1 LINES;

SET SESSION foreign_key_checks = 1;
SET SESSION unique_checks = 1;
ANALYZE TABLE date_dimension, loan_risk_segments, loan_details, borrower_profiles, loan_performance;
