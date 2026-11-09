-- 01_database_schema.sql
-- Purpose : Create the loan_default_analytics database (MySQL 8.0).
-- Design  : One row per loan in the three loan tables, keyed by the source loan id, so no
--           loan attribute is stored twice. The source has no usable borrower id (member_id
--           is 100% empty), so borrower_profiles is 1:1 with the loan at origination.
-- Excludes: emp_title, zip_code, title and desc are not loaded; they add no KPI value and
--           are the fields closest to personal information.

DROP DATABASE IF EXISTS loan_default_analytics;
CREATE DATABASE loan_default_analytics CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE loan_default_analytics;

-- Calendar table covering every origination month.
CREATE TABLE date_dimension (
    date_key        DATE        NOT NULL PRIMARY KEY,
    year_num        SMALLINT    NOT NULL,
    quarter_num     TINYINT     NOT NULL,
    month_num       TINYINT     NOT NULL,
    month_name      CHAR(3)     NOT NULL,
    year_month_label CHAR(7)    NOT NULL
) ENGINE=InnoDB;

-- Retrospective grade x term segments. Tier rules: documentation/methodology.md.
CREATE TABLE loan_risk_segments (
    risk_segment        VARCHAR(8)    NOT NULL PRIMARY KEY,
    grade               CHAR(1)       NOT NULL,
    term_months         TINYINT       NOT NULL,
    mature_resolved     INT           NOT NULL,
    mature_charged_off  INT           NOT NULL,
    mature_default_rate DECIMAL(8,6)  NULL,
    relative_risk_index DECIMAL(8,4)  NULL,
    risk_tier           VARCHAR(20)   NOT NULL,
    UNIQUE KEY uq_grade_term (grade, term_months)
) ENGINE=InnoDB;

-- Contract terms set at origination.
CREATE TABLE loan_details (
    loan_id             BIGINT        NOT NULL PRIMARY KEY,
    issue_date          DATE          NOT NULL,
    issue_year          SMALLINT      NOT NULL,
    loan_amnt           DECIMAL(10,2) NOT NULL,
    funded_amnt         DECIMAL(10,2) NOT NULL,
    funded_amnt_inv     DECIMAL(14,6) NOT NULL,
    term_months         TINYINT       NOT NULL,
    int_rate            DECIMAL(5,2)  NOT NULL,
    installment         DECIMAL(10,2) NOT NULL,
    grade               CHAR(1)       NOT NULL,
    sub_grade           CHAR(2)       NOT NULL,
    purpose_label       VARCHAR(24)   NOT NULL,
    addr_state          CHAR(2)       NOT NULL,
    application_type    VARCHAR(12)   NOT NULL,
    initial_list_status CHAR(1)       NOT NULL,
    amount_band         VARCHAR(12)   NOT NULL,
    rate_band           VARCHAR(8)    NOT NULL,
    risk_segment        VARCHAR(8)    NOT NULL,
    CONSTRAINT fk_details_date FOREIGN KEY (issue_date) REFERENCES date_dimension (date_key),
    CONSTRAINT fk_details_segment FOREIGN KEY (risk_segment) REFERENCES loan_risk_segments (risk_segment),
    KEY ix_details_year (issue_year),
    KEY ix_details_grade (grade),
    KEY ix_details_purpose (purpose_label),
    KEY ix_details_state (addr_state)
) ENGINE=InnoDB;

-- Borrower attributes at origination. Protected characteristics are not in the source.
CREATE TABLE borrower_profiles (
    loan_id              BIGINT        NOT NULL PRIMARY KEY,
    emp_length_label     VARCHAR(10)   NOT NULL,
    emp_length_years     TINYINT       NULL,
    home_ownership_group VARCHAR(10)   NOT NULL,
    annual_inc           DECIMAL(14,2) NULL,
    annual_inc_clean     DECIMAL(14,2) NULL,
    annual_inc_flag      VARCHAR(16)   NOT NULL,
    verification_status  VARCHAR(16)   NOT NULL,
    dti                  DECIMAL(7,2)  NULL,
    dti_clean            DECIMAL(7,2)  NULL,
    dti_flag             VARCHAR(18)   NOT NULL,
    fico_range_low       SMALLINT      NULL,
    fico_range_high      SMALLINT      NULL,
    earliest_cr_line     DATE          NULL,
    credit_history_years DECIMAL(5,2)  NULL,
    delinq_2yrs          SMALLINT      NULL,
    inq_last_6mths       SMALLINT      NULL,
    open_acc             SMALLINT      NULL,
    pub_rec              SMALLINT      NULL,
    revol_bal            DECIMAL(12,2) NULL,
    revol_util           DECIMAL(7,2)  NULL,
    total_acc            SMALLINT      NULL,
    income_band          VARCHAR(12)   NOT NULL,
    dti_band             VARCHAR(8)    NOT NULL,
    fico_band            VARCHAR(8)    NOT NULL,
    credit_history_band  VARCHAR(10)   NOT NULL,
    delinq_band          VARCHAR(8)    NOT NULL,
    pub_rec_band         VARCHAR(8)    NOT NULL,
    CONSTRAINT fk_borrower_loan FOREIGN KEY (loan_id) REFERENCES loan_details (loan_id)
) ENGINE=InnoDB;

-- Status and reported/calculated cash as of the data snapshot (March 2019).
CREATE TABLE loan_performance (
    loan_id                 BIGINT        NOT NULL PRIMARY KEY,
    loan_status             VARCHAR(60)   NOT NULL,
    status_clean            VARCHAR(32)   NOT NULL,
    status_group            VARCHAR(18)   NOT NULL,
    is_fully_paid           TINYINT       NOT NULL,
    is_charged_off          TINYINT       NOT NULL,
    is_resolved             TINYINT       NOT NULL,
    is_term_elapsed         TINYINT       NOT NULL,
    scheduled_maturity_date DATE          NOT NULL,
    out_prncp               DECIMAL(14,6) NOT NULL,
    total_pymnt             DECIMAL(16,6) NOT NULL,
    total_pymnt_inv         DECIMAL(16,6) NOT NULL,
    total_rec_prncp         DECIMAL(14,6) NOT NULL,
    total_rec_int           DECIMAL(14,6) NOT NULL,
    total_rec_late_fee      DECIMAL(14,6) NOT NULL,
    recoveries              DECIMAL(14,6) NOT NULL,
    collection_recovery_fee DECIMAL(14,6) NOT NULL,
    last_pymnt_d            DATE          NULL,
    last_credit_pull_d      DATE          NULL,
    debt_settlement_flag    CHAR(1)       NOT NULL,
    unpaid_principal_at_chargeoff DECIMAL(14,6) NULL,
    net_recoveries          DECIMAL(14,6) NULL,
    est_net_principal_loss  DECIMAL(14,6) NULL,
    CONSTRAINT fk_performance_loan FOREIGN KEY (loan_id) REFERENCES loan_details (loan_id),
    KEY ix_perf_status (status_clean)
) ENGINE=InnoDB;
