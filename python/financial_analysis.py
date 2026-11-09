"""Phase 5: financial exposure and recovery.

Definitions (reported = supplied by LendingClub; calculated = derived here):
  reported   funded_amnt, funded_amnt_inv, total_pymnt, total_rec_prncp, total_rec_int,
             total_rec_late_fee, recoveries, collection_recovery_fee, out_prncp
  calculated unpaid_principal_at_chargeoff = funded_amnt - total_rec_prncp (Charged Off only)
             net_recoveries = recoveries - collection_recovery_fee
             est_net_principal_loss = unpaid principal - net recoveries

None of these is an accounting loss: there is no cost of funds, servicing cost, investor
share, tax, discounting or provisioning data in this file.
"""
from __future__ import annotations

import json

import matplotlib.pyplot as plt

from analysis_common import GRID, NAVY, RED, TEAL, analytical_src, save, segment_metrics, style
from config import AGGREGATE_DIR, connect, ensure_dirs, get_logger

log = get_logger("financial_analysis")


def main() -> None:
    ensure_dirs()
    style()
    con = connect()
    src = analytical_src()

    totals = con.execute(f"""SELECT SUM(funded_amnt) funded, SUM(funded_amnt_inv) funded_inv, SUM(total_pymnt) total_payments,
        SUM(total_rec_prncp) principal_received, SUM(total_rec_int) interest_received, SUM(total_rec_late_fee_clean) late_fees,
        SUM(recoveries) recoveries_all, SUM(collection_recovery_fee) fees_all, SUM(out_prncp) outstanding,
        SUM(CASE WHEN is_charged_off=1 THEN funded_amnt END) co_funded,
        SUM(CASE WHEN is_charged_off=1 THEN total_rec_prncp END) co_principal_received,
        SUM(CASE WHEN is_charged_off=1 THEN total_rec_int END) co_interest_received,
        SUM(CASE WHEN is_charged_off=1 THEN total_pymnt END) co_total_payments,
        SUM(unpaid_principal_at_chargeoff) unpaid_principal,
        SUM(CASE WHEN is_charged_off=1 THEN recoveries END) co_recoveries,
        SUM(CASE WHEN is_charged_off=1 THEN collection_recovery_fee END) co_fees,
        SUM(net_recoveries) net_recoveries, SUM(est_net_principal_loss) est_net_loss,
        SUM(CASE WHEN status_clean='Policy Exception - Charged Off' THEN recoveries END) policy_recoveries,
        SUM(CASE WHEN status_clean='Fully Paid' THEN total_rec_int END) fp_interest
        FROM {src}""").df().iloc[0].astype(float).to_dict()
    totals["recovery_ratio_gross"] = totals["co_recoveries"] / totals["unpaid_principal"]
    totals["recovery_ratio_net"] = totals["net_recoveries"] / totals["unpaid_principal"]
    totals["fee_share_of_recoveries"] = totals["co_fees"] / totals["co_recoveries"]
    totals["principal_received_share_charged_off"] = totals["co_principal_received"] / totals["co_funded"]
    (AGGREGATE_DIR / "financial_totals.json").write_text(json.dumps(totals, indent=2))
    log.info("Totals: %s", {k: round(v, 3) for k, v in totals.items()})

    for dim in ("grade", "purpose_label", "amount_band"):
        frame = segment_metrics(con, dim, src)
        frame["share_of_funded"] = frame.funded_amount / frame.funded_amount.sum()
        frame["share_of_unpaid_principal"] = frame.unpaid_principal_at_chargeoff / frame.unpaid_principal_at_chargeoff.sum()
        frame.to_csv(AGGREGATE_DIR / f"financial_{dim}.csv", index=False)

    # Recoveries by year of origination (no recovery transaction dates exist in the data).
    rec = segment_metrics(con, "issue_year", src)
    rec[["issue_year", "charged_off", "unpaid_principal_at_chargeoff", "recoveries", "recovery_fees", "recovery_ratio"]].to_csv(
        AGGREGATE_DIR / "recoveries_by_issue_year.csv", index=False)

    # Recovery outcome distribution and the role of debt settlement.
    settle = con.execute(f"""SELECT debt_settlement_flag, COUNT(*) loans, SUM(unpaid_principal_at_chargeoff) unpaid,
        SUM(recoveries) recoveries, SUM(collection_recovery_fee) fees,
        SUM((recoveries=0)::INT) zero_recovery FROM {src} WHERE is_charged_off=1 GROUP BY 1""").df()
    settle["recovery_ratio"] = settle.recoveries / settle.unpaid
    settle.to_csv(AGGREGATE_DIR / "recoveries_by_settlement.csv", index=False)
    log.info("Settlement:\n%s", settle.round(3).to_string())

    # Cash-flow waterfall by status, for "funded versus payments received".
    by_status = con.execute(f"""SELECT status_clean, SUM(funded_amnt) funded, SUM(total_pymnt) total_payments, SUM(total_rec_prncp) principal,
        SUM(total_rec_int) interest, SUM(recoveries) recoveries, SUM(out_prncp) outstanding FROM {src} GROUP BY 1 ORDER BY 2 DESC""").df()
    by_status.to_csv(AGGREGATE_DIR / "cashflow_by_status.csv", index=False)

    grade = segment_metrics(con, "grade", src)
    fig, ax = plt.subplots(figsize=(8.2, 3.8))
    ax.bar(grade.grade, grade.unpaid_principal_at_chargeoff / 1e6, color=NAVY, width=0.68)
    ax.set_ylabel("Unpaid principal at charge-off ($M)")
    ax.set_title("Grades C and D hold the most charged-off principal, not the riskiest grades")
    save(fig, "e_unpaid_principal_by_grade")

    purpose = segment_metrics(con, "purpose_label", src).sort_values("unpaid_principal_at_chargeoff")
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    ax.barh(purpose.purpose_label, purpose.unpaid_principal_at_chargeoff / 1e6, color=NAVY, height=0.68)
    ax.grid(axis="x", color=GRID); ax.grid(axis="y", visible=False); ax.set_xlabel("Unpaid principal at charge-off ($M)")
    ax.set_title("Debt consolidation drives charged-off principal through sheer volume")
    save(fig, "e_unpaid_principal_by_purpose")

    fig, ax = plt.subplots(figsize=(8.2, 3.8))
    ax.bar(rec.issue_year.astype(str), rec.recovery_ratio * 100, color=TEAL, width=0.68)
    ax.set_xlabel("Origination year"); ax.set_ylabel("Gross recoveries / unpaid principal (%)")
    ax.set_title("Recovery ratio peaks for 2013-14; newer cohorts have had less time to recover")
    save(fig, "e_recovery_ratio_by_year")

    # Composition of the charged-off funded amount (a reconciliation of reported cash).
    fig, ax = plt.subplots(figsize=(8.2, 2.9))
    parts = [("Principal repaid before charge-off", totals["co_principal_received"], NAVY),
             ("Net recoveries", totals["net_recoveries"], TEAL),
             ("Estimated net principal loss", totals["est_net_loss"], RED)]
    left = 0.0
    for label, value, color in parts:
        ax.barh(["Charged-off funded"], value / 1e9, left=left, color=color, height=0.5, label=f"{label} ${value/1e9:.2f}B")
        left += value / 1e9
    ax.grid(axis="x", color=GRID); ax.grid(axis="y", visible=False); ax.set_xlabel("$B")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.25), ncol=2)
    ax.set_title("What happened to the funded principal of charged-off loans")
    save(fig, "e_chargeoff_composition")
    assert abs(left * 1e9 - totals["co_funded"]) < 1, "Composition must reconcile to charged-off funded amount"
    log.info("Financial analysis complete")


if __name__ == "__main__":
    main()
