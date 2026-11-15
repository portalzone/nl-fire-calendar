# Newfoundland and Labrador Fire Calendar

A web app that merges NASA MODIS and VIIRS fire hotspots into one burning-activity record for
Newfoundland and Labrador (NL). The data was requested from November 2000 to 7 November 2026; the first
detection in the province is on 9 May 2001 (the app reads this date from the data). It was built for the 2026 NASA
Space Apps Challenge, St. John's, for the challenge "Harmonization of MODIS and VIIRS Hot Spots".

Intended address: https://portalzone.github.io/nl-fire-calendar/ (GitHub Pages). Check that the page
opens before you share it.

### One-time setup for the site

1. The repository must be public.
2. On GitHub: Settings, Pages, Source: GitHub Actions.
3. Push to `main`. The workflow `.github/workflows/pages.yml` publishes only the `app/` folder, and runs
   only when something in `app/` (or the workflow itself) changes. You can also run it by hand from the
   Actions tab.

## The problem

MODIS (since 2000) and VIIRS (since 2012) both detect fires from space, but VIIRS sees much
smaller fires. Raw counts from the two sensors cannot be compared, so a "busy" month in 2005
and a "busy" month in 2022 mean different things. This app puts both on one scale.

## What the app does

- A calendar heatmap, years by months, with a colorblind-safe viridis color ramp.
- Choose any area on the map (or type latitude and longitude) and any date range. All counts
  are recomputed in the browser for that area.
- Compare a selected month, including the current partial month, against the same month in
  other years of the same sensor era.
- A "Right now" box at the top: the latest month so far, its count, the usual value for those days
  (the multi-year baseline, which is the median of other years of the same sensor era), a plain verdict,
  and the area it applies to.
- A "How to read this" box: what a square, a color, a fire cell and the median mean, and why fire cells are
  the default. Its error numbers are read from `app/data/summary.json`.
- A local check under the method table: the VIIRS/MODIS ratio for the area you chose, next to the
  province-wide ratio, with a sentence on which way older months there are probably off when the two differ
  by more than 25%.
- Downloads for the selected area and dates:
  - hotspots (CSV, one row per detection, with the sensor);
  - monthly series (CSV, with the baseline, difference from the median and percent of years below);
  - the calendar as a picture (PNG), with the area, months, count type, color scale and the NASA FIRMS credit
    printed on it;
  - the yearly chart and the month-comparison chart (SVG);
  - the validation chart (PNG).
- A smoke panel: monthly carbon monoxide (CO) from the Canadian Space Agency's MOPITT data,
  next to the fire counts, for the island of Newfoundland.

## How the merge works

1. **Clean.** Remove detections flagged as volcano, other static land source (for example
   refineries) or offshore, and low-confidence detections (MODIS confidence below 30, VIIRS
   "low"). The near-real-time rows carry no type flag, so they are kept.
2. **Count in fire cells.** A fire cell is one 0.1 degree map cell with at least one detection
   on one day. This stops VIIRS's finer pixels from inflating the count. Raw hotspot counts are
   also available.
3. **Fit one ratio.** Ratio k = VIIRS May to September totals divided by MODIS May to September
   totals, over the 14 seasons 2012 to 2025 (Suomi NPP from 2012 to March 2018, NOAA-20 from
   April 2018).
4. **Merge.** Months before VIIRS starts are MODIS counts multiplied by k. From February 2012
   the VIIRS record is used as observed. NOAA-21 is not added, to avoid double counting, and is
   used only as a check.
5. **Compare like with like.** Each month is compared only with years of its own era, because a
   MODIS zero multiplied by k is still zero while VIIRS often sees small fires in the same month.

## How well it works

These numbers come from `app/data/summary.json`.

| Count | Ratio k | Yearly ratio range | Season error* | Month error* |
|---|---|---|---|---|
| Fire cells (default) | 1.615 | 1.40 to 6.67 | 15% | 60% |
| Raw hotspots | 4.663 | 2.0 to 9.0 | 29% | 80% |

\*Median error when each season (or month) is predicted from a ratio fitted on the other seasons.

- Season totals are predicted far better than single months. Monthly numbers in the province are small.
- The highest yearly cell ratio (6.67) is 2017 alone, when MODIS saw 3 cells and VIIRS saw 20.
  Without 2017 the range is 1.40 to 2.44.
- Suomi NPP has multi-week gaps in some summers (for example 26 July to 14 August 2022 and
  10 to 29 July 2024), which is why NOAA-20 replaces it as soon as NOAA-20 starts. Keeping Suomi NPP for
  all years raises the season error from 14.6% to 18.8%.
- NOAA-21 totals are 1.03, 1.15 and 1.00 times NOAA-20's in 2023 to 2025.

## Limits

- One ratio is applied to all years. It changes from year to year and with fire size.
- A province-wide ratio is not valid for small areas. The app shows the local ratio for your area. For the
  "Island of Newfoundland" box it is 2.87 with fire cells, against 1.62 for the province (read from the app).
  Numbers for a small area are indicative, not exact.
- MODIS Terra flew alone before July 2002. Those months are marked in the calendar.
- The latest month is partial and comes from near-real-time files, which can be revised.
- Not included: fires reported by agencies are not used, only satellite detections. The app compares
  months, not single fires, so it cannot say how one particular fire compares with another.
- MODIS data is Collection 6 up to 2022 and 6.1 after. This is not modelled.
- Hotspots are satellite thermal detections, not confirmed fire perimeters.
- The CO data covers only 2012, 2013, 2018, 2019 and 2024. The data product version is V18 in
  the first four years and V20 in 2024, so the app plots CO as a percent of each year's own average.
  The CO box includes nearby sea and small parts of the Gulf, southern Labrador and Quebec.
  CO also carries smoke from fires in other provinces, so a high month is not proof of a local fire.
  Months with fewer than 15 days of readings are left out.

## Run it

```
pip install -r requirements.txt

# 1. Fire data. Download from NASA FIRMS (Archive Download, CSV, Newfoundland and Labrador,
#    buffer 0 km) and unzip each sensor into its own folder:
#      data/raw/modis/         MODIS (2000-11-01 to 2026-11-07)
#      data/raw/viirs_snpp/    VIIRS S-NPP (2012-01-20 to 2026-11-02)
#      data/raw/viirs_noaa20/  VIIRS NOAA-20
#      data/raw/viirs_noaa21/  VIIRS NOAA-21
python pipeline/build_harmonized.py

# 2. Carbon monoxide (optional). Needs internet. Keeps only the island rows.
python pipeline/download_mopitt.py --years 2012 2013 2018 2019 2024 --months 1 2 3 4 5 6 7 8 9 10 11 12
python pipeline/build_co.py

# 3. Open the app
cd app && python3 -m http.server 8000     # then open http://localhost:8000
```

If the CSA download fails with `CERTIFICATE_VERIFY_FAILED`, run `pip install truststore` first.

The `app/` folder is plain HTML, CSS and JavaScript with no build step, so it can be hosted on any
static web host.

## Tests

```
pip install -r requirements-dev.txt
python -m playwright install chromium
make test          # everything
make test-fast     # pipeline tests only
make coverage      # shows how much pipeline code the tests run
```

Build `app/data/` first (step 1 and 2 above). If it is missing, the tests fail with a message that
says so; they never skip. Last full run: 173 passed, 0 failed, 0 skipped. Pipeline line coverage: 93%
(build_co.py 94%, build_harmonized.py 95%, download_mopitt.py 90%).

- `tests/test_fire_pipeline.py` (53 tests): cleaning rules, month and confidence boundaries, cell counting,
  the ratio fit (exact known answers, leave-one-year-out), leap-day handling, and contract tests that
  check the output files have the fields the app reads, and the check that fails when `app/data/` is missing.
- `tests/test_full_run.py` (5): runs the whole pipeline on small made-up data where the right answer is known.
- `tests/test_co_pipeline.py` (23): carbon monoxide rules (box edges, fill values, duplicate files, the 15-day minimum).
- `tests/test_download.py` (16): the downloader against a small local web server.
- `tests/test_repo_files.py` (11): the Pages workflow, README claims, the CSA credit, no placeholders, and
  that the Word files, raw data and zip files are ignored by Git.
- `tests/e2e/test_app.py` (65): the app in a real browser: keyboard use, bad input, every download (CSV, PNG,
  SVG), the "Right now" and "How to read this" boxes, the local ratio against an independent count,
  color contrast, the CO panel, a missing CO file, and a phone-width screen.

## Folder layout

```
.github/workflows/  publishes app/ to GitHub Pages
app/                 the web app (index.html) and its data in app/data/
pipeline/            build_harmonized.py, build_co.py, download_mopitt.py
tests/               pipeline tests and browser tests
data/raw/            downloaded source data (not in Git)
```

## Acknowledgments

We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management
System (FIRMS) (https://earthdata.nasa.gov/firms), part of NASA's Land, Atmosphere Near real-time
Capability for Earth observations (LANCE) (https://earthdata.nasa.gov/lance) and NASA's Earth Science
Data and Information System (ESDIS).

Carbon monoxide data: MOPITT (Measurements of Pollution in the Troposphere), a Canadian instrument aboard
NASA's Terra satellite. Source: Canadian Space Agency Open Data,
https://donnees-data.asc-csa.gc.ca/en/dataset/ef42819f-35bb-49c0-a368-1e61fa876ee6.
Contains information licensed under the Open Government Licence – Canada. This project filtered the data to the
island of Newfoundland and averaged it by month.

Built with Python, pandas, NumPy, Matplotlib, pytest and Playwright. The app uses no external libraries.
