"""Phase 4: portfolio, default, interest-rate, time and geographic EDA (sections A, B, D, F, G).

Borrower analysis lives in borrower_analysis.py and financials in financial_analysis.py.
Each section writes a CSV under data/aggregate/ and charts under visuals/eda/.
"""
from __future__ import annotations

import json

import matplotlib.pyplot as plt
import numpy as np

from analysis_common import GRID, MUTED, NAVY, RED, TEAL, analytical_src, rate_bars, save, segment_metrics, style
from config import AGGREGATE_DIR, connect, ensure_dirs, get_logger

log = get_logger("eda")


def portfolio_overview(con, src) -> dict:
    row = con.execute(f"""SELECT COUNT(*) loans, SUM(loan_amnt) requested, SUM(funded_amnt) funded,
        SUM(funded_amnt_inv) funded_inv, AVG(funded_amnt) avg_funded, MEDIAN(funded_amnt) median_funded,
        AVG(int_rate) avg_rate, MEDIAN(int_rate) median_rate, MIN(issue_d) first_issue, MAX(issue_d) last_issue,
        SUM(is_fully_paid) fully_paid, SUM(is_charged_off) charged_off, SUM(is_resolved) resolved,
        SUM(CASE WHEN is_resolved=1 THEN funded_amnt END) resolved_funded,
        SUM(CASE WHEN is_charged_off=1 THEN funded_amnt END) charged_off_funded,
        SUM(CASE WHEN is_term_elapsed=1 THEN is_charged_off END) mature_co,
        SUM(CASE WHEN is_term_elapsed=1 THEN is_resolved END) mature_res,
        SUM(is_term_elapsed) mature_loans,
        SUM((status_clean='Default')::INT) default_status,
        SUM((status_clean='Policy Exception - Charged Off')::INT) policy_co,
        SUM((status_clean='Policy Exception - Fully Paid')::INT) policy_fp,
        SUM((status_group='Unresolved')::INT) unresolved,
        SUM(out_prncp) outstanding_principal
        FROM {src}""").df().iloc[0].to_dict()
    row = {k: (str(v)[:10] if "issue" in k else float(v)) for k, v in row.items()}
    row["default_rate"] = row["charged_off"] / row["resolved"]
    row["principal_weighted_rate"] = row["charged_off_funded"] / row["resolved_funded"]
    row["charged_off_funded_share_of_all_funded"] = row["charged_off_funded"] / row["funded"]
    row["mature_default_rate"] = row["mature_co"] / row["mature_res"]
    # Alternative definition, reported only as a sensitivity check.
    row["alt_default_rate_incl_default_and_policy"] = (row["charged_off"] + row["default_status"] + row["policy_co"]) / (
        row["resolved"] + row["default_status"] + row["policy_co"] + row["policy_fp"])
    (AGGREGATE_DIR / "portfolio_kpis.json").write_text(json.dumps(row, indent=2))
    log.info("Portfolio KPIs: %s", {k: round(v, 4) if isinstance(v, float) else v for k, v in row.items()})
    return row


def section_a(con, src, kpi) -> None:
    status = con.execute(f"""SELECT status_clean, status_group, COUNT(*) loans, SUM(funded_amnt) funded_amount,
        SUM(out_prncp) outstanding_principal FROM {src} GROUP BY 1,2 ORDER BY loans DESC""").df()
    status["share_of_loans"] = status.loans / status.loans.sum()
    status.to_csv(AGGREGATE_DIR / "status_summary.csv", index=False)

    amounts = con.execute(f"""SELECT MIN(funded_amnt) min, QUANTILE_CONT(funded_amnt,0.25) p25, MEDIAN(funded_amnt) p50,
        QUANTILE_CONT(funded_amnt,0.75) p75, MAX(funded_amnt) max, STDDEV(funded_amnt) sd FROM {src}""").df()
    amounts.to_csv(AGGREGATE_DIR / "loan_amount_distribution.csv", index=False)

    fig, ax = plt.subplots(figsize=(8.2, 3.8))
    hist = con.execute(f"SELECT FLOOR(funded_amnt/1000)*1000 b, COUNT(*) n FROM {src} GROUP BY 1 ORDER BY 1").df()
    ax.bar(hist.b / 1000, hist.n / 1000, width=0.85, color=NAVY)
    ax.axvline(kpi["median_funded"] / 1000, color=RED, ls="--", lw=1.5, label=f"Median ${kpi['median_funded']:,.0f}")
    ax.set_xlabel("Funded amount ($000, $1K bins)"); ax.set_ylabel("Loans (000)")
    ax.set_title("Round-number loan sizes dominate: spikes at $10K, $12K, $15K, $20K"); ax.legend()
    save(fig, "a_loan_amount_distribution")

    fig, ax = plt.subplots(figsize=(8.2, 3.8))
    s = status.sort_values("loans")
    ax.barh(s.status_clean, s.loans / 1000, color=NAVY, height=0.68)
    ax.grid(axis="x", color=GRID); ax.grid(axis="y", visible=False); ax.set_xlabel("Loans (000)")
    ax.set_title("Portfolio status: only resolved loans enter the primary default rate")
    save(fig, "a_status_distribution")


def section_b(con, src, kpi) -> None:
    base = kpi["default_rate"]
    for dim in ("grade", "sub_grade", "term_months", "purpose_label"):
        frame = segment_metrics(con, dim, src)
        frame.to_csv(AGGREGATE_DIR / f"summary_{dim}.csv", index=False)
    grade = segment_metrics(con, "grade", src)
    rate_bars(grade, "grade", "Charge-off rate climbs steadily from grade A to G",
              "Resolved loans; whiskers show 95% Wilson CI", benchmark=base, name="b_default_by_grade")
    sub = segment_metrics(con, "sub_grade", src)
    fig, ax = plt.subplots(figsize=(11, 3.8))
    ax.bar(sub.sub_grade, sub.default_rate * 100, color=NAVY, width=0.7)
    ax.axhline(base * 100, color=RED, ls="--", lw=1.5, label=f"Portfolio {base:.1%}")
    ax.tick_params(axis="x", labelsize=7.5); ax.set_ylabel("Default rate (%)"); ax.legend(loc="upper left")
    ax.set_title("Subgrades rise almost monotonically; the top of grade G exceeds 50%")
    save(fig, "b_default_by_subgrade")
    purpose = segment_metrics(con, "purpose_label", src).sort_values("default_rate", ascending=False)
    rate_bars(purpose, "purpose_label", "Small-business loans default most often", "Resolved loans; 95% Wilson CI",
              benchmark=base, name="b_default_by_purpose", horizontal=True)
    term = segment_metrics(con, ["grade", "term_months"], src)
    fig, ax = plt.subplots(figsize=(8.2, 3.8))
    width = 0.38
    x = np.arange(7)
    for i, (months, color) in enumerate(((36, NAVY), (60, TEAL))):
        part = term[term.term_months == months]
        ax.bar(x + (i - 0.5) * width, part.mature_default_rate * 100, width * 0.92, color=color, label=f"{months} months")
    ax.set_xticks(x, list("ABCDEFG")); ax.set_ylabel("Mature-cohort default rate (%)"); ax.legend()
    ax.set_title("60-month loans default more than 36-month loans in almost every grade")
    save(fig, "b_default_by_grade_term")


def section_d(con, src) -> None:
    grade = con.execute(f"""SELECT grade, AVG(int_rate) avg_rate, MIN(int_rate) min_rate, QUANTILE_CONT(int_rate,0.25) p25,
        MEDIAN(int_rate) median_rate, QUANTILE_CONT(int_rate,0.75) p75, MAX(int_rate) max_rate FROM {src} GROUP BY 1 ORDER BY 1""").df()
    grade.to_csv(AGGREGATE_DIR / "interest_rate_by_grade.csv", index=False)
    con.execute(f"""COPY (SELECT status_clean, COUNT(*) loans, AVG(int_rate) avg_rate, MEDIAN(int_rate) median_rate
                          FROM {src} GROUP BY 1 ORDER BY 3 DESC) TO '{(AGGREGATE_DIR / "interest_rate_by_status.csv").as_posix()}' (HEADER)""")
    con.execute(f"""COPY (SELECT purpose_label, term_months, COUNT(*) loans, AVG(int_rate) avg_rate, MEDIAN(int_rate) median_rate
                          FROM {src} GROUP BY 1,2 ORDER BY 1,2) TO '{(AGGREGATE_DIR / "interest_rate_by_purpose_term.csv").as_posix()}' (HEADER)""")
    rate = segment_metrics(con, "rate_band", src)
    rate.to_csv(AGGREGATE_DIR / "summary_rate_band.csv", index=False)
    rate_bars(rate, "rate_band", "Higher contract rates accompany higher charge-off rates",
              "Resolved loans; rate is assigned from risk, so this is not causal", name="d_default_by_rate_band")

    fig, ax = plt.subplots(figsize=(8.2, 3.8))
    stats_rows = [{"label": r.grade, "whislo": r.min_rate, "q1": r.p25, "med": r.median_rate, "q3": r.p75, "whishi": r.max_rate, "fliers": []}
                  for r in grade.itertuples()]
    ax.bxp(stats_rows, showfliers=False, patch_artist=True, boxprops={"facecolor": NAVY, "edgecolor": NAVY},
           medianprops={"color": "white", "lw": 1.5}, whiskerprops={"color": MUTED}, capprops={"color": MUTED})
    ax.set_ylabel("Interest rate (%)"); ax.set_title("Pricing separates grades but ranges overlap (min to max whiskers)")
    save(fig, "d_rate_by_grade")


def section_f(con, src) -> None:
    year = segment_metrics(con, "issue_year", src)
    unresolved = con.execute(f"SELECT issue_year, AVG((status_group='Unresolved')::INT) unresolved_share, AVG((status_group='Policy Exception')::INT) policy_exception_share FROM {src} GROUP BY 1").df()
    year = year.merge(unresolved, on="issue_year")
    year["pct_term_elapsed"] = year.mature_loans / year.loans
    year.to_csv(AGGREGATE_DIR / "summary_issue_year.csv", index=False)

    term_year = segment_metrics(con, ["issue_year", "term_months"], src)
    term_year["pct_term_elapsed"] = term_year.mature_loans / term_year.loans
    term_year.to_csv(AGGREGATE_DIR / "summary_issue_year_term.csv", index=False)

    month = con.execute(f"""SELECT issue_year, issue_month, COUNT(*) loans, SUM(funded_amnt) funded_amount FROM {src}
                            GROUP BY 1,2 ORDER BY 1,2""").df()
    month.to_csv(AGGREGATE_DIR / "originations_by_month.csv", index=False)
    mix = con.execute(f"""SELECT issue_year, grade, COUNT(*) loans, AVG(int_rate) avg_rate FROM {src} GROUP BY 1,2 ORDER BY 1,2""").df()
    mix["share"] = mix.loans / mix.groupby("issue_year").loans.transform("sum")
    mix.to_csv(AGGREGATE_DIR / "grade_mix_by_year.csv", index=False)

    fig, ax = plt.subplots(figsize=(8.2, 3.6))
    ax.bar(year.issue_year.astype(str), year.funded_amount / 1e9, color=NAVY, width=0.68)
    ax.set_ylabel("Funded amount ($B)"); ax.set_title("Originations grew from about $5M (2007) to about $8B (2018)")
    save(fig, "f_originations_by_year")

    fig, ax = plt.subplots(figsize=(8.2, 3.8))
    for months, color in ((36, NAVY), (60, TEAL)):
        part = term_year[(term_year.term_months == months) & (term_year.pct_term_elapsed >= 0.99)]
        ax.plot(part.issue_year, part.default_rate * 100, color=color, lw=2, marker="o", ms=6, label=f"{months} months")
    ax.set_ylabel("Default rate (%)"); ax.set_xlabel("Origination year"); ax.legend()
    ax.xaxis.get_major_locator().set_params(integer=True)
    ax.set_title("Mature-cohort charge-off rate, by term\nOnly years where at least 99% of loans have reached scheduled maturity", fontsize=11)
    save(fig, "f_mature_cohort_default")

    fig, ax = plt.subplots(figsize=(8.2, 3.6))
    ax.plot(year.issue_year, year.avg_int_rate, color=NAVY, lw=2, marker="o", ms=6)
    ax.set_ylabel("Average interest rate (%)"); ax.set_xlabel("Origination year")
    ax.set_title("Average contract rate by origination year")
    save(fig, "f_avg_rate_by_year")

    fig, ax = plt.subplots(figsize=(8.2, 3.8))
    pivot = mix.pivot(index="issue_year", columns="grade", values="share").fillna(0)
    groups = {"A-B": ["A", "B"], "C-D": ["C", "D"], "E-G": ["E", "F", "G"]}
    for (label, cols), color in zip(groups.items(), (NAVY, TEAL, RED)):
        ax.plot(pivot.index, pivot[cols].sum(axis=1) * 100, color=color, lw=2, marker="o", ms=6, label=label)
    ax.set_ylabel("Share of loans (%)"); ax.legend(); ax.set_title("Grade mix over time")
    save(fig, "f_grade_mix")

    seasonal = month[month.issue_year.between(2015, 2018)].groupby("issue_month").loans.mean().reset_index()
    fig, ax = plt.subplots(figsize=(8.2, 3.4))
    ax.bar(seasonal.issue_month.astype(str), seasonal.loans / 1000, color=NAVY, width=0.68)
    ax.set_xlabel("Month"); ax.set_ylabel("Avg loans per year (000)")
    ax.set_title("Average originations by calendar month, 2015-2018")
    save(fig, "f_originations_by_month")


def section_g(con, src, kpi) -> None:
    state = segment_metrics(con, "addr_state", src)
    state["share_of_funded"] = state.funded_amount / state.funded_amount.sum()
    state.to_csv(AGGREGATE_DIR / "summary_state.csv", index=False)
    reliable = state[state.resolved >= 1000].sort_values("default_rate", ascending=False)
    log.info("States with <1,000 resolved loans (excluded from ranking): %s",
             state[state.resolved < 1000][["addr_state", "resolved"]].values.tolist())
    rate_bars(reliable.head(15), "addr_state", "Highest state charge-off rates", "States with at least 1,000 resolved loans; correlation only, not causal",
              benchmark=kpi["default_rate"], name="g_default_by_state_top", horizontal=True)
    top = state.sort_values("funded_amount", ascending=False).head(15).sort_values("funded_amount")
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    ax.barh(top.addr_state, top.funded_amount / 1e9, color=NAVY, height=0.68)
    ax.grid(axis="x", color=GRID); ax.grid(axis="y", visible=False); ax.set_xlabel("Funded amount ($B)")
    ax.set_title("California, Texas, New York and Florida carry the largest exposure")
    save(fig, "g_funded_by_state")


def main() -> None:
    ensure_dirs()
    style()
    con = connect()
    src = analytical_src()
    kpi = portfolio_overview(con, src)
    section_a(con, src, kpi)
    section_b(con, src, kpi)
    section_d(con, src)
    section_f(con, src)
    section_g(con, src, kpi)
    log.info("EDA complete")


if __name__ == "__main__":
    main()
