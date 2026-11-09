"""Shared metric definitions and chart styling used by every analysis script.

The default-rate logic lives here once, so Python outputs cannot drift apart:
  * primary rate          = Charged Off / (Fully Paid + Charged Off), loan count
  * principal-weighted    = funded $ of Charged Off / funded $ of resolved loans
  * mature-cohort rate    = primary rate on loans whose full term has elapsed
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats as st

from config import ANALYTICAL_PARQUET, CLEAN_PARQUET, VISUALS_DIR

INK = "#14263D"
MUTED = "#5B6B7F"
GRID = "#E3E8EE"
NAVY = "#1F4E79"
TEAL = "#14A098"
GOLD = "#C9A227"
RED = "#C8452F"
SLATE = "#7A8CA5"
CATEGORICAL = [NAVY, TEAL, GOLD, RED, SLATE]

ORDERS = {
    "income_band": ["<$40K", "$40K-$60K", "$60K-$80K", "$80K-$100K", "$100K-$150K", "$150K+", "Unknown"],
    "dti_band": ["<10", "10-20", "20-30", "30-40", "40+", "Unknown"],
    "amount_band": ["<$5K", "$5K-$10K", "$10K-$15K", "$15K-$20K", "$20K-$25K", "$25K-$30K", "$30K+"],
    "rate_band": ["<8%", "8-11%", "11-14%", "14-17%", "17-20%", "20-25%", "25%+"],
    "fico_band": ["660-679", "680-699", "700-719", "720-749", "750+"],
    "credit_history_band": ["<5 yrs", "5-10 yrs", "10-15 yrs", "15-20 yrs", "20-30 yrs", "30+ yrs", "Unknown"],
    "revol_util_band": ["<25%", "25-50%", "50-75%", "75-100%", "100%+", "Unknown"],
    "emp_length_label": ["< 1 year", "1 year", "2 years", "3 years", "4 years", "5 years", "6 years",
                         "7 years", "8 years", "9 years", "10+ years", "Unknown"],
    "delinq_band": ["0", "1", "2+", "Unknown"],
    "pub_rec_band": ["0", "1", "2+", "Unknown"],
    "inquiry_band": ["0", "1", "2", "3+", "Unknown"],
    "grade": list("ABCDEFG"),
    "term_months": [36, 60],
}


def clean_src() -> str:
    return f"'{CLEAN_PARQUET.as_posix()}'"


def analytical_src() -> str:
    return f"'{ANALYTICAL_PARQUET.as_posix()}'"


def wilson_ci(events, n, z: float = 1.959964):
    """Wilson score interval: well behaved for rates near 0/1 and small segments."""
    events, n = np.asarray(events, dtype=float), np.asarray(n, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = events / n
        denom = 1 + z**2 / n
        centre = (p + z**2 / (2 * n)) / denom
        half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return centre - half, centre + half


def segment_metrics(con, dims, src: str | None = None, where: str = "1=1") -> pd.DataFrame:
    """Portfolio metrics by one or more dimensions, with correct denominators per metric."""
    dims = [dims] if isinstance(dims, str) else list(dims)
    src = src or clean_src()
    dim_sql = ", ".join(f'"{d}"' for d in dims)
    frame = con.execute(f"""
        SELECT {dim_sql},
            COUNT(*) AS loans,
            SUM(funded_amnt) AS funded_amount,
            AVG(funded_amnt) AS avg_funded_amount,
            AVG(int_rate) AS avg_int_rate,
            SUM(is_fully_paid) AS fully_paid,
            SUM(is_charged_off) AS charged_off,
            SUM(is_resolved) AS resolved,
            SUM(CASE WHEN is_resolved=1 THEN funded_amnt END) AS resolved_funded,
            SUM(CASE WHEN is_charged_off=1 THEN funded_amnt END) AS charged_off_funded,
            SUM(unpaid_principal_at_chargeoff) AS unpaid_principal_at_chargeoff,
            SUM(CASE WHEN is_charged_off=1 THEN recoveries END) AS recoveries,
            SUM(CASE WHEN is_charged_off=1 THEN collection_recovery_fee END) AS recovery_fees,
            SUM(est_net_principal_loss) AS est_net_principal_loss,
            SUM(CASE WHEN is_term_elapsed=1 THEN is_resolved END) AS mature_resolved,
            SUM(CASE WHEN is_term_elapsed=1 THEN is_charged_off END) AS mature_charged_off,
            SUM(is_term_elapsed) AS mature_loans
        FROM {src} WHERE {where} GROUP BY {dim_sql}
    """).df()
    numeric = frame.columns.difference(dims)
    frame[numeric] = frame[numeric].apply(pd.to_numeric).fillna(0)
    frame["default_rate"] = frame.charged_off / frame.resolved.replace(0, np.nan)
    low, high = wilson_ci(frame.charged_off, frame.resolved.replace(0, np.nan))
    frame["default_rate_ci_low"], frame["default_rate_ci_high"] = low, high
    frame["principal_weighted_rate"] = frame.charged_off_funded / frame.resolved_funded.replace(0, np.nan)
    frame["mature_default_rate"] = frame.mature_charged_off / frame.mature_resolved.replace(0, np.nan)
    frame["recovery_ratio"] = frame.recoveries / frame.unpaid_principal_at_chargeoff.replace(0, np.nan)
    return order_frame(frame, dims)


def order_frame(frame: pd.DataFrame, dims: list[str]) -> pd.DataFrame:
    """Sort by the business order of a band rather than alphabetically."""
    keys = []
    for dim in dims:
        if dim in ORDERS:
            frame[f"__{dim}"] = frame[dim].map({v: i for i, v in enumerate(ORDERS[dim])})
            keys.append(f"__{dim}")
        else:
            keys.append(dim)
    return frame.sort_values(keys).drop(columns=[k for k in keys if k.startswith("__")]).reset_index(drop=True)


def style() -> None:
    plt.rcParams.update({
        "text.parse_math": False,  # dollar signs in labels are currency, not math
        "figure.dpi": 110, "savefig.dpi": 130, "font.family": "DejaVu Sans", "font.size": 10,
        "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "axes.titlecolor": INK, "axes.titlesize": 12,
        "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.grid": True, "axes.grid.axis": "y",
        "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True, "axes.spines.top": False,
        "axes.spines.right": False, "axes.spines.left": False, "xtick.color": MUTED, "ytick.color": MUTED,
        "xtick.bottom": False, "ytick.left": False, "legend.frameon": False, "figure.facecolor": "white",
    })


def save(fig, name: str, folder: Path | None = None) -> Path:
    folder = folder or VISUALS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.png"
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def rate_bars(frame, dim, title, subtitle="", rate="default_rate", benchmark=None, name=None, horizontal=False, color=NAVY):
    """Bar chart of a rate by segment with 95% CI whiskers and a portfolio reference line."""
    frame = frame[frame[rate].notna()]  # a segment with no resolved loans has no rate to plot
    fig, ax = plt.subplots(figsize=(8.2, 4.2 if not horizontal else max(4.2, 0.32 * len(frame))))
    labels = frame[dim].astype(str)
    values = frame[rate] * 100
    show_ci = rate == "default_rate"
    err = None
    if show_ci:
        err = [(frame.default_rate - frame.default_rate_ci_low) * 100, (frame.default_rate_ci_high - frame.default_rate) * 100]
    if horizontal:
        ax.barh(labels, values, color=color, height=0.68, xerr=err, ecolor=MUTED, error_kw={"lw": 1})
        ax.invert_yaxis()
        ax.grid(axis="x", color=GRID)
        ax.grid(axis="y", visible=False)
        ax.set_xlabel("Default rate (%)")
        if benchmark is not None:
            ax.axvline(benchmark * 100, color=RED, lw=1.5, ls="--", label=f"Portfolio {benchmark:.1%}")
            ax.legend(loc="lower right")
    else:
        ax.bar(labels, values, color=color, width=0.68, yerr=err, ecolor=MUTED, error_kw={"lw": 1})
        ax.set_ylabel("Default rate (%)")
        if benchmark is not None:
            ax.axhline(benchmark * 100, color=RED, lw=1.5, ls="--", label=f"Portfolio {benchmark:.1%}")
            ax.legend(loc="upper left")
    ax.set_title(title + (f"\n{subtitle}" if subtitle else ""), fontsize=11)
    return save(fig, name or f"rate_by_{dim}")


def chi_square_trend(frame: pd.DataFrame) -> tuple[float, float]:
    """Pearson chi-square of independence between segment and charge-off."""
    table = np.vstack([frame.charged_off.values, frame.fully_paid.values])
    chi2, p, _, _ = st.chi2_contingency(table)
    return float(chi2), float(p)
