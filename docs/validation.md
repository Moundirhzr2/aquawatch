# Validation record

Invoice-volume reconciliation update on 2026-09-23: 35 Python tests passed; a fresh isolated browser run passed desktop/mobile navigation and the new invoice table/case link with no JavaScript errors. DuckDB `dbt build` passed 48 nodes (7 seeds, 8 models, 33 data tests), including the new volume contract. Python/SQL parity passed for every one of 120 invoices, and repository checks passed the generated four-page PBIP source (35 visual definitions). The fourth Power BI page is not yet natively refreshed or visually verified in Desktop; the historical evidence below applies to the earlier three-page version.

Project checklist updated on 2026-09-18: source published on GitHub, main branch protected, and a fresh remote Docker integration run passed. See the [publication verification record](release-2026-09-18.md) and [container evidence](container-validation.json). Earlier local engine failures remain historical records.

Power BI finishing change on 2026-09-18: `Flagged invoices` now wraps the filtered count in `COALESCE(..., 0)` so an empty selection returns zero. Updated the source model, generator and all three local report copies. A fresh native model check passed all 14 measures and explicitly verified empty/unflagged/flagged selections as 0/0/1. Desktop rendering of this change has not been rechecked.

Validated locally on Windows with Python 3.12.14 and through [GitHub Actions](https://github.com/Moundirhzr2/aquawatch/actions/workflows/ci.yml). Commands and scripts are included so results can be reproduced; dated remote results are recorded in the publication verification record.

The [14 September full audit](audit-2026-09-14.md) reran application tests, browser workflows, both analytics targets, dependency checks and release-file checks. It fixed malformed-token handling and updated pytest to 9.0.3. Docker's fresh recheck stalled because the engine was unresponsive; its 13 September pass below remains historical evidence.

| Area | Result |
|---|---|
| Application behavior, SQLite | 27 pytest tests passed with pytest 9.0.3 on 2026-09-14 |
| Application behavior, PostgreSQL | The same 27 pytest tests passed against a separate native PostgreSQL test database on 2026-09-14 |
| dbt, DuckDB | 8 models, 7 seeds and 30 data tests completed successfully |
| dbt, PostgreSQL | 8 models, 7 seeds and 30 data tests completed successfully against operational PostgreSQL sources |
| Browser | Overview, filtering, persistent decision history, status updates, import/replay, quarantine, benchmark and mobile width checks passed |
| JavaScript runtime | No page errors during the browser workflow |
| Synthetic benchmark | Three seeds, each with 25 matched events, 0 false alerts, 4 missed events |
| Power BI report JSON | 34 report/page/visual/project-definition files passed Microsoft's published schemas; required scaffold check also passes and rejects a missing version file |
| Power BI Desktop installation | Installed successfully through the official per-user Microsoft Store package; application launch confirmed |
| Power BI native model execution | **Passed on 2026-09-13**: native Power Query refresh; all 14 DAX measures, seven table counts, four districts and 90 dates matched the source CSVs |
| Power BI PBIP opening and visual rendering | **All three page layouts verified on 2026-09-13**: user screenshots confirm opening, refresh and all three populated pages with expected visible totals. The updated formatting on all three pages is also confirmed, including exact card totals and readable table headers. The user manually confirmed that Billing review district selections update the linked visuals |
| Docker installation | Docker Desktop 4.90.0 installed per user; Docker CLI 29.7.2 and Compose 5.5.1 verified |
| WSL installation | WSL 2.7.13.0 verified; activation completed after the Windows restart; Docker's WSL 2 distribution runs successfully |
| Compose configuration | The isolated integration check passed `--config-only` using the installed Compose CLI |
| Docker image and Compose execution | **Passed locally on 2026-09-13**: image build, healthy PostgreSQL/API, saved decision across app restart, ingestion replay, dbt tests, SQL parity and seven CSV exports; temporary containers and volumes removed successfully |
| Remote CI and source publication | Source published; all four jobs passed in the corrected workflow on 2026-09-18: Linux, Windows, PostgreSQL and Docker. See the publication verification record for the run and commit. No hosted web application deployment is claimed |

The application test suite verifies exact replay, row conflicts, malformed-input quarantine, whole-batch rollback, invalid/future dates, integer rounding, counter/gap handling, conservative detection, known misses, case revision conflicts and persistent history.

The browser suite starts a disposable local database and loopback server. Screenshots in `docs/images` show the tested application; files named `powerbi-*-initial.png` record the initial Power BI layout, and `powerbi-*-preview-2.png` record the verified formatting update. These Power BI screenshots were supplied by the user.

An additional Python/SQL parity check passed for 10,796 baseline observations and 120 invoices on the local backend, and 10,916 observations (baseline plus daily import) and 120 invoices on PostgreSQL. The check compares every consumption value, including null intervals, and every expected invoice amount.

Native M/DAX execution was verified using a temporary database on the local Power BI Desktop model engine, separate from the report database. All seven relationships were exercised through district/date query results. The source culture and model definitions were preserved; only the CSV path was configured for the local snapshot. The [Power BI validation guide](powerbi-validation.md) and [evidence summary](powerbi-validation.json) describe reproduction and scope. Separately, user screenshots confirm PBIP opening, Desktop refresh and all three populated pages. The updated formatting on all three pages is also confirmed, including exact card totals and readable table headers. The user manually confirmed that Billing review district selections update the linked visuals.

The container check passed using a uniquely named project, random temporary credentials, available loopback ports and a temporary export mount. It verified API startup on PostgreSQL, decision persistence and ingestion idempotency across an app restart, followed by 30 passing dbt tests, SQL parity for 10,796 observations and 120 invoices, and seven nonempty CSV exports. Its exit code was 0, including cleanup. See the [container validation summary](container-validation.json) and [Windows setup](windows-setup.md) for reproduction. The GitHub Actions containers job ran the same script successfully on 18 September.

The setup encountered third-party deprecation notices in the FastAPI/Starlette test-client dependencies; tests still passed. No production readiness, real-world detection performance, independent data validation or financial benefit is claimed.
