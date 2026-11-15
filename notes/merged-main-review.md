# Merged Main Review

Run date: 15 November 2026. Tested on Windows with Python 3.12.0 and Playwright Chromium.

## Merge and history

Commands: `git fetch origin`, `git checkout amalraj-testing`, `git merge origin/main`, `git log --oneline -8`.

The merge reported `Already up to date`. `origin/main` at `18b8191` was already an ancestor of `amalraj-testing`; the merge changed no files. The top commit is `edb08d0` (`Add branch review and test reports`).

```text
edb08d0 Add branch review and test reports
18b8191 Improve hackathon story and judging evidence (#1)
8b7220d Clarify project text and document copy fixes
5ca58a7 Add carbon monoxide data for 2012 to 2024
65cea8f Keep the open tab visible in the tab bar; add phone tap tests
8eed892 Split the page into tabs, add favicon, compact CO panel with year picker
dcd09ca Add picture and chart downloads, plain-reading boxes, local ratio check, Pages workflow and CSA credit
041bde0 Add CO smoke panel, tests and README; fix review findings
```

Files changed by this merge: none.

## Layout and screenshots

Screenshots are viewport captures at 1400x1000 and 390x844. Every file is below 1 MB; the largest is 191,339 bytes. `documentElement.scrollWidth` equaled the viewport width at both sizes and in every tab. No page-level sideways scrolling or JavaScript page errors were observed.

| Viewport | Tab bar top | Calendar heading top | Calendar grid top | Tab strip width |
|---|---:|---:|---:|---:|
| 1400 px | 1,225 px | 2,169 px | 2,277 px | 1,168 / 1,168 px |
| 390 px | 2,517 px | 3,857 px | 4,097 px | 533 / 358 px; internally scrollable |

The judge must scroll past substantial introduction text before reaching the working app: about 1.2 desktop viewports or 3 mobile viewports to the tab bar, and about 2.2 desktop viewports or 4.6 mobile viewports to the calendar. The “Explore the calendar” quick action is a shortcut, but the first screen is still story-first.

At 390 px, the tab strip and Method table require horizontal scrolling inside their own containers. Some tab labels and table columns are outside the initial visible area until swiped. They are reachable; the page itself does not overflow sideways. Content that falls below a screenshot is vertically scrollable, not clipped from the page.

| Screenshot | File |
|---|---|
| Desktop top (126,769 bytes) | [top-1400.jpg](review-shots/top-1400.jpg) |
| Desktop Area and calendar (98,204 bytes) | [tab-area-1400.jpg](review-shots/tab-area-1400.jpg) |
| Desktop Compare (137,962 bytes) | [tab-compare-1400.jpg](review-shots/tab-compare-1400.jpg) |
| Desktop Smoke (89,510 bytes) | [tab-smoke-1400.jpg](review-shots/tab-smoke-1400.jpg) |
| Desktop Downloads (157,242 bytes) | [tab-downloads-1400.jpg](review-shots/tab-downloads-1400.jpg) |
| Desktop Method (191,339 bytes) | [tab-method-1400.jpg](review-shots/tab-method-1400.jpg) |
| Mobile top (59,372 bytes) | [top-390.jpg](review-shots/top-390.jpg) |
| Mobile Area and calendar (43,603 bytes) | [tab-area-390.jpg](review-shots/tab-area-390.jpg) |
| Mobile Compare (39,193 bytes) | [tab-compare-390.jpg](review-shots/tab-compare-390.jpg) |
| Mobile Smoke (49,719 bytes) | [tab-smoke-390.jpg](review-shots/tab-smoke-390.jpg) |
| Mobile Downloads (58,001 bytes) | [tab-downloads-390.jpg](review-shots/tab-downloads-390.jpg) |
| Mobile Method (71,049 bytes) | [tab-method-390.jpg](review-shots/tab-method-390.jpg) |

## Workflow checks

| Tab | Steps | What happened | Expected behavior |
|---|---|---|---|
| Area and calendar | At both widths, choose Island of Newfoundland, set 2012-01 through 2018-12, apply, switch Count to Raw hotspots, and click Jan 2018. | The area summary showed 287 detections; the selected month was 0 hotspots. Compare showed a median of 0 from 13 other VIIRS-era years. The map rendered colored hotspot points and a separate dashed area box. | Area/date filters, count mode, selected month comparison, hotspot points, and the selected-area outline should update and remain usable. They did. |
| Compare | Open after selecting Jan 2018 at both widths. | The current count, median, other-year counts, and chart rendered. At 390 px, the comparison cards wrap vertically and the chart remains within the page width. | Show the selected month against comparable years without page-level horizontal overflow. Met. |
| Smoke | At both widths, choose 2023 in the year picker, then click “Show all years.” | The large chart changed to 2023. The actual data showed 8 charts by default and expanded to all 13 years (2012–2024); the button changed to “Show fewer.” | The picker should select a year and “Show all years” should expand the chart list. Met. |
| Downloads | At both widths, try hotspots CSV, monthly-series CSV, calendar PNG, yearly SVG, month-comparison SVG, and validation PNG. | All six downloads completed at both widths with the expected filenames. | Each download should complete. Met. |
| Method | Open at both widths. | Text and validation details rendered. At 390 px, the wide results table scrolls horizontally within its wrapper; the page does not widen. | All method columns should remain reachable. They are reachable by scrolling the table sideways. |

No JavaScript page errors occurred. The Area map plots sensor-colored hotspot marks; it is not just the selected area box. The dashed box marks the selected bounds, and faded points indicate detections outside that area.

## Links and quick actions

- Official challenge brief: HTTP 200; final URL remained `https://www.spaceappschallenge.org/2026/challenges/modis-and-viirs-hot-spots/`, whose heading is “Harmonization of MODIS and VIIRS Hot Spots.”
- St. John’s local event: HTTP 200; final URL remained `https://www.spaceappschallenge.org/2026/local-events/st-johns/`, headed “St. John’s.”
- “See evidence and limits” selected Method, showed its panel, and set `#method`.
- “Explore the calendar” selected Area and calendar, showed its panel, and set `#area`.

## Proof numbers

| Proof shown in the app | Value from `app/data/summary.json` | Result |
|---|---|---|
| Record coverage: May 2001–Nov 2026 | Earliest source date `2001-05-09`; `coverage_end` `2026-11-07` | Matches at month precision |
| Overlap seasons: 14 | `series_rules.fit_years`: 2012–2025, 14 entries | Matches |
| Median seasonal error: 15% | `ratios.cells.cv_median_pct_err`: 14.571675498155383%, rounded to 15% | Matches |

## Observed problems

| Tab | Steps | What happened | What should happen |
|---|---|---|---|
| Top / Area and calendar | Load the page at 1400 px and 390 px, then look for the tab bar and calendar. | The tab bar starts at 1,225 / 2,517 px and the calendar heading at 2,169 / 3,857 px. Introductory content pushes the working app several screens down, especially on mobile. | Keep a clear route to the working calendar near the first screen, or reduce/collapse the lead-in so a judge can reach it sooner. |
| Tab strip, 390 px | Open the page at 390 px and inspect the five-tab row. | The tab list is 533 px wide inside a 358 px viewport. Later labels are initially off-screen and require a horizontal swipe. | Make the horizontal navigation affordance clear or fit all tab labels without hiding them. |
| Method, 390 px | Open Method and inspect the results table. | The table columns past the right edge require an internal horizontal swipe. The document itself stays 390 px wide. | Preserve access to every column; a mobile stacked/table alternative could avoid the sideways scan. |

## Challenge points not covered

- The challenge mentions early warning and emergency response. This app provides historical context only; it does not issue alerts, monitor active incidents operationally, predict fire spread, or forecast fire behavior.
- It does not integrate reported or ground-truth fires, confirm satellite detections, or compare individual fire incidents. Its comparisons are monthly aggregates of satellite hotspots/fire cells.
- The data and map are limited to Newfoundland and Labrador rather than a broader or global area of interest.
- It does not estimate burned area or fire severity. The map shows hotspot detections, not fire perimeters or burn scars.
