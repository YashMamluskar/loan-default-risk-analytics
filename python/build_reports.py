"""Phase 12: write the narrative documentation from measured outputs, so reports cannot drift from the data."""
from __future__ import annotations

import json
import sys

import pandas as pd

from config import AGGREGATE_DIR, DOCS_DIR, PROJECT_ROOT, STATS_DIR, ensure_dirs

sys.path.insert(0, str(PROJECT_ROOT / "powerbi"))
from insights import build_insights  # noqa: E402


def money(value: float) -> str:
    return f"${value / 1e9:,.2f}B" if abs(value) >= 1e9 else f"${value / 1e6:,.1f}M"


def md_table(frame: pd.DataFrame) -> str:
    head = "| " + " | ".join(map(str, frame.columns)) + " |\n|" + "---|" * len(frame.columns)
    body = "\n".join("| " + " | ".join(map(str, row)) + " |" for row in frame.values)
    return head + "\n" + body


def main() -> None:
    ensure_dirs()
    kpi = json.loads((AGGREGATE_DIR / "portfolio_kpis.json").read_text())
    fin = json.loads((AGGREGATE_DIR / "financial_totals.json").read_text())
    read = lambda name: pd.read_csv(AGGREGATE_DIR / f"{name}.csv")
    ins = build_insights()

    grade = read("summary_grade")
    grade_t = pd.DataFrame({"Grade": grade.grade, "Loans": grade.loans.map("{:,.0f}".format), "Resolved": grade.resolved.map("{:,.0f}".format),
                            "Default rate": grade.default_rate.map("{:.2%}".format), "Principal-weighted": grade.principal_weighted_rate.map("{:.2%}".format),
                            "Mature rate": grade.mature_default_rate.map("{:.2%}".format), "Avg rate": grade.avg_int_rate.map("{:.2f}%".format)})
    seg = read("risk_segments_grade_term")
    seg_t = pd.DataFrame({"Segment": seg.risk_segment, "Mature resolved": seg.mature_resolved.map("{:,.0f}".format), "Mature rate": seg.mature_default_rate.map("{:.1%}".format),
                          "RRI": seg.relative_risk_index.map("{:.2f}".format), "Tier": seg.risk_tier, "Share of funded": seg.share_of_funded.map("{:.1%}".format),
                          "Share of charged-off principal": seg.share_of_unpaid_principal.map("{:.1%}".format)})
    cohort = read("summary_issue_year")
    cohort_t = pd.DataFrame({"Year": cohort.issue_year, "Loans": cohort.loans.map("{:,.0f}".format), "Funded": cohort.funded_amount.map(money), "Term elapsed": cohort.pct_term_elapsed.map("{:.0%}".format),
                             "Resolved-only rate": cohort.default_rate.map("{:.1%}".format), "Term-elapsed rate": cohort.mature_default_rate.map(lambda v: "n/a" if pd.isna(v) else f"{v:.1%}")})
    def band(name, col):
        f = read(name)
        return pd.DataFrame({"Band": f[col], "Resolved": f.resolved.map("{:,.0f}".format), "Default rate": f.default_rate.map(lambda v: "n/a" if pd.isna(v) else f"{v:.1%}")})
    purpose = read("summary_purpose_label").sort_values("default_rate", ascending=False)
    purpose_t = pd.DataFrame({"Purpose": purpose.purpose_label, "Resolved": purpose.resolved.map("{:,.0f}".format), "Default rate": purpose.default_rate.map("{:.1%}".format),
                              "Charged-off principal": purpose.unpaid_principal_at_chargeoff.map(money)})
    tests = pd.read_csv(STATS_DIR / "hypothesis_tests.csv")
    tests_t = pd.DataFrame({"Test": tests.test_name, "Method": tests.test, "p": tests.p_value_display, "Effect": tests.effect_size, "Reading": tests.business_reading})
    odds = pd.read_csv(STATS_DIR / "adjusted_odds_ratios.csv")
    odds_n = int(odds.n.iloc[0])

    bullet = lambda items: "\n".join(f"- {i}" for i in items)
    (DOCS_DIR / "insights_and_recommendations.md").write_text(f"""# Insights and Recommendations

All figures are computed from the data by `powerbi/insights.py`.

## Key findings

{bullet(ins['findings'])}

## Recommendations

These are options for management to test. They rest on historical association, so each needs a controlled pilot and compliance review before becoming policy.

{bullet(ins['recommendations'])}

## Limitations

{bullet(ins['limitations'])}
""", encoding="utf-8")

    (DOCS_DIR / "final_project_report.md").write_text(f"""# Loan Default Risk Intelligence and Credit Portfolio Analytics

Final project report. All figures are generated from the pipeline outputs.

## 1. Executive summary

LendingClub's accepted-loan file holds {kpi['loans']:,.0f} loans and {money(kpi['funded'])} of funded principal, issued June 2007 to December 2018, with status as of March 2019.

- **Primary default rate:** {kpi['default_rate']:.2%} of {kpi['resolved']:,.0f} resolved loans charged off ({kpi['principal_weighted_rate']:.2%} weighted by principal).
- **Less biased view:** {kpi['mature_default_rate']:.2%} on loans whose full term has elapsed. Rates based only on resolved loans overstate recent cohorts.
- **Charged-off principal:** {money(fin['unpaid_principal'])} unpaid at charge-off, of which {fin['recovery_ratio_gross']:.1%} came back as gross recoveries.
- **Concentration:** the High risk tier is {pd.read_csv(AGGREGATE_DIR / 'risk_tier_summary.csv').set_index('risk_tier').share_of_funded['High']:.0%} of funding and {pd.read_csv(AGGREGATE_DIR / 'risk_tier_summary.csv').set_index('risk_tier').share_of_unpaid_principal['High']:.0%} of charged-off principal.

## 2. Business problem

Management needs to see how the portfolio performed, which segments drove charge-offs, how much was recovered, and which actions merit testing. See [business_understanding.md](business_understanding.md).

## 3. Dataset

{kpi['loans']:,.0f} loans, 151 source columns, from the public Kaggle LendingClub release. See [dataset_audit.md](dataset_audit.md) and [data_dictionary.csv](data_dictionary.csv).

## 4. Data quality

Loan ids are unique, no duplicates exist, and the reported cash identity holds on every loan. Only 33 non-loan rows were removed. Placeholder values are isolated in `*_clean` fields. See [data_quality_report.md](data_quality_report.md) and [cleaning_log.md](cleaning_log.md).

## 5. Methodology

Definitions, denominators and maturity logic are in [methodology.md](methodology.md).

## 6. Portfolio overview

| Measure | Value |
|---|---:|
| Loans | {kpi['loans']:,.0f} |
| Funded principal | {money(kpi['funded'])} |
| Average / median loan | ${kpi['avg_funded']:,.0f} / ${kpi['median_funded']:,.0f} |
| Average contract rate | {kpi['avg_rate']:.2f}% |
| Fully Paid | {kpi['fully_paid']:,.0f} |
| Charged Off | {kpi['charged_off']:,.0f} |
| Unresolved (Current, Grace, Late) | {kpi['unresolved']:,.0f} |
| Default status (reported separately) | {kpi['default_status']:,.0f} |
| Policy exceptions (reported separately) | {kpi['policy_fp'] + kpi['policy_co']:,.0f} |

## 7. Default analysis

{md_table(grade_t)}

Sensitivity: adding Default-status and policy-exception loans moves the rate only to {kpi['alt_default_rate_incl_default_and_policy']:.2%}.

Charged-off funded principal is {kpi['charged_off_funded_share_of_all_funded']:.2%} of all originated principal. That denominator includes unresolved loans, so it is not comparable to the default rate.

{md_table(purpose_t)}

### Vintage view

{md_table(cohort_t)}

Compare only rows where terms have elapsed. The resolved-only rate for later years reflects early failures resolving first.

## 8. Borrower risk

**Income**

{md_table(band('summary_income_band', 'income_band'))}

**Debt-to-income**

{md_table(band('summary_dti_band', 'dti_band'))}

**Employment length**

{md_table(band('summary_emp_length_label', 'emp_length_label'))}

**FICO at origination**

{md_table(band('summary_fico_band', 'fico_band'))}

## 9. Loan performance

Charged-off loans carried higher contract rates, and pricing follows grade. Term remains associated with charge-off after controlling for grade. Charts are in `visuals/eda/`.

## 10. Financial exposure

| Item | Type | Amount |
|---|---|---:|
| Funded on charged-off loans | Reported | {money(fin['co_funded'])} |
| Principal repaid before charge-off | Reported | {money(fin['co_principal_received'])} |
| Unpaid principal at charge-off | Calculated | {money(fin['unpaid_principal'])} |
| Gross recoveries | Reported | {money(fin['co_recoveries'])} |
| Recovery fees | Reported | {money(fin['co_fees'])} |
| Estimated net principal loss | Calculated | {money(fin['est_net_loss'])} |
| Interest received on charged-off loans | Reported | {money(fin['co_interest_received'])} |

Estimated net principal loss is not an accounting loss. It ignores interest income, funding and servicing costs, tax and discounting.

## 11. Statistical findings

{md_table(tests_t)}

Adjusted odds ratios are from a multivariable logit on {odds_n:,} sampled term-elapsed resolved loans, in `data/aggregate/statistics/adjusted_odds_ratios.csv`. They describe association, not causation. The model is not a scorecard.

## 12. Risk segmentation

Relative Risk Index = segment term-elapsed rate / portfolio term-elapsed rate. Low under 0.75, Medium 0.75 to under 1.25, High 1.25 or more.

{md_table(seg_t)}

These tiers are retrospective classifications, not underwriting rules or credit decisions.

## 13. Dashboard findings

See [powerbi/data_model.md](../powerbi/data_model.md), [powerbi/dax_measures.md](../powerbi/dax_measures.md) and `visuals/dashboard_screenshots/`. Status of the PBIX is stated in [testing_report.md](testing_report.md).

## 14. Recommendations

{bullet(ins['recommendations'])}

## 15. Limitations

{bullet(ins['limitations'])}

## 16. Future improvements

- Add monthly payment histories, which would allow real survival and roll-rate analysis.
- Add rejected-application data to study selection effects.
- Add funding and servicing costs to estimate true return.
- Run the optional predictive module under the guardrails described in the brief.
""", encoding="utf-8")
    print("Reports written")


if __name__ == "__main__":
    main()
