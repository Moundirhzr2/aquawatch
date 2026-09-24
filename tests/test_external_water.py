"""Checks for the boundary between external readings and synthetic cases."""

import csv
from zipfile import ZipFile

import pytest

from aquawatch import external_water


def archive_with_rows(tmp_path, rows, name="hh-04/smartmeter.csv"):
    archive = tmp_path / "household.zip"
    source = tmp_path / "smartmeter.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time", "unixtime", "total_m3"])
        writer.writerows(rows)
    with ZipFile(archive, "w") as bundle:
        bundle.write(source, name)
    return archive


def test_external_summary_excludes_unlabeled_performance_claims(tmp_path, monkeypatch):
    archive = archive_with_rows(
        tmp_path,
        [
            ("2022-01-01 23:00:00+00:00", 1641078000, "1.000"),
            ("2022-01-01 23:00:00+00:00", 1641078000, "1.000"),
            ("2022-01-02 23:00:00+00:00", 1641164400, "1.100"),
            ("2022-01-04 23:00:00+00:00", 1641337200, "1.300"),
            ("2022-01-05 23:00:00+00:00", 1641423600, "not-a-number"),
        ],
    )
    monkeypatch.setitem(external_water.HOUSEHOLD_ARCHIVES, "hh-04", archive)
    result = external_water.evaluate_household("hh-04")
    assert result["source_rows"] == 5
    assert result["valid_rows"] == 3
    assert result["duplicate_timestamps"] == 1
    assert result["invalid_rows"] == 1
    assert result["daily_observations"] == 3
    assert result["valid_daily_intervals"] == 1
    assert result["rule_flags_by_kind"] == {"missing_reading": 1}
    assert result["precision"] is None and result["recall"] is None
    assert "1.300" not in str(result)


def test_rejects_archive_with_unexpected_layout(tmp_path, monkeypatch):
    archive = archive_with_rows(tmp_path, [], name="other/smartmeter.csv")
    monkeypatch.setitem(external_water.HOUSEHOLD_ARCHIVES, "hh-04", archive)
    with pytest.raises(ValueError, match="layout"):
        external_water.evaluate_household("hh-04")


def test_rejects_unlisted_household():
    with pytest.raises(KeyError):
        external_water.evaluate_household("../../private")
