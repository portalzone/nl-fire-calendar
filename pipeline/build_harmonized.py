#!/usr/bin/env python3
"""
NL Fire Calendar: harmonize NASA FIRMS MODIS and VIIRS hotspots.

Run from the repo root:
    python pipeline/build_harmonized.py

Reads   data/raw/modis, data/raw/viirs_noaa20, data/raw/viirs_noaa21
        (fire_archive_*.csv + fire_nrt_*.csv from the FIRMS Archive Download)
Writes  data/processed/ (and copies the site files to app/data/ if that folder exists):
    monthly_harmonized.csv   one row per month, raw counts per sensor + harmonized series
    monthly_baseline.csv     per calendar month: median, quartiles, max over past years
    hotspots_clean.csv       cleaned individual detections (for the CSV download feature)
    summary.json             filters applied, fitted ratios, validation, month-to-date comparison
    validation.png           MODIS vs VIIRS season totals + raw vs harmonized series

Method in one paragraph
-----------------------
1. Clean: keep presumed vegetation fires (type 0, or NRT rows that carry no type),
   drop low-confidence detections (MODIS < 30, VIIRS 'l'), drop duplicates.
2. Count per month for each sensor, two ways: raw hotspots (pixels) and "fire cells"
   (unique 0.1 degree cell + day), which is less sensitive to VIIRS's finer pixels.
3. On the years where MODIS and VIIRS NOAA-20 both ran a full season (2018-2025), fit one
   ratio k = sum(VIIRS May-Sep totals) / sum(MODIS May-Sep totals). Season totals are used
   because provincial counts are low and month-by-month ratios would be noisy.
4. Validate with leave-one-year-out: predict each year's VIIRS total from MODIS using a
   ratio fitted on the other years.
5. Harmonized series = MODIS x k before NOAA-20 starts (2018-04), NOAA-20 observed after.
   NOAA-21 (2023-03 on) is kept as a cross-check only, so no fire is counted twice.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- configuration
SOURCES = {"modis": "modis", "n20": "viirs_noaa20", "n21": "viirs_noaa21"}
METRICS = ("hotspots", "cells")
PRIMARY = "cells"   # metric used for baseline, anomalies and month-to-date (best validated)
SEASON_MONTHS = [5, 6, 7, 8, 9]
OVERLAP_YEARS = list(range(2018, 2026))          # full MODIS + NOAA-20 seasons
N21_CHECK_YEARS = [2023, 2024, 2025]             # full NOAA-20 + NOAA-21 seasons
SERIES_START = pd.Period("2000-11", "M")
SERIES_END = pd.Period("2026-11", "M")
COVERAGE_END = pd.Timestamp("2026-11-07")        # end date used in the FIRMS request
VIIRS_START = pd.Period("2018-04", "M")          # NOAA-20 first month
AQUA_START = pd.Period("2002-07", "M")           # before this MODIS is Terra only
CELL_DEG = 0.1
MODIS_MIN_CONF = 30


# ---------------------------------------------------------------- loading + cleaning
def load_source(raw: Path, key: str, folder: str):
    d = raw / folder
    parts = {"archive": [], "nrt": []}
    for origin in parts:
        for f in sorted(d.glob(f"fire_{origin}_*.csv")):
            df = pd.read_csv(f, dtype={"acq_time": str, "confidence": str})
            df["origin"] = origin
            parts[origin].append(df)
    if not parts["archive"]:
        sys.exit(f"No fire_archive_*.csv found in {d}. Unzip the FIRMS download there.")

    df = pd.concat(parts["archive"] + parts["nrt"], ignore_index=True)
    df["date"] = pd.to_datetime(df["acq_date"])
    info = {"rows_archive": int(sum(len(p) for p in parts["archive"])),
            "rows_nrt": int(sum(len(p) for p in parts["nrt"]))}

    arch_last = df.loc[df.origin == "archive", "date"].max()
    nrt_first = df.loc[df.origin == "nrt", "date"].min() if info["rows_nrt"] else pd.NaT
    info["archive_last_date"] = str(arch_last.date())
    info["nrt_first_date"] = None if pd.isna(nrt_first) else str(nrt_first.date())
    info["gap_days_between_archive_and_nrt"] = (
        None if pd.isna(nrt_first) else int((nrt_first - arch_last).days))

    n = len(df)
    df = df.drop_duplicates(["latitude", "longitude", "acq_date", "acq_time", "satellite"])
    info["duplicates_removed"] = int(n - len(df))

    # type: 0 presumed vegetation fire, 1 volcano, 2 other static land source, 3 offshore.
    # NRT files have no type column, so those rows are kept.
    typ = pd.to_numeric(df["type"], errors="coerce")
    bad_type = typ.notna() & (typ != 0)
    info["removed_non_vegetation"] = {str(int(k)): int(v)
                                      for k, v in typ[bad_type].value_counts().items()}
    df = df[~bad_type]

    conf = df["confidence"].astype(str).str.strip().str.lower()
    if key == "modis":
        keep = pd.to_numeric(conf, errors="coerce") >= MODIS_MIN_CONF
    else:
        keep = conf.isin(["n", "nominal", "h", "high"])
    info["removed_low_confidence"] = int((~keep).sum())
    df = df[keep].copy()

    df["month"] = df["date"].dt.to_period("M")
    df = df[(df.month >= SERIES_START) & (df.month <= SERIES_END)]
    df["ci"] = np.floor(df["latitude"] / CELL_DEG).astype(int)
    df["cj"] = np.floor(df["longitude"] / CELL_DEG).astype(int)
    df["source"] = key
    info["rows_kept"] = int(len(df))
    info["first_date"] = str(df["date"].min().date())
    info["last_date"] = str(df["date"].max().date())
    return df, info


def monthly_counts(df: pd.DataFrame, idx: pd.PeriodIndex) -> pd.DataFrame:
    hot = df.groupby("month").size()
    cells = df.drop_duplicates(["ci", "cj", "date"]).groupby("month").size()
    return (pd.DataFrame({"hotspots": hot, "cells": cells})
            .reindex(idx).fillna(0).astype(int))


def season_totals(s: pd.Series) -> pd.Series:
    s = s[s.index.month.isin(SEASON_MONTHS)]
    return s.groupby(s.index.year).sum()


# ---------------------------------------------------------------- harmonization
def fit_ratio(modis_s: pd.Series, viirs_s: pd.Series, years: list[int]):
    m = modis_s.reindex(years).astype(float)
    v = viirs_s.reindex(years).astype(float)
    if m.sum() == 0:
        sys.exit("MODIS season total is zero over the overlap years; check the data.")
    k = v.sum() / m.sum()
    rows = []
    for y in years:
        others = [x for x in years if x != y]
        k_y = v[others].sum() / m[others].sum()
        pred = k_y * m[y]
        rows.append({"year": y, "modis": m[y], "viirs": v[y], "predicted": pred,
                     "abs_err": abs(pred - v[y]),
                     "pct_err": abs(pred - v[y]) / v[y] * 100 if v[y] > 0 else np.nan})
    cv = pd.DataFrame(rows)
    stats = {"k": k, "n_years": len(years), "years": years,
             "pearson_r": m.corr(v), "spearman_rho": m.corr(v, method="spearman"),
             "cv_median_pct_err": cv["pct_err"].median(),
             "cv_mean_abs_err": cv["abs_err"].mean(),
             "leave_one_year_out": cv.round(2).to_dict(orient="records")}
    return k, stats


def month_to_date(daily: pd.Series, end: pd.Timestamp) -> dict:
    """Compare the (partial) latest month with the same days in earlier years."""
    M, d = end.month, end.day
    vals = {}
    for y in range(2000, end.year + 1):
        if pd.Period(year=y, month=M, freq="M") < AQUA_START:
            continue
        s, e = pd.Timestamp(y, M, 1), pd.Timestamp(y, M, d)
        if s < daily.index[0]:
            continue
        vals[y] = float(daily.loc[s:e].sum())
    cur = vals.pop(end.year, None)
    past = pd.Series(vals)
    return {"month": f"{end.year}-{M:02d}", "through_day": d, "current": cur,
            "historical_median": float(past.median()) if len(past) else None,
            "historical_mean": float(past.mean()) if len(past) else None,
            "n_past_years": int(len(past)),
            "share_of_past_years_at_or_below": (float((past <= cur).mean())
                                                if len(past) and cur is not None else None)}


def make_figure(path: Path, modis_s, n20_s, harm_s, stats, k):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed; skipping validation.png (pip install matplotlib)")
        return
    yrs = stats["years"]
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    x, y = modis_s.reindex(yrs), n20_s.reindex(yrs)
    ax[0].scatter(x, y)
    for yr in yrs:
        ax[0].annotate(str(yr), (x[yr], y[yr]), textcoords="offset points", xytext=(4, 4), fontsize=8)
    xs = np.linspace(0, max(float(x.max()), 1), 50)
    ax[0].plot(xs, k * xs, "--", label=f"VIIRS = {k:.2f} x MODIS")
    ax[0].set(xlabel="MODIS May-Sep hotspots", ylabel="VIIRS NOAA-20 May-Sep hotspots",
              title=f"Overlap years (r = {stats['pearson_r']:.2f})")
    ax[0].legend()
    ax[1].plot(modis_s.index, modis_s.values, marker="o", ms=3, label="MODIS raw")
    ax[1].plot(n20_s.index[n20_s > 0], n20_s[n20_s > 0], marker="o", ms=3, label="VIIRS NOAA-20 raw")
    ax[1].plot(harm_s.index, harm_s.values, marker="o", ms=3, label="Harmonized")
    ax[1].set(xlabel="Year", ylabel="May-Sep hotspots", title="Before and after harmonization")
    ax[1].legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _json(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if np.isnan(o) else float(o)
    return str(o)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--publish", default="app/data", help="copy site files here if the folder exists")
    a = ap.parse_args()
    raw, out = Path(a.raw), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    dfs, infos = {}, {}
    for key, folder in SOURCES.items():
        dfs[key], infos[key] = load_source(raw, key, folder)
        i = infos[key]
        print(f"[{key}] archive {i['rows_archive']} + nrt {i['rows_nrt']} rows | "
              f"dups {i['duplicates_removed']} | non-vegetation removed {i['removed_non_vegetation']} | "
              f"low confidence removed {i['removed_low_confidence']} | kept {i['rows_kept']} "
              f"({i['first_date']} to {i['last_date']})")
        g = i["gap_days_between_archive_and_nrt"]
        if g is not None and g > 1:
            print(f"   WARNING: {g} day gap between end of archive ({i['archive_last_date']}) and "
                  f"start of NRT ({i['nrt_first_date']}). Months in the gap may be under-counted.")

    idx = pd.period_range(SERIES_START, SERIES_END, freq="M")
    counts = {k: monthly_counts(df, idx) for k, df in dfs.items()}

    tbl = pd.DataFrame(index=idx)
    for k in SOURCES:
        for met in METRICS:
            tbl[f"{k}_{met}"] = counts[k][met]

    # ---- fit ratios and validate
    ratios, harm = {}, {}
    for met in METRICS:
        mod_s = season_totals(tbl[f"modis_{met}"])
        n20_s = season_totals(tbl[f"n20_{met}"])
        k, stats = fit_ratio(mod_s, n20_s, OVERLAP_YEARS)
        ratios[met] = stats
        use_viirs = idx >= VIIRS_START
        tbl[f"harmonized_{met}"] = np.where(use_viirs, tbl[f"n20_{met}"], tbl[f"modis_{met}"] * k).round(2)
        harm[met] = (mod_s, n20_s, season_totals(tbl[f"harmonized_{met}"]), k, stats)
        print(f"[{met}] ratio VIIRS/MODIS = {k:.3f} | r = {stats['pearson_r']:.2f} | "
              f"spearman = {stats['spearman_rho']:.2f} | leave-one-year-out median error = "
              f"{stats['cv_median_pct_err']:.0f}% over {stats['n_years']} seasons")

    tbl["harmonized_source"] = np.where(idx >= VIIRS_START, "VIIRS NOAA-20", "MODIS (scaled)")
    tbl["terra_only"] = idx < AQUA_START
    partial = COVERAGE_END.day < COVERAGE_END.days_in_month
    tbl["is_partial"] = (idx == COVERAGE_END.to_period("M")) if partial else False

    # ---- baseline (complete months, Terra + Aqua era only) and anomalies
    last_complete = COVERAGE_END.to_period("M") - (1 if partial else 0)
    base_rows = tbl[(tbl.index >= AQUA_START) & (tbl.index <= last_complete)]
    g = base_rows.groupby(base_rows.index.month)[f"harmonized_{PRIMARY}"]
    baseline = pd.DataFrame({"n_years": g.count(), "median": g.median(), "mean": g.mean().round(2),
                             "p25": g.quantile(0.25), "p75": g.quantile(0.75), "max": g.max()})
    baseline.index.name = "month_num"
    tbl["baseline_median"] = [baseline.loc[p.month, "median"] for p in idx]
    tbl["anomaly"] = (tbl[f"harmonized_{PRIMARY}"] - tbl["baseline_median"]).round(2)
    dist = {m: base_rows.loc[base_rows.index.month == m, f"harmonized_{PRIMARY}"].values for m in range(1, 13)}
    tbl["percentile"] = [round(float((dist[p.month] <= v).mean() * 100), 1)
                         for p, v in zip(idx, tbl[f"harmonized_{PRIMARY}"])]

    # ---- month-to-date comparison for the latest month
    dix = pd.date_range("2000-11-01", COVERAGE_END)
    def _daily(df):
        d = df if PRIMARY == "hotspots" else df.drop_duplicates(["ci", "cj", "date"])
        return d.groupby("date").size().reindex(dix).fillna(0)
    mod_d, n20_d = _daily(dfs["modis"]), _daily(dfs["n20"])
    daily = pd.Series(np.where(dix >= VIIRS_START.start_time, n20_d, mod_d * harm[PRIMARY][3]), index=dix)
    mtd = month_to_date(daily, COVERAGE_END)

    # ---- NOAA-21 cross-check (never added to the series)
    n21_s, n20_s2 = season_totals(tbl["n21_hotspots"]), season_totals(tbl["n20_hotspots"])
    n21_chk = {"years": N21_CHECK_YEARS,
               "n21": n21_s.reindex(N21_CHECK_YEARS).tolist(),
               "n20": n20_s2.reindex(N21_CHECK_YEARS).tolist(),
               "ratio_n21_over_n20": float(n21_s.reindex(N21_CHECK_YEARS).sum()
                                           / max(n20_s2.reindex(N21_CHECK_YEARS).sum(), 1))}
    print(f"[cross-check] NOAA-21 / NOAA-20 May-Sep totals {N21_CHECK_YEARS}: "
          f"{n21_chk['n21']} vs {n21_chk['n20']} (ratio {n21_chk['ratio_n21_over_n20']:.2f})")
    print(f"[month-to-date] {mtd}")

    # ---- write outputs
    t = tbl.copy()
    t.insert(0, "month", t.index.astype(str))
    t.insert(1, "year", t.index.year)
    t.insert(2, "month_num", t.index.month)
    t.to_csv(out / "monthly_harmonized.csv", index=False)
    baseline.reset_index().to_csv(out / "monthly_baseline.csv", index=False)

    cols = ["date", "acq_time", "latitude", "longitude", "source", "satellite",
            "instrument", "confidence", "frp", "daynight"]
    hs = pd.concat([d[cols] for d in dfs.values()]).sort_values(["date", "acq_time"])
    hs["date"] = hs["date"].dt.strftime("%Y-%m-%d")
    hs.to_csv(out / "hotspots_clean.csv", index=False)

    summary = {"area": "Newfoundland and Labrador", "coverage_end": str(COVERAGE_END.date()),
               "filters": {"modis_min_confidence": MODIS_MIN_CONF, "viirs_confidence": "nominal or high",
                           "type": "0 (presumed vegetation fire); NRT rows have no type and are kept",
                           "fire_cell_size_deg": CELL_DEG},
               "primary_metric": PRIMARY, "sources": infos, "ratios": ratios, "month_to_date": mtd, "noaa21_cross_check": n21_chk,
               "notes": ["Nov 2000 to Jun 2002 is MODIS Terra only (Aqua starts 2002-07); excluded from baseline.",
                         "Latest month is partial; compare with month_to_date, not the monthly baseline.",
                         "Ratio fitted on May-Sep season totals over " + f"{OVERLAP_YEARS[0]}-{OVERLAP_YEARS[-1]}."]}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=_json))

    mod_s, n20_s, harm_s, k, stats = harm[PRIMARY]
    make_figure(out / "validation.png", mod_s, n20_s, harm_s, stats, k)

    pub = Path(a.publish)
    if pub.exists():
        for f in ["monthly_harmonized.csv", "monthly_baseline.csv", "hotspots_clean.csv",
                  "summary.json", "validation.png"]:
            if (out / f).exists():
                shutil.copy(out / f, pub / f)
        print(f"Copied site files to {pub}/")
    print(f"Done. Outputs in {out}/")


if __name__ == "__main__":
    main()
