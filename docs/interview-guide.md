# Interview preparation

## Questions worth practicing

1. **Why cumulative counters?** Explain the difference between a counter and daily consumption, plus why gaps and resets cannot be treated as ordinary daily deltas.
2. **What does idempotency mean here?** File-byte SHA-256 avoids an exact replay; meter/date uniqueness protects individual observations. A changed file can contain duplicate rows that are quarantined.
3. **What happens if an import fails?** Accepted rows and generated cases roll back together; the separate run ledger records the failure. Discuss crash recovery as an explicit limitation.
4. **Why not overwrite conflicting readings?** Preserving the original and quarantining the conflict makes provenance reviewable. A production correction workflow would need a versioned source-of-truth policy.
5. **How do you avoid look-ahead leakage?** A baseline uses preceding observations. Three high days are needed before confirming an event whose onset was two days earlier.
6. **Why is recall below 100%?** Conservative thresholds miss the deliberately subtle events. Describe the operator workload/recall tradeoff without claiming that synthetic precision predicts real-world performance.
7. **Why PostgreSQL and dbt?** Explain transactional operational writes, dimensional reporting grains, SQL transformations, lineage and tests.
8. **How are concurrent updates handled?** Conditional SQL update on case version, HTTP 409 for stale edits, transactionally recorded history.
9. **Are the financial amounts savings?** No. They are simulated arithmetic discrepancies requiring review. Volume reconciliation, taxes and tariff changes are outside scope.
10. **What would block public production use?** Authentication, multi-process ingestion coordination, migrations, job recovery, operational monitoring and independent validation.

## Suggested learning sequence

- Follow one row from CSV through ingestion, database, detection and API response.
- Change one validation rule and add a behavioral test demonstrating its consequences.
- Write a SQL query comparing valid intervals by district and explain the grain.
- Reproduce the benchmark, inspect the missed events, and explain a sensible next experiment.
- Modify one dashboard view and verify keyboard/mobile behavior.
- Refresh Power BI and explain the difference between active case amounts and all invoice discrepancies.

## CV entry after you can explain and demonstrate it

**AquaWatch — Projet personnel Data Engineering & BI**  
Pipeline Python/SQL de traitement de relevés de compteurs simulés, modélisation PostgreSQL/dbt et contrôles automatisés de qualité. Développement d'une interface d'investigation avec historique des décisions ; évaluation des règles sur un benchmark synthétique de 120 compteurs.

Add the Power BI report to this wording after opening, refreshing and verifying it in Desktop. Do not describe this as client work, a Veolia implementation, an independently validated model or a source of proven savings.

The project was developed with Codex assistance. Do not invent a development history or claim to have written every line independently. Be ready to explain the code, identify tradeoffs and make changes yourself.
