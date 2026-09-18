# Engineering decisions

## Integer liters and cents

Cumulative counters and money use integer units. Python tariff calculation uses integer half-up rounding. dbt performs the corresponding calculation with a numeric expression. This avoids ordinary floating-point money comparisons. The scope does not include taxes, progressive bands or effective-dated contracts.

## Separate ingestion, detection and evaluation

Ingestion validates and records data; detection explains business exceptions; evaluation compares predictions to a separate label file. The detector has no input for labels, names or event IDs. The generator also creates benign one-day spikes to test whether the sustained rule avoids alerting on every large value.

## SQL for the analytical model

Staging uses `LAG` over meter/date to calculate intervals. Fact and dimension models establish explicit grains. The same models run on PostgreSQL and DuckDB, with dbt's date-difference macro handling dialect variation. PostgreSQL reads live source tables; DuckDB reads exported CSV snapshots. Seeds in the PostgreSQL build are reference snapshots, not the sources of its marts.

## Two runnable database modes

PostgreSQL demonstrates a conventional operational database. SQLite and DuckDB make the demo accessible on a laptop without Docker. They are not presented as identical engines: concurrency and operational deployment differ. Application tests run against both operational backends; dbt checks run on both analytics backends.

## One API process and local operator

A process lock serializes API writes, and conditional SQL updates protect case revisions. This is deliberately a single-operator demonstration, not a multi-tenant service. A session token and trusted-host checks protect local write endpoints against basic cross-origin browser abuse. They do not constitute authentication. A public deployment would require a different security and job-processing design.

## Conservative rules before machine learning

The consumption rule uses only earlier baseline values and requires a three-day run. It trades recall for explainability. Four subtle 1.5× events are missed, which the benchmark reports. A future model should improve a separately held-out evaluation, not merely add another library to the stack.

## Native browser interface

Semantic HTML, CSS and JavaScript provide four focused views without a frontend build dependency. Server state is authoritative; no case decisions live only in browser storage. Native dialogs supply modal focus handling. User-derived strings are escaped before rendering. Node/Playwright are test dependencies only.

## Versioned Power BI source

PBIP/PBIR and a JSON semantic model keep report structure, Power Query and DAX reviewable in Git. A generated folder parameter connects exported marts. Schema validation, native model execution and visual inspection are separate checks. Native M/DAX and relationship behavior passed through a temporary database on Desktop's local engine, with every result compared against CSV data. User screenshots subsequently confirmed PBIP opening, Desktop refresh and all three populated pages. The updated formatting on all three pages is also confirmed, including exact card totals and readable table headers. The user manually confirmed that Billing review district selections update the linked visuals. See [Power BI validation](powerbi-validation.md).

## What would change for production

Add authenticated roles, private TLS deployment, schema migrations, per-source ingestion locks, resumable background jobs, durable scheduling, reconciliation and retention policies, observability, independent real-data validation, and effective-dated tariff modeling. The current engine re-evaluates history after each small batch and has bounded file size; it is not a streaming service.
