# Hackathon readiness review

Branch: `improve/hackathon-judging-readiness`

Review date: 15 November 2026 (Newfoundland Time)

## Outcome

The project already implements the core challenge: it combines MODIS and VIIRS hotspot records, provides a monthly burning-activity calendar, lets a user choose an area and date range, compares a selected month with a historical median, and exports data and charts.

The largest weakness was presentation, not missing analysis. A judge arriving at the app had to infer the problem, target users, challenge fit, validation result, and safe use from several tabs. The update adds a concise, evidence-backed introduction and a three-step path into the working prototype.

No claim of winning, user adoption, operational deployment, fire prediction, or improved emergency outcomes is made.

## Evidence reviewed

### Repository documents

- `Harmonization of MODIS and VIIRS Hot Spots.docx`: the saved challenge statement, background, objectives, potential users, suggested interactions, historical comparisons, accessible color ramps, and CSV output.
- `more details.docx`: transcript of the challenge-author video. It reinforces the two-part task—sensor harmonization followed by a web calendar—but contains transcription errors, so it was used for context rather than quoted for factual claims.
- `nasa overview for hackathon.docx`: St. John's event overview, schedule, submission deadline, and description of the local judging panel's areas of expertise.
- `app/data/summary.json`: source for the number of fit seasons and validation error shown in the new interface.
- `app/data/hotspots_clean.csv`: source for the first detection month displayed in the new interface.

### Public sources

- Official 2026 challenge page: <https://www.spaceappschallenge.org/2026/challenges/modis-and-viirs-hot-spots/>
- Official St. John's local-event page: <https://www.spaceappschallenge.org/2026/local-events/st-johns/>
- NASA Space Apps 2026 overview and submission dates: <https://www.spaceappschallenge.org/2026/>
- NASA Space Apps description of its open-data purpose and judging process: <https://www.spaceappschallenge.org/about/>
- Recent official global award descriptions, used only as strategic context rather than a promise about 2026 local prizes: <https://www.spaceappschallenge.org/2025/awards/>

Official and official-platform 2026 pages consistently describe five judging concerns: impact, creativity, validity, relevance, and presentation. The St. John's material in the repository does not publish scoring weights or named local awards. This review therefore does not invent weights, rankings, or a likely award.

## Assessment against the judging concerns

| Concern | Evidence already in the project | Gap found | Improvement made |
|---|---|---|---|
| Impact | Focused Newfoundland and Labrador tool; area selection; current-month and historical comparisons; downloads | Intended users and practical use were buried | The opening now names the challenge's intended users and explains the historical decisions the tool supports, without claiming operational adoption |
| Creativity | Daily 0.1° fire cells reduce sensor-resolution effects; overlap-period multiplier; CO context | The distinctive approach was visible mainly in Method and README | The opening explains the two-sensor problem and the fire-cell/overlap solution in plain language |
| Validity | Reproducible pipeline, validation chart, leave-one-season-out error, limits, tests | Strong evidence appeared late in the journey | Three data-backed proof points are displayed near the top, and a direct button opens the evidence and limits |
| Relevance | Calendar, selected area, date range, historical median, accessible colors, CSV and chart downloads match the challenge brief | The official challenge connection was only in the footer | The header links the exact official challenge and St. John's event; the three-step tour mirrors the requested workflow |
| Presentation | Working tabs and charts, responsive layout, explanations | The first screen began with output before explaining the problem and solution | Added a stronger visual hierarchy, judge-facing story, demo path, quick actions, and keyboard skip link |

## Interface changes and why they matter

1. **Challenge-first hero context.** The header now identifies NASA Space Apps 2026 and St. John's and links to the exact challenge and event. This makes relevance verifiable without adding a NASA logo or implying NASA endorsement.

2. **Plain-language problem and solution.** A new introductory card states that MODIS and VIIRS count hotspots differently and explains that the app uses daily fire cells plus their overlap years to adjust the older record. A judge can understand the innovation before opening the Method tab.

3. **Data-backed proof points.** The interface reads, rather than hard-codes:

   - record coverage from the earliest loaded detection and `summary.json` coverage end;
   - the number of overlap seasons from `summary.json`;
   - the rounded median May-to-September fire-cell error from `summary.json`.

   Reading these values from the data avoids stale claims when the pipeline is rebuilt.

4. **Three-step demo path.** The page tells a judge to choose an area and dates, find an unusual period, then inspect assumptions and export results. This directly follows the challenge workflow and makes a short live demonstration easier to follow.

5. **Quick actions.** “Explore the calendar” and “See evidence and limits” open the correct tabs. This reduces the time needed to reach the working prototype and its scientific support.

6. **Explicit operational limit.** The new note says the prototype provides historical context, does not confirm fire perimeters, and does not forecast spread. This improves scientific validity and prevents an emergency-response audience from interpreting the prototype as an alerting system.

7. **Accessibility and responsive presentation.** A keyboard skip link was added. The new evidence and tour layouts collapse on narrow screens, while existing tab and calendar keyboard behavior remains intact.

## Claims used in the new interface

| Interface claim | Basis |
|---|---|
| MODIS provides a longer record and VIIRS detects smaller hot areas | Official challenge statement and saved challenge document |
| Emergency responders, scientists, and land managers are intended users | Official challenge statement and saved challenge document |
| Earlier MODIS months are adjusted using overlap years | Repository method and `summary.json` fit years |
| Record coverage | Earliest date in the loaded cleaned hotspot records plus `summary.json.coverage_end` |
| Number of overlap seasons | `summary.json.series_rules.fit_years` |
| Median season error | Rounded `summary.json.ratios.cells.cv_median_pct_err`; label specifies May–September fire-cell totals |
| Not an operational alert or spread forecast | Existing project limits and the absence of an alert/forecast model |

## Important remaining presentation work

These items are outside the repository interface and should be completed for the project submission or pitch:

- Use a short demo sequence: problem (sensor break), choose a local area, select an unusual month, show the median comparison, then open Method to show validation and limits.
- State exactly how NASA FIRMS data is used. Do not merely list NASA as a source.
- Show one concrete Newfoundland and Labrador example selected live in the app; describe only what the satellite record shows.
- Keep the limitation statement in the spoken pitch. Avoid describing the app as a forecast, early-warning alert, confirmed-fire database, or burned-area map.
- If a video or slides are submitted, make the public link accessible without a login and verify it before the deadline.

## Verification added

Browser tests now check that the introductory proof points match `summary.json`, that the safe-use wording is present, that the official links point to the expected pages, and that both quick-action buttons open the intended tabs.
