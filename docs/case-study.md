# Case study: AquaWatch

## Business problem

Utility operations teams need to decide which readings and invoices deserve investigation. A daily consumption spike can mean a leak, changed activity or an input problem. A dashboard that only totals usage cannot explain which source records are trustworthy or what an operator should check.

This independent portfolio project is inspired by Moundir Houazar's experience with meter-data quality at Amendis. It uses no company data and claims no company deployment or operational benefit.

## Delivered solution

The pipeline reads daily cumulative meter observations, validates records, preserves provenance and quarantines problematic rows. Five explained exception types feed an investigation queue. An operator can inspect the underlying meter history, change the case status and retain a decision note. dbt builds an analytical model for a three-page Power BI report.

## Experimental design

120 meters, 90 observation dates, residential and commercial baselines, controlled noise, one-day benign spikes and known anomalies. The baseline contains 10,804 incoming rows: 10,796 accepted and 8 quarantined. Of the quarantined rows, five are duplicates; three have invalid values, dates or meter references.

The label file contains 29 events: six clear sustained-use anomalies, four subtle sustained-use anomalies, four counter resets, four missing-reading events, six tariff mismatches and five duplicates. Detection is evaluated by exact meter/type/onset-date matching.

## Results

| Event | Matched | False alerts | Missed |
|---|---:|---:|---:|
| Sustained consumption | 6 | 0 | 4 |
| Counter reset | 4 | 0 | 0 |
| Missing reading | 4 | 0 | 0 |
| Billing mismatch | 6 | 0 | 0 |
| Duplicate reading | 5 | 0 | 0 |
| **Total** | **25** | **0** | **4** |

This gives 100% synthetic precision and 86.2% synthetic recall. Seeds 71 and 103 produce the same event results while varying consumption values. They reuse the event templates and therefore do not establish external generalization.

The six invoice discrepancies total €255 in the fixture. This is a simulated amount requiring review, not money saved or recovered. Timings are recorded in `benchmark.json`; they depend on the test machine and are not a service-level guarantee.

## Why the result is useful

The demonstration makes correctness inspectable: replay a file, examine quarantine, explain a counter reset, save a decision and rebuild reporting tables. Tests verify behavior that matters operationally, including rollback and stale-update rejection. The project exposes missed detections and separates record validity from usable daily consumption.

## Next experiment

Obtain domain feedback, establish meter-type/cadence requirements, and evaluate against a genuinely independent dataset with permission. Compare a seasonal or segment-aware baseline to the current rule using a fixed held-out set, detection delay and operator review cost. Add model complexity only if the evidence justifies it.
