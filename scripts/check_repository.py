"""Check report bindings, mart contracts, dimensional integrity and local Markdown links."""

import csv
import json
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def check_report_scaffold(pbi):
    """Catch missing PBIR files that validating only existing JSON cannot detect."""
    for relative in (
        "AquaWatch.pbip",
        "AquaWatch.Report/definition.pbir",
        "AquaWatch.Report/definition/version.json",
        "AquaWatch.Report/definition/report.json",
        "AquaWatch.Report/definition/pages/pages.json",
        "AquaWatch.SemanticModel/definition.pbism",
        "AquaWatch.SemanticModel/model.bim",
    ):
        assert (pbi / relative).is_file(), f"Missing Power BI project file: {relative}"
    definition = pbi / "AquaWatch.Report/definition"
    version = json.loads((definition / "version.json").read_text(encoding="utf-8"))
    assert version["version"] == "2.0.0", "Expected PBIR definition version 2.0.0"
    pages = json.loads((definition / "pages/pages.json").read_text(encoding="utf-8"))
    order = pages["pageOrder"]
    assert order and len(order) == len(set(order)), "Missing or duplicate report pages"
    assert pages["activePageName"] in order, "Active page is not in page order"
    for name in order:
        page_file = definition / "pages" / name / "page.json"
        assert page_file.is_file(), f"Missing report page: {name}"
        page = json.loads(page_file.read_text(encoding="utf-8"))
        assert page["name"] == name, f"Report page name mismatch: {name}"
        assert list((page_file.parent / "visuals").glob("*/visual.json")), name


def check():
    check_report_scaffold(ROOT / "powerbi")
    model = json.loads(
        (ROOT / "powerbi/AquaWatch.SemanticModel/model.bim").read_text(encoding="utf-8")
    )["model"]
    tables = {t["name"]: t for t in model["tables"]}
    rows = {}
    for name, table in tables.items():
        with (ROOT / "powerbi/data" / f"{name}.csv").open(encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            assert reader.fieldnames == [c["name"] for c in table["columns"]], name
            rows[name] = list(reader)
        assert rows[name], f"Empty mart {name}"
    for relation in model["relationships"]:
        source, target = rows[relation["fromTable"]], rows[relation["toTable"]]
        values = [r[relation["toColumn"]] for r in target]
        assert all(values) and len(values) == len(set(values)), relation
        assert {r[relation["fromColumn"]] for r in source} <= set(values), relation

    def inspect(value):
        if isinstance(value, dict):
            for kind in ["Column", "Measure"]:
                if kind in value:
                    field = value[kind]
                    table = tables[field["Expression"]["SourceRef"]["Entity"]]
                    collection = table["columns"] if kind == "Column" else table["measures"]
                    assert field["Property"] in {c["name"] for c in collection}, field
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)

    visuals = list((ROOT / "powerbi/AquaWatch.Report").rglob("visual.json"))
    for path in visuals:
        definition = json.loads(path.read_text(encoding="utf-8"))
        inspect(definition)
        visual = definition["visual"]
        if visual["visualType"] == "cardVisual":
            for name in ("label", "value", "layout", "outline", "fillCustom"):
                for entry in visual.get("objects", {}).get(name, []):
                    assert entry.get("selector") == {"id": "default"}, (
                        f"Card formatting needs an instance selector: {path} / {name}"
                    )
    for document in [
        ROOT / "README.md",
        ROOT / "SECURITY.md",
        *list((ROOT / "docs").glob("*.md")),
        ROOT / "powerbi/README.md",
    ]:
        for link in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
            if "://" in link or link.startswith("#"):
                continue
            target = document.parent / unquote(link.split("#")[0])
            assert target.exists(), f"Broken link in {document.name}: {link}"
    print(
        f"Repository checks passed: {len(tables)} mart contracts, {len(model['relationships'])} relationships, {len(visuals)} visual definitions and local documentation links."
    )


if __name__ == "__main__":
    check()
