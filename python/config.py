"""Shared paths, logging and DuckDB session settings for the whole pipeline.

Every script imports from here so that no machine-specific absolute path is
hardcoded. Paths resolve relative to this file. The raw CSV location can be
overridden with the LC_RAW_CSV environment variable.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
EXPORT_DIR = DATA_DIR / "exports"
AGGREGATE_DIR = DATA_DIR / "aggregate"
AUDIT_DIR = AGGREGATE_DIR / "audit"
STATS_DIR = AGGREGATE_DIR / "statistics"
DOCS_DIR = PROJECT_ROOT / "documentation"
VISUALS_DIR = PROJECT_ROOT / "visuals" / "eda"
LOG_DIR = PROJECT_ROOT / "logs"
DUCK_TMP = DATA_DIR / ".duckdb_tmp"

RAW_FILENAME = "accepted_2007_to_2018Q4.csv"
STAGING_PARQUET = PROCESSED_DIR / "_staging_all_varchar.parquet"
CLEAN_PARQUET = PROCESSED_DIR / "lendingclub_cleaned.parquet"
ANALYTICAL_PARQUET = PROCESSED_DIR / "lendingclub_analytical.parquet"

# Machine has ~7 GB of RAM: cap DuckDB and let it spill to disk.
DUCKDB_MEMORY_LIMIT = os.environ.get("LC_DUCKDB_MEMORY", "2GB")
DUCKDB_THREADS = int(os.environ.get("LC_DUCKDB_THREADS", "4"))


def raw_csv_path() -> Path:
    """Locate the raw CSV without assuming a machine path; fail clearly if absent."""
    override = os.environ.get("LC_RAW_CSV")
    candidates = [Path(override)] if override else []
    candidates += [RAW_DIR / RAW_FILENAME, PROJECT_ROOT.parent / RAW_FILENAME]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"Raw CSV not found. Looked in: {[str(c) for c in candidates]}. "
        "Download it from Kaggle (wordsforthewise/lending-club) into data/raw/."
    )


def get_logger(name: str) -> logging.Logger:
    """Console + file logger; one log file per script under logs/."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    for handler in (
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / f"{name}.log", mode="w", encoding="utf-8"),
    ):
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    return logger


def connect() -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB session, memory-capped and allowed to spill to disk."""
    DUCK_TMP.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(":memory:")
    con.execute(f"SET memory_limit='{DUCKDB_MEMORY_LIMIT}'")
    con.execute(f"SET threads={DUCKDB_THREADS}")
    con.execute(f"SET temp_directory='{DUCK_TMP.as_posix()}'")
    con.execute("SET preserve_insertion_order=false")
    return con


def ensure_dirs() -> None:
    for path in (PROCESSED_DIR, EXPORT_DIR, AGGREGATE_DIR, AUDIT_DIR, STATS_DIR, DOCS_DIR, VISUALS_DIR, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)
