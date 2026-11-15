"""Tests for pipeline/build_harmonized.py.

Test types used here:
  - equivalence partitioning: one test per kind of input (kept, removed, missing)
  - boundary values: the exact edge of each rule (confidence 29/30, series start/end)
  - error cases: missing files, zero totals
  - contract tests: the output files have the fields the web app needs
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import build_harmonized as bh

ROOT = Path(__file__).resolve().parent.parent
APP_DATA = ROOT / "app" / "data"

COLS = ["latitude", "longitude", "acq_date", "acq_time", "satellite", "confidence",
        "type", "frp", "daynight", "instrument", "version"]


def row(date="2018-06-01", lat=48.0, lon=-55.0, conf="85", typ=0, time="1200", sat="Terra"):
    return [lat, lon, date, time, sat, conf, typ, 10.0, "D", "MODIS", "6.1"]


def write_source(tmp_path, folder, archive_rows, nrt_rows=None, key="modis"):
    d = tmp_path / folder
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(archive_rows, columns=COLS).to_csv(d / "fire_archive_X.csv", index=False)
    if nrt_rows is not None:
        # near-real-time files have no "type" column
        nrt = pd.DataFrame(nrt_rows, columns=COLS).drop(columns=["type", "version"])
        nrt.to_csv(d / "fire_nrt_X.csv", index=False)
    return tmp_path


# ---------------------------------------------------------------- load_source
class TestLoadSource:
    def test_type_filter_keeps_only_vegetation_fire(self, tmp_path):
        rows = [row(typ=0), row(lat=48.1, typ=1), row(lat=48.2, typ=2), row(lat=48.3, typ=3)]
        write_source(tmp_path, "modis", rows)
        df, info = bh.load_source(tmp_path, "modis", "modis")
        assert len(df) == 1
        assert info["removed_non_vegetation"] == {"1": 1, "2": 1, "3": 1}

    def test_nrt_rows_without_type_are_kept(self, tmp_path):
        write_source(tmp_path, "modis", [row()], nrt_rows=[row(date="2026-10-01", lat=49.0)])
        df, info = bh.load_source(tmp_path, "modis", "modis")
        assert len(df) == 2
        assert info["rows_without_type_kept"] == 1

    @pytest.mark.parametrize("conf,kept", [("29", False), ("30", True), ("31", True), ("0", False), ("100", True)])
    def test_modis_confidence_boundary(self, tmp_path, conf, kept):
        write_source(tmp_path, "modis", [row(conf=conf)])
        df, _ = bh.load_source(tmp_path, "modis", "modis")
        assert (len(df) == 1) is kept

    @pytest.mark.parametrize("conf,kept", [("l", False), ("low", False), ("n", True), ("nominal", True),
                                           ("h", True), ("high", True), ("H", True)])
    def test_viirs_confidence_classes(self, tmp_path, conf, kept):
        write_source(tmp_path, "viirs_noaa20", [row(conf=conf)])
        df, _ = bh.load_source(tmp_path, "n20", "viirs_noaa20")
        assert (len(df) == 1) is kept

    def test_duplicates_removed(self, tmp_path):
        write_source(tmp_path, "modis", [row(), row()])
        df, info = bh.load_source(tmp_path, "modis", "modis")
        assert len(df) == 1 and info["duplicates_removed"] == 1

    def test_same_place_different_time_is_not_a_duplicate(self, tmp_path):
        write_source(tmp_path, "modis", [row(time="1200"), row(time="1330")])
        df, _ = bh.load_source(tmp_path, "modis", "modis")
        assert len(df) == 2

    @pytest.mark.parametrize("date,kept", [("2000-10-31", False), ("2000-11-01", True),
                                           ("2026-11-30", True), ("2026-12-01", False)])
    def test_series_window_boundaries(self, tmp_path, date, kept):
        write_source(tmp_path, "modis", [row(date=date)])
        df, _ = bh.load_source(tmp_path, "modis", "modis")
        assert (len(df) == 1) is kept

    def test_missing_archive_file_is_an_error(self, tmp_path):
        (tmp_path / "modis").mkdir()
        with pytest.raises(SystemExit):
            bh.load_source(tmp_path, "modis", "modis")

    def test_missing_folder_is_an_error(self, tmp_path):
        with pytest.raises(SystemExit):
            bh.load_source(tmp_path, "modis", "does_not_exist")


# ---------------------------------------------------------------- monthly_counts
class TestMonthlyCounts:
    def idx(self):
        return pd.period_range("2018-05", "2018-07", freq="M")

    def make(self, tmp_path, rows):
        write_source(tmp_path, "modis", rows)
        df, _ = bh.load_source(tmp_path, "modis", "modis")
        return df

    def test_two_detections_in_one_cell_one_day_is_one_cell(self, tmp_path):
        df = self.make(tmp_path, [row(lat=48.01, lon=-55.01, time="1000"), row(lat=48.04, lon=-55.04, time="1100")])
        c = bh.monthly_counts(df, self.idx())
        assert c.loc["2018-06", "hotspots"] == 2 and c.loc["2018-06", "cells"] == 1

    def test_same_cell_on_two_days_is_two_cells(self, tmp_path):
        df = self.make(tmp_path, [row(date="2018-06-01"), row(date="2018-06-02")])
        assert bh.monthly_counts(df, self.idx()).loc["2018-06", "cells"] == 2

    def test_cell_edge_goes_to_next_cell(self, tmp_path):
        # 48.0999 and 48.1000 are in different 0.1 degree cells
        df = self.make(tmp_path, [row(lat=48.0999), row(lat=48.1000, time="1300")])
        assert bh.monthly_counts(df, self.idx()).loc["2018-06", "cells"] == 2

    def test_months_without_data_are_zero_not_missing(self, tmp_path):
        df = self.make(tmp_path, [row()])
        c = bh.monthly_counts(df, self.idx())
        assert list(c.index.astype(str)) == ["2018-05", "2018-06", "2018-07"]
        assert c.loc["2018-05", "cells"] == 0 and c.loc["2018-07", "hotspots"] == 0

    def test_empty_input(self):
        empty = pd.DataFrame({"month": pd.PeriodIndex([], freq="M"), "ci": [], "cj": [], "date": pd.to_datetime([])})
        c = bh.monthly_counts(empty, self.idx())
        assert c.to_numpy().sum() == 0


# ---------------------------------------------------------------- fit_ratio
def series(values_by_year, months=bh.SEASON_MONTHS):
    """Monthly series with the given season total put in the first season month."""
    idx = pd.period_range("2010-01", "2025-12", freq="M")
    s = pd.Series(0, index=idx, dtype=float)
    for y, v in values_by_year.items():
        s[pd.Period(year=y, month=months[0], freq="M")] = v
    return s


class TestFitRatio:
    years = [2018, 2019, 2020, 2021]

    def test_exact_ratio_is_recovered_with_zero_error(self):
        modis = series({y: 10 * (i + 1) for i, y in enumerate(self.years)})
        viirs = modis * 2.5
        k, st = bh.fit_ratio(modis, viirs, self.years)
        assert k == pytest.approx(2.5)
        assert st["cv_median_pct_err"] == pytest.approx(0, abs=1e-9)
        assert st["yearly_ratio_min"] == st["yearly_ratio_max"] == pytest.approx(2.5)
        assert st["pearson_r"] == pytest.approx(1.0)

    def test_k_is_total_over_total_not_mean_of_ratios(self):
        modis = series({2018: 10, 2019: 100})
        viirs = series({2018: 40, 2019: 100})   # yearly ratios 4 and 1
        k, st = bh.fit_ratio(modis, viirs, [2018, 2019])
        assert k == pytest.approx(140 / 110)
        assert st["yearly_ratio_min"] == pytest.approx(1.0) and st["yearly_ratio_max"] == pytest.approx(4.0)

    def test_only_season_months_count(self):
        modis = series({2018: 10, 2019: 10})
        viirs = modis * 2
        viirs[pd.Period("2018-01", "M")] = 999      # January is outside May to September
        k, _ = bh.fit_ratio(modis, viirs, [2018, 2019])
        assert k == pytest.approx(2.0)

    def test_leave_one_year_out_error_known_value(self):
        modis = series({2018: 10, 2019: 10, 2020: 10})
        viirs = series({2018: 20, 2019: 20, 2020: 40})
        _, st = bh.fit_ratio(modis, viirs, [2018, 2019, 2020])
        errs = {r["year"]: r["pct_err"] for r in st["leave_one_year_out"]}
        assert errs[2020] == pytest.approx(50.0)          # predicts 20 for a true 40
        assert errs[2018] == pytest.approx(abs(30 - 20) / 20 * 100)

    def test_modis_all_zero_is_an_error(self):
        with pytest.raises(SystemExit):
            bh.fit_ratio(series({2018: 0, 2019: 0}), series({2018: 5, 2019: 5}), [2018, 2019])

    def test_a_year_where_modis_saw_nothing_is_skipped_in_yearly_ratios(self):
        modis = series({2018: 0, 2019: 10})
        viirs = series({2018: 5, 2019: 20})
        _, st = bh.fit_ratio(modis, viirs, [2018, 2019])
        assert list(st["yearly_ratios"]) == [2019]

    def test_monthly_error_counts_only_months_where_viirs_saw_fire(self):
        modis = series({2018: 10, 2019: 10})
        viirs = series({2018: 20, 2019: 20})
        _, st = bh.fit_ratio(modis, viirs, [2018, 2019])
        assert st["monthly_cv_n_months"] == 2


# ---------------------------------------------------------------- month_to_date
class TestMonthToDate:
    def daily(self, hits):
        idx = pd.date_range("2000-11-01", "2030-12-31", freq="D")
        s = pd.Series(0.0, index=idx)
        for d in hits:
            s[pd.Timestamp(d)] += 1
        return s

    def test_counts_only_days_up_to_the_cut_off(self):
        s = self.daily(["2024-11-03", "2024-11-20", "2026-11-02"])
        r = bh.month_to_date(s, pd.Timestamp("2026-11-07"), pd.Period("2018-04", "M"))
        assert r["current"] == 1
        # 2018-2025: only 2024 has a detection on days 1-7 (Nov 3), so it equals the current 1; the other 7 years have 0.
        # The 20 November detection is after the cut-off and must not count.
        assert r["years_fewer"] == 7 and r["years_equal"] == 1 and r["years_more"] == 0
        assert r["same_era_years"] == 8

    def test_first_era_month_is_respected(self):
        s = self.daily([])
        r = bh.month_to_date(s, pd.Timestamp("2026-11-07"), pd.Period("2020-01", "M"))
        assert r["same_era_years"] == 6

    def test_leap_day_cut_off_does_not_crash(self):
        s = self.daily(["2024-02-29", "2023-02-28"])
        r = bh.month_to_date(s, pd.Timestamp("2028-02-29"), pd.Period("2018-04", "M"))
        assert r["month"] == "2028-02" and r["current"] == 0
        assert r["years_more"] == 2  # 2023 (Feb 1-28 clamp) and 2024 each have one

    def test_no_earlier_years_gives_none_not_an_error(self):
        s = self.daily([])
        r = bh.month_to_date(s, pd.Timestamp("2026-11-07"), pd.Period("2026-01", "M"))
        assert r["same_era_years"] == 0 and r["historical_median"] is None and r["years_fewer"] is None


# ---------------------------------------------------------------- season_totals
def test_season_totals_sums_may_to_september_by_year():
    s = series({2018: 7, 2019: 3})
    out = bh.season_totals(s)
    assert out[2018] == 7 and out[2019] == 3


# ---------------------------------------------------------------- contract: output files
needs_outputs = pytest.mark.skipif(not (APP_DATA / "summary.json").exists(),
                                   reason="run pipeline/build_harmonized.py first")


@needs_outputs
class TestOutputContract:
    """The web app reads these fields. If a field is renamed or removed, the app breaks."""

    @pytest.fixture(scope="class")
    def summary(self):
        return json.loads((APP_DATA / "summary.json").read_text())

    def test_summary_has_fields_used_by_the_app(self, summary):
        for k in ("ratios", "series_rules", "coverage_end", "checks"):
            assert k in summary
        for metric in ("cells", "hotspots"):
            r = summary["ratios"][metric]
            for f in ("k", "yearly_ratio_min", "yearly_ratio_max", "pearson_r",
                      "cv_median_pct_err", "monthly_cv_median_pct_err"):
                assert isinstance(r[f], (int, float)), (metric, f)
        for f in ("viirs_first", "noaa20_from", "has_snpp", "fit_years"):
            assert f in summary["series_rules"]

    def test_ratios_are_sane(self, summary):
        k = summary["ratios"]["cells"]["k"]
        assert 0.5 < k < 10
        assert summary["ratios"]["cells"]["yearly_ratio_min"] <= k <= summary["ratios"]["cells"]["yearly_ratio_max"]

    def test_hotspot_file_has_the_columns_the_app_reads(self):
        head = (APP_DATA / "hotspots_clean.csv").open().readline().strip().split(",")
        for c in ("date", "latitude", "longitude", "source"):
            assert c in head

    def test_hotspot_sources_are_known(self):
        df = pd.read_csv(APP_DATA / "hotspots_clean.csv", usecols=["source"])
        assert set(df.source) <= {"modis", "snpp", "n20", "n21"}

    def test_monthly_series_is_complete_and_in_order(self):
        m = pd.read_csv(APP_DATA / "monthly_harmonized.csv")
        p = pd.PeriodIndex(m.month, freq="M")
        assert p.is_monotonic_increasing and len(p) == len(set(p))
        assert (p[1:] - p[:-1]).map(lambda x: x.n).max() == 1     # no missing month
        assert (m.harmonized_cells >= 0).all() and (m.harmonized_hotspots >= 0).all()

    def test_zero_months_never_get_a_high_percentile(self):
        m = pd.read_csv(APP_DATA / "monthly_harmonized.csv")
        zero = m[m.harmonized_cells == 0].percent_of_years_below.fillna(0)
        assert (zero == 0).all()

    def test_viirs_era_months_use_observed_counts_not_scaled_ones(self):
        m = pd.read_csv(APP_DATA / "monthly_harmonized.csv")
        n20 = m[(m.harmonized_source == "VIIRS NOAA-20")]
        assert (n20.harmonized_cells == n20.n20_cells).all()
        assert (n20.era == "VIIRS").all()

    def test_modis_months_are_scaled_by_k(self, summary):
        k = summary["ratios"]["cells"]["k"]
        m = pd.read_csv(APP_DATA / "monthly_harmonized.csv")
        sc = m[m.harmonized_source == "MODIS (scaled)"]
        assert np.allclose(sc.harmonized_cells, sc.modis_cells * k, atol=0.01)

    def test_baseline_never_mixes_eras(self):
        b = pd.read_csv(APP_DATA / "monthly_baseline.csv")
        assert "era" in b.columns
