"""Helpers that emit Power BI report-layout JSON, plus the page definitions for this dashboard."""
from __future__ import annotations

import json
import uuid

NAVY_BG = "#0F2A47"
NAVY = "#1F4E79"
TEAL = "#14A098"
GOLD = "#C9A227"
RED = "#C8452F"
SLATE = "#7A8CA5"
INK = "#14263D"
MUTED = "#5B6B7F"
SURFACE = "#FFFFFF"
CANVAS = "#EEF1F5"
LINE = "#D9DFE6"
FONT = "Segoe UI"
F = "fact_loans"

CONTENT_X = 148
CONTENT_W = 1124
PAGES = [
    ("ReportSection1", "Executive Overview"),
    ("ReportSection2", "Borrower Risk"),
    ("ReportSection3", "Loan Performance"),
    ("ReportSection4", "Exposure & Recovery"),
    ("ReportSection5", "Time & Geography"),
    ("ReportSection6", "Risk Insights"),
]
DRILL = ("ReportSection7", "Grade Detail")
TOOLTIP = ("ReportSection8", "Risk Tooltip")


def lit(value):
    if isinstance(value, bool):
        return {"expr": {"Literal": {"Value": "true" if value else "false"}}}
    if isinstance(value, (int, float)):
        return {"expr": {"Literal": {"Value": f"{value}D"}}}
    return {"expr": {"Literal": {"Value": "'" + str(value).replace("'", "''") + "'"}}}


def color(hex_value):
    return {"solid": {"color": lit(hex_value)}}


class Query:
    """Accumulates entities, select items and projections for one visual."""

    def __init__(self):
        self.sources: dict[str, str] = {}
        self.select: list[dict] = []
        self.projections: dict[str, list[dict]] = {}
        self.order: list[dict] = []

    def _src(self, entity: str) -> str:
        if entity not in self.sources:
            self.sources[entity] = f"t{len(self.sources)}"
        return self.sources[entity]

    def _field(self, kind: str, entity: str, prop: str) -> tuple[dict, str]:
        ref = {kind: {"Expression": {"SourceRef": {"Source": self._src(entity)}}, "Property": prop}}
        return ref, f"{entity}.{prop}"

    def column(self, role: str, entity: str, prop: str, display: str | None = None) -> "Query":
        return self._add("Column", role, entity, prop, display)

    def measure(self, role: str, prop: str, display: str | None = None) -> "Query":
        return self._add("Measure", role, F, prop, display)

    def _add(self, kind, role, entity, prop, display) -> "Query":
        ref, name = self._field(kind, entity, prop)
        if not any(s["Name"] == name for s in self.select):
            item = dict(ref)
            item["Name"] = name
            if display:
                item["NativeReferenceName"] = display
            self.select.append(item)
        self.projections.setdefault(role, []).append({"queryRef": name, **({"active": True} if role == "Category" else {})})
        return self

    def sort(self, kind: str, entity: str, prop: str, descending: bool = True) -> "Query":
        ref, _ = self._field(kind, entity, prop)
        self.order.append({"Direction": 2 if descending else 1, "Expression": ref})
        return self

    def prototype(self) -> dict:
        q = {"Version": 2, "From": [{"Name": a, "Entity": e, "Type": 0} for e, a in self.sources.items()], "Select": self.select}
        if self.order:
            q["OrderBy"] = self.order
        return q


class Page:
    def __init__(self, name, display, hidden=False, width=1280, height=720, kind=None):
        self.name, self.display, self.hidden, self.width, self.height, self.kind = name, display, hidden, width, height, kind
        self.visuals: list[dict] = []
        self.z = 0
        self.filters: list[dict] = []

    def add(self, visual_type, x, y, w, h, query=None, objects=None, vc=None, extra=None):
        name = uuid.uuid5(uuid.NAMESPACE_DNS, f"{self.name}-{self.z}").hex[:20]
        single = {"visualType": visual_type, "drillFilterOtherVisuals": True}
        if query:
            single["projections"] = query.projections
            single["prototypeQuery"] = query.prototype()
        if objects:
            single["objects"] = objects
        if vc:
            single["vcObjects"] = vc
        if extra:
            single.update(extra)
        config = {"name": name, "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": self.z, "width": w, "height": h, "tabOrder": self.z}}], "singleVisual": single}
        self.visuals.append({"x": x, "y": y, "z": self.z, "width": w, "height": h, "config": json.dumps(config), "filters": "[]"})
        self.z += 1000
        return name

    def to_section(self, ordinal):
        config = {"objects": {"background": [{"properties": {"color": color(CANVAS if self.kind != "tooltip" else SURFACE), "transparency": lit(0)}}],
                              "outspace": [{"properties": {"color": color(CANVAS), "transparency": lit(0)}}]}}
        if self.hidden:
            config["visibility"] = 1
        if self.kind == "tooltip":
            config["type"] = 1
        if self.kind == "drillthrough":
            config["type"] = 2
        section = {"name": self.name, "displayName": self.display, "filters": json.dumps(self.filters), "ordinal": ordinal, "width": self.width, "height": self.height,
                   "displayOption": 3 if self.kind == "tooltip" else 1, "config": json.dumps(config), "visualContainers": self.visuals}
        return section


def title_objects(title, subtitle=None):
    vc = {
        "title": [{"properties": {"show": lit(True), "text": lit(title), "fontColor": color(INK), "fontSize": lit(11), "bold": lit(True), "fontFamily": lit(FONT), "alignment": lit("left")}}],
        "background": [{"properties": {"show": lit(True), "color": color(SURFACE), "transparency": lit(0)}}],
        "border": [{"properties": {"show": lit(True), "color": color(LINE), "radius": lit(4)}}],
        "padding": [{"properties": {"top": lit(6), "bottom": lit(4), "left": lit(8), "right": lit(8)}}],
    }
    if subtitle:
        vc["subTitle"] = [{"properties": {"show": lit(True), "text": lit(subtitle), "fontColor": color(MUTED), "fontSize": lit(8), "fontFamily": lit(FONT), "alignment": lit("left")}}]
    return vc


def text(page, x, y, w, h, runs, background=None):
    """runs: list of paragraphs; each paragraph is a list of (text, size, color, bold)."""
    paragraphs = []
    for para in runs:
        paragraphs.append({"textRuns": [{"value": t, "textStyle": {"fontFamily": FONT, "fontSize": f"{size}pt", "color": col, **({"fontWeight": "bold"} if bold else {})}} for t, size, col, bold in para]})
    vc = {"background": [{"properties": {"show": lit(bool(background)), **({"color": color(background), "transparency": lit(0)} if background else {})}}]}
    page.add("textbox", x, y, w, h, objects={"general": [{"properties": {"paragraphs": paragraphs}}]}, vc=vc)


def card(page, x, y, w, h, measure, label, tone=INK):
    q = Query().measure("Values", measure)
    objects = {"labels": [{"properties": {"color": color(tone), "fontSize": lit(16), "fontFamily": lit("Segoe UI Semibold"), "labelPrecision": lit(2)}}],
               "categoryLabels": [{"properties": {"show": lit(True), "color": color(MUTED), "fontSize": lit(8), "fontFamily": lit(FONT)}}]}
    vc = {"background": [{"properties": {"show": lit(True), "color": color(SURFACE), "transparency": lit(0)}}],
          "border": [{"properties": {"show": lit(True), "color": color(LINE), "radius": lit(4)}}],
          "title": [{"properties": {"show": lit(False)}}]}
    objects["categoryLabels"][0]["properties"]["show"] = lit(True)
    q.select[0]["NativeReferenceName"] = label
    page.add("card", x, y, w, h, q, objects, vc, extra={"columnProperties": {f"{F}.{measure}": {"displayName": label}}})


def axes(show_value_axis=False, label_format=True):
    return {
        "categoryAxis": [{"properties": {"show": lit(True), "showAxisTitle": lit(False), "labelColor": color(MUTED), "fontSize": lit(8), "gridlineShow": lit(False)}}],
        "valueAxis": [{"properties": {"show": lit(show_value_axis), "showAxisTitle": lit(False), "labelColor": color(MUTED), "fontSize": lit(8), "gridlineShow": lit(show_value_axis), "gridlineColor": color(LINE)}}],
        "labels": [{"properties": {"show": lit(not show_value_axis), "color": color(INK), "fontSize": lit(8), "labelPosition": lit("OutsideEnd")}}],
        "legend": [{"properties": {"show": lit(False)}}],
    }


def fill_rule(measure="Rate Color"):
    return [{"properties": {"fill": {"solid": {"color": {"expr": {"Measure": {"Expression": {"SourceRef": {"Entity": F}}, "Property": measure}}}}}},
             "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}]


def solid_fill(hex_value):
    return [{"properties": {"fill": color(hex_value)}}]


def bar(page, x, y, w, h, entity, column, measure, title, subtitle=None, horizontal=False, rule=False, tone=NAVY, sort_measure=False, tooltip=True, labels=True):
    kind = "clusteredBarChart" if horizontal else "clusteredColumnChart"
    q = Query().column("Category", entity, column).measure("Y", measure)
    if sort_measure:
        q.sort("Measure", F, measure)
    else:
        q.sort("Column", entity, column, descending=False)
    objects = axes(show_value_axis=not labels)
    if column == "issue_year":
        objects["categoryAxis"][0]["properties"]["axisType"] = lit("Categorical")
    if not labels:
        objects["categoryAxis"][0]["properties"]["preferredCategoryWidth"] = lit(14)
    objects["dataPoint"] = fill_rule() if rule else solid_fill(tone)
    vc = title_objects(title, subtitle)
    if tooltip:
        vc["visualTooltip"] = [{"properties": {"show": lit(True), "type": lit("Canvas"), "section": lit(TOOLTIP[0])}}]
    return page.add(kind, x, y, w, h, q, objects, vc)


def multi_measure(page, kind, x, y, w, h, entity, column, measures, colors, title, subtitle=None, descending=False):
    q = Query().column("Category", entity, column)
    for m in measures:
        q.measure("Y", m)
    q.sort("Column", entity, column, descending=descending)
    objects = axes(show_value_axis=True)
    objects["legend"] = [{"properties": {"show": lit(True), "position": lit("Top"), "showTitle": lit(False), "fontSize": lit(8), "labelColor": color(MUTED)}}]
    if kind == "lineChart":
        objects["lineStyles"] = [{"properties": {"strokeWidth": lit(2), "showMarker": lit(True), "markerSize": lit(6)}}]
    objects["dataPoint"] = [{"properties": {"fill": color(c)}, "selector": {"metadata": f"{F}.{m}"}} for m, c in zip(measures, colors)]
    return page.add(kind, x, y, w, h, q, objects, title_objects(title, subtitle))


def line(page, x, y, w, h, entity, column, measure, title, subtitle=None, tone=NAVY, series=None, continuous=False):
    q = Query().column("Category", entity, column).measure("Y", measure)
    if series:
        q.column("Series", *series)
    q.sort("Column", entity, column, descending=False)
    objects = axes(show_value_axis=True)
    if not continuous:
        objects["categoryAxis"][0]["properties"]["axisType"] = lit("Categorical")
        objects["categoryAxis"][0]["properties"]["preferredCategoryWidth"] = lit(14)
    objects["lineStyles"] = [{"properties": {"strokeWidth": lit(2), "showMarker": lit(not continuous), "markerSize": lit(6)}}]
    if series:
        objects["legend"] = [{"properties": {"show": lit(True), "position": lit("Top"), "showTitle": lit(False), "fontSize": lit(8), "labelColor": color(MUTED)}}]
    else:
        objects["dataPoint"] = solid_fill(tone)
    return page.add("lineChart", x, y, w, h, q, objects, title_objects(title, subtitle))


def table(page, x, y, w, h, columns, title, subtitle=None, sort=None, font=8):
    q = Query()
    names = {}
    for kind, entity, prop, display in columns:
        if kind == "c":
            q.column("Values", entity, prop)
            names[f"{entity}.{prop}"] = {"displayName": display}
        else:
            q.measure("Values", prop)
            names[f"{F}.{prop}"] = {"displayName": display}
    if sort:
        q.sort(*sort)
    objects = {"grid": [{"properties": {"gridVertical": lit(False), "rowPadding": lit(2), "outlineColor": color(LINE)}}],
               "columnHeaders": [{"properties": {"fontColor": color("#FFFFFF"), "backColor": color(NAVY), "fontSize": lit(font), "fontFamily": lit(FONT)}}],
               "values": [{"properties": {"fontColorPrimary": color(INK), "fontSize": lit(font), "fontFamily": lit(FONT), "backColorSecondary": color("#F6F8FA")}}],
               "total": [{"properties": {"totals": lit(False)}}]}
    return page.add("tableEx", x, y, w, h, q, objects, title_objects(title, subtitle), extra={"columnProperties": names})


def slicer(page, x, y, w, h, entity, column, label, group):
    q = Query().column("Values", entity, column)
    objects = {"data": [{"properties": {"mode": lit("Dropdown")}}],
               "header": [{"properties": {"show": lit(True), "text": lit(label), "fontColor": color(MUTED), "textSize": lit(8), "fontFamily": lit(FONT)}}],
               "items": [{"properties": {"fontColor": color(INK), "textSize": lit(9)}}],
               "selection": [{"properties": {"selectAllCheckboxEnabled": lit(True)}}]}
    vc = {"background": [{"properties": {"show": lit(True), "color": color(SURFACE), "transparency": lit(0)}}],
          "border": [{"properties": {"show": lit(True), "color": color(LINE), "radius": lit(4)}}],
          "title": [{"properties": {"show": lit(False)}}]}
    page.add("slicer", x, y, w, h, q, objects, vc, extra={"syncGroup": {"groupName": group, "fieldChanges": True, "filterChanges": True}})


def nav_button(page, x, y, w, h, label, link, active=False):
    """Visible label is a text box; a transparent button above it takes the click."""
    text(page, x, y, w, h, [[(label, 9, "#FFFFFF", active)]], background=TEAL if active else NAVY)
    objects = {"fill": [{"properties": {"show": lit(False), "transparency": lit(100)}, "selector": {"id": "default"}}],
               "outline": [{"properties": {"show": lit(False), "transparency": lit(100)}, "selector": {"id": "default"}}],
               "text": [{"properties": {"show": lit(True), "fontColor": color("#FFFFFF"), "fontSize": lit(9), "horizontalAlignment": lit("left")}, "selector": {"id": "default"}}],
               "icon": [{"properties": {"show": lit(False)}, "selector": {"id": "default"}}]}
    vc = {"visualLink": [{"properties": link}], "title": [{"properties": {"show": lit(False)}}], "background": [{"properties": {"show": lit(False)}}]}
    page.add("actionButton", x, y, w, h, None, objects, vc)


def chrome(page, subtitle):
    """Navigation rail, header and population label shared by the analysis pages."""
    text(page, 0, 0, 140, 720, [[(" ", 8, "#FFFFFF", False)]], background=NAVY_BG)
    text(page, 4, 4, 134, 72, [[("Loan Default Risk", 10, "#FFFFFF", True)], [("Credit Portfolio Analytics", 7, "#B9C6D6", False)]])
    y = 80
    for section, display in PAGES:
        nav_button(page, 8, y, 124, 32, display, {"show": lit(True), "type": lit("PageNavigation"), "navigationSection": lit(section)}, active=section == page.name)
        y += 36
    nav_button(page, 8, y + 14, 124, 32, " ", {"show": lit(True), "type": lit("ClearAllSlicers")})
    text(page, 4, 630, 134, 86, [[("Default rate = Charged Off / (Fully Paid + Charged Off). Unresolved loans are excluded.", 7, "#B9C6D6", False)]])
    text(page, CONTENT_X, -2, 620, 40, [[(page.display, 15, INK, True)]])
    text(page, CONTENT_X, 24, 720, 26, [[(subtitle, 8, MUTED, False)]])
    q = Query().measure("Values", "Scope Label")
    objects = {"labels": [{"properties": {"color": color(MUTED), "fontSize": lit(8), "fontFamily": lit(FONT)}}], "categoryLabels": [{"properties": {"show": lit(False)}}]}
    page.add("card", 770, 6, 502, 40, q, objects, {"title": [{"properties": {"show": lit(False)}}], "background": [{"properties": {"show": lit(False)}}]})


def slicers(page, y=112):
    w = (CONTENT_W - 4 * 6) // 5
    spec = [("dim_date", "issue_year", "Origination year", "year"), ("dim_grade", "grade", "Loan grade", "grade"), ("dim_purpose", "purpose_label", "Loan purpose", "purpose"),
            ("dim_term", "term_label", "Loan term", "term"), ("dim_state", "state_name", "State", "state")]
    for i, (entity, column, label, group) in enumerate(spec):
        slicer(page, CONTENT_X + i * (w + 6), y, w, 52, entity, column, label, group)


def card_row(page, specs, y=50, h=60):
    gap = 6
    w = (CONTENT_W - gap * (len(specs) - 1)) // len(specs)
    for i, spec in enumerate(specs):
        card(page, CONTENT_X + i * (w + gap), y, w, h, *spec)


def grid_positions(rows=2, cols=3, top=168, bottom=714, gap=6):
    w = (CONTENT_W - gap * (cols - 1)) // cols
    h = (bottom - top - gap * (rows - 1)) // rows
    return [(CONTENT_X + c * (w + gap), top + r * (h + gap), w, h) for r in range(rows) for c in range(cols)]


def build_pages(insights: dict) -> list[Page]:
    pages = []

    # Page 1: Executive overview
    p = Page(*PAGES[0])
    chrome(p, "How is the portfolio performing, and where do charge-offs sit?")
    card_row(p, [("Total Loans", "Total Loans"), ("Total Funded Amount", "Total Funded"), ("Fully Paid Loans", "Fully Paid"), ("Charged-Off Loans", "Charged Off"),
                 ("Historical Default Rate", "Historical Default Rate", RED), ("Average Interest Rate", "Avg Interest Rate"), ("Average Loan Amount", "Avg Loan Amount"),
                 ("Charged-Off Principal Exposure", "Charged-Off Principal", RED)])
    slicers(p)
    g = grid_positions()
    bar(p, *g[0], "dim_status", "status_clean", "Total Loans", "Portfolio status", "Loans by status. Only Fully Paid and Charged Off enter the default rate", horizontal=True)
    bar(p, *g[1], "dim_date", "issue_year", "Loan Origination Count", "Originations by year", "Number of loans issued")
    bar(p, *g[2], "dim_grade", "grade", "Total Funded Amount", "Funded amount by grade", "Original funded principal")
    bar(p, *g[3], "dim_grade", "grade", "Historical Default Rate", "Default rate by grade", "Red: 1.25x+ selection rate. Teal: under 0.75x. Right-click a bar to drill through", rule=True)
    bar(p, *g[4], "dim_purpose", "purpose_label", "Total Loans", "Loan purpose", "Loans by stated purpose", horizontal=True, sort_measure=True)
    bar(p, *g[5], "dim_term", "term_label", "Total Loans", "Loan term", "Loans by contract term")
    pages.append(p)

    # Page 2: Borrower risk
    p = Page(*PAGES[1])
    chrome(p, "Which borrower characteristics are associated with higher charge-off rates? Associations, not causes.")
    card_row(p, [("Average Annual Income", "Avg Annual Income"), ("Median Annual Income", "Median Annual Income"), ("Average DTI", "Avg DTI"), ("Average Loan Amount", "Avg Loan Amount"), ("Average Employment Length", "Avg Employment (yrs, capped at 10)")])
    slicers(p)
    g = grid_positions()
    for pos, (e, c, t, s) in zip(g, [
        ("dim_income_band", "income_band", "Default rate by income band", "Zero incomes shown as Unknown"),
        ("dim_dti_band", "dti_band", "Default rate by DTI band", "Debt-to-income, placeholders shown as Unknown"),
        ("dim_emp_length", "emp_length_label", "Default rate by employment length", "Missing length stands apart from every stated length"),
        ("dim_home_ownership", "home_ownership_group", "Default rate by home ownership", "OTHER groups ANY, NONE and OTHER"),
        ("dim_verification", "verification_status", "Default rate by verification status", "Likely reflects who gets verified, not verification itself"),
        ("dim_fico_band", "fico_band", "Default rate by FICO band", "FICO at origination; a credit-history indicator"),
    ]):
        bar(p, *pos, e, c, "Historical Default Rate", t, s, rule=True)
    pages.append(p)

    # Page 3: Loan performance
    p = Page(*PAGES[2])
    chrome(p, "Which loan characteristics are associated with weaker repayment outcomes?")
    card_row(p, [("Average Interest Rate", "Avg Interest Rate"), ("Average Loan Term", "Avg Term (months)"), ("Total Funded Amount", "Total Loan Amount"), ("Charged-Off Loans", "Charged-Off Loans", RED)])
    slicers(p)
    g = grid_positions()
    bar(p, *g[0], "dim_grade", "grade", "Historical Default Rate", "Default rate by grade", "Resolved loans", rule=True)
    bar(p, *g[1], "dim_grade", "sub_grade", "Historical Default Rate", "Default rate by subgrade", "Resolved loans. Scroll for all 35 subgrades", rule=True, labels=False)
    bar(p, *g[2], "dim_purpose", "purpose_label", "Historical Default Rate", "Default rate by purpose", "Sorted highest first", horizontal=True, rule=True, sort_measure=True)
    multi_measure(p, "lineChart", *g[3], "dim_grade", "grade", ["Rate P25", "Rate Median", "Rate P75"], [SLATE, NAVY, TEAL], "Interest rate distribution by grade", "25th percentile, median and 75th percentile")
    multi_measure(p, "clusteredBarChart", *g[4], "dim_status", "status_clean", ["Amount P25", "Amount Median", "Amount P75"], [SLATE, NAVY, TEAL], "Loan amount distribution by status", "25th percentile, median and 75th percentile")
    multi_measure(p, "clusteredColumnChart", *g[5], "dim_term", "term_label", ["Historical Default Rate", "Mature Default Rate"], [NAVY, TEAL], "Term versus default rate", "Resolved-only rate overstates young loans; mature rate is lower")
    pages.append(p)

    # Page 4: Exposure and recovery
    p = Page(*PAGES[3])
    chrome(p, "Reported cash and calculated estimates. None of these figures is an accounting loss.")
    card_row(p, [("Total Funded Amount", "Principal Funded"), ("Total Principal Received", "Principal Received"), ("Total Recoveries", "Recoveries (gross)"), ("Total Recovery Fees", "Recovery Fees"),
                 ("Charged-Off Principal Exposure", "Charged-Off Principal (calc.)", RED), ("Recovery Ratio", "Recovery / Charged-Off Principal")])
    slicers(p)
    g = grid_positions()
    multi_measure(p, "clusteredColumnChart", *g[0], "dim_grade", "grade", ["Total Funded Amount", "Total Payments Received"], [NAVY, TEAL], "Funded versus payments received", "Reported cash, all statuses. Young loans have not finished paying")
    bar(p, *g[1], "dim_grade", "grade", "Charged-Off Principal Exposure", "Charged-off principal by grade", "Calculated: funded minus principal repaid", tone=RED)
    bar(p, *g[2], "dim_purpose", "purpose_label", "Charged-Off Principal Exposure", "Charged-off principal by purpose", "Calculated; sorted largest first", horizontal=True, tone=RED, sort_measure=True)
    bar(p, *g[3], "dim_grade", "grade", "Total Recoveries", "Recoveries by grade", "Reported, gross of fees", tone=TEAL)
    line(p, *g[4], "dim_date", "issue_year", "Recovery Ratio", "Recovery ratio by origination year", "No recovery dates exist in the data; newer cohorts have had less time", tone=TEAL)
    bar(p, *g[5], "dim_amount_band", "amount_band", "Historical Default Rate", "Default rate by principal band", "Funded amount at origination", rule=True)
    pages.append(p)

    # Page 5: Time and geography
    p = Page(*PAGES[4])
    chrome(p, "Historical trends and geographic patterns. Geographic differences are descriptive, not causal.")
    slicers(p, y=52)
    g = grid_positions(rows=2, cols=4, top=108)
    bar(p, *g[0], "dim_date", "issue_year", "Loan Origination Amount", "Originations by year", "Funded amount")
    line(p, *g[1], "dim_date", "date", "Loan Origination Count", "Originations by month", "Loans issued each month", continuous=True)
    line(p, *g[2], "dim_date", "issue_year", "Mature Cohort Default Rate", "Mature-cohort default rate", "Only cohorts with 99%+ of terms elapsed", series=("dim_term", "term_label"))
    line(p, *g[3], "dim_date", "issue_year", "Average Interest Rate", "Average interest rate by year", "Unweighted mean contract rate")
    bar(p, *g[4], "dim_state", "addr_state", "Total Loans", "Loans by state", "Largest first; scroll for all states", horizontal=True, sort_measure=True)
    bar(p, *g[5], "dim_state", "addr_state", "Historical Default Rate", "Default rate by state", "Highest first. Iowa has only 7 resolved loans; ignore its rate", horizontal=True, rule=True, sort_measure=True)
    bar(p, *g[6], "dim_state", "addr_state", "Charged-Off Principal Exposure", "Charged-off principal by state", "Largest first", horizontal=True, tone=RED, sort_measure=True)
    table(p, *g[7], [("c", "dim_state", "state_name", "State"), ("m", None, "Total Loans", "Loans"), ("m", None, "Historical Default Rate", "Rate"), ("m", None, "Resolved Loans", "Resolved")], "State detail", "All states, with sample size", sort=("Measure", F, "Total Loans"))
    pages.append(p)

    # Page 6: Insights, recommendations, limitations
    p = Page(*PAGES[5])
    chrome(p, "Figures in the text panels describe the full portfolio and do not respond to filters. Tables do respond.")
    g = grid_positions(rows=2, cols=3, top=52, bottom=420)
    table(p, *g[0], [("c", "dim_risk_segment", "risk_segment", "Segment"), ("c", "dim_risk_segment", "risk_tier", "Tier"), ("m", None, "Mature Default Rate", "Mature rate"), ("m", None, "Share of Funded", "% funded"), ("m", None, "Share of Exposure", "% charged-off")],
          "Risk segments: grade x term", "Retrospective; not an underwriting rule", sort=("Measure", F, "Mature Default Rate"))
    table(p, *g[1], [("c", "dim_grade", "grade", "Grade"), ("m", None, "Historical Default Rate", "Rate"), ("m", None, "Mature Default Rate", "Mature"), ("m", None, "Recovery Ratio", "Recovery"), ("m", None, "Loss Concentration Index", "Loss index")],
          "Highest-risk grades", "Index above 1: more exposure than funding share", sort=("Measure", F, "Historical Default Rate"))
    table(p, *g[2], [("c", "dim_purpose", "purpose_label", "Purpose"), ("m", None, "Historical Default Rate", "Rate"), ("m", None, "Share of Exposure", "% charged-off")],
          "Purpose comparison", "Rate and share of charged-off principal", sort=("Measure", F, "Historical Default Rate"))
    table(p, g[3][0], g[3][1], g[3][2] * 2 + 6, g[3][3], [("c", "ref_statistical_findings", "test_name", "Test"), ("c", "ref_statistical_findings", "p_value_display", "p-value"), ("c", "ref_statistical_findings", "effect_size", "Effect size")],
          "Statistical findings", "With 1M+ loans almost everything is significant, so read the effect size", sort=("Column", "ref_statistical_findings", "finding_sort", False))
    bar(p, *g[5], "dim_risk_segment", "risk_tier", "Risk Segment Distribution", "Loans by retrospective tier", "Low, Medium and High, by mature-cohort rate relative to the portfolio", tooltip=False)

    column_w = (CONTENT_W - 12) // 3
    panel_y, panel_h = 426, 288
    def panel(i, heading, items):
        paragraphs = [[(heading, 11, NAVY, True)]] + [[("- " + item, 8, INK, False)] for item in items]
        text(p, CONTENT_X + i * (column_w + 6), panel_y, column_w, panel_h, paragraphs, background=SURFACE)
    panel(0, "Key findings", insights["findings"])
    panel(1, "Management recommendations", insights["recommendations"])
    panel(2, "Limitations", insights["limitations"])
    pages.append(p)

    # Drill-through page on grade
    p = Page(*DRILL, hidden=True, kind="drillthrough")
    p.filters = [{"name": "drillGrade", "expression": {"Column": {"Expression": {"SourceRef": {"Entity": "dim_grade"}}, "Property": "grade"}}, "type": "Categorical", "howCreated": 5}]
    chrome(p, "Drill-through from any grade: right-click a bar and choose Drill through.")
    q = Query().measure("Values", "Drill Title")
    p.add("card", CONTENT_X, 50, 300, 60, q, {"labels": [{"properties": {"color": color(NAVY), "fontSize": lit(16)}}], "categoryLabels": [{"properties": {"show": lit(False)}}]}, {"title": [{"properties": {"show": lit(False)}}]})
    specs = [("Historical Default Rate", "Default Rate", RED), ("Mature Default Rate", "Mature Rate"), ("Total Funded Amount", "Funded"), ("Charged-Off Principal Exposure", "Charged-Off Principal", RED), ("Recovery Ratio", "Recovery Ratio")]
    w = (CONTENT_W - 306 - 4 * 6) // 5
    for i, spec in enumerate(specs):
        card(p, CONTENT_X + 306 + i * (w + 6), 50, w, 60, *spec)
    g = grid_positions(top=114)
    bar(p, *g[0], "dim_grade", "sub_grade", "Historical Default Rate", "Default rate by subgrade", tooltip=False, rule=True, labels=False)
    bar(p, *g[1], "dim_term", "term_label", "Mature Default Rate", "Mature default rate by term", tooltip=False)
    bar(p, *g[2], "dim_purpose", "purpose_label", "Charged-Off Principal Exposure", "Charged-off principal by purpose", horizontal=True, tone=RED, sort_measure=True, tooltip=False)
    bar(p, *g[3], "dim_dti_band", "dti_band", "Historical Default Rate", "Default rate by DTI band", tooltip=False, rule=True)
    bar(p, *g[4], "dim_credit_history_band", "credit_history_band", "Historical Default Rate", "Default rate by credit history length", tooltip=False, rule=True)
    bar(p, *g[5], "dim_delinq_band", "delinq_band", "Historical Default Rate", "Default rate by 2-year delinquencies", tooltip=False, rule=True)
    pages.append(p)

    # Report-page tooltip
    p = Page(*TOOLTIP, hidden=True, width=320, height=240, kind="tooltip")
    rows = [("Historical Default Rate", "Default rate"), ("Default Rate CI Low", "95% CI low"), ("Default Rate CI High", "95% CI high"), ("Resolved Loans", "Resolved loans"), ("Charged-Off Loans", "Charged off"), ("Mature Default Rate", "Mature rate")]
    for i, spec in enumerate(rows):
        card(p, 6 + (i % 2) * 156, 6 + (i // 2) * 77, 152, 73, *spec)
    pages.append(p)
    return pages
