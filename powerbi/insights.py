"""Insight-panel text, computed from analysis outputs so no figure is typed by hand."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from config import AGGREGATE_DIR, STATS_DIR  # noqa: E402


def build_insights() -> dict:
    kpi = json.loads((AGGREGATE_DIR / "portfolio_kpis.json").read_text())
    fin = json.loads((AGGREGATE_DIR / "financial_totals.json").read_text())
    read = lambda name: pd.read_csv(AGGREGATE_DIR / f"{name}.csv")
    grade = read("summary_grade").set_index("grade")
    tier = read("risk_tier_summary").set_index("risk_tier")
    dti = read("summary_dti_band").set_index("dti_band")
    purpose = read("summary_purpose_label").set_index("purpose_label")
    fin_grade = read("financial_grade").set_index("grade")
    term = read("summary_term_months").set_index("term_months")
    settle = read("recoveries_by_settlement").set_index("debt_settlement_flag")
    tests = pd.read_csv(STATS_DIR / "hypothesis_tests.csv").set_index("test_name")
    odds = pd.read_csv(STATS_DIR / "adjusted_odds_ratios.csv").set_index("term")

    zero_recovery = (settle.zero_recovery.sum()) / settle.loans.sum()
    dc = purpose.loc["Debt Consolidation"]
    sb = purpose.loc["Small Business"]
    total_unpaid = fin["unpaid_principal"]
    cd_share = fin_grade.loc[["C", "D"], "share_of_unpaid_principal"].sum()
    efg_funded = fin_grade.loc[["E", "F", "G"], "share_of_funded"].sum()
    efg_loss = fin_grade.loc[["E", "F", "G"], "share_of_unpaid_principal"].sum()

    findings = [
        f"{kpi['default_rate']:.2%} of {kpi['resolved']:,.0f} resolved loans charged off ({kpi['principal_weighted_rate']:.2%} weighted by principal). Term-elapsed loans show {kpi['mature_default_rate']:.2%}, partly because recent resolved loans over-represent early failures.",
        f"Grade is the strongest single segmenter: {grade.default_rate['A']:.1%} (A) to {grade.default_rate['G']:.1%} (G).",
        f"High-tier segments are {tier.share_of_funded['High']:.0%} of funded principal and {tier.share_of_unpaid_principal['High']:.0%} of charged-off principal.",
        f"Grades C and D hold {cd_share:.0%} of charged-off principal; E to G hold {efg_loss:.0%} on {efg_funded:.0%} of funding.",
        f"Debt consolidation holds {dc.unpaid_principal_at_chargeoff / total_unpaid:.0%} of charged-off principal through volume. Small business has the highest rate at {sb.default_rate:.1%}.",
        f"DTI rises from {dti.default_rate['<10']:.1%} under 10 to {dti.default_rate['40+']:.1%} at 40+. After adjusting for grade, term, FICO and income, each 10 DTI points multiply the odds by {odds.odds_ratio['dti_clean_scaled']:.2f}.",
        f"Recoveries return {fin['recovery_ratio_gross']:.1%} of charged-off principal ({fin['recovery_ratio_net']:.1%} after fees), and {zero_recovery:.0%} of charged-off loans recovered nothing.",
    ]
    recommendations = [
        f"Review pricing and limits for High-tier segments first. They carry {tier.share_of_unpaid_principal['High'] / tier.share_of_funded['High']:.1f}x their proportional share of charged-off principal.",
        f"Test tighter 60-month criteria in grades C to E. Term stays material after controlling for grade (pooled odds ratio {tests.effect_size['Term vs charge-off, stratified by grade (mature loans)'].split()[3]}).",
        "Add a DTI overlay inside grades. DTI still separates risk within a grade, so a pilot could test whether grade pricing already captures it fully.",
        f"Monitor debt-consolidation concentration, because its {dc.share_of_funded if 'share_of_funded' in dc else dc.funded_amount / purpose.funded_amount.sum():.0%} funding share drives exposure more than its rate does.",
        f"Review collections strategy. Settled loans recovered {settle.recovery_ratio['Y']:.1%} against {settle.recovery_ratio['N']:.1%} for others; test whether earlier settlement offers improve net recoveries.",
        "Judge new vintages on term-elapsed or seasoned data, never on resolved-only rates.",
        "Treat missing employment length as a data-review flag: it stands apart from every stated length, and the reason needs investigating before any policy use.",
    ]
    limitations = [
        "Accepted loans only, so there is no view of rejected applicants and no causal inference.",
        "Status snapshot of March 2019. Loans still Current or Late are unresolved and excluded from the primary rate.",
        "Calculated exposure and net loss are estimates, not accounting losses: no funding, servicing, tax or provisioning data.",
        "Recoveries have no transaction dates, so trends are by origination year and newer cohorts are immature.",
        "60-month term-elapsed cohorts end in March 2014, so they omit later credit conditions.",
        "Risk tiers are retrospective portfolio classifications, not underwriting rules or individual credit decisions.",
        "No protected characteristics are used. Geography and purpose can still proxy for them, so fair-lending review is required before any policy use.",
    ]
    return {"findings": findings, "recommendations": recommendations, "limitations": limitations}


if __name__ == "__main__":
    print(json.dumps(build_insights(), indent=2))
