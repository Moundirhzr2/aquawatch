# Power BI report

`AquaWatch.pbip` links an editable three-page PBIR report to a semantic model with seven tables, 14 DAX measures and seven single-direction relationships.

1. Install Power BI Desktop. Windows may require administrator approval; the project does not automate that security prompt.
2. From the repository root, run `aquawatch demo` then `aquawatch analytics`.
3. Run `python scripts/build_powerbi.py --data-dir "C:/absolute/path/to/aquawatch/powerbi/data"`.
4. Open `AquaWatch.pbip` in Desktop. If necessary, enable the Power BI Project preview feature in Desktop Options.
5. Refresh. The Power Query `DataFolder` parameter points to the exported UTF-8 CSV marts.
6. Inspect all three pages and save. Keep `.pbi` cache files out of Git.

Pages:

- **Network overview:** inventory, active investigations, review amount, acceptance rate, daily consumption, exception counts and case table.
- **Data quality:** accepted/quarantined rows, record acceptance rate, interval validity and import ledger.
- **Billing review:** actual and expected amounts, discrepancies, flagged invoices, district comparison and invoice table.

All tables and measures have explicit grains. Read `docs/metric-definitions.md` before combining time filters or totals. Monetary table columns use cents; measures explicitly marked EUR divide by 100.

The report definitions passed Microsoft's JSON schema checks, and the exported data came from successfully built/tested dbt marts on PostgreSQL and DuckDB. The semantic model also passed **native Power Query refresh and DAX validation** through Desktop's local model engine: all 14 measures, seven tables, four districts and 90 dates matched the CSV snapshot. See [native validation and reproduction](../docs/powerbi-validation.md).

**PBIP opening, Desktop refresh and all three populated pages are confirmed** by user-provided screenshots on 2026-09-13, with the visible totals matching the expected snapshot at their displayed precision. The updated formatting on all three pages is also confirmed, including exact card totals and readable table headers. The user manually confirmed that Billing review district selections update the linked visuals. The validation guide records the evidence and remaining checks.

`build_powerbi.py` regenerates report source. If you manually customize the report in Desktop, commit those changes before rerunning the generator. Never run it against an open report with unsaved edits.
