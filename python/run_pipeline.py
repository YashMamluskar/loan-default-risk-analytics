"""Run the data pipeline end to end, stopping at the first failure. MySQL and Power BI are separate steps."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = ["data_inspection", "data_cleaning", "data_validation", "build_data_dictionary", "risk_segmentation", "eda", "borrower_analysis",
         "financial_analysis", "statistical_analysis", "mysql_export", "powerbi_export", "build_notebooks", "build_reports"]


def main() -> int:
    for step in STEPS:
        print(f"=== {step} ===", flush=True)
        if subprocess.run([sys.executable, str(HERE / f"{step}.py")], cwd=HERE).returncode:
            print(f"Stopped: {step} failed")
            return 1
    print("Pipeline complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
