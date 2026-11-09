"""Phase 1: read-only audit of the raw CSV.

Writes an all-text staging Parquet (so later steps never re-parse 1.6 GB of CSV)
and per-column profile tables under data/aggregate/audit/. Nothing is cleaned,
dropped or coerced here: every value is profiled as the original text.
"""
from __future__ import annotations

import json
import time

import pandas as pd

from config import AUDIT_DIR, STAGING_PARQUET, connect, ensure_dirs, get_logger, raw_csv_path

log = get_logger("data_inspection")

NUMERIC_RE = r"^\s*-?\d+(\.\d+)?([eE][-+]?\d+)?\s*$"
LOW_CARDINALITY_LIMIT = 60
SRC = f"'{STAGING_PARQUET.as_posix()}'"


def build_staging(con, csv_path) -> None:
    """Stream CSV -> Parquet with every column as text."""
    if STAGING_PARQUET.exists():
        log.info("Staging Parquet exists, reusing: %s", STAGING_PARQUET)
        return
    start = time.time()
    tmp = STAGING_PARQUET.with_suffix(".tmp")
    con.execute(f"""
        COPY (
            SELECT * FROM read_csv('{csv_path.as_posix()}', header=true, all_varchar=true,
                                   quote='"', escape='"', delim=',', strict_mode=false,
                                   null_padding=true, parallel=false, max_line_size=2000000)
        ) TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)
    """)
    tmp.replace(STAGING_PARQUET)
    log.info("Staging Parquet written in %.0fs", time.time() - start)


def profile_columns(con) -> pd.DataFrame:
    """One row per column: fill rate, cardinality, numeric parse rate, range."""
    columns = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {SRC}").fetchall()]
    total = con.execute(f"SELECT COUNT(*) FROM {SRC}").fetchone()[0]
    rows = []
    for position, name in enumerate(columns, start=1):
        q = f'"{name}"'
        non_null, distinct, numeric, min_len, max_len = con.execute(f"""
            SELECT COUNT({q}), APPROX_COUNT_DISTINCT({q}),
                   SUM(CASE WHEN regexp_matches({q}, '{NUMERIC_RE}') THEN 1 ELSE 0 END),
                   MIN(LENGTH({q})), MAX(LENGTH({q}))
            FROM {SRC}
        """).fetchone()
        numeric = int(numeric or 0)
        stats = {"min": None, "p01": None, "median": None, "p99": None, "max": None, "mean": None}
        if non_null and numeric / non_null > 0.95:
            res = con.execute(f"""
                SELECT MIN(v), QUANTILE_CONT(v,0.01), MEDIAN(v), QUANTILE_CONT(v,0.99), MAX(v), AVG(v)
                FROM (SELECT TRY_CAST({q} AS DOUBLE) v FROM {SRC})
            """).fetchone()
            stats = dict(zip(stats.keys(), res))
        rows.append({
            "position": position, "column_name": name, "non_null": non_null,
            "missing": total - non_null, "missing_pct": round(100 * (total - non_null) / total, 4),
            "approx_distinct": distinct,
            "numeric_parse_pct": round(100 * numeric / non_null, 2) if non_null else None,
            "min_text_len": min_len, "max_text_len": max_len, **stats,
        })
        log.info("Profiled %3d/%d %s", position, len(columns), name)
    return pd.DataFrame(rows)


def main() -> None:
    ensure_dirs()
    csv_path = raw_csv_path()
    con = connect()
    log.info("Raw CSV: %s (%.1f MB)", csv_path, csv_path.stat().st_size / 1024**2)
    build_staging(con, csv_path)

    profile = profile_columns(con)
    profile.to_csv(AUDIT_DIR / "column_profile.csv", index=False)

    # Frequency tables for every low-cardinality column.
    freq_frames = []
    for row in profile[profile["approx_distinct"] <= LOW_CARDINALITY_LIMIT].itertuples():
        q = f'"{row.column_name}"'
        freq = con.execute(f"SELECT {q} AS value, COUNT(*) AS records FROM {SRC} GROUP BY 1 ORDER BY 2 DESC").df()
        freq.insert(0, "column_name", row.column_name)
        freq_frames.append(freq)
    pd.concat(freq_frames).to_csv(AUDIT_DIR / "categorical_frequencies.csv", index=False)

    facts = {
        "csv_bytes": csv_path.stat().st_size,
        "csv_records_excl_header": con.execute(f"SELECT COUNT(*) FROM {SRC}").fetchone()[0],
        "columns": len(profile),
        "distinct_id": con.execute(f"SELECT COUNT(DISTINCT id) FROM {SRC}").fetchone()[0],
        "null_id": con.execute(f"SELECT COUNT(*) FROM {SRC} WHERE id IS NULL").fetchone()[0],
    }
    # Rows that are not loans are captured verbatim as audit evidence.
    junk = con.execute(f"""SELECT id, member_id, loan_amnt, loan_status FROM {SRC}
                           WHERE loan_amnt IS NULL OR NOT regexp_matches(id, '^[0-9]+$')""").df()
    facts["non_numeric_id_or_null_amount_rows"] = len(junk)
    junk.to_csv(AUDIT_DIR / "non_loan_rows.csv", index=False)

    dup = con.execute(f"SELECT id, COUNT(*) AS records FROM {SRC} GROUP BY 1 HAVING COUNT(*) > 1").df()
    facts["duplicated_ids"] = len(dup)
    dup.to_csv(AUDIT_DIR / "duplicate_ids.csv", index=False)

    # Hash-based exact-duplicate check over all columns (avoids a huge DISTINCT in RAM).
    all_cols = ",".join(f'"{c}"' for c in profile["column_name"])
    facts["distinct_full_row_hashes"] = con.execute(
        f"SELECT COUNT(DISTINCT hash({all_cols})) FROM {SRC}"
    ).fetchone()[0]
    (AUDIT_DIR / "audit_facts.json").write_text(json.dumps(facts, indent=2, default=str))
    log.info("Audit facts: %s", facts)


if __name__ == "__main__":
    main()
