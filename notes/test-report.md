# Merged Main Test Report

Run date: 15 November 2026
Branch: `amalraj-testing` (origin/main already up to date)
Platform: Windows, Python 3.12.0, Playwright Chromium

## Pytest

Command: `python -X utf8 -m pytest`

```text
248 passed, 2 warnings in 83.09s
Failed: 0
Skipped: 0
```

The two warnings are `PytestRemovedIn10Warning` notices for class-scoped fixtures declared as instance methods.

Command: `python -X utf8 -m pytest --collect-only -q`

```text
tests/e2e/test_app.py: 140
tests/test_co_pipeline.py: 23
tests/test_download.py: 16
tests/test_fire_pipeline.py: 53
tests/test_full_run.py: 5
tests/test_repo_files.py: 11
Total: 248
```

## Playwright

Captured the page top and all five tabs at 1400x1000 and 390x844. The 12 JPEGs are in [review-shots](review-shots/); each is under 1 MB. All tabs were visible at both sizes, no page-level horizontal overflow occurred, and no app page errors were reported.

At both widths, selected Island of Newfoundland and dates 2012-01 through 2018-12, applied the area, changed Count to Raw hotspots, selected Jan 2018, and checked its comparison. The area summary showed 287 detections. Jan 2018 showed 0 hotspots and a median of 0 from 13 other VIIRS-era years.

The CO year picker selected 2023. “Show all years” expanded the actual data from 8 charts to all 13 years. All six downloads completed at both widths: hotspots CSV, monthly-series CSV, calendar PNG, yearly SVG, month-comparison SVG, and validation PNG.

Both header links returned HTTP 200 at their expected official URLs. The “See evidence and limits” and “Explore the calendar” buttons selected Method and Area, respectively.

| Proof | App | `app/data/summary.json` |
|---|---|---|
| Record period | May 2001–Nov 2026 | First source date `2001-05-09`; coverage end `2026-11-07` |
| Overlap seasons | 14 | 14 fit years, 2012–2025 |
| Median seasonal fire-cell error | 15% | 14.571675498155383%, rounded to 15% |

Measured from the page top: tab bar at 1,225 px desktop and 2,517 px mobile; calendar heading at 2,169 px desktop and 3,857 px mobile. A judge must scroll through substantial introduction text before reaching the calendar. The mobile tab strip and Method table scroll horizontally inside their own containers; the page does not scroll sideways.

## Limits

Processed app data was checked in. `data/raw/` is absent, so the pipeline was not rebuilt from NASA source files. `-X utf8` avoids Windows' default `cp1252` decoding of UTF-8 project files. Detailed findings and per-screenshot sizes are in [merged-main-review.md](merged-main-review.md).
