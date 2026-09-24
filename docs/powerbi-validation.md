# Power BI validation

**24 September update:** The current four-page source has 18 measures after adding invoice-volume reconciliation. A fresh native Power Query refresh and DAX/CSV parity check passed for all 18 measures, seven tables, four districts and 90 dates using the Power BI Desktop Store engine. The checked-in [current validation record](powerbi-validation-2026-09-24.json) includes the CSV hashes and exact results. The model was loaded into an isolated temporary database; this does **not** prove that the PBIP file opens or that the fourth page renders correctly. The earlier screenshots below apply to the three-page version only. The current CSV snapshot has 27 active cases, EUR 14,155.84 billed, EUR 13,900.84 expected, two volume mismatches, eight unverified periods and 20.0 m³ of volume to review.

The source semantic model passed a native Power Query refresh and DAX execution check on 2026-09-13 using the local Analysis Services engine shipped with Power BI Desktop. All 14 measures, seven table counts, four district groups and 90 date groups matched independently calculated CSV results. The grouped queries exercise all seven model relationships.

This check loads the source model into a new temporary database on an identified local Desktop engine. It preserves the source's `en-US` culture and changes only the in-memory CSV folder parameter to the repository's data directory. It does not modify existing report databases or source files. The temporary database is removed after the queries finish.

**PBIP opening, Desktop refresh and all three populated pages are confirmed by user-provided screenshots on 2026-09-13.** The refreshed overview displays 120 connected meters, 25 active investigations, EUR 255.00 to review and a 99.93% acceptance rate. Data quality shows 10,796 accepted rows in its ledger (the original card rounds this to 11K), eight quarantined rows and five duplicates within that quarantine count. Billing review shows six flagged invoices and EUR 255.00 to review; the original billed and expected cards display rounded EUR 14.14K and EUR 13.89K, consistent with the exact engine-validated values. Charts and tables contain data on all three pages. The user subsequently confirmed that Billing review district selections update the linked visuals.

Screenshots of the initial rendered layout: [Network overview](images/powerbi-network-initial.png), [Data quality](images/powerbi-quality-initial.png), [Billing review](images/powerbi-billing-initial.png). These show the layout before the formatting update below.

A manual opening attempt on 2026-09-13 identified a missing `definition/version.json` file. The generator now emits this required PBIR metadata, and the repository check requires the report scaffold and each listed page. After repairing the source and local copies, the user successfully opened, refreshed and saved the local report.

**The corrected formatting is visually confirmed on all three pages in Preview 2.** The screenshots show one title per card, larger values, readable table headers, and fully visible chart categories. Data quality displays exactly 10,796 accepted rows, eight quarantined rows and 99.93% acceptance. Billing review displays EUR 14,142.84 billed, EUR 13,887.84 expected, EUR 255.00 to review and six flagged invoices. These match the independently validated model results. Evidence: [Network overview](images/powerbi-network-preview-2.png), [Data quality](images/powerbi-quality-preview-2.png), [Billing review](images/powerbi-billing-preview-2.png).

The generator supplies the required card instance selectors, removes internal card outlines, and gives bar-chart labels more space. See Microsoft's [card formatting reference](https://github.com/microsoft/skills-for-fabric/blob/main/plugins/powerbi-authoring/skills/powerbi-report-authoring/references/card.md) for the selector requirement. The repository check rejects unscoped card settings. In the earlier version, all 34 report definitions and 18 non-text visual formatting configurations passed Microsoft's published schemas. Billing review district selection was manually checked by the user, who confirmed that the linked visuals update. Model-level district/date filter behavior passed separately. This establishes the demonstrated interactions, not exhaustive testing of every combination of selections.

## Reproduce the native check

Requires Windows, Power BI Desktop, PowerShell 7.4 or newer, and Python. For the default process-path check, open an isolated copy of `AquaWatch.pbip` in Desktop first. The Store-edition mode needs one running Desktop engine but cannot establish that the PBIP opened. From the repository root:

```powershell
pwsh -NoProfile -File scripts/check_powerbi_engine.ps1 -ReportPath "C:/absolute/path/to/AquaWatch.pbip" -DownloadClient
python scripts/check_powerbi_results.py
```

`-DownloadClient` downloads Microsoft's two NuGet packages, `Microsoft.AnalysisServices` and `Microsoft.AnalysisServices.AdomdClient`, pinned to 19.117.0. They are stored under ignored `runtime/powerbi-client`. Existing libraries can instead be supplied with `-ClientDirectory`. No cloud account or Power BI service connection is used.

The script normally identifies the selected Desktop process by its exact report path. Microsoft Store editions may omit that path from their process command line. With exactly one Desktop process running, add `-UseAnyDesktopEngine` to run the same isolated source-model test on its engine. This mode validates native Power Query and DAX, but explicitly does not verify PBIP opening. Results are written to ignored `runtime/powerbi-validation`. The Python check compares those results with the seven CSVs, including counts and filter behavior. Run both commands; successful query execution alone does not establish numerical parity.

The earlier [validation summary](powerbi-validation.json) records the three-page model. The [24 September summary](powerbi-validation-2026-09-24.json) records the current model and input CSV hashes. Regenerating the marts changes the snapshot and requires a new validation run. The live web application may contain later imports or investigation decisions.

## Remaining visual check

Use the [Power BI setup](../powerbi/README.md) to set the CSV folder, open the PBIP and refresh it. For the checked-in snapshot, inspect these unfiltered values:

| Value | Expected |
|---|---:|
| Connected meters | 120 |
| Readings / accepted rows | 10,796 |
| Consumption | 3,955.375 m³ before display rounding |
| Valid interval share | 98.81% |
| Active investigations | 27 |
| Active amount to review | EUR 255.00 |
| Quarantined rows | 8 |
| Acceptance rate | 99.93% |
| Billed amount | EUR 14,155.84 |
| Expected amount | EUR 13,900.84 |
| Flagged invoices | 6 |
| Comparable invoice periods | 112 |
| Volume mismatches | 2 |
| Unverified invoice periods | 8 |
| Volume to review | 20.0 m³ |

Inspect Network overview, Data quality, Billing review and Volume reconciliation for visual errors, clipped text, readable dates and correctly formatted amounts. Verify that district selections affect meter-level consumption, cases and invoices; `network_daily` is a network aggregate and is intentionally not related to the meter dimension. Clear all selections before comparing the totals above. Capture a screenshot of each page only after the report renders successfully.

Microsoft documents the [Tabular Object Model](https://learn.microsoft.com/en-us/analysis-services/tom/tom-pbi-datasets), [client libraries](https://learn.microsoft.com/en-us/analysis-services/client-libraries) and [Desktop external-tool model operations](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-external-tools).

## Manual interaction check

The user confirmed linked visual updates after selecting district bars on Billing review. Earlier screenshots also demonstrate invoice-row selection: INV-0001 produces EUR 137.44 billed and expected, and INV-0002 produces EUR 138.38 for both; each has EUR 0.00 to review. With no matching flagged invoices, the count measure returns blank and the card displays `--`. This is a known presentation limitation for empty selections, not a discrepancy in invoice arithmetic.
