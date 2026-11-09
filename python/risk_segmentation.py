"""Phase 6: transparent, retrospective risk segmentation.

A loan's segment is grade x term: both are known at origination and together they
explain most of the observed variation. Each segment gets a tier from its mature-
cohort charge-off rate relative to the mature-cohort portfolio rate:

    Relative Risk Index (RRI) = segment mature rate / portfolio mature rate
    Low: RRI < 0.75 | Medium: 0.75 <= RRI < 1.25 | High: RRI >= 1.25

Segments with fewer than MIN_RESOLVED mature resolved loans are "Insufficient data".
These tiers describe past portfolio behaviour. They are not underwriting rules or
individual credit decisions, and no protected characteristic is used.
"""
from __future__ import annotations

import pandas as pd

from analysis_common import clean_src, segment_metrics
from config import AGGREGATE_DIR, ANALYTICAL_PARQUET, connect, ensure_dirs, get_logger

log = get_logger("risk_segmentation")

LOW_RRI, HIGH_RRI = 0.75, 1.25
MIN_RESOLVED = 500
# Single-dimension views for the segment summary table (retrospective comparison only).
SUMMARY_DIMS = ["grade", "sub_grade", "term_months", "purpose_label", "income_band", "dti_band", "amount_band",
                "rate_band", "fico_band", "emp_length_label", "home_ownership_group", "verification_status",
                "credit_history_band", "delinq_band", "pub_rec_band", "inquiry_band", "revol_util_band"]


def classify(rri: float, resolved: float) -> str:
    if resolved < MIN_RESOLVED or pd.isna(rri):
        return "Insufficient data"
    if rri < LOW_RRI:
        return "Low"
    return "Medium" if rri < HIGH_RRI else "High"


def main() -> None:
    ensure_dirs()
    con = connect()
    src = clean_src()
    base = con.execute(f"""SELECT SUM(CASE WHEN is_term_elapsed=1 THEN is_charged_off END)*1.0 /
                                  SUM(CASE WHEN is_term_elapsed=1 THEN is_resolved END) FROM {src}""").fetchone()[0]
    log.info("Mature-cohort portfolio rate = %.4f", base)

    # Loan-level segment: grade x term.
    core = segment_metrics(con, ["grade", "term_months"])
    core["risk_segment"] = core.grade + "-" + core.term_months.astype(str) + "m"
    core["relative_risk_index"] = core.mature_default_rate / base
    core["risk_tier"] = [classify(r, n) for r, n in zip(core.relative_risk_index, core.mature_resolved)]
    core["share_of_funded"] = core.funded_amount / core.funded_amount.sum()
    total_unpaid = core.unpaid_principal_at_chargeoff.sum()
    core["share_of_unpaid_principal"] = core.unpaid_principal_at_chargeoff / total_unpaid
    core.to_csv(AGGREGATE_DIR / "risk_segments_grade_term.csv", index=False)
    log.info("\n%s", core[["risk_segment", "loans", "mature_resolved", "default_rate", "mature_default_rate",
                           "relative_risk_index", "risk_tier", "share_of_funded", "share_of_unpaid_principal"]].round(3).to_string())

    # Tier onto every loan and write the analytical file (register avoids a pandas copy of all loans).
    mapping = core[["grade", "term_months", "risk_segment", "relative_risk_index", "risk_tier"]]
    con.register("segment_map", mapping)
    tmp = ANALYTICAL_PARQUET.with_suffix(".tmp")
    con.execute(f"""COPY (SELECT c.*, m.risk_segment, m.relative_risk_index, m.risk_tier
                          FROM {src} c JOIN segment_map m USING (grade, term_months))
                    TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)""")
    tmp.replace(ANALYTICAL_PARQUET)
    rows = con.execute(f"SELECT COUNT(*) FROM '{ANALYTICAL_PARQUET.as_posix()}'").fetchone()[0]
    assert rows == con.execute(f"SELECT COUNT(*) FROM {src}").fetchone()[0], "Segment join changed row count"

    # One-dimensional comparison table for every segmentation dimension.
    frames = []
    for dim in SUMMARY_DIMS:
        frame = segment_metrics(con, dim)
        frame.insert(0, "dimension", dim)
        frame = frame.rename(columns={dim: "segment"})
        frame["segment"] = frame["segment"].astype(str)
        frames.append(frame)
    summary = pd.concat(frames, ignore_index=True)
    summary["relative_risk_index"] = summary.mature_default_rate / base
    summary["risk_tier"] = [classify(r, n) for r, n in zip(summary.relative_risk_index, summary.mature_resolved)]
    summary["share_of_funded"] = summary.funded_amount / summary.groupby("dimension").funded_amount.transform("sum")
    summary["share_of_unpaid_principal"] = summary.unpaid_principal_at_chargeoff / total_unpaid
    summary.to_csv(AGGREGATE_DIR / "risk_segment_summary.csv", index=False)
    log.info("Segment summary rows: %d; tier counts: %s", len(summary), summary.risk_tier.value_counts().to_dict())

    tiers = core.groupby("risk_tier", as_index=False)[["loans", "funded_amount", "resolved", "charged_off",
                                                       "unpaid_principal_at_chargeoff"]].sum()
    tiers["default_rate"] = tiers.charged_off / tiers.resolved
    tiers["share_of_funded"] = tiers.funded_amount / tiers.funded_amount.sum()
    tiers["share_of_unpaid_principal"] = tiers.unpaid_principal_at_chargeoff / tiers.unpaid_principal_at_chargeoff.sum()
    tiers.to_csv(AGGREGATE_DIR / "risk_tier_summary.csv", index=False)
    log.info("\n%s", tiers.round(3).to_string())


if __name__ == "__main__":
    main()
