# NL Fire Calendar: demo script

Two versions:

- A. The official Space Apps video. At most 30 seconds, with English subtitles (`notes/subtitles.srt`).
- B. The live 2-minute presentation.

Speaker: Amalraj Rajesh, Basepan Space Challenge Team.

What the app does and does not do. It gives historical context: when and where satellites saw fire in the past. It does not predict fires, send alerts or confirm fires. A heat detection is not a confirmed fire.

## Numbers used (from app/data/summary.json, data through 2026-11-07)

- Record: May 2001 to Nov 2026.
- Overlap seasons used to fit the ratio: 14 (2012 to 2025).
- Ratio for fire cells: 1.615. One MODIS fire cell counts as about 1.6 VIIRS fire cells.
- Typical (median) error when each May to September total is predicted from the other seasons: 15%. For single months the error is much larger: about 60%.
- Peak month, island of Newfoundland: August 2025, 64 fire cells. The median for August in the other 14 VIIRS-era years is 2.

## How the page is laid out now

- At the top: the header, then the headline card ("Two satellite sensors count fires differently...") with three boxes: "May 2001–Nov 2026 record coverage", "14 fit seasons" and "15% season error". Below them are the buttons "Explore the calendar" and "See evidence and limits", and a closed section "About: problem, method, tour, safe use".
- Next to the headline card: the "Right now" box.
- Below: a closed section "How to read this: squares, colors, median".
- Then the tabs: Area and calendar, Compare, Smoke, Downloads, Method.
- In "Area and calendar", the calendar comes first ("1. Burning activity calendar"). Under its title is a line such as "Area: the island of Newfoundland" and a link "Change the area or dates". The area controls come second ("2. Choose an area and dates"). The "Island of Newfoundland" button is in that second card.

Leave both closed sections closed while recording.

## Before you record (both versions)

1. Open https://portalzone.github.io/nl-fire-calendar/ at 1400 px wide or more. Do a hard refresh (Ctrl+Shift+R) so you do not see an old copy.
2. Click "Explore the calendar". Click "Change the area or dates" on the calendar card. Click "Island of Newfoundland".
3. Check the line under "1. Burning activity calendar" says "Area: the island of Newfoundland". The area stays selected when you change tabs. Do not reload the page after this, or the area resets.
4. Scroll back to the top of the page.

---

## A. Official video: 30 seconds, 70 spoken words

| Time | On screen | Click | Words to say | Words |
|---|---|---|---|---|
| 0:00.0 to 0:03.5 | Top of the page: the title "Newfoundland and Labrador Fire Calendar" | None | I'm Amalraj Rajesh, from Basepan Space Challenge Team. | 8 |
| 0:03.5 to 0:12.0 | The same view. The headline card "Two satellite sensors count fires differently" with the boxes "14 fit seasons" and "15% season error" | None | Challenge: Harmonization of MODIS and VIIRS Hot Spots. MODIS is retiring; more than a decade of fire history could be lost. | 21 |
| 0:12.0 to 0:16.5 | "1. Burning activity calendar", one square per month, years 2000 to 2026, area: the island of Newfoundland | "Explore the calendar" (opens the Area and calendar tab at the calendar) | NL Fire Calendar: twenty-five years of fire history on one scale. | 11 |
| 0:16.5 to 0:22.0 | The calendar. Point at a 2009 row (MODIS, scaled) and a 2022 row (VIIRS). | None | Fire cells and one ratio from fourteen overlap seasons scale MODIS to VIIRS. | 13 |
| 0:22.0 to 0:24.5 | Smoke tab: carbon monoxide chart | "Smoke" tab | Data: NASA FIRMS and CSA MOPITT. | 6 |
| 0:24.5 to 0:30.0 | Compare tab: August 2025, 64 fire cells against a median of 2 | "Compare" tab, then "Peak month in range" | Pick an area and month for historical context. Next: every province. | 11 |

Total: 70 words in 30 seconds. Leave about half a second of silence at the end.

The app's data has about 11 years with MODIS alone (late 2000 to early 2012).

---

## B. Live presentation: 2 minutes, about 280 spoken words

Speak at a calm pace. The times are a guide.

**0:00 to 0:15. Who we are and the problem.**
Screen: top of the page: the header, the headline card and the "Right now" box.
Click: none.
Say: "Hi, I'm Amalraj Rajesh, from Basepan Space Challenge Team. Our challenge is Harmonization of MODIS and VIIRS Hot Spots. Satellites have tracked fire for over twenty years. But the record is split between two sensors, and MODIS is being retired. If we cannot compare the two, more than a decade of fire history is lost."

**0:15 to 0:35. The idea.**
Screen: the headline card with the boxes "14 fit seasons" and "15% season error".
Click: none. Point at the two boxes.
Say: "VIIRS sees smaller fires than MODIS, so it counts more. We count fire cells: a small map square with at least one detection on one day. Then we use the fourteen seasons when both sensors flew to fit one ratio. One MODIS fire cell counts as about one point six VIIRS cells."

**0:35 to 0:55. The calendar.**
Screen: "1. Burning activity calendar" for the island of Newfoundland.
Click: "Explore the calendar". The Area and calendar tab opens with the calendar at the top.
Say: "This is NL Fire Calendar. Each square is one month, from 2001 to today, on one scale. Yellow means a lot of burning. Grey means none was seen. Before 2012 the numbers are MODIS, scaled. After that they are VIIRS."

**0:55 to 1:15. Pick a month.**
Screen: Compare tab, August 2025.
Click: "Compare" tab, then "Peak month in range".
Say: "Pick a month, and we compare it with the same month in other years. August 2025 had sixty-four fire cells. The usual August has two. Fourteen of fourteen other years had fewer."

**1:15 to 1:30. Your own area and the downloads.**
Screen: Area and calendar tab, then "2. Choose an area and dates", then the Downloads tab.
Click: "Area and calendar" tab. Click "Change the area or dates" on the calendar card. In "2. Choose an area and dates", type new numbers in the latitude and longitude boxes and click "Apply area and dates", or press "Draw area on map", then drag a box on the map. Then click the "Downloads" tab.
Say: "You can choose your own area: type it, or press Draw area on map, then drag. Then download the hotspots and the monthly series as CSV, or the charts as pictures."

**1:30 to 1:42. Smoke.**
Screen: Smoke tab.
Click: "Smoke" tab.
Say: "The Smoke tab adds carbon monoxide from the Canadian Space Agency's MOPITT instrument. It is context only. It does not prove which fire caused which reading."

**1:42 to 1:55. Limits.**
Screen: Method tab.
Click: "Method" tab.
Say: "The limits. This is historical context. It does not predict fires or send alerts. A heat detection is not a confirmed fire. Season totals are within about fifteen percent. Single months are much rougher."

**1:55 to 2:00. Next.**
Screen: top of the page.
Click: scroll to the top.
Say: "Next, we want the same calendar for every province. Thank you."

Note: the area you typed in step 1:15 stays selected. If you run the demo again, click "Island of Newfoundland" again first.

---

## Screenshots (notes/screenshots/)

All four were taken from the live site https://portalzone.github.io/nl-fire-calendar/ with Playwright at 1400 px wide, on 2026-11-15 at 11:16 Newfoundland time (UTC-3:30). This was after the final carbon monoxide data and the shorter page layout went live. The browser started with an empty cache and asked for fresh files (the same as a hard refresh). The live `index.html`, `data/co_monthly.json` and `data/summary.json` were checked and are the same as on `main` (commit dd0b5ce).

- `01-right-now.png`: the header, the headline, the three proof boxes and the "Right now" box. Area: all of Newfoundland and Labrador (the page default).
- `02-calendar-island.png`: "1. Burning activity calendar" for the island of Newfoundland.
- `03-compare-month.png`: the Compare tab with August 2025 selected: 64 fire cells, median 2.
- `04-smoke.png`: the Smoke tab, island of Newfoundland selected.

Carbon monoxide years on the Smoke tab (read from the page at 11:16):

- Years drawn: 2002, 2003, and 2010 to 2024. That is 17 years ("Show all years (17)").
- No data loaded for 2004 to 2009.
- 2001 is not drawn: it has only 7 months with values, and a year needs at least 9.
- There is no carbon monoxide data for 2025 or 2026.

In screenshots 02, 03 and 04 the tab bar was set to not stick to the top, in the test browser only, so it would not cover the card. The app file was not changed.

No console errors on the live site while taking the screenshots.
