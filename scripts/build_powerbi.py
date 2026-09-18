"""Generate an editable PBIP report and semantic model from the actual dbt mart CSVs.

Report structure follows Microsoft's public PBIR schemas; no external report is copied.
Run after `aquawatch analytics`. Use --data-dir to set the Power Query folder parameter.
"""

from __future__ import annotations

import argparse
import csv
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PBI = ROOT / "powerbi"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/"


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def literal(value):
    if isinstance(value, bool):
        raw = str(value).lower()
    elif isinstance(value, (int, float)):
        raw = f"{value}D"
    else:
        raw = "'" + str(value).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": raw}}}


def field(table, prop, measure=False):
    return {
        "Measure" if measure else "Column": {
            "Expression": {"SourceRef": {"Entity": table}},
            "Property": prop,
        }
    }


def projection(table, prop, measure=False):
    labels = {
        "meter_id": "Meter",
        "invoice_id": "Invoice",
        "title": "Investigation",
        "event_date": "Event date",
        "amount_cents": "Review (cents)",
        "file_name": "File",
        "rejected": "Quarantined",
        "billed_volume_liters": "Volume (L)",
        "billed_amount_cents": "Billed (cents)",
        "expected_amount_cents": "Expected (cents)",
        "signed_difference_cents": "Difference (cents)",
    }
    return {
        "field": field(table, prop, measure),
        "queryRef": f"{table}.{prop}",
        "nativeQueryRef": prop,
        "displayName": labels.get(prop, prop.replace("_", " ").capitalize())
        if not measure
        else prop,
    }


def color(hex_value):
    return {"solid": {"color": literal(hex_value)}}


def properties(**values):
    return [
        {"properties": {k: v if isinstance(v, dict) else literal(v) for k, v in values.items()}}
    ]


def visual(page, name, kind, x, y, width, height, roles, title):
    title = {
        "Active amount to review EUR": "Active review amount",
        "Invoice amount to review EUR": "Invoice review amount",
        "Billed amount EUR": "Billed amount",
        "Expected amount EUR": "Expected amount",
    }.get(title, title)
    data = {
        "$schema": SCHEMA + "report/definition/visualContainer/2.4.0/schema.json",
        "name": name,
        "position": {
            "x": x,
            "y": y,
            "z": y + x,
            "width": width,
            "height": height,
            "tabOrder": y + x,
        },
        "visual": {
            "visualType": kind,
            "query": {
                "queryState": {role: {"projections": values} for role, values in roles.items()}
            },
            "drillFilterOtherVisuals": True,
            "visualContainerObjects": {
                "title": [
                    {
                        "properties": {
                            "show": literal(True),
                            "text": literal(title),
                            "fontSize": literal(14),
                            "fontFamily": literal("Segoe UI"),
                            "fontColor": color("#172D35"),
                            "bold": literal(True),
                            "titleWrap": literal(True),
                        }
                    }
                ],
                "background": [
                    {
                        "properties": {
                            "show": literal(True),
                            "color": {"solid": {"color": literal("#FFFFFF")}},
                            "transparency": literal(0),
                        }
                    }
                ],
                "border": [
                    {
                        "properties": {
                            "show": literal(True),
                            "color": {"solid": {"color": literal("#E3E9E6")}},
                            "radius": literal(10),
                        }
                    }
                ],
                "general": [
                    {"properties": {"altText": literal(title + ". Synthetic demonstration data.")}}
                ],
            },
        },
    }
    if kind == "cardVisual":
        data["visual"]["objects"] = {
            "label": properties(show=False),
            "value": properties(
                fontSize=26,
                fontColor=color("#172D35"),
                bold=True,
                labelDisplayUnits=1,
            ),
            "layout": properties(backgroundShow=False),
            "outline": properties(show=False),
            "fillCustom": properties(show=False),
        }
        # Card formatting targets an instance; unscoped properties validate but are ignored.
        for entries in data["visual"]["objects"].values():
            for entry in entries:
                entry["selector"] = {"id": "default"}
    elif kind == "tableEx":
        data["visual"]["objects"] = {
            "grid": properties(rowPadding=5, textSize=12, gridVertical=False),
            "columnHeaders": properties(
                fontSize=11,
                bold=True,
                fontColor=color("#172D35"),
                backColor=color("#EDF4F1"),
                wordWrap=True,
            ),
            "values": properties(fontSize=12, fontColorPrimary=color("#172D35"), wordWrap=True),
        }
    elif kind in {"lineChart", "clusteredBarChart"}:
        data["visual"]["objects"] = {
            "categoryAxis": properties(fontSize=11, labelColor=color("#405951")),
            "valueAxis": properties(fontSize=11, labelColor=color("#405951")),
        }
        if kind == "clusteredBarChart":
            data["visual"]["objects"]["categoryAxis"][0]["properties"]["maxMarginFactor"] = literal(
                50
            )
    write(PBI / "AquaWatch.Report/definition/pages" / page / "visuals" / name / "visual.json", data)


def text_visual(page, name, text, y=20, size=26, height=55):
    data = {
        "$schema": SCHEMA + "report/definition/visualContainer/2.4.0/schema.json",
        "name": name,
        "position": {"x": 28, "y": y, "z": y, "width": 1220, "height": height, "tabOrder": y},
        "visual": {
            "visualType": "textbox",
            "objects": {
                "general": [
                    {
                        "properties": {
                            "paragraphs": [
                                {
                                    "textRuns": [
                                        {
                                            "value": text,
                                            "textStyle": {
                                                "fontFamily": "Segoe UI",
                                                "fontSize": f"{size}pt",
                                                "color": "#172D35",
                                            },
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ]
            },
        },
    }
    write(PBI / "AquaWatch.Report/definition/pages" / page / "visuals" / name / "visual.json", data)


def build(data_dir):
    write(
        PBI / "AquaWatch.Report/definition/version.json",
        {
            "$schema": SCHEMA + "report/definition/versionMetadata/1.0.0/schema.json",
            "version": "2.0.0",
        },
    )
    write(
        PBI / "AquaWatch.pbip",
        {
            "version": "1.0",
            "artifacts": [{"report": {"path": "AquaWatch.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    write(
        PBI / "AquaWatch.Report/definition.pbir",
        {
            "$schema": SCHEMA + "report/definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {"byPath": {"path": "../AquaWatch.SemanticModel"}},
        },
    )
    write(
        PBI / "AquaWatch.SemanticModel/definition.pbism",
        {
            "$schema": SCHEMA + "semanticModel/definitionProperties/1.0.0/schema.json",
            "version": "1.0",
            "settings": {},
        },
    )
    model = {
        "culture": "en-US",
        "defaultPowerBIDataSourceVersion": "powerBI_V3",
        "tables": [],
        "relationships": [],
        "expressions": [
            {
                "name": "DataFolder",
                "kind": "m",
                "expression": '"'
                + str(data_dir).replace('"', '""')
                + '" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
            }
        ],
        "annotations": [
            {
                "name": "PBI_QueryOrder",
                "value": '["DataFolder","dim_meters","dim_date","fct_consumption","fct_billing","fct_cases","fct_imports","network_daily"]',
            }
        ],
    }
    integer_names = {
        "counter_liters",
        "previous_counter_liters",
        "interval_days",
        "consumption_liters",
        "billed_volume_liters",
        "billed_amount_cents",
        "expected_amount_cents",
        "signed_difference_cents",
        "review_amount_cents",
        "amount_cents",
        "version",
        "accepted",
        "rejected",
        "duplicates",
        "received_readings",
        "valid_intervals",
        "year_number",
        "month_number",
        "day_number",
    }
    dates = {
        "installed_on",
        "reading_date",
        "calendar_date",
        "period_start",
        "period_end",
        "event_date",
        "started_at",
    }
    measures = {
        "dim_meters": [("Connected meters", "DISTINCTCOUNT(dim_meters[meter_id])", "#,0")],
        "fct_consumption": [
            ("Consumption m3", "DIVIDE(SUM(fct_consumption[consumption_liters]), 1000)", "#,0.0"),
            (
                "Valid interval share",
                'DIVIDE(CALCULATE(COUNTROWS(fct_consumption), fct_consumption[interval_status] = "valid"), COUNTROWS(fct_consumption))',
                "0.00%",
            ),
            ("Reading count", "COUNTROWS(fct_consumption)", "#,0"),
        ],
        "fct_cases": [
            (
                "Active investigations",
                'CALCULATE(COUNTROWS(fct_cases), fct_cases[status] IN {"open", "investigating"})',
                "#,0",
            ),
            ("Case count", "COUNTROWS(fct_cases)", "#,0"),
            (
                "Active amount to review EUR",
                'DIVIDE(CALCULATE(SUM(fct_cases[amount_cents]), fct_cases[status] IN {"open", "investigating"}), 100)',
                "€ #,0.00",
            ),
        ],
        "fct_billing": [
            (
                "Invoice amount to review EUR",
                "DIVIDE(SUM(fct_billing[review_amount_cents]), 100)",
                "€ #,0.00",
            ),
            ("Billed amount EUR", "DIVIDE(SUM(fct_billing[billed_amount_cents]), 100)", "€ #,0.00"),
            (
                "Expected amount EUR",
                "DIVIDE(SUM(fct_billing[expected_amount_cents]), 100)",
                "€ #,0.00",
            ),
            (
                "Flagged invoices",
                "COALESCE(CALCULATE(COUNTROWS(fct_billing), fct_billing[review_amount_cents] > 0), 0)",
                "#,0",
            ),
        ],
        "fct_imports": [
            ("Accepted rows", "SUM(fct_imports[accepted])", "#,0"),
            ("Quarantined rows", "SUM(fct_imports[rejected])", "#,0"),
            (
                "Acceptance rate",
                "DIVIDE(SUM(fct_imports[accepted]), SUM(fct_imports[accepted]) + SUM(fct_imports[rejected]))",
                "0.00%",
            ),
        ],
    }
    for name in [
        "dim_meters",
        "dim_date",
        "fct_consumption",
        "fct_billing",
        "fct_cases",
        "fct_imports",
        "network_daily",
    ]:
        with (PBI / "data" / f"{name}.csv").open(encoding="utf-8") as handle:
            columns = next(csv.reader(handle))
        defs, types = [], []
        for column in columns:
            dtype = (
                "int64" if column in integer_names else "dateTime" if column in dates else "string"
            )
            item = {
                "name": column,
                "dataType": dtype,
                "sourceColumn": column,
                "summarizeBy": "none",
            }
            if dtype == "dateTime":
                item["formatString"] = "yyyy-MM-dd"
            defs.append(item)
            mtype = (
                "Int64.Type"
                if dtype == "int64"
                else "type datetime"
                if column == "started_at"
                else "type date"
                if dtype == "dateTime"
                else "type text"
            )
            types.append('{"' + column + '", ' + mtype + "}")
        expression = [
            "let",
            f'  Source = Csv.Document(File.Contents(DataFolder & "/{name}.csv"), [Delimiter=",", Columns={len(columns)}, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
            "  Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
            '  EmptyToNull = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers)),',
            "  Typed = Table.TransformColumnTypes(EmptyToNull, {"
            + ", ".join(types)
            + '}, "en-US")',
            "in",
            "  Typed",
        ]
        table = {
            "name": name,
            "columns": defs,
            "partitions": [
                {"name": name, "mode": "import", "source": {"type": "m", "expression": expression}}
            ],
        }
        if name in measures:
            table["measures"] = [
                {
                    "name": label,
                    "expression": exp,
                    "formatString": fmt,
                    "description": "Synthetic demonstration; see docs/metric-definitions.md for grain and limitations.",
                }
                for label, exp, fmt in measures[name]
            ]
        model["tables"].append(table)
    for fact in ["fct_consumption", "fct_billing", "fct_cases"]:
        model["relationships"].append(
            {
                "name": str(uuid.uuid5(uuid.NAMESPACE_URL, fact + "-meter")),
                "fromTable": fact,
                "fromColumn": "meter_id",
                "toTable": "dim_meters",
                "toColumn": "meter_id",
                "crossFilteringBehavior": "oneDirection",
            }
        )
    for fact, column in [
        ("fct_consumption", "reading_date"),
        ("fct_cases", "event_date"),
        ("fct_billing", "period_end"),
        ("network_daily", "reading_date"),
    ]:
        model["relationships"].append(
            {
                "name": str(uuid.uuid5(uuid.NAMESPACE_URL, fact + "-date")),
                "fromTable": fact,
                "fromColumn": column,
                "toTable": "dim_date",
                "toColumn": "calendar_date",
                "crossFilteringBehavior": "oneDirection",
            }
        )
    write(
        PBI / "AquaWatch.SemanticModel/model.bim",
        {"name": "AquaWatch", "compatibilityLevel": 1600, "model": model},
    )
    theme = {
        "name": "AquaWatch",
        "dataColors": ["#146B5B", "#91AC82", "#C6AE6F", "#65868D", "#B45345"],
        "background": "#F5F7F6",
        "foreground": "#172D35",
        "tableAccent": "#146B5B",
        "textClasses": {
            "title": {"fontFace": "Segoe UI", "color": "#172D35"},
            "label": {"fontFace": "Segoe UI", "color": "#526A60"},
        },
    }
    write(PBI / "AquaWatch.Report/StaticResources/RegisteredResources/AquaWatch.json", theme)
    write(PBI / "theme.json", theme)
    write(
        PBI / "AquaWatch.Report/definition/report.json",
        {
            "$schema": SCHEMA + "report/definition/report/2.0.0/schema.json",
            "themeCollection": {
                "customTheme": {
                    "name": "AquaWatch",
                    "reportVersionAtImport": "5.55",
                    "type": "RegisteredResources",
                }
            },
            "resourcePackages": [
                {
                    "name": "RegisteredResources",
                    "type": "RegisteredResources",
                    "items": [
                        {"name": "AquaWatch", "path": "AquaWatch.json", "type": "CustomTheme"}
                    ],
                }
            ],
        },
    )
    pages = [
        ("network", "01 · Network overview"),
        ("quality", "02 · Data quality"),
        ("billing", "03 · Billing review"),
    ]
    write(
        PBI / "AquaWatch.Report/definition/pages/pages.json",
        {
            "$schema": SCHEMA + "report/definition/pagesMetadata/1.0.0/schema.json",
            "pageOrder": [p[0] for p in pages],
            "activePageName": "network",
        },
    )
    for page, display in pages:
        write(
            PBI / "AquaWatch.Report/definition/pages" / page / "page.json",
            {
                "$schema": SCHEMA + "report/definition/page/2.0.0/schema.json",
                "name": page,
                "displayName": display,
                "displayOption": "FitToPage",
                "width": 1280,
                "height": 800,
            },
        )
        text_visual(page, "title", "AquaWatch  /  " + display[5:])
        text_visual(
            page,
            "subtitle",
            "Synthetic utility data · Moundir Houazar · Amounts requiring review are not confirmed savings",
            y=72,
            size=11,
            height=32,
        )
    for i, (table, measure) in enumerate(
        [
            ("dim_meters", "Connected meters"),
            ("fct_cases", "Active investigations"),
            ("fct_cases", "Active amount to review EUR"),
            ("fct_imports", "Acceptance rate"),
        ]
    ):
        visual(
            "network",
            f"kpi{i}",
            "cardVisual",
            28 + i * 312,
            122,
            290,
            125,
            {"Data": [projection(table, measure, True)]},
            measure,
        )
    visual(
        "network",
        "consumption",
        "lineChart",
        28,
        270,
        715,
        275,
        {
            "Category": [projection("dim_date", "calendar_date")],
            "Y": [projection("fct_consumption", "Consumption m3", True)],
        },
        "Daily consumption · valid intervals only",
    )
    visual(
        "network",
        "exceptions",
        "clusteredBarChart",
        765,
        270,
        487,
        275,
        {
            "Category": [projection("fct_cases", "kind")],
            "Y": [projection("fct_cases", "Active investigations", True)],
        },
        "Active exceptions by type",
    )
    visual(
        "network",
        "queue",
        "tableEx",
        28,
        568,
        1224,
        204,
        {
            "Values": [
                projection("fct_cases", c)
                for c in ["meter_id", "title", "severity", "status", "event_date", "amount_cents"]
            ]
        },
        "Investigation queue · amounts in cents",
    )
    for i, measure in enumerate(["Accepted rows", "Quarantined rows", "Acceptance rate"]):
        visual(
            "quality",
            f"kpi{i}",
            "cardVisual",
            28 + i * 416,
            122,
            390,
            125,
            {"Data": [projection("fct_imports", measure, True)]},
            measure,
        )
    visual(
        "quality",
        "intervals",
        "clusteredBarChart",
        28,
        270,
        550,
        250,
        {
            "Category": [projection("fct_consumption", "interval_status")],
            "Y": [projection("fct_consumption", "Reading count", True)],
        },
        "Reading intervals by usability",
    )
    visual(
        "quality",
        "runs",
        "tableEx",
        600,
        270,
        652,
        250,
        {
            "Values": [
                projection("fct_imports", c)
                for c in ["file_name", "status", "accepted", "rejected", "duplicates"]
            ]
        },
        "Import ledger",
    )
    text_visual(
        "quality",
        "method",
        "Null consumption is intentional: first observations, resets and missing daily intervals are excluded.",
        y=555,
        size=14,
        height=100,
    )
    for i, measure in enumerate(
        [
            "Billed amount EUR",
            "Expected amount EUR",
            "Invoice amount to review EUR",
            "Flagged invoices",
        ]
    ):
        visual(
            "billing",
            f"kpi{i}",
            "cardVisual",
            28 + i * 312,
            122,
            290,
            125,
            {"Data": [projection("fct_billing", measure, True)]},
            measure,
        )
    visual(
        "billing",
        "district",
        "clusteredBarChart",
        28,
        270,
        430,
        270,
        {
            "Category": [projection("dim_meters", "district")],
            "Y": [projection("fct_billing", "Invoice amount to review EUR", True)],
        },
        "Invoice discrepancies by district",
    )
    visual(
        "billing",
        "invoices",
        "tableEx",
        480,
        270,
        772,
        360,
        {
            "Values": [
                projection("fct_billing", c)
                for c in [
                    "invoice_id",
                    "meter_id",
                    "billed_volume_liters",
                    "billed_amount_cents",
                    "expected_amount_cents",
                    "signed_difference_cents",
                ]
            ]
        },
        "Invoice arithmetic · liters and integer cents",
    )
    text_visual(
        "billing",
        "scope",
        "Scope: stated invoice volume × synthetic tariff + fixed fee. Meter-to-invoice volume reconciliation is out of scope.",
        y=670,
        size=12,
        height=80,
    )
    print("Built Power BI project: 7 tables, 14 measures, 7 relationships and 3 report pages.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="C:/AquaWatch/powerbi/data")
    build(parser.parse_args().data_dir)
