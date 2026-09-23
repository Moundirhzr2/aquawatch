# Two-minute demonstration

Use a fresh demo if you want the exact baseline numbers. The database is persistent; previous imports and decisions remain visible.

**0:00–0:20 — Explain the context.**

“My experience with meter-data quality inspired AquaWatch. This is an independent project with synthetic data. It helps an operator move from a suspicious reading to an explained investigation.”

**0:20–0:40 — Show the network overview.**

Point to the meters, accepted readings, active cases and acceptance rate. Explain that a high acceptance rate does not mean every meter supplied every reading. State that invoice discrepancies are review amounts, not savings.
If time permits, open invoice INV-0029 in the volume table: its tariff arithmetic is correct, but its stated volume is 12 m³ above the complete meter-period change.

**0:40–1:10 — Investigate M-0001.**

Open Investigations, search M-0001 and inspect the sustained consumption case. Explain the earlier median, the threshold and three-day confirmation. Record an investigation note and change the case to Investigating. Refresh and show the persisted history.

**1:10–1:30 — Demonstrate reliability.**

Run the daily import, then run it again. The first accepts 120 new observations; the replay returns the existing run. Open the baseline import to inspect the eight quarantined records.

**1:30–1:50 — Show evidence and limits.**

Open Model & evidence. Explain the 27 matched events and four misses. Discuss why subtle consumption changes are hard to distinguish from legitimate activity without additional context.

**1:50–2:00 — Show the engineering.**

Open the repository architecture, tests and dbt model graph. If Power BI has been locally refreshed, show its four report pages, including the separate volume comparison. Be clear about which features you can demonstrate versus those still needing native verification.

For a longer interview, walk through `pipeline.py`, `fct_consumption.sql`, a concurrency test and a Power BI measure. Explain the implementation in your own words, including the role of AI assistance.
