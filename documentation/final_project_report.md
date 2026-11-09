# Loan Default Risk Intelligence and Credit Portfolio Analytics

Final project report. All figures are generated from the pipeline outputs.

## 1. Executive summary

LendingClub's accepted-loan file holds 2,260,668 loans and $34.00B of funded principal, issued June 2007 to December 2018, with status as of March 2019.

- **Primary default rate:** 19.96% of 1,345,310 resolved loans charged off (21.55% weighted by principal).
- **Less biased view:** 15.15% on loans whose full term has elapsed. Rates based only on resolved loans overstate recent cohorts.
- **Charged-off principal:** $3.00B unpaid at charge-off, of which 10.8% came back as gross recoveries.
- **Concentration:** the High risk tier is 39% of funding and 66% of charged-off principal.

## 2. Business problem

Management needs to see how the portfolio performed, which segments drove charge-offs, how much was recovered, and which actions merit testing. See [business_understanding.md](business_understanding.md).

## 3. Dataset

2,260,668 loans, 151 source columns, from the public Kaggle LendingClub release. See [dataset_audit.md](dataset_audit.md) and [data_dictionary.csv](data_dictionary.csv).

## 4. Data quality

Loan ids are unique, no duplicates exist, and the reported cash identity holds on every loan. Only 33 non-loan rows were removed. Placeholder values are isolated in `*_clean` fields. See [data_quality_report.md](data_quality_report.md) and [cleaning_log.md](cleaning_log.md).

## 5. Methodology

Definitions, denominators and maturity logic are in [methodology.md](methodology.md).

## 6. Portfolio overview

| Measure | Value |
|---|---:|
| Loans | 2,260,668 |
| Funded principal | $34.00B |
| Average / median loan | $15,042 / $12,875 |
| Average contract rate | 13.09% |
| Fully Paid | 1,076,751 |
| Charged Off | 268,559 |
| Unresolved (Current, Grace, Late) | 912,569 |
| Default status (reported separately) | 40 |
| Policy exceptions (reported separately) | 2,749 |

## 7. Default analysis

| Grade | Loans | Resolved | Default rate | Principal-weighted | Mature rate | Avg rate |
|---|---|---|---|---|---|---|
| A | 433,027 | 235,090 | 6.04% | 5.97% | 5.51% | 7.08% |
| B | 663,557 | 392,741 | 13.39% | 13.71% | 11.55% | 10.68% |
| C | 650,053 | 381,686 | 22.44% | 23.33% | 18.68% | 14.14% |
| D | 324,424 | 200,953 | 30.38% | 31.85% | 24.48% | 18.14% |
| E | 135,639 | 93,650 | 38.48% | 39.66% | 30.44% | 21.83% |
| F | 41,800 | 32,058 | 45.20% | 46.40% | 35.25% | 25.45% |
| G | 12,168 | 9,132 | 49.93% | 49.73% | 39.02% | 28.07% |

Sensitivity: adding Default-status and policy-exception loans moves the rate only to 19.98%.

Charged-off funded principal is 12.29% of all originated principal. That denominator includes unresolved loans, so it is not comparable to the default rate.

| Purpose | Resolved | Default rate | Charged-off principal |
|---|---|---|---|
| Small Business | 15,416 | 29.7% | $58.4M |
| Renewable Energy | 933 | 23.7% | $1.8M |
| Moving | 9,480 | 23.4% | $14.9M |
| House | 7,253 | 21.9% | $19.8M |
| Medical | 15,554 | 21.8% | $26.1M |
| Debt Consolidation | 780,321 | 21.1% | $1.93B |
| Other | 77,875 | 21.0% | $139.8M |
| Vacation | 9,065 | 19.2% | $10.3M |
| Major Purchase | 29,425 | 18.6% | $63.1M |
| Home Improvement | 87,504 | 17.7% | $182.7M |
| Educational | 326 | 17.2% | $0.2M |
| Credit Card | 295,279 | 16.9% | $538.5M |
| Car | 14,585 | 14.7% | $15.8M |
| Wedding | 2,294 | 12.2% | $2.2M |

### Vintage view

| Year | Loans | Funded | Term elapsed | Resolved-only rate | Term-elapsed rate |
|---|---|---|---|---|---|
| 2007 | 603 | $4.8M | 100% | 17.9% | 17.9% |
| 2008 | 2,393 | $20.0M | 100% | 15.8% | 15.8% |
| 2009 | 5,281 | $51.8M | 100% | 12.6% | 12.6% |
| 2010 | 12,537 | $126.4M | 100% | 12.9% | 12.9% |
| 2011 | 21,721 | $257.4M | 100% | 15.2% | 15.2% |
| 2012 | 53,367 | $717.9M | 100% | 16.2% | 16.2% |
| 2013 | 134,814 | $1.98B | 100% | 15.6% | 15.6% |
| 2014 | 235,629 | $3.50B | 75% | 18.4% | 14.6% |
| 2015 | 421,095 | $6.42B | 67% | 20.2% | 14.9% |
| 2016 | 434,407 | $6.40B | 22% | 23.3% | 16.1% |
| 2017 | 443,579 | $6.58B | 0% | 23.1% | n/a |
| 2018 | 495,242 | $7.94B | 0% | 15.7% | n/a |

Compare only rows where terms have elapsed. The resolved-only rate for later years reflects early failures resolving first.

## 8. Borrower risk

**Income**

| Band | Resolved | Default rate |
|---|---|---|
| <$40K | 210,013 | 23.8% |
| $40K-$60K | 355,532 | 21.7% |
| $60K-$80K | 307,925 | 20.1% |
| $80K-$100K | 194,544 | 18.3% |
| $100K-$150K | 192,751 | 16.4% |
| $150K+ | 84,184 | 14.9% |
| Unknown | 361 | 18.8% |

**Debt-to-income**

| Band | Resolved | Default rate |
|---|---|---|
| <10 | 245,712 | 14.9% |
| 10-20 | 561,904 | 17.8% |
| 20-30 | 408,641 | 23.0% |
| 30-40 | 121,907 | 29.1% |
| 40+ | 6,732 | 30.6% |
| Unknown | 414 | 19.3% |

**Employment length**

| Band | Resolved | Default rate |
|---|---|---|
| < 1 year | 108,061 | 20.5% |
| 1 year | 88,494 | 20.6% |
| 2 years | 121,743 | 19.8% |
| 3 years | 107,597 | 20.0% |
| 4 years | 80,556 | 19.7% |
| 5 years | 84,154 | 19.6% |
| 6 years | 62,733 | 19.4% |
| 7 years | 59,624 | 19.5% |
| 8 years | 60,701 | 19.9% |
| 9 years | 50,937 | 19.9% |
| 10+ years | 442,199 | 18.8% |
| Unknown | 78,511 | 26.9% |

**FICO at origination**

| Band | Resolved | Default rate |
|---|---|---|
| 660-679 | 459,480 | 25.3% |
| 680-699 | 361,326 | 21.4% |
| 700-719 | 246,203 | 17.3% |
| 720-749 | 171,700 | 13.3% |
| 750+ | 106,601 | 8.9% |

## 9. Loan performance

Charged-off loans carried higher contract rates, and pricing follows grade. Term remains associated with charge-off after controlling for grade. Charts are in `visuals/eda/`.

## 10. Financial exposure

| Item | Type | Amount |
|---|---|---:|
| Funded on charged-off loans | Reported | $4.18B |
| Principal repaid before charge-off | Reported | $1.18B |
| Unpaid principal at charge-off | Calculated | $3.00B |
| Gross recoveries | Reported | $324.8M |
| Recovery fees | Reported | $54.1M |
| Estimated net principal loss | Calculated | $2.73B |
| Interest received on charged-off loans | Reported | $722.2M |

Estimated net principal loss is not an accounting loss. It ignores interest income, funding and servicing costs, tax and discounting.

## 11. Statistical findings

| Test | Method | p | Effect | Reading |
|---|---|---|---|---|
| Grade vs charge-off | Pearson chi-square (df=6) | <1e-300 | Cramer's V = 0.262 | Moderate association and the strongest single segmenter: rate rises from 6.0% (A) to 49.9% (G). |
| Term vs charge-off (all resolved) | Pearson chi-square (df=1) | <1e-300 | Cramer's V = 0.176 | Unadjusted rate is 16.0% for 36 months against 32.4% for 60 months; see the grade-stratified test. |
| Term vs charge-off, stratified by grade (mature loans) | Cochran-Mantel-Haenszel | <1e-300 | Pooled odds ratio 1.19 (95% CI 1.17-1.21) | Within the same grade, 60-month loans have about 1.19 times the odds of charge-off, so the term effect is smaller than the raw gap but still material. |
| DTI band trend | Cochran-Armitage trend | <1e-300 | Rate 14.9% to 30.6% | Charge-off moves steadily across DTI bands from 14.9% to 30.6%. This is an association, not proof that DTI causes default. |
| Income band trend | Cochran-Armitage trend | <1e-300 | Rate 23.8% to 14.9% | Charge-off moves steadily across income bands from 23.8% to 14.9%. This is an association, not proof that income causes default. |
| FICO band trend | Cochran-Armitage trend | <1e-300 | Rate 25.3% to 8.9% | Charge-off moves steadily across FICO bands from 25.3% to 8.9%. This is an association, not proof that FICO causes default. |
| Employment length (known values) vs charge-off | Pearson chi-square (df=10) | 1.21e-62 | Cramer's V = 0.016 | Statistically detectable but practically negligible (V=0.016); rates span only 18.8%-20.6%. Missing employment length (26.9%) separates more than any stated length. |
| Income verification vs charge-off, stratified by grade | Cochran-Mantel-Haenszel | <1e-300 | Pooled odds ratio 1.22 (95% CI 1.21-1.24) | Pooled across grades, verified loans carry higher charge-off odds. Verification is not evidence of lower risk here; a plausible explanation is that it targets applicants already considered riskier (selection), which this data cannot confirm. |
| Interest rate: Charged Off vs Fully Paid | Welch t-test, with Mann-Whitney on a sample as a robustness check | <1e-300 | Cohen's d = 0.65; rank AUC = 0.68 | Charged-off loans carried 3.09 percentage points higher rates on average. Pricing reflects risk ordering, and it also raises the payment burden; the direction of cause cannot be separated here. |
| Loan-level recovery ratio across grades | Kruskal-Wallis | 6.37e-144 | Epsilon-squared = 0.0063 | Differences across grades are real but tiny, so recovery does not offset the higher charge-off rates of riskier grades. |

Adjusted odds ratios are from a multivariable logit on 174,836 sampled term-elapsed resolved loans, in `data/aggregate/statistics/adjusted_odds_ratios.csv`. They describe association, not causation. The model is not a scorecard.

## 12. Risk segmentation

Relative Risk Index = segment term-elapsed rate / portfolio term-elapsed rate. Low under 0.75, Medium 0.75 to under 1.25, High 1.25 or more.

| Segment | Mature resolved | Mature rate | RRI | Tier | Share of funded | Share of charged-off principal |
|---|---|---|---|---|---|---|
| A-36m | 165,804 | 5.5% | 0.36 | Low | 17.0% | 3.5% |
| A-60m | 1,215 | 8.3% | 0.55 | Low | 1.5% | 0.3% |
| B-36m | 242,619 | 11.4% | 0.75 | Medium | 19.5% | 10.9% |
| B-60m | 9,099 | 15.3% | 1.01 | Medium | 8.2% | 4.3% |
| C-36m | 184,598 | 18.3% | 1.21 | Medium | 14.9% | 15.0% |
| C-60m | 22,242 | 21.5% | 1.42 | High | 13.8% | 14.4% |
| D-36m | 84,939 | 24.0% | 1.58 | High | 6.7% | 10.2% |
| D-60m | 14,825 | 27.2% | 1.80 | High | 8.3% | 13.9% |
| E-36m | 24,535 | 29.8% | 1.97 | High | 1.8% | 3.8% |
| E-60m | 12,385 | 31.8% | 2.10 | High | 5.1% | 13.3% |
| F-36m | 5,116 | 34.3% | 2.27 | High | 0.3% | 0.9% |
| F-60m | 6,549 | 36.0% | 2.37 | High | 2.1% | 6.9% |
| G-36m | 757 | 42.4% | 2.80 | High | 0.1% | 0.3% |
| G-60m | 1,593 | 37.4% | 2.47 | High | 0.6% | 2.4% |

These tiers are retrospective classifications, not underwriting rules or credit decisions.

## 13. Dashboard findings

See [powerbi/data_model.md](../powerbi/data_model.md), [powerbi/dax_measures.md](../powerbi/dax_measures.md) and `visuals/dashboard_screenshots/`. Status of the PBIX is stated in [testing_report.md](testing_report.md).

## 14. Recommendations

- Review pricing and limits for High-tier segments first. They carry 1.7x their proportional share of charged-off principal.
- Test tighter 60-month criteria in grades C to E. Term stays material after controlling for grade (pooled odds ratio 1.19).
- Add a DTI overlay inside grades. DTI still separates risk within a grade, so a pilot could test whether grade pricing already captures it fully.
- Monitor debt-consolidation concentration, because its 60% funding share drives exposure more than its rate does.
- Review collections strategy. Settled loans recovered 25.7% against 9.0% for others; test whether earlier settlement offers improve net recoveries.
- Judge new vintages on term-elapsed or seasoned data, never on resolved-only rates.
- Treat missing employment length as a data-review flag: it stands apart from every stated length, and the reason needs investigating before any policy use.

## 15. Limitations

- Accepted loans only, so there is no view of rejected applicants and no causal inference.
- Status snapshot of March 2019. Loans still Current or Late are unresolved and excluded from the primary rate.
- Calculated exposure and net loss are estimates, not accounting losses: no funding, servicing, tax or provisioning data.
- Recoveries have no transaction dates, so trends are by origination year and newer cohorts are immature.
- 60-month term-elapsed cohorts end in March 2014, so they omit later credit conditions.
- Risk tiers are retrospective portfolio classifications, not underwriting rules or individual credit decisions.
- No protected characteristics are used. Geography and purpose can still proxy for them, so fair-lending review is required before any policy use.

## 16. Future improvements

- Add monthly payment histories, which would allow real survival and roll-rate analysis.
- Add rejected-application data to study selection effects.
- Add funding and servicing costs to estimate true return.
- Run the optional predictive module under the guardrails described in the brief.
