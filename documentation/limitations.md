# Limitations

## Data

* **Accepted loans only.** Rejected applications are not included, so segment rates describe approved loans. They cannot show what would happen under a looser policy.
* **One snapshot.** Each loan has one status as of early 2019. There is no monthly history, so survival or roll-rate analysis is not possible.
* **No recovery dates.** Recovery trends use origination year; recent cohorts have had less time to recover.
* **No cost data.** Funding, servicing, tax and provisioning are absent, so no accounting loss or return can be computed.
* **Self-reported fields.** Income, employment and purpose come from applicants, and many are unverified.
* **Changing fields.** Several credit-bureau fields only begin part-way through the program.
* **No borrower id.** `member_id` is empty, so repeat borrowers cannot be identified.
* **No official dictionary.** The file has no dictionary, so business meanings in `data_dictionary.csv` are analyst descriptions.

## Analysis

* **Association, not causation.** Grade and rate are assigned from risk, and geography and purpose can proxy for other factors.
* **Resolved-only bias.** The primary rate includes young resolved loans, which over-represent failures. The term-elapsed rate reduces this but covers older credit conditions, especially for 60-month loans.
* **Era effects.** Results span the post-2008 recovery and do not show a fresh downturn.
* **Average income.** The mean is skewed by extreme values (maximum $110M), so medians are reported as well.
* **Risk tiers.** Thresholds are transparent analyst choices, not validated policy.
* **Adjusted odds ratios.** The model is deliberately simple and explanatory, with low pseudo-R-squared. It is not a scorecard.

## Responsible use

No output here should drive an individual credit decision. Geography, purpose and employment fields can act as proxies for protected characteristics, so any policy use needs fair-lending review. Protected characteristics are absent from the source and are not used.

## Tooling

* Details of what was and was not verified in Power BI and MySQL are in [testing_report.md](testing_report.md).
* The optional predictive module was not built, as it was optional and comes after the dashboard.
