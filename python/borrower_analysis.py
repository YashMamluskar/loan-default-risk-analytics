"""Phase 4C: borrower characteristics and loan performance.

Rates here are retrospective associations. Grade already prices most of this risk,
so a grade-controlled view is included to show what each factor adds within a grade.
"""
from __future__ import annotations

import json

import matplotlib.pyplot as plt

from analysis_common import NAVY, RED, TEAL, analytical_src, rate_bars, save, segment_metrics, style
from config import AGGREGATE_DIR, connect, ensure_dirs, get_logger

log = get_logger("borrower_analysis")

DIMENSIONS = {
    "income_band": "Lower-income bands default more often",
    "dti_band": "Charge-off rate rises with debt-to-income ratio",
    "emp_length_label": "Employment length barely separates risk, except when unknown",
    "home_ownership_group": "Renters default more often than mortgage holders",
    "verification_status": "Verified income shows higher default, reflecting who gets verified",
    "fico_band": "Charge-off rate falls steadily as FICO rises",
    "credit_history_band": "Longer credit history is associated with lower default",
    "delinq_band": "Delinquencies in the prior 2 years: modest difference",
    "pub_rec_band": "Public records: modest difference",
    "inquiry_band": "More recent credit inquiries, more default",
    "revol_util_band": "Higher revolving utilisation, more default",
}


def main() -> None:
    ensure_dirs()
    style()
    con = connect()
    src = analytical_src()
    base = json.loads((AGGREGATE_DIR / "portfolio_kpis.json").read_text())["default_rate"]

    frames = {}
    for dim, title in DIMENSIONS.items():
        frame = segment_metrics(con, dim, src)
        frame.to_csv(AGGREGATE_DIR / f"summary_{dim}.csv", index=False)
        frames[dim] = frame
        rate_bars(frame, dim, title, "Resolved loans; 95% Wilson CI", benchmark=base, name=f"c_default_by_{dim}")

    profile = con.execute(f"""SELECT AVG(annual_inc_clean) avg_income, MEDIAN(annual_inc_clean) median_income,
        AVG(dti_clean) avg_dti, MEDIAN(dti_clean) median_dti, AVG(emp_length_years) avg_emp_years,
        AVG(fico_mid) avg_fico, AVG(credit_history_years) avg_history_years FROM {src}""").df()
    profile.to_csv(AGGREGATE_DIR / "borrower_profile.csv", index=False)
    log.info("Borrower profile: %s", profile.round(2).to_dict("records")[0])

    outcome = con.execute(f"""SELECT status_clean, COUNT(*) loans, MEDIAN(annual_inc_clean) median_income, AVG(dti_clean) avg_dti,
        AVG(fico_mid) avg_fico, AVG(int_rate) avg_rate, AVG(funded_amnt) avg_funded FROM {src}
        WHERE is_resolved=1 GROUP BY 1""").df()
    outcome.to_csv(AGGREGATE_DIR / "borrower_profile_by_outcome.csv", index=False)
    log.info("By outcome:\n%s", outcome.round(2).to_string())

    # Does a factor still separate risk inside a grade?
    within = segment_metrics(con, ["grade", "dti_band"], src)
    within.to_csv(AGGREGATE_DIR / "summary_grade_dti.csv", index=False)
    within2 = segment_metrics(con, ["grade", "income_band"], src)
    within2.to_csv(AGGREGATE_DIR / "summary_grade_income.csv", index=False)

    fig, ax = plt.subplots(figsize=(8.2, 4))
    bands = ["<10", "10-20", "20-30", "30-40", "40+"]
    series = {"B": NAVY, "D": TEAL, "F": RED}
    for grade, color in series.items():
        part = within[(within.grade == grade) & within.dti_band.isin(bands)].set_index("dti_band").loc[bands]
        ax.plot(bands, part.default_rate * 100, color=color, lw=2, marker="o", ms=6, label=f"Grade {grade}")
    ax.set_xlabel("DTI band"); ax.set_ylabel("Default rate (%)"); ax.legend()
    ax.set_title("DTI still separates risk within a grade")
    save(fig, "c_dti_within_grade")
    log.info("Borrower analysis complete")


if __name__ == "__main__":
    main()
