"""Generate and execute the seven analysis notebooks (needs: python -m ipykernel install --sys-prefix --name loan_risk).

The pipeline scripts remain the source of logic. Each notebook reruns a live query against the
Parquet data, reads the pipeline's outputs, shows the charts and states the takeaway, so a reviewer
can read the analysis in order and confirm the published numbers.
"""
from __future__ import annotations

import subprocess
import sys

import nbformat as nbf

from config import PROJECT_ROOT, get_logger

log = get_logger("build_notebooks")
NB_DIR = PROJECT_ROOT / "notebooks"

SETUP = """import json, sys
from pathlib import Path
import pandas as pd
from IPython.display import Image, display
sys.path.insert(0, str(Path.cwd().parent / 'python'))
from analysis_common import analytical_src, segment_metrics
from config import AGGREGATE_DIR, AUDIT_DIR, CLEAN_PARQUET, DOCS_DIR, STATS_DIR, VISUALS_DIR, connect
pd.set_option('display.max_columns', 40, 'display.width', 180, 'display.float_format', '{:,.4f}'.format)
con = connect(); src = analytical_src()
kpi = json.loads((AGGREGATE_DIR / 'portfolio_kpis.json').read_text())
fin = json.loads((AGGREGATE_DIR / 'financial_totals.json').read_text())
show = lambda name: display(Image(filename=str(VISUALS_DIR / f'{name}.png')))
csv = lambda name: pd.read_csv(AGGREGATE_DIR / f'{name}.csv')"""

NOTEBOOKS = {
    "01_dataset_understanding": [
        ("md", "# 1. Dataset Understanding\nProfile of the raw LendingClub file before any change. Produced by `python/data_inspection.py`."),
        ("code", "facts = json.loads((AUDIT_DIR / 'audit_facts.json').read_text()); facts"),
        ("md", "2,260,701 records include 33 non-loan rows. No duplicated ids or exact duplicates exist."),
        ("code", "pd.read_csv(AUDIT_DIR / 'non_loan_rows.csv').head(6)"),
        ("code", "profile = pd.read_csv(AUDIT_DIR / 'column_profile.csv')\nprofile.sort_values('missing_pct', ascending=False)[['column_name','missing_pct','approx_distinct']].head(15)"),
        ("code", "freq = pd.read_csv(AUDIT_DIR / 'categorical_frequencies.csv')\nfreq[freq.column_name == 'loan_status']"),
        ("md", "Only Fully Paid and Charged Off are terminal outcomes in the primary default rate. Current and Late loans are never counted as defaults."),
        ("code", "pd.read_csv(DOCS_DIR / 'data_dictionary.csv').groupby('category').column_name.count().sort_values(ascending=False)"),
    ],
    "02_data_cleaning": [
        ("md", "# 2. Data Cleaning\nPipeline: `python/data_cleaning.py`, checked by `python/data_validation.py`."),
        ("code", "json.loads((AUDIT_DIR / 'cleaning_counts.json').read_text())"),
        ("code", "v = pd.read_csv(AUDIT_DIR / 'validation_results.csv'); print(v.severity.value_counts().to_dict(), 'failed errors:', ((~v.passed) & (v.severity=='error')).sum()); v"),
        ("md", "Live check: original values stay untouched while cleaned fields sit beside them."),
        ("code", "con.execute(f\"SELECT dti_flag, COUNT(*) n, MIN(dti) min_raw, MAX(dti) max_raw, MAX(dti_clean) max_clean FROM {src} GROUP BY 1 ORDER BY n DESC\").df()"),
        ("code", "con.execute(f\"SELECT annual_inc_flag, COUNT(*) n, MIN(annual_inc) min_raw, MAX(annual_inc) max_raw FROM {src} GROUP BY 1 ORDER BY n DESC\").df()"),
    ],
    "03_exploratory_analysis": [
        ("md", "# 3. Exploratory Analysis\nPortfolio, default, interest-rate, time and geographic views (`python/eda.py`)."),
        ("code", "live = con.execute(f'SELECT SUM(is_charged_off)*1.0/SUM(is_resolved) FROM {src}').fetchone()[0]\nassert abs(live - kpi['default_rate']) < 1e-12\nprint(f\"Default rate {live:.4%}, principal-weighted {kpi['principal_weighted_rate']:.4%}, mature {kpi['mature_default_rate']:.4%}\")"),
        ("code", "show('a_status_distribution'); show('a_loan_amount_distribution')"),
        ("md", "## Default analysis"),
        ("code", "show('b_default_by_grade'); show('b_default_by_subgrade'); show('b_default_by_purpose'); show('b_default_by_grade_term')"),
        ("md", "## Interest rates\nPricing follows grade, so rate and default move together. That is pricing for risk rather than proof that rate alone causes default."),
        ("code", "show('d_rate_by_grade'); show('d_default_by_rate_band'); csv('interest_rate_by_status')"),
        ("md", "## Time\nOnly cohorts whose terms have elapsed compare fairly. The resolved-only rate for 2016 and 2017 is inflated because early failures resolve first."),
        ("code", "csv('summary_issue_year')[['issue_year','loans','default_rate','mature_default_rate','pct_term_elapsed','unresolved_share']]"),
        ("code", "show('f_originations_by_year'); show('f_mature_cohort_default'); show('f_avg_rate_by_year'); show('f_grade_mix'); show('f_originations_by_month')"),
        ("md", "## Geography\nDescriptive only; these rates do not establish that location causes default."),
        ("code", "show('g_funded_by_state'); show('g_default_by_state_top')"),
    ],
    "04_borrower_risk_analysis": [
        ("md", "# 4. Borrower Risk Analysis\nAssociations from `python/borrower_analysis.py`. Grade already prices much of this risk."),
        ("code", "csv('borrower_profile').T"),
        ("code", "csv('borrower_profile_by_outcome')"),
        ("code", "for n in ['income_band','dti_band','emp_length_label','home_ownership_group','verification_status','fico_band','credit_history_band','delinq_band','pub_rec_band','inquiry_band','revol_util_band']:\n    show(f'c_default_by_{n}')"),
        ("md", "Employment length barely separates risk among stated values, while missing employment length stands out. Verified loans look riskier, which likely reflects who gets verified."),
        ("code", "show('c_dti_within_grade')"),
        ("code", "segment_metrics(con, ['grade','dti_band'], src).pivot(index='grade', columns='dti_band', values='default_rate')[['<10','10-20','20-30','30-40','40+']]"),
    ],
    "05_financial_analysis": [
        ("md", "# 5. Financial Analysis\nReported cash and calculated estimates (`python/financial_analysis.py`). None of these is an accounting profit or loss."),
        ("code", "pd.Series(fin).to_frame('value')"),
        ("code", "show('e_chargeoff_composition')\nassert abs(fin['co_principal_received'] + fin['net_recoveries'] + fin['est_net_loss'] - fin['co_funded']) < 1"),
        ("code", "csv('cashflow_by_status')"),
        ("code", "csv('financial_grade')[['grade','funded_amount','unpaid_principal_at_chargeoff','recoveries','recovery_ratio','share_of_funded','share_of_unpaid_principal']]"),
        ("code", "show('e_unpaid_principal_by_grade'); show('e_unpaid_principal_by_purpose'); show('e_recovery_ratio_by_year')"),
        ("code", "csv('recoveries_by_settlement')"),
    ],
    "06_statistical_analysis": [
        ("md", "# 6. Statistical Analysis\nHypothesis tests with assumptions and effect sizes (`python/statistical_analysis.py`). With over a million loans p-values are almost always tiny, so the effect size carries the business meaning."),
        ("code", "t = pd.read_csv(STATS_DIR / 'hypothesis_tests.csv'); t[['test_name','test','statistic','p_value_display','effect_size','significant_bonferroni','n']]"),
        ("code", "pd.set_option('display.max_colwidth', None); t[['test_name','null_hypothesis','alternative_hypothesis','why_selected','assumption_check','business_reading']]"),
        ("code", "pd.read_csv(STATS_DIR / 'confidence_intervals.csv')"),
        ("code", "show('s_correlation_heatmap')"),
        ("code", "pd.read_csv(STATS_DIR / 'distribution_outliers.csv')[['column','median','max','skewness','iqr_outliers','iqr_outlier_pct']]"),
        ("md", "Adjusted odds ratios describe association after controlling for the other fields. This is not a credit-scoring model."),
        ("code", "pd.read_csv(STATS_DIR / 'adjusted_odds_ratios.csv')"),
    ],
    "07_risk_segmentation": [
        ("md", "# 7. Risk Segmentation\nTransparent, retrospective tiers (`python/risk_segmentation.py`).\n\nRelative Risk Index = segment mature-cohort rate / portfolio mature-cohort rate. Low: under 0.75. Medium: 0.75 to under 1.25. High: 1.25 or more. Fewer than 500 mature resolved loans: Insufficient data.\n\nThese classify past portfolio behaviour. They are not underwriting rules or individual credit decisions, and they use no protected characteristics."),
        ("code", "csv('risk_segments_grade_term')[['risk_segment','loans','mature_resolved','default_rate','mature_default_rate','relative_risk_index','risk_tier','share_of_funded','share_of_unpaid_principal']]"),
        ("code", "csv('risk_tier_summary')"),
        ("code", "s = csv('risk_segment_summary'); s[s.risk_tier=='High'].sort_values('relative_risk_index', ascending=False)[['dimension','segment','mature_resolved','mature_default_rate','relative_risk_index','share_of_funded','share_of_unpaid_principal']].head(20)"),
    ],
}


def main() -> None:
    NB_DIR.mkdir(exist_ok=True)
    for name, cells in NOTEBOOKS.items():
        nb = nbf.v4.new_notebook()
        nb.metadata["kernelspec"] = {"name": "loan_risk", "display_name": "Loan Risk (.venv)", "language": "python"}
        nb.cells = [nbf.v4.new_code_cell(SETUP)] + [nbf.v4.new_markdown_cell(c) if k == "md" else nbf.v4.new_code_cell(c) for k, c in cells]
        path = NB_DIR / f"{name}.ipynb"
        nbf.write(nb, path)
        result = subprocess.run([sys.executable, "-m", "nbconvert", "--to", "notebook", "--execute", "--inplace", "--ExecutePreprocessor.timeout=600", "--ExecutePreprocessor.kernel_name=loan_risk", str(path)],
                                cwd=NB_DIR, capture_output=True, text=True)
        if result.returncode:
            log.error("%s failed:\n%s", name, result.stderr[-1500:])
            raise SystemExit(1)
        log.info("Executed %s (%.0f KB)", name, path.stat().st_size / 1024)


if __name__ == "__main__":
    main()
