"""Tests for pipeline/build_co.py (CSA MOPITT carbon monoxide)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import build_co as bc

HEADER = "# Latitude, Longitude, COTotalColumn,COMixingRatio surface\n"


def write(folder, name, rows, header=True):
    p = Path(folder) / name
    p.write_text((HEADER if header else "") + "".join(f"{a},{b},{c},{d}\n" for a, b, c, d in rows))
    return p


class TestReadDay:
    def test_header_line_is_skipped(self, tmp_path):
        p = write(tmp_path, "d.csv", [(48, -55, 2e18, 100)])
        assert len(bc.read_day(p)) == 1

    def test_header_only_file_is_empty_not_an_error(self, tmp_path):
        assert len(bc.read_day(write(tmp_path, "d.csv", []))) == 0

    def test_cut_off_line_is_skipped_with_a_warning(self, tmp_path, capsys):
        # a download that stopped mid-line: the header and then "-8"
        p = tmp_path / "MOP02J-20030303-L2V18.0.3.csv"
        p.write_text(HEADER + "-8")
        assert len(bc.read_day(p)) == 0
        assert "skipped 1 incomplete line" in capsys.readouterr().out

    def test_cut_off_line_after_good_rows_keeps_the_good_rows(self, tmp_path, capsys):
        p = tmp_path / "d.csv"
        p.write_text(HEADER + "48,-55,2e18,100\n49,-56,2.1e18,110\n47.5,-5")
        df = bc.read_day(p)
        assert len(df) == 2 and df.co_total.tolist() == [2e18, 2.1e18]
        assert "skipped 1 incomplete line" in capsys.readouterr().out

    def test_full_14_column_rows_are_read(self, tmp_path, capsys):
        p = tmp_path / "d.csv"
        p.write_text(HEADER + "48,-55,2e18,100" + ",1" * 10 + "\n")
        assert len(bc.read_day(p)) == 1 and capsys.readouterr().out == ""

    def test_zero_byte_file_is_empty_not_an_error(self, tmp_path):
        p = tmp_path / "d.csv"
        p.write_text("")
        assert len(bc.read_day(p)) == 0

    @pytest.mark.parametrize("lat,lon,kept", [
        (46.4, -55, True), (46.39, -55, False),        # south edge
        (51.9, -55, True), (51.91, -55, False),        # north edge
        (48, -59.7, True), (48, -59.71, False),        # west edge
        (48, -52.4, True), (48, -52.39, False),        # east edge
    ])
    def test_island_box_boundaries(self, tmp_path, lat, lon, kept):
        assert (len(bc.read_day(write(tmp_path, "d.csv", [(lat, lon, 2e18, 100)]))) == 1) is kept

    def test_point_far_away_is_dropped(self, tmp_path):
        assert len(bc.read_day(write(tmp_path, "d.csv", [(10, 10, 2e18, 100)]))) == 0


class TestValid:
    def test_fill_values_and_bad_numbers_become_missing(self):
        out = bc.valid(pd.Series([2.0, 0.0, -9999.0, np.nan, np.inf, "x"]))
        assert out.notna().tolist() == [True, False, False, False, False, False]


class TestOneFilePerDate:
    def test_duplicate_date_uses_shorter_name(self, tmp_path, capsys):
        a = write(tmp_path, "MOP02J-20190927-L2V18.0.3.csv", [(48, -55, 1e18, 1)])
        b = write(tmp_path, "MOP02J-20190927-L2V18.0.3 (1).csv", [(48, -55, 9e18, 9)])
        out = bc.one_file_per_date([str(b), str(a)])
        assert out == [str(a)]
        assert "WARNING" in capsys.readouterr().out

    def test_files_without_a_date_are_ignored(self, tmp_path):
        a = write(tmp_path, "notes.csv", [])
        assert bc.one_file_per_date([str(a)]) == []


def daily_frame(rows):
    return pd.DataFrame(rows, columns=["year", "month", "n_total", "n_surface", "co_total_1e18", "co_surface_ppbv"])


class TestMonthly:
    def test_each_day_counts_once_not_by_number_of_readings(self):
        # day 1: 100 readings of 1.0; 14 other days: 1 reading of 3.0
        rows = [(2013, 6, 100, 100, 1.0, 100.0)] + [(2013, 6, 1, 1, 3.0, 200.0)] * 14
        m = bc.build_monthly(daily_frame(rows), min_days=15)
        assert m.co_total_1e18.iloc[0] == pytest.approx((1.0 + 14 * 3.0) / 15)

    @pytest.mark.parametrize("days,has_value", [(14, False), (15, True), (16, True)])
    def test_minimum_days_boundary(self, days, has_value):
        rows = [(2013, 6, 5, 5, 2.0, 100.0)] * days
        m = bc.build_monthly(daily_frame(rows), min_days=15)
        assert (not np.isnan(m.co_total_1e18.iloc[0])) is has_value
        assert m.days_with_data.iloc[0] == days

    def test_days_with_no_valid_reading_are_not_counted(self):
        rows = [(2013, 6, 5, 5, 2.0, 100.0)] * 14 + [(2013, 6, 0, 0, np.nan, np.nan)] * 5
        m = bc.build_monthly(daily_frame(rows), min_days=15)
        assert m.days_with_data.iloc[0] == 14 and np.isnan(m.co_total_1e18.iloc[0])

    def test_months_are_separate(self):
        rows = [(2013, 6, 5, 5, 2.0, 100.0)] * 15 + [(2013, 7, 5, 5, 4.0, 300.0)] * 15
        m = bc.build_monthly(daily_frame(rows), min_days=15).set_index("month")
        assert m.loc[6, "co_total_1e18"] == 2.0 and m.loc[7, "co_total_1e18"] == 4.0


def test_end_to_end_on_small_folder(tmp_path, monkeypatch):
    raw, out = tmp_path / "raw", tmp_path / "out"
    raw.mkdir()
    for d in range(1, 17):
        write(raw, f"MOP02J-201306{d:02d}-L2V18.0.3.csv", [(48, -55, 2e18, 100), (10, 10, 9e18, 900)])
    monkeypatch.setattr("sys.argv", ["build_co.py", "--raw", str(raw), "--out", str(out), "--publish", "none"])
    bc.main()
    j = json.loads((out / "co_monthly.json").read_text())
    assert j["months"][0]["year"] == 2013 and j["months"][0]["co_total_1e18"] == pytest.approx(2.0)
    assert j["months"][0]["days_with_data"] == 16
    assert (out / "co_daily.csv").exists() and (out / "co_monthly.csv").exists()


def test_no_files_is_an_error(tmp_path):
    with pytest.raises(SystemExit):
        bc.build_daily(str(tmp_path))
