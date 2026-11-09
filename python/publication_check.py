"""Final local review: which files would be published, and do they pass the release checks?

Only reads files. It creates no repository and contacts no remote.
Writes documentation/publication_checklist.md.
"""
from __future__ import annotations

import ast
import fnmatch
import json
import re
import zipfile

import pandas as pd

from config import AGGREGATE_DIR, DOCS_DIR, PROJECT_ROOT

GITHUB_FILE_LIMIT = 100 * 1024**2
TEXT_SUFFIXES = {".py", ".sql", ".md", ".csv", ".json", ".ipynb", ".txt", ".ps1", ".gitignore"}
# Literal patterns are assembled so this file does not match itself.
SENSITIVE = {
    "user home path": r"C:[\\/]+Users[\\/]",
    "project absolute path": "TY" + r"DSDA",
    "email address": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.(com|org|net|in)",
    "password or secret": r"(?i)(password|secret|api[_-]?key)\s*[:=]\s*['\"][^'\"]+['\"]",
}


def ignore_patterns() -> list[str]:
    return [l.strip() for l in (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]


def ignored(rel: str, patterns: list[str]) -> bool:
    parts = rel.split("/")
    for pattern in patterns:
        if pattern.endswith("/"):
            if rel.startswith(pattern) or pattern.rstrip("/") in parts[:-1]:
                return True
        elif fnmatch.fnmatch(parts[-1], pattern) or fnmatch.fnmatch(rel, pattern):
            return True
    return False


def unused_imports(path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names[(a.asname or a.name).split(".")[0]] = node.lineno
        elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
            for a in node.names:
                names[a.asname or a.name] = node.lineno
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.value.id for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
    return [n for n in names if n not in used]


def main() -> None:
    patterns = ignore_patterns()
    files = [p for p in PROJECT_ROOT.rglob("*") if p.is_file()]
    published = [p for p in files if not ignored(p.relative_to(PROJECT_ROOT).as_posix(), patterns)]
    rel = lambda p: p.relative_to(PROJECT_ROOT).as_posix()

    oversize = [rel(p) for p in published if p.stat().st_size > GITHUB_FILE_LIMIT]
    total_mb = sum(p.stat().st_size for p in published) / 1024**2
    raw_like = [rel(p) for p in published if re.search(r"accepted_|rejected_|fact_loans|lendingclub_(cleaned|analytical)|loan_details\.csv|loan_performance\.csv|borrower_profiles\.csv", p.name)]

    hits: dict[str, list[str]] = {k: [] for k in SENSITIVE}
    for p in published:
        if p.suffix.lower() in TEXT_SUFFIXES and p.name not in ("publication_check.py",):
            text = p.read_text(encoding="utf-8", errors="ignore")
            for label, pattern in SENSITIVE.items():
                if re.search(pattern, text):
                    hits[label].append(rel(p))

    # The template stores the data folder default as a parameter.
    template = PROJECT_ROOT / "powerbi" / "Loan_Default_Risk_Dashboard.pbit"
    schema = zipfile.ZipFile(template).read("DataModelSchema").decode("utf-16-le")
    template_has_path = "TY" + "DSDA" in schema

    largest_aggregate = max((p.stat().st_size for p in published if rel(p).startswith("data/aggregate")), default=0) / 1024**2
    py_files = [p for p in published if p.suffix == ".py"]
    unused = {rel(p): unused_imports(p) for p in py_files}
    unused = {k: v for k, v in unused.items() if v}
    required = ["README.md", "requirements.txt", ".gitignore", "documentation/project_overview.md", "documentation/business_understanding.md", "documentation/dataset_audit.md",
                "documentation/data_dictionary.csv", "documentation/data_quality_report.md", "documentation/cleaning_log.md", "documentation/methodology.md", "documentation/sql_documentation.md",
                "documentation/insights_and_recommendations.md", "documentation/limitations.md", "documentation/final_project_report.md", "documentation/testing_report.md",
                "powerbi/dax_measures.md", "powerbi/data_model.md", "powerbi/theme_loan_risk.json", "sql/01_database_schema.sql", "sql/06_kpi_views.sql"]
    missing = [r for r in required if not (PROJECT_ROOT / r).exists()]
    qa = pd.read_csv(AGGREGATE_DIR / "qa_results.csv")
    counts = qa.result.value_counts().to_dict()
    mark = lambda ok: "Pass" if ok else "ACTION"
    fmt = lambda items: "none" if not items else ", ".join(f"`{i}`" for i in items[:8]) + (f" and {len(items) - 8} more" if len(items) > 8 else "")

    (DOCS_DIR / "publication_checklist.md").write_text(f"""# Publication Checklist

**Status: nothing has been published.** No Git repository was created, no commit was made and no remote was contacted. Publishing waits for explicit approval from the project owner.

Generated by `python/publication_check.py`.

## What would be published

{len(published)} files, {total_mb:,.0f} MB in total, after applying `.gitignore`. Excluded: the raw and processed data, loan-level exports, the virtual environment, logs and the PBIX.

## Automated checks

| Check | Result | Detail |
|---|---|---|
| Raw or loan-level data excluded | {mark(not raw_like)} | {fmt(raw_like)} |
| No file above GitHub's 100 MB limit | {mark(not oversize)} | {fmt(oversize)} |
| No home-directory paths | {mark(not hits['user home path'])} | {fmt(hits['user home path'])} |
| No project absolute paths | {mark(not hits['project absolute path'])} | {fmt(hits['project absolute path'])} |
| No email addresses | {mark(not hits['email address'])} | {fmt(hits['email address'])} |
| No hardcoded passwords or secrets | {mark(not hits['password or secret'])} | {fmt(hits['password or secret'])} |
| Template free of machine paths | {mark(not template_has_path)} | {'`DataFolder` default holds this machine path' if template_has_path else 'Clean'} |
| No unused Python imports | {mark(not unused)} | {json.dumps(unused) if unused else 'none'} |
| Required documents present | {mark(not missing)} | {fmt(missing)} |
| Cross-tool QA | {mark(counts.get('FAIL', 0) == 0)} | {counts.get('Pass', 0)} passed, {counts.get('FAIL', 0)} failed, {counts.get('NOT RUN', 0)} not run |

## Needs your decision or check

- [ ] **Dataset licence.** Confirm the terms on the [Kaggle dataset page](https://www.kaggle.com/datasets/wordsforthewise/lending-club) allow what you plan to publish. Not verified here. Only code, documentation and aggregates are proposed for release, and no raw data.
- [ ] **PBIX.** At 113 MB with all loan-level data embedded, it exceeds GitHub's file limit and is excluded. Recommended: publish the template and screenshots only.
- [ ] **Slicers.** Click a slicer, confirm it carries across pages, then press Clear all slicers. This was not tested through the interface.
- [ ] **Author details.** Add your name and links to the README if you want them.
- [ ] **Repository.** Choose its name and visibility.

## Steps after approval

1. Rebuild the template with a neutral path if the check above flags one: `python powerbi/build_template.py "C:\\path\\to\\data\\exports\\powerbi"`.
2. Rerun this check.
3. Create the repository, review the staged file list, then commit and push.
""", encoding="utf-8")
    print(f"published={len(published)} {total_mb:.0f}MB oversize={oversize} raw={raw_like} hits={ {k: v[:6] for k, v in hits.items()} } template_path={template_has_path} unused={unused} missing={missing} largest_agg={largest_aggregate:.1f}MB")


if __name__ == "__main__":
    main()
