# Business Understanding

## Context

A lender needs evidence about how its loans performed, where credit losses concentrate, and what management could change. This project treats LendingClub's accepted-loan history as that portfolio.

## Questions and where they are answered

| # | Management question | Where |
|---|---|---|
| 1 | How is the portfolio performing? | Report section 6; dashboard Executive Overview; SQL Q01, Q02 |
| 2 | What share of resolved loans charged off? | Report section 7; SQL Q03, Q04 |
| 3 | Which grades and subgrades have the highest rates? | Dashboard Loan Performance; SQL Q05, Q06, Q23 |
| 4 | Which borrower characteristics are associated with default? | Dashboard Borrower Risk; notebook 04; SQL Q09 to Q13 |
| 5 | How do rate, amount and term relate to outcomes? | Dashboard Loan Performance; SQL Q07, Q14, Q15 |
| 6 | How does DTI affect performance? | Report section 8; SQL Q10, Q33, Q35 |
| 7 | Which employment and income segments are riskier? | Report section 8; SQL Q09, Q11 |
| 8 | Which purposes default more? | Report section 7; SQL Q08 |
| 9 | How much principal was recovered from charged-off loans? | Report section 10; SQL Q17, Q34 |
| 10 | Which segments contribute most to losses? | Report section 12; SQL Q18, Q19, Q28, Q31 |
| 11 | How does performance vary by origination year? | Report section 7; dashboard Time & Geography; SQL Q20, Q26, Q27 |
| 12 | What actions should management consider? | [insights_and_recommendations.md](insights_and_recommendations.md); dashboard Risk Insights |

## Stakeholders

| Stakeholder | Need |
|---|---|
| Senior management | Headline performance and concentration |
| Credit risk | Segment-level risk, with sound denominators |
| Pricing and product | Rate, term and grade evidence |
| Collections | Recovery performance |
| Compliance | Clear limits, no protected characteristics |

## Constraints

* Public data, with no internal cost, funding or decision data.
* The file holds one status snapshot rather than monthly payment history.
* Accepted loans only, so rejected applicants are not visible.
* Findings are retrospective associations, not causal claims or credit policy.
