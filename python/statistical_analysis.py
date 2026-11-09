"""Phase 5: hypothesis tests, confidence intervals, correlation, outliers, adjusted odds ratios.

With over a million resolved loans almost any difference reaches p < 0.001, so every test
reports an effect size and the business reading depends on the effect, not the p-value.
Full-population tests use exact group counts. Loan-level tests needing a rank or a model use
a seeded random sample, whose size is stated in the result.
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import statsmodels.formula.api as smf
from scipy import stats as st
from statsmodels.stats.contingency_tables import StratifiedTable

from analysis_common import ORDERS, analytical_src, save, segment_metrics, style, wilson_ci
from config import STATS_DIR, connect, ensure_dirs, get_logger

log = get_logger("statistical_analysis")
SEED = 42
SAMPLE_PPM = 225_000  # about 22.5% of resolved loans
RECOVERY_SAMPLE_PPM = 400_000  # about 40% of charged-off loans
ALPHA = 0.05
CORR_COLUMNS = ["default_flag", "int_rate", "funded_amnt", "annual_inc_clean", "dti_clean", "fico_mid", "term_months",
                "credit_history_years", "revol_util", "inq_last_6mths", "delinq_2yrs", "pub_rec", "open_acc", "emp_length_years"]
OUTLIER_COLUMNS = ["funded_amnt", "int_rate", "annual_inc", "dti", "revol_util", "revol_bal", "open_acc", "delinq_2yrs", "pub_rec", "total_acc"]

tests: list[dict] = []


def add_test(name, h0, h1, test, why, assumptions, statistic, p, effect, reading, n) -> None:
    tests.append({"test_name": name, "null_hypothesis": h0, "alternative_hypothesis": h1, "test": test, "why_selected": why,
                  "assumption_check": assumptions, "statistic": statistic, "p_value": p, "effect_size": effect,
                  "business_reading": reading, "n": n, "significant_bonferroni": None})
    log.info("%s: stat=%.4g p=%.3g effect=%s", name, statistic, p, effect)


def chi_square_block(frame, label, h0, h1, reading_fn) -> None:
    """Pearson chi-square of independence with Cramer's V and expected-count check."""
    table = np.vstack([frame.charged_off.values, frame.fully_paid.values])
    chi2, p, dof, expected = st.chi2_contingency(table)
    n = table.sum()
    v = float(np.sqrt(chi2 / (n * (min(table.shape) - 1))))
    add_test(label, h0, h1, f"Pearson chi-square (df={dof})", "Two categorical variables with independent loan outcomes",
             f"Minimum expected cell count {expected.min():,.0f} (needs >= 5)", float(chi2), float(p),
             f"Cramer's V = {v:.3f}", reading_fn(v, frame), int(n))


def cochran_armitage(frame) -> tuple[float, float]:
    """Cochran-Armitage test for a linear trend in proportions over ordered bands."""
    w = np.arange(len(frame), dtype=float)
    n = frame.resolved.values.astype(float)
    r = frame.charged_off.values.astype(float)
    N, R = n.sum(), r.sum()
    t = (w * (r - n * R / N)).sum()
    var = (R / N) * (1 - R / N) * ((w**2 * n).sum() - (w * n).sum() ** 2 / N)
    z = t / np.sqrt(var)
    return float(z), float(2 * st.norm.sf(abs(z)))


def run_tests(con, src, sample) -> None:
    grade = segment_metrics(con, "grade", src)
    chi_square_block(grade, "Grade vs charge-off", "Charge-off is independent of grade", "Charge-off depends on grade",
                     lambda v, f: f"Moderate association and the strongest single segmenter: rate rises from {f.default_rate.iloc[0]:.1%} (A) to {f.default_rate.iloc[-1]:.1%} (G).")

    term = segment_metrics(con, "term_months", src)
    chi_square_block(term, "Term vs charge-off (all resolved)", "Charge-off is independent of term", "Charge-off depends on term",
                     lambda v, f: f"Unadjusted rate is {f.default_rate.iloc[0]:.1%} for 36 months against {f.default_rate.iloc[1]:.1%} for 60 months; see the grade-stratified test.")

    # Term controlling for grade: 36/60-month charge-off in each grade, mature loans only.
    cells = segment_metrics(con, ["grade", "term_months"], src)
    tables = []
    for g in ORDERS["grade"]:
        c = cells[cells.grade == g].sort_values("term_months")
        m60, m36 = c.iloc[1], c.iloc[0]
        tables.append(np.array([[m60.mature_charged_off, m60.mature_resolved - m60.mature_charged_off],
                                [m36.mature_charged_off, m36.mature_resolved - m36.mature_charged_off]]))
    strat = StratifiedTable(tables)
    res = strat.test_null_odds()
    lo, hi = strat.oddsratio_pooled_confint()
    homog = strat.test_equal_odds()
    add_test("Term vs charge-off, stratified by grade (mature loans)", "Common odds ratio of 60 vs 36 months equals 1 within grades",
             "Common odds ratio differs from 1", "Cochran-Mantel-Haenszel", "Isolates term from grade mix, because 60-month loans skew to lower grades",
             f"Breslow-Day-type homogeneity p={homog.pvalue:.3g}: when small, the pooled ratio is an average across differing grades",
             float(res.statistic), float(res.pvalue), f"Pooled odds ratio {strat.oddsratio_pooled:.2f} (95% CI {lo:.2f}-{hi:.2f})",
             f"Within the same grade, 60-month loans have about {strat.oddsratio_pooled:.2f} times the odds of charge-off, so the term effect is smaller than the raw gap but still material.",
             int(sum(t.sum() for t in tables)))

    for dim, label, word in (("dti_band", "DTI band trend", "DTI"), ("income_band", "Income band trend", "income"), ("fico_band", "FICO band trend", "FICO")):
        frame = segment_metrics(con, dim, src)
        frame = frame[frame[dim] != "Unknown"]
        z, p = cochran_armitage(frame)
        add_test(label, f"No linear trend in charge-off rate across ordered {word} bands", "A linear trend exists", "Cochran-Armitage trend",
                 "Bands are ordered, so a trend test is more powerful than an unordered chi-square",
                 f"Group sizes {frame.resolved.min():,.0f}-{frame.resolved.max():,.0f}; large-sample normal approximation holds. 'Unknown' excluded",
                 z, p, f"Rate {frame.default_rate.iloc[0]:.1%} to {frame.default_rate.iloc[-1]:.1%}",
                 f"Charge-off moves steadily across {word} bands from {frame.default_rate.iloc[0]:.1%} to {frame.default_rate.iloc[-1]:.1%}. This is an association, not proof that {word} causes default.",
                 int(frame.resolved.sum()))

    emp = segment_metrics(con, "emp_length_label", src)
    emp_known = emp[emp.emp_length_label != "Unknown"]
    chi_square_block(emp_known, "Employment length (known values) vs charge-off", "Charge-off is independent of employment length", "Charge-off depends on employment length",
                     lambda v, f: f"Statistically detectable but practically negligible (V={v:.3f}); rates span only {f.default_rate.min():.1%}-{f.default_rate.max():.1%}. Missing employment length ({emp[emp.emp_length_label=='Unknown'].default_rate.iloc[0]:.1%}) separates more than any stated length.")

    # Verification appears riskier raw; check inside each grade.
    ver = segment_metrics(con, ["grade", "verification_status"], src)
    ver["verified_any"] = ver.verification_status != "Not Verified"
    agg = ver.groupby(["grade", "verified_any"], as_index=False)[["charged_off", "fully_paid"]].sum()
    tables = []
    for g in ORDERS["grade"]:
        a = agg[agg.grade == g].sort_values("verified_any", ascending=False)
        tables.append(a[["charged_off", "fully_paid"]].values.astype(float))
    strat2 = StratifiedTable(tables)
    res2 = strat2.test_null_odds()
    lo2, hi2 = strat2.oddsratio_pooled_confint()
    add_test("Income verification vs charge-off, stratified by grade", "Common odds ratio of verified vs not verified equals 1 within grades", "Common odds ratio differs from 1",
             "Cochran-Mantel-Haenszel", "Verification is targeted at riskier applicants, so raw comparison is confounded with grade",
             "Large cell counts in every grade stratum", float(res2.statistic), float(res2.pvalue),
             f"Pooled odds ratio {strat2.oddsratio_pooled:.2f} (95% CI {lo2:.2f}-{hi2:.2f})",
             "Pooled across grades, verified loans carry higher charge-off odds. Verification is not evidence of lower risk here; a plausible explanation is that it targets applicants already considered riskier (selection), which this data cannot confirm.",
             int(sum(t.sum() for t in tables)))

    # Interest rate by outcome: Welch from exact group moments.
    m = con.execute(f"""SELECT is_charged_off, COUNT(*) n, AVG(int_rate) mean, VAR_SAMP(int_rate) var FROM {src}
                        WHERE is_resolved=1 GROUP BY 1 ORDER BY 1""").df()
    t, p = st.ttest_ind_from_stats(m["mean"][1], np.sqrt(m["var"][1]), m["n"][1], m["mean"][0], np.sqrt(m["var"][0]), m["n"][0], equal_var=False)
    pooled = np.sqrt((m["var"][0] + m["var"][1]) / 2)
    d = (m["mean"][1] - m["mean"][0]) / pooled
    mw_a = sample[sample.default_flag == 1].int_rate
    mw_b = sample[sample.default_flag == 0].int_rate
    u, up = st.mannwhitneyu(mw_a, mw_b, alternative="two-sided")
    auc = u / (len(mw_a) * len(mw_b))
    add_test("Interest rate: Charged Off vs Fully Paid", "Mean interest rate is equal for both outcomes", "Means differ", "Welch t-test, with Mann-Whitney on a sample as a robustness check",
             "Compares a continuous value between two groups with unequal variances",
             f"Rates are not normal, but n is huge so the mean is approximately normal (CLT); Mann-Whitney on {len(sample):,} sampled loans p={up:.3g} agrees",
             float(t), float(p), f"Cohen's d = {d:.2f}; rank AUC = {auc:.2f}",
             f"Charged-off loans carried {m['mean'][1] - m['mean'][0]:.2f} percentage points higher rates on average. Pricing reflects risk ordering, and it also raises the payment burden; the direction of cause cannot be separated here.",
             int(m.n.sum()))

    # Recovery ratio by grade (loan-level, charged-off with positive unpaid principal).
    rec = con.execute(f"""SELECT grade, recoveries / unpaid_principal_at_chargeoff AS ratio FROM {src}
                          WHERE is_charged_off=1 AND unpaid_principal_at_chargeoff > 0
                            AND hash(id + {SEED}) % 1000000 < {RECOVERY_SAMPLE_PPM}""").df()
    groups = [g.ratio.values for _, g in rec.groupby("grade")]
    h, p = st.kruskal(*groups)
    eps2 = (h - len(groups) + 1) / (len(rec) - len(groups))
    add_test("Loan-level recovery ratio across grades", "Recovery-ratio distribution is the same across grades", "At least one grade differs", "Kruskal-Wallis",
             "Ratios are heavily zero-inflated and non-normal, so a rank test fits better than ANOVA",
             f"Independent samples; {len(rec):,} sampled charged-off loans; {(rec.ratio == 0).mean():.0%} have zero recovery", float(h), float(p),
             f"Epsilon-squared = {eps2:.4f}", "Differences across grades are real but tiny, so recovery does not offset the higher charge-off rates of riskier grades.", len(rec))

    frame = pd.DataFrame(tests)
    frame["bonferroni_alpha"] = ALPHA / len(frame)
    frame["significant_bonferroni"] = frame.p_value < frame.bonferroni_alpha
    # scipy returns exactly 0 when a p-value underflows double precision.
    frame["p_value_display"] = frame.p_value.map(lambda v: "<1e-300" if v == 0 else f"{v:.3g}")
    frame.to_csv(STATS_DIR / "hypothesis_tests.csv", index=False)


def confidence_intervals(con, src) -> None:
    rows = []
    def add(label, where):
        e, n = con.execute(f"SELECT SUM(is_charged_off), SUM(is_resolved) FROM {src} WHERE {where}").fetchone()
        lo, hi = wilson_ci(e, n)
        rows.append({"estimate": label, "charged_off": int(e), "resolved": int(n), "default_rate": e / n, "ci_low_95": float(lo), "ci_high_95": float(hi)})
    add("All resolved loans (primary)", "1=1")
    add("Mature loans only", "is_term_elapsed=1")
    for g in ORDERS["grade"]:
        add(f"Grade {g}", f"grade='{g}'")
    for t in (36, 60):
        add(f"Term {t} months", f"term_months={t}")
        add(f"Term {t} months, mature", f"term_months={t} AND is_term_elapsed=1")
    add("Small Business", "purpose_label='Small Business'")
    add("Debt Consolidation", "purpose_label='Debt Consolidation'")
    pd.DataFrame(rows).to_csv(STATS_DIR / "confidence_intervals.csv", index=False)


def correlations(sample) -> None:
    corr = sample[CORR_COLUMNS].corr(method="spearman")
    corr.to_csv(STATS_DIR / "spearman_correlation.csv")
    fig, ax = plt.subplots(figsize=(9, 7.4))
    sns.heatmap(corr, cmap=sns.diverging_palette(245, 15, s=70, l=45, as_cmap=True), center=0, vmin=-1, vmax=1, annot=True, fmt=".2f",
                annot_kws={"size": 7.5}, linewidths=0.5, ax=ax, cbar_kws={"shrink": 0.7, "label": "Spearman rho"})
    ax.grid(False)
    ax.set_title(f"Spearman correlation of origination fields and charge-off\nSeeded sample of {len(sample):,} resolved loans; pairwise complete", fontsize=11)
    save(fig, "s_correlation_heatmap")
    ranked = corr["default_flag"].drop("default_flag").sort_values(key=np.abs, ascending=False)
    log.info("Correlation with default:\n%s", ranked.round(3).to_string())


def outliers(con, src) -> None:
    rows = []
    for col in OUTLIER_COLUMNS:
        r = con.execute(f"""SELECT COUNT({col}), QUANTILE_CONT({col},0.25), QUANTILE_CONT({col},0.5), QUANTILE_CONT({col},0.75), MAX({col}),
                            AVG({col}), STDDEV({col}), SKEWNESS({col}), KURTOSIS({col}) FROM {src}""").fetchone()
        n, q1, q2, q3, mx, mean, sd, skew, kurt = r
        upper, lower = q3 + 1.5 * (q3 - q1), q1 - 1.5 * (q3 - q1)
        count = con.execute(f"SELECT COUNT(*) FROM {src} WHERE {col} > {upper} OR {col} < {lower}").fetchone()[0]
        rows.append({"column": col, "n": n, "q1": q1, "median": q2, "q3": q3, "max": mx, "mean": mean, "sd": sd, "skewness": skew, "excess_kurtosis": kurt,
                     "iqr_upper_fence": upper, "iqr_outliers": count, "iqr_outlier_pct": count / n})
    frame = pd.DataFrame(rows)
    frame.to_csv(STATS_DIR / "distribution_outliers.csv", index=False)
    log.info("Outliers:\n%s", frame[["column", "skewness", "iqr_outlier_pct", "max"]].round(3).to_string())


def adjusted_odds(sample) -> None:
    """Multivariable logit: association after adjusting for other origination fields. Not a scoring model."""
    data = sample[(sample.is_term_elapsed == 1)].dropna(subset=["annual_inc_clean", "dti_clean", "fico_mid"]).copy()
    data["log_income"] = np.log(data.annual_inc_clean.clip(lower=1000))
    data["term60"] = (data.term_months == 60).astype(int)
    for col, unit in (("dti_clean", 10), ("fico_mid", 20), ("log_income", 1)):
        data[col + "_scaled"] = data[col] / unit
    model = smf.logit("default_flag ~ C(grade, Treatment('A')) + term60 + dti_clean_scaled + fico_mid_scaled + log_income_scaled", data=data).fit(disp=False)
    ci = model.conf_int()
    out = pd.DataFrame({"term": model.params.index, "odds_ratio": np.exp(model.params.values), "ci_low_95": np.exp(ci[0].values), "ci_high_95": np.exp(ci[1].values), "p_value": model.pvalues.values})
    out["n"] = int(model.nobs)
    out["pseudo_r2"] = model.prsquared
    out.to_csv(STATS_DIR / "adjusted_odds_ratios.csv", index=False)
    log.info("Adjusted odds ratios (n=%d):\n%s", model.nobs, out.round(3).to_string())


def check_representative(con, src, sample) -> None:
    """Fail loudly if the sample's year mix or charge-off rate drifts from the population."""
    pop = con.execute(f"SELECT issue_year, COUNT(*) n FROM {src} WHERE is_resolved=1 GROUP BY 1").df().set_index("issue_year").n
    pop_share = pop / pop.sum()
    sample_share = sample.issue_year.value_counts(normalize=True).reindex(pop_share.index).fillna(0)
    worst = float((sample_share - pop_share).abs().max())
    pop_rate = con.execute(f"SELECT SUM(is_charged_off)*1.0/SUM(is_resolved) FROM {src}").fetchone()[0]
    gap = abs(float(sample.default_flag.mean()) - pop_rate)
    log.info("Sample check: worst year-share gap %.5f, default-rate gap %.5f", worst, gap)
    assert worst < 0.005 and gap < 0.005, "Statistical sample is not representative"


def main() -> None:
    ensure_dirs()
    style()
    con = connect()
    src = analytical_src()
    # Hash of the loan id gives a repeatable random sample. DuckDB's reservoir sampling under a
    # parallel scan was found to be badly unrepresentative here (82% of rows from 2015), so it is not used.
    sample = con.execute(f"""SELECT is_charged_off AS default_flag, is_term_elapsed, grade, int_rate, funded_amnt, annual_inc_clean, dti_clean, fico_mid, term_months,
          credit_history_years, revol_util, inq_last_6mths, delinq_2yrs, pub_rec, open_acc, emp_length_years, issue_year
          FROM {src} WHERE is_resolved=1 AND hash(id + {SEED}) % 1000000 < {SAMPLE_PPM}""").df()
    log.info("Sample: %d rows", len(sample))
    check_representative(con, src, sample)
    run_tests(con, src, sample)
    confidence_intervals(con, src)
    correlations(sample)
    outliers(con, src)
    adjusted_odds(sample)
    log.info("Statistical analysis complete; %d tests", len(tests))


if __name__ == "__main__":
    main()
