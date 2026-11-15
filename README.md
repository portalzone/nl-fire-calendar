# Newfoundland and Labrador Fire Calendar

A web app that combines NASA MODIS and VIIRS satellite heat detections into one monthly record for
Newfoundland and Labrador (NL). These detections, often called hotspots, are unusually hot areas seen by a
satellite; they are not confirmed fires. The requested data spans November 2000 to 7 November 2026, and the first
detection in the province is on 9 May 2001 (the app reads this date from the data). The app was built for the 2026 NASA
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

MODIS (since 2000) and VIIRS (since 2012) both detect unusually hot areas from space, but VIIRS can detect
smaller hot areas. A direct count from VIIRS is therefore usually higher than a MODIS count for the same
conditions. The app adjusts earlier MODIS counts with a multiplier so that monthly values can be compared.

## What the app does

- A calendar grid, with years as rows and months as columns. Its colors are designed to remain distinct for
  people with common forms of color-vision deficiency.
- Choose any area on the map (or type latitude and longitude) and any date range. All counts
  are recomputed in the browser for that area.
- Compare a selected month, including the latest partial month, with the same month in other years from the
  same instrument period: the MODIS period or the VIIRS period.
- A "Right now" box at the top: the latest available month, its count, the usual value for those days
  (the median from other years in the same instrument period), a plain-language comparison,
  and the area it applies to.
- A "How to read this" box: what a square, a color, a fire cell and the median mean, and why fire cells are
  the default. Its error numbers are read from `app/data/summary.json`.
- A comparison under the method table: the VIIRS/MODIS multiplier for the chosen area beside the
  province-wide multiplier. If they differ by more than 25%, the app says whether older, adjusted MODIS
  months may be too high or too low.
- Downloads for the selected area and dates:
  - hotspots (CSV, one row per detection, with the sensor);
  - monthly series (CSV, with the baseline, difference from the median and percent of years below);
  - the calendar as a picture (PNG), with the area, months, count type, color scale and the NASA FIRMS credit
    printed on it;
  - the yearly chart and the month-comparison chart (SVG);
  - the sensor-comparison chart used to validate (check) the merged results (`validation.png`, PNG).
- A carbon monoxide panel: monthly carbon monoxide (CO) from the Canadian Space Agency's MOPITT data,
  next to the fire counts, for the island of Newfoundland.

## How the merge works

1. **Clean.** Remove detections flagged as volcano, other static land source (for example
   refineries) or offshore, and low-confidence detections (MODIS confidence below 30, VIIRS
   "low"). The near-real-time rows carry no type flag, so they are kept.
2. **Count in fire cells.** A fire cell is one 0.1 degree map cell with at least one detection
   on one day. The cell counts once that day even if VIIRS records several detections there. A separate
   raw-hotspot option counts every detection.
3. **Calculate one multiplier.** The multiplier, k, is the total VIIRS count from May through September
   divided by the total MODIS count for those months across the 14 seasons from 2012 through 2025. The
   VIIRS record uses Suomi NPP from 2012 through March 2018 and NOAA-20 from April 2018.
4. **Combine the records.** MODIS counts before February 2012 are multiplied by k. From February 2012,
   the VIIRS count is used without adjustment. NOAA-21 is not added, to avoid double counting, and is
   used only as a check.
5. **Keep the comparison periods separate.** Each month is compared only with years from the same
   instrument period. Multiplying a MODIS count of zero by k still gives zero, while VIIRS may detect
   small hot areas during the same month.

## How well it works

These numbers come from `app/data/summary.json`.

| Count | Adjustment multiplier k | Range of yearly multipliers | Median season error* | Median month error* |
|---|---|---|---|---|
| Fire cells (default) | 1.615 | 1.40 to 6.67 | 15% | 60% |
| Raw hotspots | 4.663 | 2.0 to 9.0 | 29% | 80% |

\*For each season or month, the app recalculates the multiplier without that period and reports the median
percentage difference between the estimate and the recorded VIIRS count.

- May-to-September totals have lower estimation errors than individual months. Monthly counts in the province
  are often small.
- The highest yearly fire-cell multiplier (6.67) is from 2017, when MODIS saw 3 cells and VIIRS saw 20.
  Without 2017 the range is 1.40 to 2.44.
- Suomi NPP has multi-week gaps in some summers (for example 26 July to 14 August 2022 and
  10 to 29 July 2024), which is why NOAA-20 replaces it as soon as NOAA-20 starts.
- NOAA-21 totals are 1.03, 1.15 and 1.00 times NOAA-20's in 2023 to 2025.

## Limits

- One province-wide multiplier is applied to all earlier years, although the yearly multiplier varies with
  the year and the size of the detected hot areas.
- A province-wide multiplier may not describe a small area. The app calculates the local multiplier for the
  chosen area and shows it beside the province-wide value. Use small-area results to compare broad patterns,
  not as precise counts of individual fires.
- MODIS Terra flew alone before July 2002. Those months are marked in the calendar.
- The latest month is incomplete. It comes from files published soon after the satellite observations, and
  those files may later be revised.
- Not included: fires reported by agencies are not used, only satellite detections. The app compares
  months, not single fires, so it cannot say how one particular fire compares with another.
- MODIS data uses processing version Collection 6 through 2022 and Collection 6.1 after 2022. The app does
  not adjust counts for differences between those processing versions.
- Hotspots are satellite thermal detections, not confirmed fire perimeters.
- The CO data in `app/data/co_monthly.json` runs from 2001 to 2024. No data is loaded for 2004 to 2009.
  A year is drawn only if at least 9 of its 12 months have values, because each month is compared with that
  year's own average. Drawn: 2002, 2003 and 2010 to 2024. Left out of the charts: 2001 (only 7 months).
  The CSA file names show four product versions (V18.0.3, V19.9.3, V19.10.3 and V20.2.3), and the version changes
  during 2020, 2022 and 2023. The app plots each month's CO as a percentage above or below that year's average,
  so use it to compare months within a year, not CO levels between years. In 2020, 2022 and 2023 a step inside
  the year can come from the version change and not from smoke.
  The CO box includes nearby sea and small parts of the Gulf, southern Labrador and Quebec.
  Wind can carry CO from fires in other provinces, so a high month is not proof of a local fire.
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
python pipeline/download_mopitt.py --years 2001 2002 2003 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 --months 1 2 3 4 5 6 7 8 9 10 11 12
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
says so; they never skip. Last full run: 270 passed, 0 failed, 0 skipped. Pipeline line coverage: 94%
(build_co.py 94%, build_harmonized.py 95%, download_mopitt.py 90%).

- `tests/test_fire_pipeline.py` (53 tests): cleaning rules, month and confidence boundaries, cell counting,
  the ratio fit (exact known answers, leave-one-year-out), leap-day handling, and contract tests that
  check the output files have the fields the app reads, and the check that fails when `app/data/` is missing.
- `tests/test_full_run.py` (5): runs the whole pipeline on small made-up data where the right answer is known.
- `tests/test_co_pipeline.py` (26): carbon monoxide rules (box edges, fill values, cut-off lines, duplicate files, the 15-day minimum).
- `tests/test_download.py` (16): the downloader against a small local web server.
- `tests/test_repo_files.py` (11): the Pages workflow, README claims, the CSA credit, no placeholders, and
  that the Word files, raw data and zip files are ignored by Git.
- `tests/e2e/test_app.py` (159): the app in a real browser: the tabs (keyboard, deep links, Back button), the short top of the page and its closed sections, keyboard use, bad input, every download (CSV, PNG,
  SVG), the "Right now" and "How to read this" boxes, the local ratio against an independent count,
  color contrast, the CO panel, a missing CO file, and a phone-width screen.

## Team and contributions

- Victor Chisom Muojeke: data pipeline, app, carbon monoxide data.
- Amalraj Rajesh: testing, review of the merged app, demo video.
- Chiemerie Cletus Obijiaku: screenshots, demo script and subtitles.
- Olaleye Adeniyi Akinuli: text review and the judging-readiness work on the app introduction.

## Use of AI

The code, tests and documentation in this repository were written with the help of an AI coding assistant
(Claude, by Anthropic), and the team reviewed, ran and tested them.

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
