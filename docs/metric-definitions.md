# Metric definitions

| Metric | Definition and grain | Important limit |
|---|---|---|
| Connected meters | Distinct meter IDs | Inventory, not device online status |
| Accepted readings | One record per meter/date | A valid record may still reveal a counter reset |
| Daily consumption | Current minus previous cumulative counter, only for consecutive dates with nonnegative difference | Initial, reset and gap intervals are null |
| Network consumption | Sum of valid meter/day intervals, converted from liters to m³ | Compare alongside valid-interval count; incomplete coverage can reduce totals |
| Active investigations | Cases with status `open` or `investigating` | One event, not one anomalous daily record |
| Active amount to review | Sum of active case amounts in cents / 100 | Only tariff mismatches carry an amount; not proven savings |
| Row acceptance rate | Accepted rows / (accepted + quarantined rows) | Duplicate rows are quarantined; not completeness or freshness |
| Valid interval share | Valid daily intervals / all accepted observations | Includes first observations in denominator; distinct from acceptance rate |
| Invoice amount to review | Sum of absolute invoice differences exceeding one cent | Independent of case status; includes resolved-case invoices |
| Expected invoice amount | Half-up rounding of stated liters × cents-per-m³ / 1,000, plus fixed fee | Uses stated invoice volume, not a reconstructed meter volume |
| Synthetic precision | Exact matched events / predicted events | Benchmark only; no true-negative accuracy |
| Synthetic recall | Exact matched events / labeled events | Labels include four subtle events deliberately below threshold |

All timestamps in the ledger and case history are UTC ISO-8601 values. Reading dates are date-only observation labels. The browser formats operational timestamps in the viewer's local time.

Power BI uses `dim_meters` and `dim_date` with one-way filters into the facts. Date filters apply to reading date, case onset date and invoice period end respectively. These are different business grains. Import timestamps do not share the reading-date dimension. `network_daily` is a network aggregate and should not be sliced by a meter district; use the consumption fact for district analysis.

dbt/Power BI are rebuilt snapshots. The application reads current operational tables directly. Refresh analytics after case decisions or new imports to align the reports with the app.
