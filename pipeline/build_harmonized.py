#!/usr/bin/env python3
"""
Newfoundland and Labrador fire calendar: merge NASA FIRMS MODIS and VIIRS hotspots.

Run from the repo root:
    python pipeline/build_harmonized.py

Input (FIRMS Archive Download, CSV, one folder per sensor):
    data/raw/modis/           fire_archive_*.csv + fire_nrt_*.csv
    data/raw/viirs_snpp/      optional, VIIRS Suomi NPP (Jan 2012 to Nov 2026)
    data/raw/viirs_noaa20/    VIIRS NOAA-20 (Apr 2018 on)
    data/raw/viirs_noaa21/    VIIRS NOAA-21 (Mar 2023 on), used as a check only

Output in data/processed/ (also copied to app/data/ if that folder exists):
    monthly_harmonized.csv   one row per month: counts per sensor, merged series, baseline, anomaly
    monthly_baseline.csv     median, quartiles and max per calendar month, for each era
    hotspots_clean.csv       cleaned individual detections (used by the CSV download)
    summary.json             filters, ratio, errors, checks (read by the web app)
    validation.png           MODIS against VIIRS season totals, and the series before/after

Method
------
1. Clean. Keep detections with type 0 (presumed vegetation fire). Near-real-time rows
   have no type column and are kept. Drop low confidence (MODIS below 30, VIIRS 'l').
2. Count per month, two ways: "hotspots" (every detection) and "cells" (each 0.1 degree
   map cell with a detection on a day counts once). Cells are the main metric because
   VIIRS pixels are smaller, so one fire makes many more VIIRS hotspots than MODIS hotspots.
3. VIIRS reference series: Suomi NPP from Feb 2012 until Mar 2018 (if its files exist),
   NOAA-20 from Apr 2018.
4. Fit one ratio k = sum(VIIRS May-Sep totals) / sum(MODIS May-Sep totals) over the years
   2012-2025 (or 2018-2025 without Suomi NPP). Season totals are used because monthly
   counts in the province are small.
5. Merged series: MODIS x k before the first VIIRS month, VIIRS reference after.
   NOAA-21 is never added, so no fire is counted twice.
6. Baseline and anomaly: each month is compared with the same calendar month in years of the
   SAME era (MODIS-scaled years with MODIS-scaled years, VIIRS years with VIIRS years).
   A ratio cannot turn a MODIS zero into a VIIRS 1, so mixing eras would make VIIRS-era
   months look unusually active.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- settings
SOURCES = {"modis": "modis", "snpp": "viirs_snpp", "n20": "viirs_noaa20", "n21": "viirs_noaa21"}
OPTIONAL = {"snpp"}
METRICS = ("hotspots", "cells")
PRIMARY = "cells"
SEASON_MONTHS = [5, 6, 7, 8, 9]
LAST_FIT_YEAR = 2025
SERIES_START = pd.Period("2000-11", "M")
SERIES_END = pd.Period("2026-11", "M")
COVERAGE_END = pd.Timestamp("2026-11-07")        # end date used in the FIRMS requests
SNPP_START = pd.Period("2012-02", "M")           # first full Suomi NPP month
N20_START = pd.Period("2018-04", "M")            # first NOAA-20 month
AQUA_START = pd.Period("2002-07", "M")           # before this MODIS is Terra only
CELL_DEG = 0.1
MODIS_MIN_CONF = 30


# ---------------------------------------------------------------- load and clean
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
    info["archive_last_detection"] = str(arch_last.date())
    info["nrt_first_detection"] = None if pd.isna(nrt_first) else str(nrt_first.date())

    n = len(df)
    df = df.drop_duplicates(["latitude", "longitude", "acq_date", "acq_time", "satellite"])
    info["duplicates_removed"] = int(n - len(df))

    # type: 0 vegetation fire, 1 volcano, 2 other static land source, 3 offshore.
    # NRT files have no type column, so those rows are kept (they cannot be checked).
    typ = pd.to_numeric(df["type"], errors="coerce")
    bad_type = typ.notna() & (typ != 0)
    info["removed_non_vegetation"] = {str(int(k)): int(v) for k, v in typ[bad_type].value_counts().items()}
    info["rows_without_type_kept"] = int(typ.isna().sum())
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
    return pd.DataFrame({"hotspots": hot, "cells": cells}).reindex(idx).fillna(0).astype(int)


def season_totals(s: pd.Series) -> pd.Series:
    s = s[s.index.month.isin(SEASON_MONTHS)]
    return s.groupby(s.index.year).sum()


# ---------------------------------------------------------------- ratio and validation
def fit_ratio(modis_m: pd.Series, ref_m: pd.Series, years: list[int]):
    """k = VIIRS season total / MODIS season total, with leave-one-year-out checks."""
    ms, vs = season_totals(modis_m).reindex(years).astype(float), season_totals(ref_m).reindex(years).astype(float)
    if ms.sum() == 0:
        sys.exit("MODIS season total is zero over the fit years; check the data.")
    k = vs.sum() / ms.sum()
    rows, month_errs = [], []
    for y in years:
        others = [x for x in years if x != y]
        k_y = vs[others].sum() / ms[others].sum()
        pred = k_y * ms[y]
        rows.append({"year": y, "modis": ms[y], "viirs": vs[y], "predicted": pred,
                     "abs_err": abs(pred - vs[y]),
                     "pct_err": abs(pred - vs[y]) / vs[y] * 100 if vs[y] > 0 else np.nan})
        for m in SEASON_MONTHS:                       # month-level error for the same held-out year
            p = pd.Period(year=y, month=m, freq="M")
            if ref_m[p] > 0:
                month_errs.append(abs(k_y * modis_m[p] - ref_m[p]) / ref_m[p] * 100)
    cv = pd.DataFrame(rows)
    yearly = {int(y): float(vs[y] / ms[y]) for y in years if ms[y] > 0}
    stats = {"k": k, "n_years": len(years), "years": years,
             "pearson_r": ms.corr(vs), "spearman_rho": ms.corr(vs, method="spearman"),
             "cv_median_pct_err": cv["pct_err"].median(),
             "cv_mean_abs_err": cv["abs_err"].mean(),
             "monthly_cv_median_pct_err": float(np.median(month_errs)) if month_errs else None,
             "monthly_cv_n_months": len(month_errs),
             "yearly_ratios": yearly,
             "yearly_ratio_min": min(yearly.values()), "yearly_ratio_max": max(yearly.values()),
             "leave_one_year_out": cv.round(2).to_dict(orient="records")}
    return k, stats


def quantile_sorted(vals):
    return np.sort(np.asarray(vals, dtype=float))


def month_to_date(daily: pd.Series, end: pd.Timestamp, first_period: pd.Period) -> dict:
    """Latest (partial) month against the same days in earlier years of the same era."""
    M, d = end.month, end.day
    vals = {}
    for y in range(2000, end.year + 1):
        if pd.Period(year=y, month=M, freq="M") < first_period:
            continue
        s = pd.Timestamp(y, M, 1)
        e = pd.Timestamp(y, M, min(d, s.days_in_month))
        if s < daily.index[0]:
            continue
        vals[y] = float(daily.loc[s:e].sum())
    cur = vals.pop(end.year, None)
    past = pd.Series(vals, dtype=float)
    return {"month": f"{end.year}-{M:02d}", "through_day": d, "current": cur,
            "same_era_years": int(len(past)),
            "historical_median": float(past.median()) if len(past) else None,
            "years_fewer": int((past < cur).sum()) if len(past) and cur is not None else None,
            "years_equal": int((past == cur).sum()) if len(past) and cur is not None else None,
            "years_more": int((past > cur).sum()) if len(past) and cur is not None else None}


def make_figure(path: Path, modis_s, ref_s, harm_s, stats, k, label):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed; skipping validation.png")
        return
    yrs = stats["years"]
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    x, y = modis_s.reindex(yrs), ref_s.reindex(yrs)
    ax[0].scatter(x, y)
    for yr in yrs:
        ax[0].annotate(str(yr), (x[yr], y[yr]), textcoords="offset points", xytext=(4, 4), fontsize=8)
    xs = np.linspace(0, max(float(x.max()), 1), 50)
    ax[0].plot(xs, k * xs, "--", label=f"VIIRS = {k:.2f} x MODIS")
    ax[0].set(xlabel=f"MODIS May-Sep {label}", ylabel=f"VIIRS May-Sep {label}",
              title=f"Fit years {yrs[0]}-{yrs[-1]} (r = {stats['pearson_r']:.3f})")
    ax[0].legend()
    ax[1].plot(modis_s.index, modis_s.values, marker="o", ms=3, label="MODIS raw")
    ax[1].plot(ref_s.index[ref_s > 0], ref_s[ref_s > 0], marker="o", ms=3, label="VIIRS raw")
    ax[1].plot(harm_s.index, harm_s.values, marker="o", ms=3, label="Merged series")
    ax[1].set(xlabel="Year", ylabel=f"May-Sep {label}", title="Before and after merging")
    ax[1].legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _json(o):
    if isinstance(o, np.integer):
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
        if key in OPTIONAL and not (raw / folder).exists():
            print(f"[{key}] folder {raw / folder} not found: continuing without it")
            continue
        dfs[key], infos[key] = load_source(raw, key, folder)
        i = infos[key]
        print(f"[{key}] archive {i['rows_archive']} + nrt {i['rows_nrt']} rows | dups {i['duplicates_removed']} | "
              f"non-vegetation removed {i['removed_non_vegetation']} | low confidence removed "
              f"{i['removed_low_confidence']} | kept {i['rows_kept']} ({i['first_date']} to {i['last_date']})")

    has_snpp = "snpp" in dfs
    viirs_first = SNPP_START if has_snpp else N20_START
    fit_years = list(range(viirs_first.year if has_snpp else 2018, LAST_FIT_YEAR + 1))

    idx = pd.period_range(SERIES_START, SERIES_END, freq="M")
    counts = {k: monthly_counts(df, idx) for k, df in dfs.items()}
    tbl = pd.DataFrame(index=idx)
    for k in dfs:
        for met in METRICS:
            tbl[f"{k}_{met}"] = counts[k][met]

    is_n20 = np.asarray(idx >= N20_START)
    is_snpp = np.asarray((idx >= SNPP_START) & (idx < N20_START)) if has_snpp else np.zeros(len(idx), bool)
    ratios, harm, ref_series = {}, {}, {}
    for met in METRICS:
        n20 = tbl[f"n20_{met}"].to_numpy()
        snpp = tbl[f"snpp_{met}"].to_numpy() if has_snpp else np.zeros(len(idx))
        ref = pd.Series(np.where(is_n20, n20, np.where(is_snpp, snpp, 0)), index=idx)
        k, stats = fit_ratio(tbl[f"modis_{met}"], ref, fit_years)
        ratios[met] = stats
        tbl[f"harmonized_{met}"] = np.where(is_n20 | is_snpp, ref.to_numpy(), tbl[f"modis_{met}"].to_numpy() * k).round(2)
        harm[met] = (season_totals(tbl[f"modis_{met}"]), season_totals(ref),
                     season_totals(tbl[f"harmonized_{met}"]), k, stats)
        mce = stats["monthly_cv_median_pct_err"]
        print(f"[{met}] k = {k:.3f} | yearly ratios {stats['yearly_ratio_min']:.2f} to {stats['yearly_ratio_max']:.2f} | "
              f"r = {stats['pearson_r']:.3f} | season error (leave-one-year-out) {stats['cv_median_pct_err']:.0f}% | "
              f"month error {mce:.0f}% over {stats['monthly_cv_n_months']} months | {len(fit_years)} seasons")

    tbl["harmonized_source"] = np.where(is_n20, "VIIRS NOAA-20", np.where(is_snpp, "VIIRS Suomi NPP", "MODIS (scaled)"))
    tbl["era"] = np.where(np.asarray(idx >= viirs_first), "VIIRS", "MODIS")
    tbl["terra_only"] = np.asarray(idx < AQUA_START)
    partial = COVERAGE_END.day < COVERAGE_END.days_in_month
    tbl["is_partial"] = np.asarray(idx == COVERAGE_END.to_period("M")) if partial else False

    # ---- baseline per era; each month is compared only with years of its own era
    last_complete = COVERAGE_END.to_period("M") - (1 if partial else 0)
    P = f"harmonized_{PRIMARY}"
    ok = np.asarray((idx >= AQUA_START) & (idx <= last_complete))
    months = np.asarray(idx.month)
    dist, base_rows = {}, []
    for era in ("MODIS", "VIIRS"):
        for m in range(1, 13):
            v = tbl.loc[ok & (months == m) & (tbl["era"].to_numpy() == era), P].to_numpy(dtype=float)
            dist[(era, m)] = np.sort(v)
            s = dist[(era, m)]
            base_rows.append({"era": era, "month_num": m, "n_years": len(s),
                              "median": float(np.median(s)) if len(s) else np.nan,
                              "p25": float(np.quantile(s, .25)) if len(s) else np.nan,
                              "p75": float(np.quantile(s, .75)) if len(s) else np.nan,
                              "max": float(s.max()) if len(s) else np.nan})
    baseline = pd.DataFrame(base_rows)
    med, below, n_base = [], [], []
    for p, v, era in zip(idx, tbl[P], tbl["era"]):
        s = dist[(era, p.month)]
        med.append(float(np.median(s)) if len(s) else np.nan)
        below.append(round(float((s < v).mean() * 100), 1) if len(s) else np.nan)   # share of years strictly below
        n_base.append(len(s))
    tbl["baseline_median"] = med
    tbl["anomaly"] = (tbl[P] - tbl["baseline_median"]).round(2)
    tbl["percent_of_years_below"] = below
    tbl["baseline_years"] = n_base

    # ---- month to date for the latest month
    dix = pd.date_range("2000-11-01", COVERAGE_END)

    def daily_counts(df):
        d = df if PRIMARY == "hotspots" else df.drop_duplicates(["ci", "cj", "date"])
        return d.groupby("date").size().reindex(dix).fillna(0).to_numpy()
    k_main = harm[PRIMARY][3]
    modis_d = daily_counts(dfs["modis"]) * k_main
    n20_d = daily_counts(dfs["n20"])
    snpp_d = daily_counts(dfs["snpp"]) if has_snpp else np.zeros(len(dix))
    dstart = lambda p: p.start_time
    daily = pd.Series(np.where(dix >= dstart(N20_START), n20_d,
                      np.where((dix >= dstart(SNPP_START)) & has_snpp, snpp_d, modis_d)), index=dix)
    mtd = month_to_date(daily, COVERAGE_END, viirs_first)

    # ---- cross-checks (never added to the series)
    def yearly_ratio(a: pd.Series, b: pd.Series, years):
        sa, sb = season_totals(a), season_totals(b)
        return {int(y): (float(sa.get(y, 0) / sb[y]) if sb.get(y, 0) > 0 else None) for y in years}
    n21_y = yearly_ratio(tbl[f"n21_{PRIMARY}"], tbl[f"n20_{PRIMARY}"], [2023, 2024, 2025])
    checks = {"noaa21_over_noaa20_yearly": n21_y}
    if has_snpp:
        checks["snpp_over_noaa20_yearly"] = yearly_ratio(tbl[f"snpp_{PRIMARY}"], tbl[f"n20_{PRIMARY}"], range(2018, 2026))
    print(f"[checks] {checks}")
    print(f"[month-to-date] {mtd}")

    # ---- write
    t = tbl.copy()
    t.insert(0, "month", t.index.astype(str))
    t.insert(1, "year", t.index.year)
    t.insert(2, "month_num", t.index.month)
    t.to_csv(out / "monthly_harmonized.csv", index=False)
    baseline.to_csv(out / "monthly_baseline.csv", index=False)

    cols = ["date", "acq_time", "latitude", "longitude", "source", "satellite",
            "instrument", "confidence", "frp", "daynight"]
    hs = pd.concat([d[cols] for d in dfs.values()]).sort_values(["date", "acq_time"])
    hs["date"] = hs["date"].dt.strftime("%Y-%m-%d")
    hs.to_csv(out / "hotspots_clean.csv", index=False)

    summary = {"area": "Newfoundland and Labrador", "coverage_end": str(COVERAGE_END.date()),
               "primary_metric": PRIMARY,
               "series_rules": {"viirs_first": str(viirs_first), "noaa20_from": str(N20_START),
                                "has_snpp": has_snpp, "fit_years": fit_years},
               "filters": {"modis_min_confidence": MODIS_MIN_CONF, "viirs_confidence": "nominal or high",
                           "type": "0 (presumed vegetation fire); near-real-time rows carry no type and are kept",
                           "fire_cell_size_deg": CELL_DEG},
               "sources": infos, "ratios": ratios, "month_to_date": mtd, "checks": checks,
               "notes": ["Nov 2000 to Jun 2002 is MODIS Terra only; excluded from the baseline.",
                         "The latest month is partial; use month_to_date for it.",
                         "Each month is compared with years of the same era only."]}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=_json))

    mod_s, ref_s, harm_s, k, stats = harm[PRIMARY]
    make_figure(out / "validation.png", mod_s, ref_s, harm_s, stats, k,
                "fire cells" if PRIMARY == "cells" else "hotspots")

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
