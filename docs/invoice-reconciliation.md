# Invoice-to-meter volume reconciliation

AquaWatch checks two separate questions for each synthetic invoice:

1. **Tariff arithmetic:** Does the invoice amount equal its *stated* liters multiplied by the synthetic tariff, plus the fixed fee? The existing `billing_mismatch` rule answers this.
2. **Volume evidence:** Do the stated liters agree with the change in cumulative meter counter over the same invoice period? The new `volume_mismatch` rule answers this only when the period is verifiable.

The period requires an accepted reading on both `period_start` and `period_end`, every intervening day, and no counter decrease. The measured volume is `end_counter_liters - start_counter_liters`. A positive signed difference means that the invoice states more liters than the meter change; a negative one means fewer. An absolute difference of **more than 1,000 L** creates an investigation case. This threshold is an explicit synthetic-demo tolerance, not a regulatory standard.

Missing boundary readings produce `missing_boundary`; internal missing days produce `incomplete`; a decrease produces `counter_reset`. These statuses have **null** measured volume and signed difference. A gap can contain a valid total across its endpoints, but it could also hide a replacement, so this demo conservatively marks the period unverified. If a gap and reset both occur, `counter_reset` takes priority. A later reading outside the invoice period is never used as its end boundary.

The baseline demonstrates 110 matched invoices, 2 volume mismatches and 8 unverified periods (4 gaps, 4 resets). The two mismatched invoices have correct tariff arithmetic for their stated volume. Their combined absolute difference is 20 m³, **not a confirmed overcharge or savings**. The API, Python detector and dbt mart use the same status semantics; `scripts/check_analytics.py` checks their parity invoice by invoice. The web dashboard links the two differences to persistent investigation cases. The fourth Power BI page reports the same volume states at the invoice grain.

On an existing local demo database, bootstrap updates only the two invoices whose meter, tariff, dates, old volume and old amount exactly match the earlier synthetic fixture. It then adds the two new cases without altering existing decisions. Any manually modified invoice is left unchanged; a fresh demo database reproduces the full baseline counts above.

This demo has one flat synthetic tariff. It does not model effective-dated tariff changes, real meter replacement metadata, estimated reads, bill reversals or legally authoritative consumption. Those would require additional source contracts and independent domain validation before use with real customer data.
