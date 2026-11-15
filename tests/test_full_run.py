"""Full run of pipeline/build_harmonized.py on small made-up FIRMS files.

The made-up data has a known answer: MODIS sees 5 fire cells every July, VIIRS sees 10,
so the fitted ratio for fire cells must be 2.0 and MODIS months must be scaled by 2.0.
"""
import json
import os
from pathlib import Path

import pandas as pd
import pytest

os.environ.setdefault("MPLBACKEND", "Agg")
import build_harmonized as bh  # noqa: E402

COLS = ["latitude", "longitude", "acq_date", "acq_time", "satellite", "confidence",
        "type", "frp", "daynight", "instrument", "version"]


def july_rows(year, n, conf="85"):
    # n detections on different days in July, each in its own 0.1 degree cell
    return [[48.0 + 0.2 * i, -55.0, f"{year}-07-{i + 1:02d}", "1200", "S", conf, 0, 5.0, "D", "X", "1"]
            for i in range(n)]


def write(raw, folder, rows, nrt=None):
    d = raw / folder
    d.mkdir(parents=True)
    pd.DataFrame(rows, columns=COLS).to_csv(d / "fire_archive_T.csv", index=False)
    if nrt:
        pd.DataFrame(nrt, columns=COLS).drop(columns=["type", "version"]).to_csv(d / "fire_nrt_T.csv", index=False)


def build(tmp_path, with_snpp):
    raw = tmp_path / "raw"
    modis = [r for y in range(2001, 2026) for r in july_rows(y, 5, "85")]
    n20 = [r for y in range(2018, 2026) for r in july_rows(y, 10, "n")]
    n21 = [r for y in range(2023, 2026) for r in july_rows(y, 10, "h")]
    nrt = [[49.0, -56.0, "2026-11-03", "1200", "S", "n", 0, 5.0, "D", "X", "1"]]
    write(raw, "modis", modis)
    write(raw, "viirs_noaa20", n20, nrt)
    write(raw, "viirs_noaa21", n21)
    if with_snpp:
        write(raw, "viirs_snpp", [r for y in range(2012, 2026) for r in july_rows(y, 10, "n")])
    return raw


def run(tmp_path, monkeypatch, with_snpp):
    raw, out = build(tmp_path, with_snpp), tmp_path / "out"
    monkeypatch.setattr("sys.argv", ["x", "--raw", str(raw), "--out", str(out), "--publish", str(tmp_path / "none")])
    bh.main()
    return out, json.loads((out / "summary.json").read_text()), pd.read_csv(out / "monthly_harmonized.csv")


@pytest.mark.parametrize("with_snpp", [False, True])
def test_known_answer(tmp_path, monkeypatch, with_snpp):
    out, summary, m = run(tmp_path, monkeypatch, with_snpp)
    cells = summary["ratios"]["cells"]
    assert cells["k"] == pytest.approx(2.0)
    assert cells["cv_median_pct_err"] == pytest.approx(0, abs=1e-6)
    assert summary["series_rules"]["has_snpp"] is with_snpp
    assert len(summary["series_rules"]["fit_years"]) == (14 if with_snpp else 8)
    # a MODIS-only July is scaled by k; a VIIRS-era July is the observed count
    old = m[m.month == "2005-07"].iloc[0]
    assert old.modis_cells == 5 and old.harmonized_cells == pytest.approx(10.0)
    new = m[m.month == "2020-07"].iloc[0]
    assert new.harmonized_cells == 10 and new.harmonized_source == "VIIRS NOAA-20"
    if with_snpp:
        assert m[m.month == "2014-07"].iloc[0].harmonized_source == "VIIRS Suomi NPP"
    for f in ("monthly_harmonized.csv", "monthly_baseline.csv", "hotspots_clean.csv", "summary.json", "validation.png"):
        assert (out / f).exists()


def test_partial_month_is_flagged(tmp_path, monkeypatch):
    _, _, m = run(tmp_path, monkeypatch, False)
    last = m.iloc[-1]
    assert last.month == "2026-11" and bool(last.is_partial)
    assert m.is_partial.sum() == 1


def test_publish_folder_receives_site_files(tmp_path, monkeypatch):
    raw = build(tmp_path, False)
    pub = tmp_path / "app_data"
    pub.mkdir()
    monkeypatch.setattr("sys.argv", ["x", "--raw", str(raw), "--out", str(tmp_path / "o"), "--publish", str(pub)])
    bh.main()
    assert (pub / "summary.json").exists() and (pub / "hotspots_clean.csv").exists()


def test_missing_required_sensor_stops_with_a_clear_error(tmp_path, monkeypatch):
    raw = build(tmp_path, False)
    import shutil
    shutil.rmtree(raw / "viirs_noaa20")
    monkeypatch.setattr("sys.argv", ["x", "--raw", str(raw), "--out", str(tmp_path / "o"), "--publish", "none"])
    with pytest.raises(SystemExit):
        bh.main()
