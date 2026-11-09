"""Generate Loan_Default_Risk_Dashboard.pbit plus theme, DAX and data-model documentation.

Usage: python build_template.py [data_folder]
The data folder is a Power Query parameter (DataFolder), so the template contains no fixed
machine path other than this default, which can be changed under Transform data.
"""
from __future__ import annotations

import json
import sys
import uuid
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "python"))
sys.path.insert(0, str(HERE))

from config import EXPORT_DIR, connect  # noqa: E402
from model_definition import DIMENSIONS, F, MEASURES, REFERENCE_TABLES  # noqa: E402
from report_layout import DRILL, GOLD, INK, NAVY, RED, SLATE, TEAL, TOOLTIP, build_pages  # noqa: E402
from insights import build_insights  # noqa: E402

OUT = EXPORT_DIR / "powerbi"
TEMPLATE = HERE / "Loan_Default_Risk_Dashboard.pbit"
TYPE_MAP = {"BIGINT": "int64", "INTEGER": "int64", "DOUBLE": "double", "DATE": "dateTime", "VARCHAR": "string", "TIMESTAMP": "dateTime"}
THEME = {
    "name": "Loan Risk Navy",
    "dataColors": [NAVY, TEAL, GOLD, RED, SLATE, "#3E7CB1", "#7FC8C2", "#8C6D1F"],
    "background": "#FFFFFF", "foreground": INK, "tableAccent": NAVY,
    "good": TEAL, "neutral": GOLD, "bad": RED, "maximum": RED, "center": "#FFFFFF", "minimum": NAVY,
    "textClasses": {"title": {"fontFace": "Segoe UI Semibold", "fontSize": 12, "color": INK}, "label": {"fontFace": "Segoe UI", "fontSize": 9, "color": "#5B6B7F"},
                    "callout": {"fontFace": "Segoe UI Semibold", "fontSize": 18, "color": INK}, "header": {"fontFace": "Segoe UI Semibold", "fontSize": 11, "color": INK}},
}


def table_def(con, name: str, hidden_columns=(), key=None, sort_map=None, hide_table=False, data_category=None):
    path = OUT / f"{name}.parquet"
    schema = con.execute(f"DESCRIBE SELECT * FROM '{path.as_posix()}'").fetchall()
    sort_map = sort_map or {}
    columns = []
    for col, ctype, *_ in schema:
        definition = {"name": col, "dataType": TYPE_MAP[ctype], "sourceColumn": col, "summarizeBy": "none", "lineageTag": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{name}.{col}"))}
        if ctype == "DATE":
            definition["formatString"] = "yyyy-mm-dd"
        if col in hidden_columns or col.endswith("_sort"):
            definition["isHidden"] = True
        if col in sort_map:
            definition["sortByColumn"] = sort_map[col]
        if key == col:
            definition["isKey"] = True
        columns.append(definition)
    source = f'let\n    Source = Parquet.Document(File.Contents(DataFolder & "\\{name}.parquet"))\nin\n    Source'
    table = {"name": name, "lineageTag": str(uuid.uuid5(uuid.NAMESPACE_DNS, name)), "columns": columns,
             "partitions": [{"name": name, "mode": "import", "source": {"type": "m", "expression": source}}]}
    if hide_table:
        table["isHidden"] = True
    if data_category:
        table["dataCategory"] = data_category
    return table


def build_model(con, data_folder: str) -> dict:
    fact_path = OUT / "fact_loans.parquet"
    fact_cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM '{fact_path.as_posix()}'").fetchall()]
    fact = table_def(con, F, hidden_columns=fact_cols)
    fact["measures"] = []
    for name, description, expression, fmt, folder in MEASURES:
        measure = {"name": name, "expression": expression, "description": description, "displayFolder": folder, "lineageTag": str(uuid.uuid5(uuid.NAMESPACE_DNS, "m." + name))}
        if fmt:
            measure["formatString"] = fmt
        fact["measures"].append(measure)

    tables = [fact]
    relationships = []
    for dim, key, fact_column, sort_map in DIMENSIONS:
        # Only the date table needs a key column; a key on band tables is unnecessary.
        tables.append(table_def(con, dim, key=key if dim == "dim_date" else None, sort_map=sort_map, data_category="Time" if dim == "dim_date" else None))
        relationships.append({"name": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"rel.{dim}")), "fromTable": F, "fromColumn": fact_column, "toTable": dim, "toColumn": key})
    for ref in REFERENCE_TABLES:
        tables.append(table_def(con, ref, sort_map={"test_name": "finding_sort"}))
    # Year comes from the date dimension, so it stays non-aggregated and hidden columns stay out of field lists.
    expression = f'"{data_folder}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'
    return {
        "name": str(uuid.uuid5(uuid.NAMESPACE_DNS, "loan-default-model")),
        "compatibilityLevel": 1567,
        "model": {
            "culture": "en-US", "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": True}, "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-US", "tables": tables, "relationships": relationships,
            "expressions": [{"name": "DataFolder", "kind": "m", "expression": expression, "lineageTag": str(uuid.uuid5(uuid.NAMESPACE_DNS, "DataFolder")),
                             "annotations": [{"name": "PBI_ResultType", "value": "Text"}]}],
            "annotations": [{"name": "__PBI_TimeIntelligenceEnabled", "value": "0"}, {"name": "PBIDesktopVersion", "value": "2.148.878.0"}],
        },
    }


def build_layout() -> dict:
    pages = build_pages(build_insights())
    theme_name = "LoanRiskNavy.json"
    config = {"version": "5.59", "themeCollection": {"baseTheme": {"name": "CY24SU10", "version": "5.59", "type": 2},
                                                     "customTheme": {"name": theme_name, "version": "5.59", "type": 1}},
              "activeSectionIndex": 0, "defaultDrillFilterOtherVisuals": True, "settings": {"useNewFilterPaneExperience": True, "allowChangeFilterTypes": True, "useStylableVisualContainerHeader": True, "exportDataMode": 1}}
    # "Pods" bind the hidden pages: type 1 is drill-through (with its parameter), type 2 is report-page tooltip.
    drill_expr = {"Column": {"Expression": {"SourceRef": {"Entity": "dim_grade"}}, "Property": "grade"}}
    pods = [{"name": "PodGradeDetail", "boundSection": DRILL[0], "type": 1, "referenceScope": 0, "config": json.dumps({"acceptsFilterContext": 0}),
             "parameters": json.dumps([{"name": "Param_drillGrade", "boundFilter": "drillGrade", "fieldExpr": drill_expr}])},
            {"name": "PodRiskTooltip", "boundSection": TOOLTIP[0], "type": 2, "referenceScope": 0, "config": json.dumps({"acceptsFilterContext": 0})}]
    return {"id": 0, "pods": pods, "resourcePackages": [{"resourcePackage": {"name": "RegisteredResources", "type": 1, "items": [{"name": theme_name, "path": theme_name, "type": 202}], "disabled": False}}],
            "sections": [page.to_section(i) for i, page in enumerate(pages)], "config": json.dumps(config), "layoutOptimization": 0}


CONTENT_TYPES = ('<?xml version="1.0" encoding="utf-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                 '<Default Extension="json" ContentType="application/json"/><Override PartName="/Version" ContentType=""/><Override PartName="/DataModelSchema" ContentType=""/>'
                 '<Override PartName="/DiagramLayout" ContentType=""/><Override PartName="/Report/Layout" ContentType=""/><Override PartName="/Settings" ContentType=""/>'
                 '<Override PartName="/Metadata" ContentType=""/></Types>')


def utf16(obj) -> bytes:
    return (obj if isinstance(obj, str) else json.dumps(obj)).encode("utf-16-le")


def write_template(model: dict, layout: dict) -> None:
    theme = json.dumps(THEME, indent=2)
    (HERE / "theme_loan_risk.json").write_text(theme, encoding="utf-8")
    with zipfile.ZipFile(TEMPLATE, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("Version", utf16("1.28"))
        archive.writestr("DataModelSchema", utf16(model))
        archive.writestr("DiagramLayout", utf16({"version": "1.1.0", "diagrams": [], "selectedDiagram": "All tables", "defaultDiagram": "All tables"}))
        archive.writestr("Report/Layout", utf16(layout))
        archive.writestr("Report/StaticResources/RegisteredResources/LoanRiskNavy.json", theme)
        archive.writestr("Settings", utf16({"Version": 4, "ReportSettings": {}, "QueriesSettings": {"TypeDetectionEnabled": False, "RelationshipImportEnabled": False, "Version": "2.148.878.0"}}))
        archive.writestr("Metadata", utf16({"Version": 5, "AutoCreatedRelationships": [], "CreatedFrom": "Cloud", "CreatedFromRelease": "2025.10"}))


def write_docs() -> None:
    lines = ["# DAX Measures", "", "Generated from `powerbi/model_definition.py`. All measures live on `fact_loans` in display folders.", ""]
    for folder in dict.fromkeys(m[4] for m in MEASURES):
        lines += [f"## {folder}", ""]
        for name, description, expression, fmt, _ in (m for m in MEASURES if m[4] == folder):
            lines += [f"### {name}", "", description, "", f"Format: `{fmt or 'text'}`", "", "```dax", f"{name} =", expression, "```", ""]
    (HERE / "dax_measures.md").write_text("\n".join(lines), encoding="utf-8")
    (HERE / "measure_names.txt").write_text(chr(10).join(m[0] for m in MEASURES), encoding="utf-8")

    rows = "\n".join(f"| `{dim}` | `{key}` | `{F}[{fc}]` | 1:many, single direction |" for dim, key, fc, _ in DIMENSIONS)
    doc = f"""# Power BI Data Model

Star schema: one fact table of all 2,260,668 loans at loan grain and {len(DIMENSIONS)} dimensions, plus `ref_statistical_findings`, an unrelated reference table for the insights page.

| Dimension | Key | Fact column | Relationship |
|---|---|---|---|
{rows}

## Design decisions

* **Grain and scope.** All loans are imported with no sampling. Only the columns the report uses are included, so 186 cleaned columns become {len(__import__('duckdb').sql(f"DESCRIBE SELECT * FROM '{(OUT / 'fact_loans.parquet').as_posix()}'").fetchall())} in the fact table.
* **Source.** Parquet files in `data/exports/powerbi/`, read through the `DataFolder` Power Query parameter. Change it under Transform data to move the project.
* **Date table.** `dim_date` holds every day from 2007 to 2019 and is marked as a date table. Issue dates are stored as the first of the month, which is all the source records. Auto date/time is off.
* **Bands.** Each band has a hidden sort column, so `<$40K` sorts before `$40K-$60K`.
* **Filter direction.** All relationships are single direction from dimension to fact, so totals stay predictable.
* **Hidden fact columns.** Fact columns are hidden; users work through dimensions and measures.
* **Maps.** State visuals are ranked bars and a table instead of a map. State codes are clean, but map visuals send data to an online service and a ranked view reads sample sizes more easily.
* **Boxplots.** Power BI has no native box plot, so distributions use P25, median and P75 measures on one axis.
"""
    (HERE / "data_model.md").write_text(doc, encoding="utf-8")


def main() -> None:
    con = connect()
    data_folder = sys.argv[1] if len(sys.argv) > 1 else str(OUT.resolve())
    model = build_model(con, data_folder)
    layout = build_layout()
    write_template(model, layout)
    write_docs()
    print(f"Wrote {TEMPLATE} ({TEMPLATE.stat().st_size / 1024:.0f} KB), {len(MEASURES)} measures, {len(layout['sections'])} pages")


if __name__ == "__main__":
    main()
