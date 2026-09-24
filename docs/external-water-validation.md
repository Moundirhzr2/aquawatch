# Independent water-reading compatibility check

**24 September 2026.** AquaWatch was run, without changing its detection rules, on two households from *Smart Meter Water Consumption Measurements* by Sebastian Wilhelm, Jakob Kasbauer, Dietmar Jakob, Benedikt Elser and Diane Ahrens ([Zenodo DOI](https://doi.org/10.5281/zenodo.7506076), CC BY 4.0). This is a read-only check of the external data adapter and rule burden. The source archive is not committed, imported into the operational database or mixed with the synthetic benchmark.

The source supplies timestamped **cumulative cubic metres**, not AquaWatch's daily integer-liter records. The adapter takes the last valid observation of each UTC day and rounds the cumulative volume to integer liters. It checks the Unix timestamp against the timestamp column, counts invalid and duplicate rows, then runs the unchanged daily series and detection rules. It neither imputes missing days nor carries a multi-day volume change into a daily consumption value. The source does not contain compatible leak, reset or missing-reading event labels, invoices or tariffs, so **precision and recall are unknown**. Rule flags are review candidates, not confirmed incidents or false positives.

| Household | Raw rows | Observed days / calendar span | Valid daily intervals | Missing-reading flags | Sustained-usage flags |
|---|---:|---:|---:|---:|---:|
| hh-04 | 145,515 | 95 / 533 (17.82%) | 78 | 16 | 0 |
| hh-14 | 428,090 | 111 / 522 (21.26%) | 106 | 4 | 0 |

The sampled households have sparse coverage across their full date spans. A missing-reading flag marks a **gap episode**, not one missing day. Zero sustained-usage flags does not establish that the detector found all leaks, or that there were none. This check exposes a real limitation of daily-only detection with intermittent telemetry. It does not validate billing rules or generalize to the other 15 households.

The reproducible summaries, including SHA-256 values for the two input archives, are in [external-water-validation.json](external-water-validation.json). To rerun, download `hh-04.zip` and `hh-14.zip` from the Zenodo record into ignored `runtime/external/`, then run:

```powershell
python -m aquawatch.external_water hh-04
python -m aquawatch.external_water hh-14
```

No raw household readings are stored in this repository. A true field-performance evaluation would require permissioned incident labels aligned to meters and time windows, together with an agreed matching tolerance, coverage threshold and investigation outcome. Until then, the synthetic precision and recall figures must remain explicitly separate from this external compatibility check.
