#!/usr/bin/env python3
"""
Monthly carbon monoxide (CO) for the island of Newfoundland, from CSA MOPITT.

Run from the repo root, after pipeline/download_mopitt.py:
    python pipeline/build_co.py

Input:   data/raw/csa/MOP02J-YYYYMMDD-*.csv   (island rows only, one file per day)
Output:  data/processed/co_daily.csv
         data/processed/co_monthly.csv
         data/processed/co_monthly.json   (also copied to app/data/ if that folder exists)

Columns used:
    COTotalColumn          CO in the whole air column, molecules/cm^2 (shown here in 1e18)
    COMixingRatio surface  CO near the ground, parts per billion by volume (ppbv)

Rules:
  - A reading is valid only if the value is above 0 and finite. Fill values (for
    example -9999) and blanks are dropped.
  - Rows outside the island box are dropped (the downloader already did this).
  - A month needs at least MIN_DAYS days with data to get a value; otherwise it is
    left empty, so a short month is not shown as if it were a full month.
  - One file per date. If a date has two files (for example a browser copy named
    "... (1).csv"), the file with the shortest name is used and a warning is printed.
  - Each day counts once: the monthly value is the plain average of the daily averages.
    Days are not weighted by how many readings they hold.
"""
import argparse
import glob
import json
import os
import re
import shutil
import sys

import numpy as np
import pandas as pd

BOX = {"lat_min": 46.4, "lat_max": 51.9, "lon_min": -59.7, "lon_max": -52.4}
MIN_DAYS = 15
COLS = ["lat", "lon", "co_total", "co_surface"]
DATE_RE = re.compile(r"MOP02J-(\d{4})(\d{2})(\d{2})")


def read_day(path):
    """Return a DataFrame of valid island readings for one daily file (may be empty)."""
    try:
        # Read every line as text first. A download that stopped mid-line can leave a short
        # line (for example "-8"); that line is skipped with a warning instead of stopping the run.
        raw = pd.read_csv(path, comment="#", header=None, dtype=str, skip_blank_lines=True,
                          sep="\t", names=["line"])
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=COLS)
    parts = raw["line"].str.split(",", expand=True)
    short = int(parts.reindex(columns=range(4)).isna().any(axis=1).sum()) if len(parts) else 0
    if short:
        print(f"WARNING: {os.path.basename(str(path))}: skipped {short} incomplete line(s)")
    df = parts.reindex(columns=range(4))
    df.columns = COLS
    df = df.apply(pd.to_numeric, errors="coerce")
    df = df.dropna(subset=["lat", "lon"])
    df = df[(df.lat >= BOX["lat_min"]) & (df.lat <= BOX["lat_max"]) &
            (df.lon >= BOX["lon_min"]) & (df.lon <= BOX["lon_max"])]
    return df


def valid(series):
    s = pd.to_numeric(series, errors="coerce")
    return s.where(np.isfinite(s) & (s > 0))


def one_file_per_date(files):
    """Keep one file for each date. Files without a date in the name are ignored."""
    best = {}
    for f in files:
        m = DATE_RE.search(os.path.basename(f))
        if not m:
            continue
        key = m.groups()
        if key in best:
            print(f"WARNING: two files for {'-'.join(key)}: using the shorter name, ignoring the other")
            if len(os.path.basename(f)) < len(os.path.basename(best[key])):
                best[key] = f
        else:
            best[key] = f
    return [best[k] for k in sorted(best)]


def build_daily(folder):
    files = sorted(glob.glob(os.path.join(folder, "MOP02J-*.csv")))
    if not files:
        sys.exit(f"No MOPITT files found in {folder}. Run pipeline/download_mopitt.py first.")
    files = one_file_per_date(files)
    rows = []
    for f in files:
        m = DATE_RE.search(os.path.basename(f))
        y, mo, d = (int(x) for x in m.groups())
        df = read_day(f)
        tc, sf = valid(df.co_total), valid(df.co_surface)
        rows.append({
            "date": f"{y:04d}-{mo:02d}-{d:02d}", "year": y, "month": mo,
            "n_rows": len(df),
            "n_total": int(tc.notna().sum()), "n_surface": int(sf.notna().sum()),
            "co_total_1e18": tc.mean() / 1e18 if tc.notna().any() else np.nan,
            "co_surface_ppbv": sf.mean() if sf.notna().any() else np.nan,
        })
    return pd.DataFrame(rows)


def build_monthly(daily, min_days=MIN_DAYS):
    out = []
    for (y, m), g in daily.groupby(["year", "month"]):
        tot = g.dropna(subset=["co_total_1e18"])
        sur = g.dropna(subset=["co_surface_ppbv"])
        def dmean(frame, col):
            return float(frame[col].mean()) if len(frame) else np.nan
        out.append({
            "year": y, "month": m, "month_key": f"{y:04d}-{m:02d}",
            "days_with_data": int(len(tot)),
            "readings": int(g.n_total.sum()),
            "co_total_1e18": dmean(tot, "co_total_1e18") if len(tot) >= min_days else np.nan,
            "co_surface_ppbv": dmean(sur, "co_surface_ppbv") if len(sur) >= min_days else np.nan,
            "enough_days": bool(len(tot) >= min_days),
        })
    return pd.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw/csa")
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--publish", default="app/data")
    ap.add_argument("--min-days", type=int, default=MIN_DAYS)
    a = ap.parse_args()

    daily = build_daily(a.raw)
    monthly = build_monthly(daily, a.min_days)
    os.makedirs(a.out, exist_ok=True)
    daily.round(4).to_csv(os.path.join(a.out, "co_daily.csv"), index=False)
    monthly.round(4).to_csv(os.path.join(a.out, "co_monthly.csv"), index=False)
    payload = {
        "source": "CSA MOPITT Level 2 (MOP02J), island of Newfoundland box",
        "box": BOX, "min_days": a.min_days, "averaging": "plain mean of daily means",
        "units": {"co_total_1e18": "1e18 molecules/cm^2", "co_surface_ppbv": "ppbv"},
        "months": json.loads(monthly.round(4).to_json(orient="records")),
    }
    jpath = os.path.join(a.out, "co_monthly.json")
    with open(jpath, "w") as f:
        json.dump(payload, f, allow_nan=False, default=lambda o: None)
    if os.path.isdir(a.publish):
        shutil.copy(jpath, os.path.join(a.publish, "co_monthly.json"))
        print("Copied co_monthly.json to", a.publish)
    print(f"{len(daily)} daily files, {int((daily.n_total > 0).sum())} with island readings, "
          f"{len(monthly)} months, {int(monthly.enough_days.sum())} with at least {a.min_days} days")
    print(monthly[["month_key", "days_with_data", "readings", "co_total_1e18", "co_surface_ppbv"]]
          .to_string(index=False))


if __name__ == "__main__":
    main()
