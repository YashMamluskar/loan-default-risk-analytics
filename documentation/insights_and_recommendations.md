# Insights and Recommendations

All figures are computed from the data by `powerbi/insights.py`.

## Key findings

- 19.96% of 1,345,310 resolved loans charged off (21.55% weighted by principal). Term-elapsed loans show 15.15%, partly because recent resolved loans over-represent early failures.
- Grade is the strongest single segmenter: 6.0% (A) to 49.9% (G).
- High-tier segments are 39% of funded principal and 66% of charged-off principal.
- Grades C and D hold 54% of charged-off principal; E to G hold 27% on 10% of funding.
- Debt consolidation holds 64% of charged-off principal through volume. Small business has the highest rate at 29.7%.
- DTI rises from 14.9% under 10 to 30.6% at 40+. After adjusting for grade, term, FICO and income, each 10 DTI points multiply the odds by 1.16.
- Recoveries return 10.8% of charged-off principal (9.0% after fees), and 31% of charged-off loans recovered nothing.

## Recommendations

These are options for management to test. They rest on historical association, so each needs a controlled pilot and compliance review before becoming policy.

- Review pricing and limits for High-tier segments first. They carry 1.7x their proportional share of charged-off principal.
- Test tighter 60-month criteria in grades C to E. Term stays material after controlling for grade (pooled odds ratio 1.19).
- Add a DTI overlay inside grades. DTI still separates risk within a grade, so a pilot could test whether grade pricing already captures it fully.
- Monitor debt-consolidation concentration, because its 60% funding share drives exposure more than its rate does.
- Review collections strategy. Settled loans recovered 25.7% against 9.0% for others; test whether earlier settlement offers improve net recoveries.
- Judge new vintages on term-elapsed or seasoned data, never on resolved-only rates.
- Treat missing employment length as a data-review flag: it stands apart from every stated length, and the reason needs investigating before any policy use.

## Limitations

- Accepted loans only, so there is no view of rejected applicants and no causal inference.
- Status snapshot of March 2019. Loans still Current or Late are unresolved and excluded from the primary rate.
- Calculated exposure and net loss are estimates, not accounting losses: no funding, servicing, tax or provisioning data.
- Recoveries have no transaction dates, so trends are by origination year and newer cohorts are immature.
- 60-month term-elapsed cohorts end in March 2014, so they omit later credit conditions.
- Risk tiers are retrospective portfolio classifications, not underwriting rules or individual credit decisions.
- No protected characteristics are used. Geography and purpose can still proxy for them, so fair-lending review is required before any policy use.
