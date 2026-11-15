# Text fixes

`app/index.html` was audited but not edited. README suggestions marked “applied” were made directly in `README.md`.

## README.md

### 1. Opening description — applied

- **Where:** Opening paragraph.
- **Current text:** “merges NASA MODIS and VIIRS fire hotspots into one burning-activity record”
- **Suggested text:** “combines NASA MODIS and VIIRS satellite heat detections into one monthly record,” followed by a definition of “hotspot” and a warning that a detection is not a confirmed fire.

### 2. Why direct counts cannot be compared — applied

- **Where:** “The problem.”
- **Current text:** “a ‘busy’ month in 2005 and a ‘busy’ month in 2022 mean different things. This app puts both on one scale.”
- **Suggested text:** “A direct count from VIIRS is therefore usually higher than a MODIS count for the same conditions. The app adjusts earlier MODIS counts with a multiplier so that monthly values can be compared.”

### 3. Calendar terminology — applied

- **Where:** First bullet under “What the app does.”
- **Current text:** “A calendar heatmap, years by months, with a colorblind-safe viridis color ramp.”
- **Suggested text:** “A calendar grid, with years as rows and months as columns. Its colors are designed to remain distinct for people with common forms of color-vision deficiency.”

### 4. “Sensor era” — applied

- **Where:** Month-comparison bullet under “What the app does.”
- **Current text:** “other years of the same sensor era”
- **Suggested text:** “other years from the same instrument period: the MODIS period or the VIIRS period”

### 5. “Right now” description — applied

- **Where:** “Right now” bullet under “What the app does.”
- **Current text:** “the latest month so far … the multi-year baseline … a plain verdict”
- **Suggested text:** “the latest available month … the median from other years in the same instrument period … a plain-language comparison”

### 6. Local-ratio description — applied

- **Where:** Local-check bullet under “What the app does.”
- **Current text:** “with a sentence on which way older months there are probably off”
- **Suggested text:** “If [the local and province-wide multipliers] differ by more than 25%, the app says whether older, adjusted MODIS months may be too high or too low.”

### 7. “Validation chart” and “smoke panel” — applied

- **Where:** Download and carbon-monoxide bullets under “What the app does.”
- **Current text:** “the validation chart”; “A smoke panel”
- **Suggested text:** “the sensor-comparison chart used to validate (check) the merged results”; “A carbon monoxide panel”

### 8. Ratio-fitting jargon — applied

- **Where:** Steps 3–5 under “How the merge works.”
- **Current text:** “Fit one ratio”; “used as observed”; “years of its own era”
- **Suggested text:** “Calculate one multiplier”; “used without adjustment”; “years from the same instrument period.” Also state the calculation as total VIIRS May-to-September count divided by total MODIS count across the 14 fit seasons.

### 9. Error-table jargon — applied

- **Where:** Table and footnote under “How well it works.”
- **Current text:** “Ratio k”; “Season error”; “Month error”; “predicted from a ratio fitted on the other seasons”
- **Suggested text:** “Adjustment multiplier k”; “Median season error”; “Median month error.” Explain that the multiplier is recalculated without each period and that the error is the percentage difference from its recorded VIIRS count.

### 10. Vague performance comparison — applied

- **Where:** First bullet below the error table.
- **Current text:** “Season totals are predicted far better than single months.”
- **Suggested text:** “May-to-September totals have lower estimation errors than individual months.”

### 11. Error number not stored in the required source — applied

- **Where:** Suomi NPP gap bullet under “How well it works.”
- **Current text:** “Keeping Suomi NPP for all years raises the season error from 14.6% to 18.8%.”
- **Suggested text:** Remove this comparison unless `18.8%` is added to `app/data/summary.json`. The summary supports the rounded `15%` selected-record season error, but it does not contain the alternate `18.8%` result.

### 12. Hard-coded island multiplier not in the required source — applied

- **Where:** Second bullet under “Limits.”
- **Current text:** “For the ‘Island of Newfoundland’ box it is 2.87 with fire cells, against 1.62 for the province (read from the app). Numbers for a small area are indicative, not exact.”
- **Suggested text:** “The app calculates the local multiplier for the chosen area and shows it beside the province-wide value. Use small-area results to compare broad patterns, not as precise counts of individual fires.” The province-wide value rounds correctly from the summary, but `2.87` is computed from the hotspot file and is not stored in the summary.

### 13. “Near-real-time” — applied

- **Where:** Latest-month bullet under “Limits.”
- **Current text:** “comes from near-real-time files”
- **Suggested text:** “comes from files published soon after the satellite observations, and those files may later be revised”

### 14. MODIS collection jargon — applied

- **Where:** MODIS-version bullet under “Limits.”
- **Current text:** “MODIS data is Collection 6 up to 2022 and 6.1 after. This is not modelled.”
- **Suggested text:** “MODIS data uses processing version Collection 6 through 2022 and Collection 6.1 after 2022. The app does not adjust counts for differences between those processing versions.”

### 15. Fire-cell explanation — applied

- **Where:** Step 2 under “How the merge works.”
- **Current text:** “This stops VIIRS’s finer pixels from inflating the count. Raw hotspot counts are also available.”
- **Suggested text:** “The cell counts once that day even if VIIRS records several detections there. A separate raw-hotspot option counts every detection.”

### 16. Vague multiplier and CO wording — applied

- **Where:** “How well it works” and “Limits.”
- **Current text:** “The highest yearly cell ratio”; “One ratio is applied to all years. It changes from year to year and with fire size”; “CO also carries smoke”
- **Suggested text:** “The highest yearly fire-cell multiplier”; explain that one province-wide multiplier is applied even though yearly values vary; “Wind can carry CO.”

## Shared app text

### 17. Header uses unexplained “hotspots” and “record”

- **Where:** Page subtitle (`#subtitle`, generated after the data loads).
- **Current text:** “NASA MODIS and VIIRS fire hotspots merged into one record.”
- **Suggested text:** “NASA MODIS and VIIRS satellite heat detections combined into one monthly history.”

### 18. “Right now” can imply live data

- **Where:** Heading above the latest-month summary.
- **Current text:** “Right now”
- **Suggested text:** “Latest available month”

### 19. Color description makes an unsupported fire claim

- **Where:** First bullet under “How to read this.”
- **Current text:** “Dark purple means little burning, bright yellow means a lot, and grey means none was detected.”
- **Suggested text:** “Dark purple means a low merged detection count, bright yellow means a high count, and grey means no detections were counted.”

### 20. Fire-cell definition is too dense

- **Where:** Second bullet under “How to read this.”
- **Current text:** “The number counts fire cells: map squares of 0.1° … with at least one satellite heat detection on a given day. One square on one day counts once, however many detections it has.”
- **Suggested text:** “A fire cell is a 0.1° map square with at least one satellite heat detection on one day. That square counts once for that day, even if the satellite records several detections there.” Put the approximate cell dimensions in a separate sentence.

### 21. “Known ones” has no clear referent

- **Where:** Last bullet under “How to read this.”
- **Current text:** “Industrial sites, gas flares and other hot surfaces can also be detected, although the known ones are removed.”
- **Suggested text:** “The data removes detections flagged as industrial, volcanic, or offshore, but unflagged non-fire heat sources may remain.”

## Area and calendar tab

### 22. Grammatical error and jargon in count help

- **Where:** Help text below the area controls.
- **Current text:** “Fire cells counts each 0.1° map cell with a detection on a given day once, so the finer VIIRS pixels do not inflate the count.”
- **Suggested text:** “The fire-cell measure counts each 0.1° map cell once per day if it contains a detection. This prevents VIIRS’s smaller detection areas from creating extra counts for the same place and day.”

### 23. “Merged count” and “same type” are unclear

- **Where:** Help text above the calendar.
- **Current text:** “Merged count per month … A dot marks a month where at least 90% of the other years of the same type had fewer.”
- **Suggested text:** “Monthly count after earlier MODIS values are adjusted to the VIIRS level … A dot marks a month whose count is higher than at least 90% of the other years in the same instrument period.”

### 24. “Own kind” is vague

- **Where:** Generated note at the end of the calendar instructions and calendar accessibility labels.
- **Current text:** “Each month is compared only with years of its own kind”; “other same-kind years”
- **Suggested text:** “Each month is compared only with other years in its instrument period (MODIS or VIIRS)”; “other years in the same instrument period”

### 25. Color-scale jargon

- **Where:** Help text below the calendar and generated legend label.
- **Current text:** “viridis ramp on a square-root scale”; “middle of ramp”
- **Suggested text:** “The colors use a color-blind-friendly scale. The scale gives more visual space to low counts so that both low- and high-count months remain distinguishable”; “midpoint color”

## Compare tab

### 26. Button labels hide their selection rules

- **Where:** Buttons above the selected-month comparison.
- **Current text:** “Latest month to date”; “Peak month in range”
- **Suggested text:** “Latest month through the available date”; “Highest-count complete month in the selected range”

### 27. Verdict words do not expose their thresholds

- **Where:** Generated selected-month verdicts.
- **Current text:** “Among the highest”; “Above typical”; “Below typical”; “Typical for this month.”
- **Suggested text:** “Higher than at least 90% of comparison years”; “Higher than at least 75% of comparison years”; “X of N comparison years had higher counts”; “Between the app’s high and low thresholds for this month.”

### 28. “Normal variation” claims more than the rule establishes

- **Where:** Generated verdict for counts below 3.
- **Current text:** “Counts this small are within normal variation, so no verdict is given.”
- **Suggested text:** “The app does not label counts below 3 as above or below the baseline.”

### 29. Zero-scaling explanation is awkward

- **Where:** Help text below the month-comparison chart.
- **Current text:** “a MODIS zero cannot be scaled into a VIIRS count”
- **Suggested text:** “multiplying a MODIS count of zero by the adjustment multiplier still gives zero, even when VIIRS detected small hot areas in comparable months”

## Smoke tab

### 30. Tab name overstates what CO can show

- **Where:** Tab label.
- **Current text:** “Smoke”
- **Suggested text:** “Carbon monoxide” or “Smoke context (CO)”

### 31. CO measure labels use unexplained jargon

- **Where:** “CO measure” menu.
- **Current text:** “Whole air column (10¹⁸ molecules/cm²)”; “Near the ground (ppbv)”
- **Suggested text:** “Total CO from the ground to the top of the atmosphere (10¹⁸ molecules/cm²)”; “Near-ground CO (parts per billion by volume)”

### 32. “Percent against” is awkward

- **Where:** Larger-chart heading and chart tooltips.
- **Current text:** “percent against that year’s average”
- **Suggested text:** “percent above or below that year’s average”

### 33. “One shared scale” is unclear

- **Where:** Generated chart explanation and CO note.
- **Current text:** “orange bars are fire cells for your selected area on one shared scale”
- **Suggested text:** “all orange fire-count bars use the same vertical scale across the year charts”

### 34. “Differences in level” is vague

- **Where:** Generated CO note.
- **Current text:** “This hides differences in level between years”
- **Suggested text:** “Because each year is converted to percentages around its own average, the charts do not compare absolute CO concentrations between years.”

### 35. “22 km resolution” is jargon

- **Where:** Generated CO note.
- **Current text:** “at about 22 km resolution”
- **Suggested text:** “Each CO value comes from measurements grouped into grid cells about 22 km wide.”

### 36. Seasonal and transported-smoke sentence is dense

- **Where:** Final sentence of the generated CO note.
- **Current text:** “CO also follows the seasons and carries smoke from fires in other provinces, and the box includes nearby sea and small parts of the Gulf, southern Labrador and Quebec.”
- **Suggested text:** “CO levels change with the seasons even without a local fire. Wind can also carry CO from fires outside Newfoundland. The measurement box includes nearby ocean and small parts of the Gulf, southern Labrador, and Quebec.”

## Downloads tab

### 37. Download names are not self-explanatory

- **Where:** Download buttons.
- **Current text:** “Monthly series for selected area (CSV)”; “Validation chart (PNG)”
- **Suggested text:** “Monthly counts and baseline comparisons (CSV)”; “Sensor comparison and merge check (PNG)”

### 38. “Ready for a report” is vague

- **Where:** Generated download description.
- **Current text:** “The picture shows the calendar for the selected area and dates, with its sources, ready for a report.”
- **Suggested text:** “The PNG includes the selected area, dates, count type, legend, and data-source credit.”

## Method tab

### 39. Heading does not say what “how well” means

- **Where:** Method-tab heading.
- **Current text:** “How the merge works, and how well”
- **Suggested text:** “How the records are combined and the measured estimation error”

### 40. Method paragraph uses statistical jargon

- **Where:** First generated paragraph in the Method tab.
- **Current text:** “We fit one ratio on the years both ran a full season”; “the VIIRS record is used as observed”
- **Suggested text:** “We calculate one multiplier from years with May-to-September data from both selected instruments”; “the VIIRS counts are used without adjustment.” Add the formula: total VIIRS count divided by total MODIS count.

### 41. “No such flag” is ambiguous

- **Where:** Second generated paragraph in the Method tab.
- **Current text:** “The recent near-real-time rows carry no such flag and are kept.”
- **Suggested text:** “Recent rows do not include the detection-type field, so they are kept after the confidence filter is applied.”

### 42. Table headings need definitions

- **Where:** Method table.
- **Current text:** “Correlation (r)”; “Season error”; “Month error”
- **Suggested text:** “Similarity of yearly totals (Pearson r)”; “Median May–September estimation error”; “Median monthly estimation error.” Add a short explanation that 1 means the yearly totals rise and fall together exactly.

### 43. Local-ratio warning sounds more certain than the calculation

- **Where:** Generated local-ratio note.
- **Current text:** “they are probably about [percentage] too low/too high”
- **Suggested text:** “the difference between the local and province-wide multipliers suggests that the adjusted pre-VIIRS counts may be about [percentage] too low/too high.”

### 44. “Indicative” and “compress” are vague

- **Where:** Limits paragraph in the Method tab.
- **Current text:** “numbers for a small area are indicative, not exact. Fire cells compress very large fires”
- **Suggested text:** “Use small-area values to compare broad patterns, not as precise counts of individual fires. A large fire can produce many detections, but each 0.1° cell counts only once per day.”

## Footer

### 45. “As is” does not explain the practical limit

- **Where:** Last footer sentence.
- **Current text:** “Data are provided as is.”
- **Suggested text:** “The site does not verify satellite detections against official fire reports.”

## Number check against `app/data/summary.json`

The following displayed values match the summary after the rounding used by the README and app, so no wording change is needed for them: fire-cell multiplier `1.615`; hotspot multiplier `4.663`; yearly ranges `1.40–6.67` and `2.0–9.0`; season errors `15%` and `29%`; month errors `60%` and `80%`; 14 fit seasons from 2012 through 2025; VIIRS start `2012-02`; NOAA-20 start `2018-04`; and NOAA-21/NOAA-20 checks `1.03`, `1.15`, and `1.00` for 2023–2025.

The Smoke tab intentionally offers five selected CO years: `2012`, `2013`, `2018`, `2019`, and `2024`.

The app’s other live counts are calculated from `hotspots_clean.csv` or `co_monthly.json`, not from `summary.json`. They were not treated as summary mismatches unless the prose hard-coded a stale value.
