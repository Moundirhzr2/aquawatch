# AquaWatch

[![AquaWatch checks](https://github.com/Moundirhzr2/aquawatch/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Moundirhzr2/aquawatch/actions/workflows/ci.yml)

**Explainable water-consumption and billing investigations.**

A data engineering and analytics portfolio project by **Moundir Houazar**, inspired by experience working with meter-data quality. AquaWatch turns incoming readings into validated records, explained alerts and a traceable investigation workflow.

**Independent project. All customers, readings, invoices and tariffs are synthetic. No affiliation with Amendis, Veolia or another utility.**

![AquaWatch dashboard](docs/images/dashboard.png)

The dashboard visual direction adapts the [MotionSites Forecast Center prompt](https://motionsites.ai/?prompt=forecast-center) to water-network operations. It uses an atmospheric utility header and restrained glass surfaces while keeping the charts and decisions tied to AquaWatch's actual synthetic data. Choose a 7, 30 or 90 day window, inspect a reading by pointer or keyboard, or select an exception type to open the filtered investigation queue. Animations respect reduced-motion preferences.

The brand mark, favicon and interface icons use locally bundled [Lucide icons via Iconify](https://icon-sets.iconify.design/lucide/), so they render without a third-party runtime request. The [Lucide and Feather license notices](src/aquawatch/static/icons/LICENSE) are included with the assets.

## See the complete workflow

1. Import a daily readings file.
2. Validate the schema and quarantine duplicates or invalid records.
3. Detect suspicious consumption, backwards counters, missing readings, tariff mismatches and invoice-volume differences.
4. Open a case, inspect its evidence and record an investigation decision.
5. Transform operational data with dbt and analyze the resulting marts in Power BI.

An exact file replay does not duplicate readings, runs or cases. Human case decisions survive pipeline reruns. Missing days and meter resets produce **null daily consumption**, not invented usage.

The [invoice reconciliation walkthrough](docs/invoice-reconciliation.md) shows the new distinction between tariff arithmetic, measured volume differences and unverified periods; see the [investigation screenshot](docs/images/reconciliation.png).

## Run locally

Requires **Python 3.12**. Node.js is needed only for browser regression tests. No paid account, cloud deployment or company data is required.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS / Linux instead: source .venv/bin/activate
python -m pip install -c requirements.lock -e ".[dev,analytics]"
aquawatch demo
aquawatch serve
```

Open **http://127.0.0.1:8000**. The API reference is at `/docs`. The web app uses one local operator and is bound to loopback by default. A Windows convenience launcher is provided in `scripts/start.ps1`.

The local operational database is SQLite. The local analytics warehouse is DuckDB. The PostgreSQL mode uses the **same application code and dbt models**; both database modes have been exercised. See [validation](docs/validation.md).

## Run PostgreSQL with Docker Compose

Requires Docker Engine / Docker Desktop with Compose v2.

```bash
python scripts/create_env.py
docker compose up --build -d
docker compose --profile analytics run --rm analytics
```

The credential generator refuses to overwrite an existing `.env`. App and database ports are published on loopback only. Shut down with `docker compose down`; named database volumes are retained. Set `AQUAWATCH_APP_PORT` or `AQUAWATCH_DB_PORT` in `.env` if the default ports (8000 and 5432) are in use.

For an isolated integration check, run `python scripts/check_containers.py`. It creates a uniquely named Compose project with temporary credentials, available loopback ports and temporary exports. It checks the PostgreSQL-backed API, a decision surviving an app restart, unchanged ingestion counts, dbt tests, Python/SQL parity and seven CSV exports. It removes only its own containers and volumes afterward. Add `--config-only` to validate the configuration without starting containers.

Docker verification passed locally on 2026-09-13 and again in the GitHub Actions containers job on 2026-09-18, including the image build, app restart, PostgreSQL persistence, dbt and exports. Native PostgreSQL was also tested separately. See [container evidence](docs/container-validation.json), [Windows setup](docs/windows-setup.md) and the [validation record](docs/validation.md).

To connect the application to an existing PostgreSQL database, set `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE`. For dbt/export also set `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD` and `PGDATABASE`. Use a separate database for this demonstration.

## Build the analytics and Power BI report

```bash
aquawatch analytics
# PostgreSQL alternative: aquawatch analytics --target postgres
python scripts/build_powerbi.py --data-dir "C:/absolute/path/to/aquawatch/powerbi/data"
```

The analytics command exports the operational tables, runs **dbt build**, generates dbt documentation and exports seven marts. Open `powerbi/AquaWatch.pbip` in Power BI Desktop and refresh the data. It contains four report pages: **Network overview**, **Data quality**, **Billing review**, and **Volume reconciliation**, with a semantic model, DAX measures and single-direction relationships.

The checked-in report is portable source. Its `DataFolder` parameter defaults to `C:/AquaWatch/powerbi/data`; the command above sets the path on your computer. See [Power BI setup](powerbi/README.md) and [metric definitions](docs/metric-definitions.md).

The previous three-page model passed native Power Query refresh and DAX validation for its 14 measures, seven tables, four districts and 90 dates. The fourth page and four new measures are generated and covered by mart tests and Python/SQL parity, but require a fresh Power BI Desktop refresh for native confirmation. See [Power BI validation](docs/powerbi-validation.md) for the repeatable engine check and earlier evidence.

## Architecture

```mermaid
flowchart LR
    CSV[Daily CSV files] --> ING[Python ingestion]
    ING --> Q[Quarantine and import ledger]
    ING --> DB[(PostgreSQL / local SQLite)]
    DB --> RULES[Explainable detection rules]
    RULES --> CASES[Cases and decision history]
    CASES --> API[FastAPI]
    API --> UI[HTML / CSS / JavaScript interface]
    DB --> DBT[dbt staging and marts]
    DBT --> BI[Power BI / DAX]
    LABELS[Separate synthetic labels] --> EVAL[Event benchmark]
    RULES --> EVAL
```

| Layer | Technologies | Purpose |
|---|---|---|
| Operational pipeline | Python, SQLAlchemy, PostgreSQL | Transactional ingestion, validation, provenance |
| Rules and API | Python, FastAPI, Pydantic | Explainable detection, input contracts, optimistic concurrency |
| Interface | HTML, CSS, JavaScript | Responsive investigation and import workflow |
| Analytics | SQL, dbt, PostgreSQL / DuckDB | Tested dimensions and fact tables |
| Business intelligence | Power BI, Power Query M, DAX | Three report pages and reusable measures |
| Reproducibility | Docker Compose, pytest, Playwright, GitHub Actions | Setup, integration checks and browser regression |

## Measured synthetic benchmark

The baseline covers **120 meters over 90 dates**, with **10,796 accepted readings**, **8 quarantined rows**, and **31 labeled events**. The rules detect **27** and miss **4** deliberately subtle consumption events: **100% precision and 87.1% recall** under exact event matching. These are synthetic benchmark results, not field performance claims.

```bash
aquawatch benchmark
```

Results for seeds 42, 71 and 103, including timing and missed events, are saved in [docs/benchmark.json](docs/benchmark.json). Seeds vary consumption but share event templates, so they are **not independent external validation**. See [the case study](docs/case-study.md).

## Checks

```bash
pytest -q
ruff check .
ruff format --check .
aquawatch demo
aquawatch analytics
npm ci
npx playwright install chromium
npm run test:browser
```

Browser checks launch a disposable local database and test server on port 8011. They exercise filtering, persistent decisions, replay, quarantine, benchmark rendering and mobile overflow. Set `AQUAWATCH_PYTHON` to your virtual environment's Python if it is not active. Set `AQUAWATCH_BROWSER_CHANNEL=msedge` to use an installed Edge browser.

GitHub Actions includes Linux/Windows checks, a real PostgreSQL service, dbt builds, browser tests and an isolated Compose integration job. See the [live workflow results](https://github.com/Moundirhzr2/aquawatch/actions/workflows/ci.yml) and the dated [validation record](docs/validation.md).

See the [18 September publication verification](docs/release-2026-09-18.md) for remote execution, branch protection and the latest native Power BI checks. The [14 September audit](docs/audit-2026-09-14.md) records the earlier application fixes and local results.

## Repository map

```text
src/aquawatch/      pipeline, detector, database, API, CLI and web interface
tests/             behavioral tests and browser regression
dbt/               staging, marts, tests, source contracts and profiles
powerbi/           editable PBIP report, semantic model, theme and mart CSVs
scripts/           local setup and report generator
docs/              architecture, benchmark, decisions and interview walkthrough
.github/workflows/ continuous integration
```

## Scope and tradeoffs

- Daily cumulative meter readings; integer liters and cents; a deliberately simplified synthetic tariff.
- Rules flag **possible** issues. They do not confirm a leak, fraud, liability or financial savings.
- Billing checks separately verify tariff arithmetic from the **stated invoice volume** and compare that volume with complete, reset-free meter periods. Missing boundary readings, gaps and resets remain unverified; effective-dated tariff changes and confirmed overcharge estimation are not implemented. See [invoice reconciliation](docs/invoice-reconciliation.md).
- Row acceptance rate is not a completeness or freshness score. The dashboard describes its denominator.
- Case status is operational. dbt/Power BI are snapshots refreshed by the analytics command.
- Local single-operator demo, one API worker, bounded 5 MB files. Concurrent status edits are guarded; multi-process ingestion orchestration, user authentication, tenant isolation, background job queues, migrations and production deployment are future work.
- Detection currently re-evaluates stored observations after each batch. It is transparent and sufficient for this dataset, but is not an internet-scale streaming design.

See [security and deployment boundaries](SECURITY.md), [design decisions](docs/decisions.md), [data contract](docs/data-contract.md), and [references](docs/references.md).

## Presenting the project

Use the [two-minute demo script](docs/demo-script.md) and [interview guide](docs/interview-guide.md). Study and adapt the implementation before claiming independent mastery. Development was assisted by OpenAI Codex; the repository includes explicit assumptions, tests and limitations for review.

Licensed under MIT. External dependencies retain their own licenses. No code from the reference projects was copied.
