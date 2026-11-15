"""Browser tests for app/index.html, using Playwright.

Run the pipeline first so that app/data/ exists. The tests start their own small web
server for the app folder. A made-up CO file is injected so the CO panel can be tested
without the real MOPITT download.
"""
import functools
import http.server
import json
import math
import re
import threading
from pathlib import Path

import pytest

import playwright.sync_api as playwright   # fails loudly if Playwright is not installed

from conftest import require_app_data

ROOT = Path(__file__).resolve().parent.parent.parent
APP = ROOT / "app"

@pytest.fixture(autouse=True, scope="module")
def _app_data_must_exist():
    """Fail, never skip, when app/data has not been built."""
    require_app_data()


def fake_co():
    months = []
    for y in (2012, 2013):
        for m in range(1, 13):
            ok = not (y == 2012 and m == 3)
            months.append({"year": y, "month": m, "month_key": f"{y}-{m:02d}", "days_with_data": 20 if ok else 8,
                           "readings": 100, "co_total_1e18": 2.0 + 0.01 * m if ok else None,
                           "co_surface_ppbv": 130 + m if ok else None, "enough_days": ok})
    return json.dumps({"min_days": 15, "months": months})


@pytest.fixture(scope="module")
def base():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(APP))
    handler.log_message = lambda *a, **k: None
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/"
    httpd.shutdown()


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def open_tab(pg, name):
    """Open one tab of the page the way a user would: click it."""
    pg.click(f"#tab-{name}")
    assert pg.get_attribute(f"#tab-{name}", "aria-selected") == "true"


@pytest.fixture()
def page(browser, base):
    ctx = browser.new_context(viewport={"width": 1200, "height": 900}, accept_downloads=True)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.route("**/data/co_monthly.json*", lambda r: r.fulfill(status=200, content_type="application/json", body=fake_co()))
    pg.goto(base)
    pg.wait_for_selector(".cell")
    yield pg
    assert pg.errors == [], pg.errors
    ctx.close()


# ---------------------------------------------------------------- loading and calendar
def test_calendar_renders_all_months(page):
    summary = json.loads((APP / "data" / "summary.json").read_text())
    assert page.locator(".cell").count() >= 300
    assert "Fire cells" in page.inner_text("#metric")


def test_page_has_title_language_and_nasa_acknowledgment(page):
    assert page.title() and page.get_attribute("html", "lang") == "en"
    assert "NASA's Fire Information for Resource Management System" in page.inner_text("footer")


def test_challenge_brief_uses_data_backed_evidence(page):
    summary = json.loads((APP / "data" / "summary.json").read_text())
    first = min(source["first_date"] for source in summary["sources"].values())
    end = summary["coverage_end"]
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    expected_period = f"{months[int(first[5:7]) - 1]} {first[:4]}–{months[int(end[5:7]) - 1]} {end[:4]}"
    assert page.inner_text("#proofPeriod") == expected_period
    assert page.inner_text("#proofSeasons") == str(len(summary["series_rules"]["fit_years"]))
    assert page.inner_text("#proofError") == f"{round(summary['ratios']['cells']['cv_median_pct_err'])}%"
    page.click("#introMore summary")          # the introduction is closed by default
    text = page.inner_text("#challengeBrief")
    for phrase in ("MODIS", "VIIRS", "emergency responders", "historical context", "does not forecast"):
        assert phrase in text


def test_challenge_brief_links_and_tour_buttons_work(page):
    links = page.locator("header .hero-links a")
    assert links.count() == 2
    assert "/2026/challenges/modis-and-viirs-hot-spots/" in links.nth(0).get_attribute("href")
    assert "/2026/local-events/st-johns/" in links.nth(1).get_attribute("href")
    page.click("#briefMethod")
    assert page.is_visible("#panel-method") and page.evaluate("location.hash") == "#method"
    page.click("#briefExplore")
    assert page.is_visible("#panel-area") and page.evaluate("location.hash") == "#area"


def test_zero_months_never_show_a_dot(page):
    zero_with_dot = page.locator(".cell.zero .flag").count()
    assert zero_with_dot == 0


# ---------------------------------------------------------------- keyboard
def test_one_tab_stop_in_the_calendar(page):
    assert page.locator(".cell[tabindex='0']").count() == 1


def test_arrow_keys_move_focus_and_enter_keeps_focus(page):
    page.locator(".cell[tabindex='0']").focus()
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    assert "cell" in page.evaluate("document.activeElement.className")
    assert page.locator(".cell[aria-pressed='true']").count() == 1


def test_selected_month_updates_comparison_panel(page):
    open_tab(page, "compare")
    page.click("#selComplete")
    assert "other" in page.inner_text("#cmp") and "VIIRS-era" in page.inner_text("#cmp")


# ---------------------------------------------------------------- comparison wording
def test_low_counts_give_no_verdict(page):
    open_tab(page, "compare")
    page.click("#selLatest")      # Nov 1-7: zero cells
    text = page.inner_text("#cmp")
    assert "typical" in text.lower() or "no verdict" in text.lower() or "too few" in text.lower()
    assert "Well above" not in text


def test_wording_says_other_years_not_earlier_years(page):
    open_tab(page, "compare")
    page.click("#selComplete")
    assert "earlier" not in page.inner_text("#cmp")


# ---------------------------------------------------------------- inputs: equivalence classes and boundaries
def set_dates(pg, start=None, end=None):
    """Type dates and press Apply, the way a user would."""
    if start is not None:
        pg.fill("#start", start)
    if end is not None:
        pg.fill("#end", end)
    pg.click("#apply")


def use_text_fallback(pg):
    """Desktop Safari and Firefox show a plain text box instead of a month picker. Do the same here."""
    pg.evaluate("for (const id of ['start', 'end']) document.getElementById(id).type = 'text'")
    assert pg.get_attribute("#start", "type") == "text"


def applied_range(pg):
    return pg.evaluate("[idxToStr(state.startIdx), idxToStr(state.endIdx)]")


@pytest.mark.parametrize("bad", ["April 2018", "04/2018", "2018-13", "2018-00", "", "abcd-ef", "2018-4"])
def test_bad_date_strings_show_a_message_and_keep_the_last_good_dates(page, bad):
    use_text_fallback(page)
    before = applied_range(page)
    set_dates(page, start=bad)
    assert "Use the form YYYY-MM" in page.inner_text("#startErr")
    assert page.get_attribute("#start", "aria-invalid") == "true"
    assert applied_range(page) == before
    assert page.locator(".cell").count() >= 300


def test_dates_outside_the_record_are_rejected(page):
    set_dates(page, start="1990-01")
    assert "Allowed: 2000-11 to 2026-11" in page.inner_text("#startErr")
    assert applied_range(page) == ["2000-11", "2026-11"]


def test_start_after_end_is_rejected_with_a_message(page):
    set_dates(page, start="2020-06", end="2019-06")
    assert "start month is after the end month" in page.inner_text("#startErr")
    assert page.get_attribute("#start", "aria-invalid") == "true"
    assert applied_range(page) == ["2000-11", "2026-11"]


@pytest.mark.parametrize("field,value,fragment", [
    ("latMax", "", "Fill in all four"),
    ("latMax", "5000", "Latitude must be between"),
    ("lonMin", "58", "Longitude must be negative"),
    ("latMin", "60", "South must be below north"),
])
def test_bad_area_values_give_a_message(page, field, value, fragment):
    page.fill(f"#{field}", value)
    page.click("#apply")
    assert fragment in page.inner_text("#msg")


def test_valid_area_changes_the_detection_count(page):
    full = page.inner_text("#areasummary")
    page.click("#island")
    assert page.inner_text("#areasummary") != full
    page.click("#reset")
    assert page.inner_text("#areasummary") == full


def test_island_button_fills_the_boxes(page):
    page.click("#island")
    assert page.input_value("#latMin") == "46.40" and page.input_value("#lonMax") == "-52.40"


# ---------------------------------------------------------------- downloads
def test_hotspot_download_row_count_matches_the_page(page):
    page.click("#island")
    shown = int(page.inner_text("#areasummary").split("°W.")[1].split("cleaned")[0].replace(",", "").strip())
    open_tab(page, "downloads")
    with page.expect_download() as d:
        page.click("#dlHot")
    lines = Path(d.value.path()).read_text().strip().splitlines()
    assert len(lines) - 1 == shown
    assert lines[0].startswith("date,")


def test_series_download_has_area_and_era_columns(page):
    open_tab(page, "downloads")
    with page.expect_download() as d:
        page.click("#dlSeries")
    head = Path(d.value.path()).read_text().splitlines()[0].split(",")
    for c in ("area_south", "area_north", "era", "partial_month", "terra_only", "count_type"):
        assert c in head


# ---------------------------------------------------------------- CO panel
def test_co_panel_shows_one_chart_per_year(page):
    open_tab(page, "smoke")
    assert page.is_visible("#coCard") and page.locator("#coChart > div").count() == 2


def test_co_panel_lists_months_left_out(page):
    open_tab(page, "smoke")
    assert "Mar 2012 (8 days)" in page.inner_text("#coNote")


def test_co_panel_warns_when_area_is_not_the_island(page):
    open_tab(page, "smoke")
    assert "not the island" in page.inner_text("#coNote")
    open_tab(page, "area")
    page.click("#island")
    open_tab(page, "smoke")
    assert "not the island" not in page.inner_text("#coNote")


def test_co_table_matches_the_data(page):
    open_tab(page, "smoke")
    page.click("#coCard summary")
    assert "2.01" in page.inner_text("#coTable") and "–" in page.inner_text("#coTable")


def test_co_measure_switch(page):
    open_tab(page, "smoke")
    page.select_option("#coMeasure", "co_surface_ppbv")
    assert "ppbv" in page.text_content("#coTable")
    assert "ppbv" in page.locator("#coChart circle title").first.text_content()


def test_page_works_without_co_file(browser, base):
    pg = browser.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.route("**/data/co_monthly.json*", lambda r: r.fulfill(status=404, body="no"))
    pg.goto(base)
    pg.wait_for_selector(".cell")
    assert pg.evaluate("document.getElementById('coCard').hidden") and errors == []
    pg.close()


def test_co_file_with_only_empty_values_hides_the_panel(browser, base):
    pg = browser.new_page()
    pg.route("**/data/co_monthly.json*", lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"months": [{"year": 2013, "month": 1, "co_total_1e18": None, "co_surface_ppbv": None, "days_with_data": 3}]})))
    pg.goto(base)
    pg.wait_for_selector(".cell")
    assert pg.evaluate("document.getElementById('coCard').hidden")
    pg.close()


# ---------------------------------------------------------------- phone
def test_no_sideways_scroll_on_a_phone(browser, base):
    ctx = browser.new_context(viewport={"width": 390, "height": 800}, has_touch=True)
    pg = ctx.new_page()
    pg.route("**/data/co_monthly.json*", lambda r: r.fulfill(status=200, content_type="application/json", body=fake_co()))
    pg.goto(base)
    pg.wait_for_selector(".cell")
    assert pg.evaluate("document.documentElement.scrollWidth") <= 390
    ctx.close()


def test_touch_drawing_is_off_until_switched_on(page):
    assert page.get_attribute("#drawmode", "aria-pressed") == "false"
    page.click("#drawmode")
    assert page.get_attribute("#drawmode", "aria-pressed") == "true"
    assert "draw" in page.get_attribute("#map", "class")


# ---------------------------------------------------------------- method text
def test_method_text_has_no_unsupported_claims(page):
    open_tab(page, "method")
    text = page.inner_text("#method")
    assert "only presumed vegetation" not in text.lower()
    assert "agrees" not in text.lower()
    assert "Yearly ratio range" in text and "Month error" in text


def test_validation_chart_has_alt_text(page):
    assert len(page.get_attribute("img", "alt")) > 20


# ---------------------------------------------------------------- challenge requirements added late
def test_right_now_card_gives_a_plain_verdict_first(page):
    text = page.inner_text("#now")
    assert "Data through" in text and "usual" in text
    assert any(w in text for w in ("typical", "highest", "Above", "Below", "too few", "No verdict", "no verdict"))
    # the card sits above the area controls
    assert page.evaluate("document.querySelector('#nowCard').getBoundingClientRect().top < document.querySelector('#start').getBoundingClientRect().top")


def test_right_now_card_names_the_area(page):
    assert "all of Newfoundland and Labrador" in page.inner_text("#now")
    page.click("#island")
    assert "island of Newfoundland" in page.inner_text("#now")


def test_how_to_read_box_explains_fire_cells_median_and_error(page):
    page.click("#howDetails summary")         # "How to read this" is closed by default
    text = page.inner_text("#howDetails")
    assert "fire cells" in text and "median" in text and "multi-year baseline" in text
    summary = json.loads((APP / "data" / "summary.json").read_text())
    cells = round(summary["ratios"]["cells"]["cv_median_pct_err"])
    hot = round(summary["ratios"]["hotspots"]["cv_median_pct_err"])
    assert f"error is {cells}% with fire cells and {hot}% with raw hotspots" in text
    assert "not a confirmed fire" in text


def test_subtitle_does_not_claim_data_from_before_the_first_detection(page):
    sub = page.inner_text("#subtitle")
    assert "first detection" in sub and "2001" in sub


def test_calendar_png_download_is_a_real_picture(page):
    open_tab(page, "downloads")
    with page.expect_download() as d:
        page.click("#dlPng")
    path = Path(d.value.path())
    assert d.value.suggested_filename.endswith(".png")
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) > 10_000
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    assert width > 800 and height > 600


def test_calendar_png_respects_the_selected_date_range(page):
    set_dates(page, start="2020-01", end="2021-12")
    open_tab(page, "downloads")
    with page.expect_download() as d:
        page.click("#dlPng")
    assert "2020-01_2021-12" in d.value.suggested_filename
    data = Path(d.value.path()).read_bytes()
    assert int.from_bytes(data[20:24], "big") < 900     # two year rows are much shorter than the full calendar


@pytest.mark.parametrize("button,name", [("#dlAnnualSvg", "nl_fire_yearly_totals.svg"), ("#dlMonthSvg", "nl_fire_month_comparison.svg")])
def test_chart_svg_downloads_are_valid_standalone_files(page, button, name):
    open_tab(page, "downloads")
    with page.expect_download() as d:
        page.click(button)
    assert d.value.suggested_filename == name
    text = Path(d.value.path()).read_text()
    assert text.startswith("<?xml") and 'xmlns="http://www.w3.org/2000/svg"' in text and "<rect" in text


def test_validation_chart_can_be_downloaded(page):
    open_tab(page, "downloads")
    assert page.get_attribute("#dlValid", "download") == "nl_fire_validation.png"
    assert (APP / "data" / "validation.png").exists()


def test_local_ratio_check_follows_the_selected_area(page):
    open_tab(page, "method")
    all_nl = page.inner_text("#localratio")
    assert "local ratio" in all_nl and "whole province" in all_nl
    open_tab(page, "area")
    page.click("#island")
    open_tab(page, "method")
    assert page.inner_text("#localratio") != all_nl


def test_local_ratio_for_an_area_with_no_modis_fires_is_explained(page):
    for f, v in (("latMax", "40.5"), ("latMin", "40"), ("lonMin", "-30"), ("lonMax", "-29")):
        page.fill(f"#{f}", v)
    page.click("#apply")
    open_tab(page, "method")
    assert "cannot be computed" in page.inner_text("#localratio")


def test_limits_name_what_is_not_included(page):
    open_tab(page, "method")
    text = page.inner_text("#method")
    assert "Not included" in text and "reported by agencies" in text and "single fires" in text


def test_csa_credit_is_complete_and_has_no_placeholder(page):
    html = (APP / "index.html").read_text()
    assert "TODO" not in html
    foot = page.inner_text("footer")
    assert "Open Government Licence" in foot and "Canadian Space Agency" in foot and "MOPITT" in foot


def _contrast(a, b):
    def lum(c):
        f = [v / 255 for v in c]
        f = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in f]
        return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _rgb(css):
    return [int(float(x)) for x in re.findall(r"[\d.]+", css)[:3]]


def test_zero_month_cells_have_a_border_of_at_least_3_to_1(page):
    border = _rgb(page.evaluate("getComputedStyle(document.querySelector('.cell.zero')).borderTopColor"))
    assert _contrast(border, (255, 255, 255)) >= 3      # against the white card
    assert _contrast(border, (236, 239, 241)) >= 3 - 0.6  # and still visible against the grey fill


def test_selected_month_has_a_black_and_white_double_ring(page):
    open_tab(page, "compare")
    page.click("#selComplete")
    open_tab(page, "area")
    shadow = page.evaluate("getComputedStyle(document.querySelector('.cell.sel')).boxShadow")
    assert shadow.count("inset") == 2
    assert "rgb(0, 0, 0)" in shadow and "rgb(255, 255, 255)" in shadow


@pytest.mark.parametrize("cell_colour", ["#440154", "#1f9e89", "#35b779", "#fde725", "#eceff1"])
def test_selected_ring_is_visible_on_every_cell_colour(cell_colour):
    """One of the two rings (black or white) must reach 3:1 on every calendar colour."""
    c = [int(cell_colour[i:i + 2], 16) for i in (1, 3, 5)]
    assert max(_contrast(c, (0, 0, 0)), _contrast(c, (255, 255, 255))) >= 3


def test_right_now_card_shows_coordinates_for_a_drawn_box(page):
    for f, v in (("latMax", "50"), ("latMin", "48"), ("lonMin", "-58"), ("lonMax", "-54")):
        page.fill(f"#{f}", v)
    page.click("#apply")
    text = page.inner_text("#now")
    assert "48.0 to 50.0°N" in text and "58.0 to 54.0°W" in text
    assert "multi-year baseline" in text and "other" in text and "earlier" not in text


def test_right_now_numbers_match_the_comparison_panel(page):
    open_tab(page, "compare")
    page.click("#selLatest")
    now = page.inner_text("#now")
    cmp_text = page.inner_text("#cmp")
    verdict = page.inner_text("#now p b")
    assert verdict in cmp_text
    assert page.inner_text("#now .stat .big >> nth=1") == page.inner_text("#cmp .stat b >> nth=1")


def test_subtitle_first_detection_comes_from_the_data(page):
    rows = (APP / "data" / "hotspots_clean.csv").read_text().splitlines()[1:]
    first = min(r.split(",")[0] for r in rows)
    month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][int(first[5:7]) - 1]
    assert f"first detection in the province: {month} {first[:4]}" in page.inner_text("#subtitle")


def test_local_ratio_matches_an_independent_count_for_the_island(page):
    """Recount fire cells on the island from the CSV, with the same fit seasons and sensors."""
    summary = json.loads((APP / "data" / "summary.json").read_text())
    years = set(summary["series_rules"]["fit_years"])
    n20_from = summary["series_rules"]["noaa20_from"]
    seen, v, m = set(), 0, 0
    rows = (APP / "data" / "hotspots_clean.csv").read_text().splitlines()
    head = rows[0].split(",")
    i_d, i_la, i_lo, i_s = (head.index(c) for c in ("date", "latitude", "longitude", "source"))
    for line in rows[1:]:
        f = line.split(",")
        d, la, lo, src = f[i_d], float(f[i_la]), float(f[i_lo]), f[i_s]
        if not (46.4 <= la <= 51.9 and -59.7 <= lo <= -52.4) or int(d[:4]) not in years or not 5 <= int(d[5:7]) <= 9:
            continue
        use_viirs = "n20" if d[:7] >= n20_from else "snpp"
        if src not in ("modis", use_viirs):
            continue
        key = (src, math.floor(la / 0.1), math.floor(lo / 0.1), d)
        if key in seen:
            continue
        seen.add(key)
        if src == "modis":
            m += 1
        else:
            v += 1
    k_local, k_prov = v / m, summary["ratios"]["cells"]["k"]
    page.click("#island")
    open_tab(page, "method")
    text = page.inner_text("#localratio")
    assert f"local ratio of {k_local:.2f}" in text and f"{k_prov:.2f} for the whole province" in text
    assert f"about {round(100 * (1 - k_prov / k_local))}% too low" in text      # island ratio is higher


def test_local_ratio_says_nothing_extra_when_close_to_the_province(page):
    # all of NL: the local ratio is the province ratio, so no correction sentence
    open_tab(page, "method")
    text = page.inner_text("#localratio")
    assert "too low" not in text and "too high" not in text


def test_local_ratio_follows_the_count_type(page):
    open_tab(page, "method")
    cells = page.inner_text("#localratio")
    open_tab(page, "area")
    page.select_option("#metric", "hotspots")
    open_tab(page, "method")
    assert page.inner_text("#localratio") != cells and "hotspots" in page.inner_text("#localratio")


def test_no_hard_coded_regional_ratios_in_the_page():
    html = (APP / "index.html").read_text()
    assert "1.4 in Labrador" not in html and "2.9 on the island" not in html and "2.3 on the island" not in html


def test_png_has_no_text_cut_off_and_matches_the_range(page):
    set_dates(page, start="2025-01")
    open_tab(page, "downloads")
    with page.expect_download() as d:
        page.click("#dlPng")
    data = Path(d.value.path()).read_bytes()
    width = int.from_bytes(data[16:20], "big") // 2       # drawn at 2x
    # the widest line drawn on the picture must fit inside it
    widest = page.evaluate("""() => { const c = document.createElement('canvas').getContext('2d');
        c.font = '13px system-ui,Helvetica,Arial,sans-serif';
        const lines = ['Dashed outline: partial month. Striped: before July 2002 (Terra only). Grey: none detected.'];
        c.font = '11px system-ui,Helvetica,Arial,sans-serif';
        lines.push('Data: NASA FIRMS, MODIS and VIIRS active fire detections (https://earthdata.nasa.gov/firms). Merged by the NL Fire Calendar.');
        return Math.max(...lines.map(l => c.measureText(l).width)); }""")
    assert widest + 16 < width


def test_downloads_use_the_selected_area(page):
    for f, v in (("latMax", "50"), ("latMin", "48"), ("lonMin", "-58"), ("lonMax", "-54")):
        page.fill(f"#{f}", v)
    page.click("#apply")
    open_tab(page, "downloads")
    with page.expect_download() as d:
        page.click("#dlMonthSvg")
    assert "<rect" in Path(d.value.path()).read_text()
    assert page.evaluate("document.querySelector('#dlValid').getAttribute('href')") == "data/validation.png"


# ---------------------------------------------------------------- tabs
TABS = ["area", "compare", "smoke", "downloads", "method"]


def test_tabs_use_the_standard_pattern(page):
    assert page.get_attribute("#tablist", "role") == "tablist"
    for t in TABS:
        assert page.get_attribute(f"#tab-{t}", "role") == "tab"
        assert page.get_attribute(f"#tab-{t}", "aria-controls") == f"panel-{t}"
        assert page.get_attribute(f"#panel-{t}", "role") == "tabpanel"
        assert page.get_attribute(f"#panel-{t}", "aria-labelledby") == f"tab-{t}"
    # the default tab is "Area and calendar"; only it is open and only it is a tab stop
    assert page.get_attribute("#tab-area", "aria-selected") == "true"
    assert page.locator("[role=tab][tabindex='0']").count() == 1
    assert page.locator("[role=tabpanel]:not([hidden])").count() == 1


def test_right_now_and_how_to_read_stay_visible_in_every_tab(page):
    for t in TABS:
        open_tab(page, t)
        assert page.is_visible("#nowCard") and page.is_visible("#h-how")


def test_arrow_home_end_move_between_tabs_and_enter_opens(page):
    page.focus("#tab-area")
    page.keyboard.press("ArrowRight")
    assert page.evaluate("document.activeElement.id") == "tab-compare"
    assert page.get_attribute("#tab-area", "aria-selected") == "true"      # moving does not open
    page.keyboard.press("End")
    assert page.evaluate("document.activeElement.id") == "tab-method"
    page.keyboard.press("ArrowRight")                                         # wraps to the first
    assert page.evaluate("document.activeElement.id") == "tab-area"
    page.keyboard.press("ArrowLeft")                                          # wraps to the last
    assert page.evaluate("document.activeElement.id") == "tab-method"
    page.keyboard.press("Home")
    assert page.evaluate("document.activeElement.id") == "tab-area"
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    assert page.get_attribute("#tab-smoke", "aria-selected") == "true" and page.is_visible("#panel-smoke")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Space")
    assert page.get_attribute("#tab-downloads", "aria-selected") == "true"
    assert page.locator("[role=tab][tabindex='0']").count() == 1


def test_hidden_panels_are_not_reachable_with_tab(page):
    hidden_ids = page.evaluate("""() => [...document.querySelectorAll('[role=tabpanel][hidden] button, [role=tabpanel][hidden] a, [role=tabpanel][hidden] select, [role=tabpanel][hidden] input')].map(e => e.id)""")
    assert "dlPng" in hidden_ids and "coMeasure" in hidden_ids
    reached = set()
    for _ in range(60):
        page.keyboard.press("Tab")
        reached.add(page.evaluate("document.activeElement.id"))
    assert not reached & set(hidden_ids)
    assert page.evaluate("getComputedStyle(document.getElementById('panel-smoke')).display") == "none"


def test_opening_a_tab_puts_it_in_the_address_and_back_works(page):
    open_tab(page, "smoke")
    assert page.evaluate("location.hash") == "#smoke"
    open_tab(page, "method")
    assert page.evaluate("location.hash") == "#method"
    page.go_back()
    page.wait_for_function("document.getElementById('tab-smoke').getAttribute('aria-selected') === 'true'")
    assert page.is_visible("#panel-smoke") and not page.is_visible("#panel-method")
    page.go_back()
    page.wait_for_function("document.getElementById('tab-area').getAttribute('aria-selected') === 'true'")


@pytest.mark.parametrize("tab", TABS)
def test_deep_link_opens_that_tab(browser, base, tab):
    pg = browser.new_page()
    pg.route("**/data/co_monthly.json*", lambda r: r.fulfill(status=200, content_type="application/json", body=fake_co()))
    pg.goto(base + "#" + tab)
    pg.wait_for_selector(".cell", state="attached")
    assert pg.get_attribute(f"#tab-{tab}", "aria-selected") == "true" and pg.is_visible(f"#panel-{tab}")
    pg.close()


@pytest.mark.parametrize("bad", ["#nothing", "#", "#panel-smoke", "#SMOKE"])
def test_unknown_address_opens_the_default_tab(browser, base, bad):
    pg = browser.new_page()
    pg.goto(base + bad)
    pg.wait_for_selector(".cell")
    assert pg.get_attribute("#tab-area", "aria-selected") == "true"
    pg.close()


@pytest.mark.parametrize("button", ["#nowDetails", "#selLatest", "#selComplete", "#selPeak"])
def test_buttons_open_the_compare_tab_and_scroll_to_it(page, button):
    if button != "#nowDetails":
        open_tab(page, "compare")
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.click(button)
    assert page.get_attribute("#tab-compare", "aria-selected") == "true"
    top = page.evaluate("document.getElementById('panel-compare').getBoundingClientRect().top")
    assert -5 <= top <= 200
    assert "other" in page.inner_text("#cmp")


def test_peak_month_result_is_shown_in_compare(page):
    open_tab(page, "compare")
    page.click("#selPeak")
    assert page.inner_text("#cmp").startswith("Jun 2012")


def test_switching_tabs_keeps_area_dates_count_and_month(page):
    page.click("#island")
    set_dates(page, start="2010-01")
    page.select_option("#metric", "hotspots")
    page.click("#heat button[aria-label^='Jun 2012:']")
    before = page.evaluate("JSON.stringify([state.bbox, state.startIdx, state.endIdx, state.metric, state.sel])")
    for t in ["compare", "smoke", "downloads", "method", "area"]:
        open_tab(page, t)
    assert page.evaluate("JSON.stringify([state.bbox, state.startIdx, state.endIdx, state.metric, state.sel])") == before
    assert page.input_value("#start") == "2010-01" and page.input_value("#metric") == "hotspots"
    assert page.get_attribute("#heat button[aria-label^='Jun 2012:']", "aria-pressed") == "true"


def test_map_is_drawn_when_its_tab_is_opened_from_a_deep_link(browser, base):
    pg = browser.new_page(viewport={"width": 1200, "height": 900})
    pg.goto(base + "#method")
    pg.wait_for_selector(".cell", state="attached")
    pg.click("#tab-area")
    width = pg.evaluate("document.getElementById('map').clientWidth")
    canvas_w = pg.evaluate("document.getElementById('map').width")
    assert width > 300 and abs(canvas_w - width * pg.evaluate("devicePixelRatio")) < 2
    # some pixels have been painted
    painted = pg.evaluate("""() => { const c = document.getElementById('map'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
        let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++; return n; }""")
    assert painted > 1000
    pg.close()


def test_charts_are_drawn_when_their_tab_is_opened(browser, base):
    pg = browser.new_page(viewport={"width": 1200, "height": 900})
    pg.route("**/data/co_monthly.json*", lambda r: r.fulfill(status=200, content_type="application/json", body=fake_co()))
    pg.goto(base)
    pg.wait_for_selector(".cell")
    pg.click("#tab-compare")
    assert pg.evaluate("document.querySelector('#annual svg').getBoundingClientRect().width") > 300
    assert pg.locator("#annual rect").count() > 20 and pg.locator("#cmp svg rect").count() > 5
    pg.click("#tab-smoke")
    assert pg.evaluate("document.querySelector('#coChart svg').getBoundingClientRect().width") > 150
    assert pg.evaluate("document.querySelector('#coBig svg').getBoundingClientRect().width") > 300
    pg.close()


def test_tab_bar_on_a_phone_scrolls_inside_its_box_and_text_is_large_enough(browser, base):
    ctx = browser.new_context(viewport={"width": 390, "height": 800}, has_touch=True, is_mobile=True)
    pg = ctx.new_page()
    pg.goto(base)
    pg.wait_for_selector(".cell")
    assert pg.evaluate("document.documentElement.scrollWidth") <= 390
    # the tab labels wrap onto two rows, so every tab is inside the bar without scrolling
    for t in TABS:
        left, right, bl, br = tab_inside_bar(pg, t)
        assert left >= bl - 0.5 and right <= br + 0.5, t
    for t in TABS:
        assert float(pg.evaluate(f"getComputedStyle(document.getElementById('tab-{t}')).fontSize").replace("px", "")) >= 14
        pg.click(f"#tab-{t}")
        assert pg.evaluate("document.documentElement.scrollWidth") <= 390, t
    ctx.close()


def test_tab_focus_outline_is_visible_with_3_to_1_contrast(page):
    page.focus("#tab-area")
    page.keyboard.press("ArrowRight")           # keyboard focus, so :focus-visible applies
    style = page.evaluate("(() => { const s = getComputedStyle(document.activeElement); return [s.outlineStyle, s.outlineWidth, s.outlineColor]; })()")
    assert style[0] == "solid" and float(style[1].replace("px", "")) >= 2
    outline = _rgb(style[2])
    for bg in ((230, 234, 239), (255, 255, 255), (246, 247, 249)):    # tab, open tab, page
        assert _contrast(outline, bg) >= 3


# ---------------------------------------------------------------- browser tab: favicon and title
def test_favicon_is_an_inline_svg_and_title_is_meaningful(page):
    href = page.get_attribute("link[rel=icon]", "href")
    assert href.startswith("data:image/svg+xml,") and "<svg" in __import__("urllib.parse").parse.unquote(href)
    assert page.get_attribute("link[rel=icon]", "type") == "image/svg+xml"
    assert page.title() == "NL Fire Calendar"


def test_page_makes_no_outside_requests(browser, base):
    pg = browser.new_page()
    urls = []
    pg.on("request", lambda r: urls.append(r.url))
    pg.goto(base)
    pg.wait_for_selector(".cell")
    assert all(u.startswith(base) or u.startswith("data:") or u.startswith("blob:") for u in urls), urls
    pg.close()


# ---------------------------------------------------------------- wide screens
@pytest.mark.parametrize("width", [1400, 2000, 3450])
def test_main_column_is_centered_with_no_sideways_scroll(browser, base, width):
    pg = browser.new_page(viewport={"width": width, "height": 1000})
    pg.goto(base)
    pg.wait_for_selector(".cell")
    box = pg.evaluate("(() => { const r = document.querySelector('main').getBoundingClientRect(); return [r.left, innerWidth - r.right, r.width]; })()")
    assert abs(box[0] - box[1]) <= 2 and box[2] <= 1200
    assert pg.evaluate("document.documentElement.scrollWidth") <= width
    pg.close()


# ---------------------------------------------------------------- compact CO panel
def co_years(n, last=2025, short=None):
    """n years of made-up CO data ending in `last`. short = {year: months with values}."""
    short = short or {}
    months = []
    for y in range(last - n + 1, last + 1):
        keep = short.get(y, 12)
        for m in range(1, 13):
            ok = m <= keep
            months.append({"year": y, "month": m, "month_key": f"{y}-{m:02d}", "days_with_data": 22 if ok else 5,
                           "readings": 100, "co_total_1e18": 2.0 + 0.01 * ((m * 7 + y) % 5) if ok else None,
                           "co_surface_ppbv": 130 + (m * 3 + y) % 9 if ok else None, "enough_days": ok})
    return json.dumps({"min_days": 15, "months": months})


def co_page(browser, base, body, width=1400, height=900):
    ctx = browser.new_context(viewport={"width": width, "height": height}, has_touch=width < 500, is_mobile=width < 500)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.route("**/data/co_monthly.json*", lambda r: r.fulfill(status=200, content_type="application/json", body=body))
    pg.goto(base + "#smoke")
    pg.wait_for_selector("#coChart svg")
    return ctx, pg


def drawn_years(pg):
    return [int(h) for h in pg.eval_on_selector_all("#coChart h3", "els => els.map(e => e.textContent)")]


@pytest.mark.parametrize("n", [13, 25])
def test_co_default_shows_the_8_most_recent_years_and_show_all_shows_every_year(browser, base, n):
    ctx, pg = co_page(browser, base, co_years(n))
    assert drawn_years(pg) == list(range(2025, 2017, -1))
    assert pg.get_attribute("#coMore", "aria-expanded") == "false"
    pg.click("#coMore")
    assert drawn_years(pg) == list(range(2025, 2025 - n, -1))
    assert pg.inner_text("#coMore") == "Show fewer" and pg.get_attribute("#coMore", "aria-expanded") == "true"
    pg.click("#coMore")
    assert len(drawn_years(pg)) == 8
    assert pg.errors == []
    ctx.close()


@pytest.mark.parametrize("n,button_shown", [(7, False), (8, False), (9, True)])
def test_co_show_all_button_only_when_there_are_more_than_8_years(browser, base, n, button_shown):
    ctx, pg = co_page(browser, base, co_years(n))
    assert len(drawn_years(pg)) == min(n, 8)
    assert pg.is_visible("#coMore") == button_shown
    ctx.close()


def test_co_grid_has_4_per_row_on_desktop_and_2_on_a_phone(browser, base):
    for width, per_row in ((1400, 4), (390, 2)):
        ctx, pg = co_page(browser, base, co_years(13), width=width)
        tops = pg.eval_on_selector_all("#coChart > div", "els => els.map(e => Math.round(e.getBoundingClientRect().top))")
        assert tops.count(tops[0]) == per_row, (width, tops)
        assert pg.evaluate("document.documentElement.scrollWidth") <= width
        ctx.close()


def test_co_panel_is_shorter_than_two_screens_by_default(browser, base):
    ctx, pg = co_page(browser, base, co_years(25), height=900)
    assert pg.evaluate("document.getElementById('coCard').offsetHeight") < 2 * 900
    ctx.close()


def test_co_year_picker_works_with_the_keyboard(browser, base):
    ctx, pg = co_page(browser, base, co_years(13))
    assert pg.input_value("#coYear") == "2025"
    pg.focus("#coYear")
    # typing the year picks it on every platform (on macOS the arrow keys open the native list instead)
    pg.keyboard.type("2024")
    pg.wait_for_function("document.querySelector('#coBig h3').textContent.startsWith('2024')")
    assert pg.locator("#coBig svg circle").count() == 12
    assert "%" in pg.inner_text("#coBig") or pg.locator("#coBig svg text").count() >= 12
    label = pg.get_attribute("#coBig svg", "aria-label")
    assert "2024" in label and "percent above or below that year's own average" in label and "molecules/cm²" in label
    ctx.close()


@pytest.mark.parametrize("months,drawn", [(8, False), (9, True), (12, True), (0, False)])
def test_co_year_needs_9_months_to_be_drawn(browser, base, months, drawn):
    ctx, pg = co_page(browser, base, co_years(3, short={2024: months}))
    assert (2024 in drawn_years(pg)) == drawn
    assert ("2024" in pg.eval_on_selector_all("#coYear option", "els => els.map(e => e.value)")) == drawn
    note = pg.inner_text("#coNote")
    if drawn:
        assert "2024: only" not in note
    else:
        assert f"2024: only {months} month" in note
    ctx.close()


def test_co_table_keeps_every_year_and_scrolls_inside_its_box(browser, base):
    ctx, pg = co_page(browser, base, co_years(25, short={2010: 7}), width=390)
    pg.click("#coCard summary")
    heads = pg.eval_on_selector_all("#coTable tr:first-child th[colspan]", "els => els.map(e => e.textContent)")
    assert heads == [str(y) for y in range(2001, 2026)]                     # all 25, including the 7-month year
    box = pg.evaluate("(() => { const b = document.getElementById('coTable'); return [b.scrollWidth, b.clientWidth, getComputedStyle(b).overflowX]; })()")
    assert box[0] > box[1] and box[2] == "auto"
    assert pg.evaluate("getComputedStyle(document.querySelector('#coTable tr th')).position") == "sticky"
    assert pg.evaluate("document.documentElement.scrollWidth") <= 390
    ctx.close()


@pytest.mark.parametrize("width", [390, 1400])
def test_co_chart_text_is_at_least_9_px(browser, base, width):
    ctx, pg = co_page(browser, base, co_years(13), width=width)
    sizes = pg.evaluate("""() => [...document.querySelectorAll('#panel-smoke svg text')].map(t => {
        const svg = t.ownerSVGElement; return parseFloat(getComputedStyle(t).fontSize) * svg.getBoundingClientRect().width / svg.viewBox.baseVal.width; })""")
    assert sizes and min(sizes) >= 9
    ctx.close()


def test_co_keeps_honesty_notes(browser, base):
    ctx, pg = co_page(browser, base, co_years(13))
    note = pg.inner_text("#coNote")
    assert "percent above or below that year's own average" in note
    assert "V18" in note and "V20" in note
    assert "nearby sea" in note
    assert "%" in pg.inner_text("#coScale")
    ctx.close()


def test_co_file_with_bad_shape_does_not_break_the_page(browser, base):
    for body in ('{"months": "oops"}', "[]", '{"months": [{"year": 2020, "month": 1}]}'):
        pg = browser.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.route("**/data/co_monthly.json*", functools.partial(lambda b, r: r.fulfill(status=200, content_type="application/json", body=b), body))
        pg.goto(base + "#smoke")
        pg.wait_for_selector(".cell", state="attached")
        assert errors == [] and pg.is_visible("#coNone")
        pg.close()


# ---------------------------------------------------------------- downloads still work from their tab
@pytest.mark.parametrize("button,ending", [("#dlPng", ".png"), ("#dlAnnualSvg", ".svg"), ("#dlMonthSvg", ".svg")])
def test_picture_downloads_work_from_the_downloads_tab_opened_first(browser, base, button, ending):
    pg = browser.new_page(accept_downloads=True)
    pg.goto(base + "#downloads")
    pg.wait_for_selector(".cell", state="attached")
    with pg.expect_download() as d:
        pg.click(button)
    data = Path(d.value.path()).read_bytes()
    assert d.value.suggested_filename.endswith(ending) and len(data) > 500
    if ending == ".svg":
        assert b"<rect" in data and b'viewBox="0 0 0' not in data
    pg.close()


def test_click_on_the_calendar_right_after_typing_a_date_is_not_lost(page):
    page.fill("#start", "2010-01")          # typed but not applied yet; leaving the box must not rebuild the grid
    page.click("#heat button[aria-label^='Jun 2012:']")      # moving focus fires "change" again
    assert page.evaluate("state.sel") == {"y": 2012, "m": 6, "maxDay": 31}


# ---------------------------------------------------------------- phone: tab bar and map after a tap
def phone_page(browser, base, address=""):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, device_scale_factor=2)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.route("**/data/co_monthly.json*", lambda r: r.fulfill(status=200, content_type="application/json", body=fake_co()))
    pg.goto(base + address)
    pg.wait_for_selector(".cell", state="attached")
    return ctx, pg


def tab_inside_bar(pg, name):
    """Left and right edges of the tab, and of the tab bar's visible box."""
    return pg.evaluate(f"""() => {{ const t = document.getElementById('tab-{name}').getBoundingClientRect(),
        b = document.getElementById('tablist').getBoundingClientRect();
        return [t.left, t.right, b.left, b.right]; }}""")


def map_painted(pg):
    return pg.evaluate("""() => { const c = document.getElementById('map');
        if (!c.width || !c.clientWidth) return 0;
        const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
        let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++; return n; }""")


def test_phone_tab_bar_starts_at_the_left_on_load(browser, base):
    ctx, pg = phone_page(browser, base)
    assert pg.evaluate("document.getElementById('tablist').scrollLeft") == 0
    left, right, bl, br = tab_inside_bar(pg, "area")
    assert left >= bl - 0.5 and right <= br + 0.5
    ctx.close()


@pytest.mark.parametrize("how", ["tap", "keyboard", "link"])
@pytest.mark.parametrize("tab", TABS)
def test_phone_open_tab_is_fully_visible_in_the_tab_bar(browser, base, tab, how):
    if how == "link":
        ctx, pg = phone_page(browser, base, "#" + tab)
    else:
        ctx, pg = phone_page(browser, base)
        if how == "tap":
            # start from the far end so the bar has to scroll back for the first tabs
            pg.tap("#tab-method")
            pg.tap(f"#tab-{tab}")
        else:
            pg.focus("#tab-area")
            for _ in range(TABS.index(tab)):
                pg.keyboard.press("ArrowRight")
            pg.keyboard.press("Enter")
    pg.wait_for_timeout(100)
    assert pg.get_attribute(f"#tab-{tab}", "aria-selected") == "true"
    left, right, bl, br = tab_inside_bar(pg, tab)
    assert left >= bl - 0.5 and right <= br + 0.5, (tab, how, left, right, bl, br)
    assert pg.evaluate("document.documentElement.scrollWidth") <= 390
    assert pg.errors == []
    ctx.close()


@pytest.mark.parametrize("start", [t for t in TABS if t != "area"])
def test_phone_tap_on_area_tab_draws_the_map(browser, base, start):
    ctx, pg = phone_page(browser, base, "#" + start)
    assert pg.is_visible(f"#panel-{start}")
    pg.tap("#tab-area")
    pg.wait_for_timeout(100)
    assert pg.is_visible("#map")
    assert pg.evaluate("document.getElementById('map').clientWidth") > 250
    assert map_painted(pg) > 1000
    ctx.close()


@pytest.mark.parametrize("address", ["", "#area"])
def test_phone_map_is_drawn_on_load_and_from_a_deep_link(browser, base, address):
    ctx, pg = phone_page(browser, base, address)
    pg.wait_for_timeout(100)
    assert pg.evaluate("document.getElementById('map').clientWidth") > 250
    assert map_painted(pg) > 1000
    ctx.close()


def test_phone_map_is_redrawn_after_a_round_trip_through_every_tab(browser, base):
    ctx, pg = phone_page(browser, base)
    for t in ["compare", "smoke", "downloads", "method", "area"]:
        pg.tap(f"#tab-{t}")
    pg.wait_for_timeout(100)
    assert map_painted(pg) > 1000
    ctx.close()


# ---------------------------------------------------------------- short top of the page
def first_screen(browser, base, width, height):
    ctx = browser.new_context(viewport={"width": width, "height": height}, has_touch=width < 500, is_mobile=width < 500)
    pg = ctx.new_page()
    pg.route("**/data/co_monthly.json*", lambda r: r.fulfill(status=200, content_type="application/json", body=fake_co()))
    pg.goto(base)
    pg.wait_for_selector(".cell")
    return ctx, pg


def top_of(pg, selector):
    return pg.evaluate(f"document.querySelector('{selector}').getBoundingClientRect().top + scrollY")


def test_tab_bar_and_calendar_are_in_the_first_screen_at_1400(browser, base):
    ctx, pg = first_screen(browser, base, 1400, 900)
    assert top_of(pg, ".tabbar") <= 450
    assert top_of(pg, "#h-cal") < 900 - 30          # the calendar card's heading shows in a 1400x900 window
    ctx.close()


@pytest.mark.parametrize("width,limit", [(390, 700), (1400, 450)])
def test_tab_bar_position_limits(browser, base, width, limit):
    ctx, pg = first_screen(browser, base, width, 844)
    assert top_of(pg, ".tabbar") <= limit
    assert pg.evaluate("document.documentElement.scrollWidth") <= width
    ctx.close()


def test_introduction_and_how_to_read_are_closed_by_default(page):
    for d in ("#introMore", "#howDetails"):
        assert page.evaluate(f"document.querySelector('{d}').open") is False
        assert page.inner_text(f"{d} summary").strip()            # each has a one-line summary
    assert not page.is_visible(".judge-path") and not page.is_visible(".science-note")
    assert page.is_visible("#h-brief") and page.is_visible(".proof-grid") and page.is_visible("#briefExplore")


@pytest.mark.parametrize("key", ["Enter", " "])
@pytest.mark.parametrize("section", ["#introMore", "#howDetails"])
def test_collapsed_sections_open_with_enter_and_space(page, section, key):
    page.focus(f"{section} summary")
    page.keyboard.press(key)
    assert page.evaluate(f"document.querySelector('{section}').open") is True
    page.keyboard.press(key)
    assert page.evaluate(f"document.querySelector('{section}').open") is False


def test_proof_numbers_are_visible_and_match_summary_json(page):
    summary = json.loads((APP / "data" / "summary.json").read_text())
    assert page.is_visible("#proofPeriod") and page.is_visible("#proofSeasons") and page.is_visible("#proofError")
    assert page.inner_text("#proofSeasons") == str(len(summary["series_rules"]["fit_years"]))
    assert page.inner_text("#proofError") == f"{round(summary['ratios']['cells']['cv_median_pct_err'])}%"
    first = min(s["first_date"] for s in summary["sources"].values())
    assert page.inner_text("#proofPeriod").startswith(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][int(first[5:7]) - 1] + " " + first[:4])


def test_skip_link_goes_to_the_main_content(page):
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.className") == "skip-link"
    assert page.get_attribute(".skip-link", "href") == "#main" and page.locator("#main").count() == 1


def test_calendar_comes_first_and_change_area_link_moves_to_the_controls(page):
    assert top_of(page, "#h-cal") < top_of(page, "#h-area")
    assert "Area: all of Newfoundland and Labrador" in page.inner_text("#calArea")
    page.click("#changeArea")
    assert page.evaluate("document.activeElement.id") == "start"
    page.click("#island")
    assert "island of Newfoundland" in page.inner_text("#calArea")


# ---------------------------------------------------------------- CO note: versions and missing years
def co_custom(years, version=None):
    months = []
    for y in years:
        for m in range(1, 13):
            row = {"year": y, "month": m, "month_key": f"{y}-{m:02d}", "days_with_data": 20, "readings": 100,
                   "co_total_1e18": 2.0 + 0.01 * m, "co_surface_ppbv": 130 + m, "enough_days": True}
            if version:
                row["version"] = version(y, m)
            months.append(row)
    return json.dumps({"min_days": 15, "months": months})


@pytest.mark.parametrize("years,expected", [
    ([2001, 2002, 2003, 2010, 2011], "No data loaded for 2004 to 2009."),
    ([2010, 2012], "No data loaded for 2011."),
    ([2001, 2003, 2006, 2007, 2010], "No data loaded for 2002, 2004 to 2005 and 2008 to 2009."),
])
def test_co_note_names_missing_years(browser, base, years, expected):
    ctx, pg = co_page(browser, base, co_custom(years))
    assert expected in pg.inner_text("#coNote")
    ctx.close()


@pytest.mark.parametrize("years", [[2010, 2011, 2012], [2020]])
def test_co_note_says_nothing_about_gaps_when_there_are_none(browser, base, years):
    ctx, pg = co_page(browser, base, co_custom(years))
    assert "No data loaded" not in pg.inner_text("#coNote")
    ctx.close()


def test_co_note_without_version_field_explains_versions_in_general(browser, base):
    ctx, pg = co_page(browser, base, co_custom([2019, 2020, 2021]))
    note = pg.inner_text("#coNote")
    assert "changed during some years, for example 2020, 2022 and 2023" in note
    assert "can come from the version change and not from smoke" in note
    ctx.close()


def test_co_note_with_version_field_names_the_years_where_it_changed(browser, base):
    ver = lambda y, m: {2020: "V18.0.3" if m < 6 else "V19.9.3", 2022: "V19.9.3" if m < 9 else "V19.10.3"}.get(y, "V19.9.3")
    ctx, pg = co_page(browser, base, co_custom([2020, 2021, 2022], ver))
    note = pg.inner_text("#coNote")
    assert "version changed during 2020 and 2022" in note and "2021" not in note.split("version changed during")[1].split(".")[0]
    assert "V18.0.3" in note and "can come from the version change and not from smoke" in note
    assert "for example 2020, 2022 and 2023" not in note       # no general sentence when the file says it
    ctx.close()


def test_co_note_with_one_version_everywhere_names_no_change(browser, base):
    ctx, pg = co_page(browser, base, co_custom([2020, 2021], lambda y, m: "V20.2.3"))
    note = pg.inner_text("#coNote")
    assert "V20.2.3" in note and "version changed during" not in note
    ctx.close()


# ---------------------------------------------------------------- map zoom and pan
def map_state(pg):
    return pg.evaluate("""() => { const b = mapBounds(); return {z: state.view.z, lat: state.view.lat, lon: state.view.lon,
        latMin: b.latMin, latMax: b.latMax, lonMin: b.lonMin, lonMax: b.lonMax,
        labels: document.getElementById('map').dataset.labels, text: document.getElementById('mapZoom').textContent}; }""")


def counts_and_area(pg):
    return pg.evaluate("JSON.stringify([state.bbox, state.startIdx, state.endIdx, state.series.map(r => r.value)])")


def map_page(browser, base, width=1400, height=900, touch=False):
    ctx = browser.new_context(viewport={"width": width, "height": height}, has_touch=touch, is_mobile=touch)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("console", lambda m: pg.errors.append(m.text) if m.type == "error" else None)
    pg.goto(base)
    pg.wait_for_selector(".cell")
    pg.locator("#map").scroll_into_view_if_needed()
    return ctx, pg


def test_map_starts_at_the_full_view_with_a_status_line(page):
    s = map_state(page)
    assert s["z"] == 1 and "full view" in s["text"] and "Scroll or pinch to zoom, drag to move." in s["text"]
    assert page.is_disabled("#mapOut") and page.is_disabled("#mapReset") and not page.is_disabled("#mapIn")


@pytest.mark.parametrize("button", ["#mapIn", "#mapOut"])
def test_zoom_buttons_change_the_extent_and_the_labels(page, button):
    full = map_state(page)
    page.click("#mapIn")
    page.click("#mapIn")
    zoomed = map_state(page)
    assert zoomed["z"] > 1 and (zoomed["latMax"] - zoomed["latMin"]) < (full["latMax"] - full["latMin"])
    assert zoomed["labels"] != full["labels"] and "Zoom 2.3×" in zoomed["text"]
    if button == "#mapOut":
        page.click("#mapOut")
        out = map_state(page)
        assert 1 < out["z"] < zoomed["z"] and (out["latMax"] - out["latMin"]) > (zoomed["latMax"] - zoomed["latMin"])


def test_reset_map_restores_the_full_view(page):
    full = map_state(page)
    for _ in range(3):
        page.click("#mapIn")
    page.focus("#map")
    page.keyboard.press("ArrowLeft")
    page.click("#mapReset")
    assert map_state(page) == full


def test_zoom_to_selected_area_is_disabled_until_an_area_is_chosen(page):
    assert page.is_disabled("#mapArea")
    page.click("#island")
    assert not page.is_disabled("#mapArea")
    page.click("#mapArea")
    s = map_state(page)
    assert s["z"] > 1
    # the whole island box is inside the view
    assert s["latMin"] <= 46.4 and s["latMax"] >= 51.9 and s["lonMin"] <= -59.7 and s["lonMax"] >= -52.4
    page.click("#reset")
    assert page.is_disabled("#mapArea")


def test_zoom_limits(page):
    for _ in range(40):
        page.click("#mapIn") if not page.is_disabled("#mapIn") else None
    s = map_state(page)
    km_across = (s["latMax"] - s["latMin"]) * 111
    assert page.is_disabled("#mapIn") and 8 <= km_across <= 12, km_across
    for _ in range(40):
        page.click("#mapOut") if not page.is_disabled("#mapOut") else None
    assert map_state(page)["z"] == 1 and page.is_disabled("#mapOut")


def test_panning_cannot_leave_the_data_area(page):
    page.click("#mapIn")
    page.click("#mapIn")
    page.focus("#map")
    for _ in range(200):
        page.keyboard.press("ArrowRight")
    s = map_state(page)
    ext = page.evaluate("EXTENT")
    assert ext["lonMin"] <= s["lon"] <= ext["lonMax"] and ext["latMin"] <= s["lat"] <= ext["latMax"]
    assert s["lonMin"] < ext["lonMax"] and s["lonMax"] > ext["lonMin"]      # some data area still shows


def test_keyboard_zoom_and_pan_on_the_focused_map(page):
    page.focus("#map")
    page.keyboard.press("+")
    assert map_state(page)["z"] > 1
    before = map_state(page)
    page.keyboard.press("ArrowLeft")
    after = map_state(page)
    assert after["lon"] < before["lon"]
    page.keyboard.press("ArrowUp")
    assert map_state(page)["lat"] > after["lat"]
    page.keyboard.press("-")
    assert map_state(page)["z"] < after["z"]
    assert page.evaluate("document.activeElement.id") == "map"


def test_map_buttons_have_names_and_visible_focus(page):
    for sel, name in (("#mapIn", "Zoom in"), ("#mapOut", "Zoom out")):
        assert page.get_attribute(sel, "aria-label") == name
    assert page.inner_text("#mapArea") == "Zoom to selected area" and page.inner_text("#mapReset") == "Reset map"
    page.focus("#tab-area")
    page.keyboard.press("Tab")
    for _ in range(40):
        if page.evaluate("document.activeElement.id") == "mapIn":
            break
        page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.id") == "mapIn"
    assert page.evaluate("getComputedStyle(document.activeElement).outlineStyle") == "solid"


def test_wheel_zooms_around_the_pointer(browser, base):
    ctx, pg = map_page(browser, base)
    box = pg.locator("#map").bounding_box()
    x, y = box["x"] + box["width"] * 0.7, box["y"] + box["height"] * 0.7
    point = f"(() => {{ const r = cv.getBoundingClientRect(), k = cv.width / r.width; return unproj((({x}) - r.left) * k, (({y}) - r.top) * k); }})()"
    under = pg.evaluate(point)
    pg.mouse.move(x, y)
    pg.mouse.wheel(0, -400)
    pg.wait_for_timeout(50)
    after = pg.evaluate(point)
    assert map_state(pg)["z"] > 1
    assert abs(after["lat"] - under["lat"]) < 0.01 and abs(after["lon"] - under["lon"]) < 0.01
    assert pg.errors == []
    ctx.close()


def test_mouse_drag_pans_and_does_not_change_the_area(browser, base):
    ctx, pg = map_page(browser, base)
    pg.click("#mapIn")
    before, area = map_state(pg), counts_and_area(pg)
    box = pg.locator("#map").bounding_box()
    pg.mouse.move(box["x"] + 200, box["y"] + 200)
    pg.mouse.down()
    pg.mouse.move(box["x"] + 120, box["y"] + 150, steps=5)
    pg.mouse.up()
    pg.wait_for_timeout(50)
    after = map_state(pg)
    assert after["lon"] > before["lon"] and after["lat"] < before["lat"]
    assert counts_and_area(pg) == area
    ctx.close()


def test_drawing_a_box_while_zoomed_in_selects_the_right_coordinates(browser, base):
    ctx, pg = map_page(browser, base)
    for _ in range(3):
        pg.click("#mapIn")
    pg.click("#drawmode")
    box = pg.locator("#map").bounding_box()
    x1, y1, x2, y2 = box["x"] + 100, box["y"] + 80, box["x"] + 300, box["y"] + 260
    expect = pg.evaluate(f"""(() => {{ const r = cv.getBoundingClientRect(), k = cv.width / r.width;
        const a = unproj(({x1} - r.left) * k, ({y2} - r.top) * k), b = unproj(({x2} - r.left) * k, ({y1} - r.top) * k);
        return {{latMin: a.lat, lonMin: a.lon, latMax: b.lat, lonMax: b.lon}}; }})()""")
    pg.mouse.move(x1, y1)
    pg.mouse.down()
    pg.mouse.move(x2, y2, steps=6)
    pg.mouse.up()
    got = pg.evaluate("state.bbox")
    for k in expect:
        assert abs(got[k] - expect[k]) < 0.02, (k, got[k], expect[k])
    assert abs(float(pg.input_value("#latMin")) - got["latMin"]) <= 0.005     # the boxes show 2 decimals
    # the box is much smaller than at the full view, as it should be when zoomed in
    assert got["latMax"] - got["latMin"] < 3
    ctx.close()


def test_shift_drag_draws_a_box_without_draw_mode(browser, base):
    ctx, pg = map_page(browser, base)
    box = pg.locator("#map").bounding_box()
    pg.keyboard.down("Shift")
    pg.mouse.move(box["x"] + 100, box["y"] + 100)
    pg.mouse.down()
    pg.mouse.move(box["x"] + 250, box["y"] + 220, steps=5)
    pg.mouse.up()
    pg.keyboard.up("Shift")
    assert pg.evaluate("state.bbox.latMax - state.bbox.latMin") < 12
    assert map_state(pg)["z"] == 1
    ctx.close()


def test_zoom_does_not_change_area_dates_calendar_or_downloads(page):
    page.click("#island")
    before = counts_and_area(page)
    summary = page.inner_text("#areasummary")
    page.click("#mapIn")
    page.click("#mapArea")
    page.focus("#map")
    page.keyboard.press("ArrowDown")
    page.click("#mapOut")
    assert counts_and_area(page) == before and page.inner_text("#areasummary") == summary
    open_tab(page, "downloads")
    with page.expect_download() as d:
        page.click("#dlHot")
    lines = Path(d.value.path()).read_text().strip().splitlines()
    assert len(lines) - 1 == int(summary.split("°W.")[1].split("cleaned")[0].replace(",", "").strip())


def test_zoom_survives_tab_switches_and_resizing(page):
    page.click("#mapIn")
    page.click("#mapIn")
    z = map_state(page)["z"]
    for t in ("compare", "smoke", "area"):
        open_tab(page, t)
    assert map_state(page)["z"] == z
    page.set_viewport_size({"width": 1000, "height": 800})
    page.wait_for_timeout(100)
    assert map_state(page)["z"] == z


def test_map_on_a_phone_pinch_zooms_and_one_finger_pans_without_sideways_scroll(browser, base):
    ctx, pg = map_page(browser, base, 390, 844, touch=True)
    assert pg.evaluate("document.documentElement.scrollWidth") <= 390
    box = pg.locator("#map").bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    s = ctx.new_cdp_session(pg)
    s.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": cx - 20, "y": cy, "id": 1}, {"x": cx + 20, "y": cy, "id": 2}]})
    for i in range(1, 6):
        s.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": cx - 20 - 15 * i, "y": cy, "id": 1}, {"x": cx + 20 + 15 * i, "y": cy, "id": 2}]})
    s.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    pinched = map_state(pg)
    assert pinched["z"] > 2
    s.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": cx, "y": cy, "id": 3}]})
    for i in range(1, 6):
        s.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": cx + 10 * i, "y": cy, "id": 3}]})
    s.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    assert map_state(pg)["lon"] < pinched["lon"]
    assert pg.evaluate("state.bbox") == pg.evaluate("EXTENT")       # panning did not draw an area
    assert pg.evaluate("document.documentElement.scrollWidth") <= 390
    assert pg.errors == []
    ctx.close()


def test_phone_page_still_scrolls_when_touching_outside_the_map(browser, base):
    ctx, pg = map_page(browser, base, 390, 844, touch=True)
    pg.evaluate("window.scrollTo(0, 0)")
    s = ctx.new_cdp_session(pg)
    # a swipe on the header (outside the map) scrolls the page
    s.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": 200, "y": 600}]})
    for i in range(1, 8):
        s.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": 200, "y": 600 - 60 * i}]})
    s.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    pg.wait_for_timeout(300)
    assert pg.evaluate("scrollY") > 100
    # the map leaves part of the screen free to touch
    assert pg.evaluate("document.getElementById('map').getBoundingClientRect().height") < 844 * 0.7
    ctx.close()


def test_map_dots_stay_readable_and_drawing_is_fast(page):
    page.click("#mapIn")
    ms = page.evaluate("(() => { const t = performance.now(); for (let i = 0; i < 5; i++) drawMap(); return (performance.now() - t) / 5; })()")
    assert ms < 100, ms
    painted = page.evaluate("""() => { const c = document.getElementById('map'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
        let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++; return n; }""")
    assert painted > 1000



# ---------------------------------------------------------------- month pickers and the Apply button
def test_date_boxes_are_month_pickers_with_the_data_limits(page):
    for box in ("#start", "#end"):
        assert page.get_attribute(box, "type") == "month"
        assert page.get_attribute(box, "min") == "2000-11" and page.get_attribute(box, "max") == "2026-11"
    assert page.inner_text("#dateRange") == "Allowed: 2000-11 to 2026-11"


@pytest.mark.parametrize("start,end", [("2000-11", "2026-11"), ("2000-11", "2000-11"), ("2026-11", "2026-11")])
def test_first_and_last_allowed_months_are_accepted(page, start, end):
    set_dates(page, start=start, end=end)
    assert applied_range(page) == [start, end]
    assert page.inner_text("#startErr") == "" and page.inner_text("#endErr") == ""
    assert page.get_attribute("#start", "aria-invalid") == "false"


@pytest.mark.parametrize("box,value", [("start", "2000-10"), ("end", "2026-12"), ("start", "2026-12"), ("end", "2000-10")])
def test_one_month_outside_the_data_is_rejected(page, box, value):
    set_dates(page, **{box: value})
    assert "Outside the data. Allowed: 2000-11 to 2026-11." in page.inner_text(f"#{box}Err")
    assert page.get_attribute(f"#{box}", "aria-invalid") == "true"
    assert applied_range(page) == ["2000-11", "2026-11"]
    assert page.inner_text("#applied") == ""


@pytest.mark.parametrize("start,end,ok", [("2020-06", "2020-06", True), ("2020-07", "2020-06", False), ("2020-05", "2020-06", True)])
def test_start_after_end_boundary(page, start, end, ok):
    set_dates(page, start=start, end=end)
    assert (applied_range(page) == [start, end]) == ok
    assert ("start month is after the end month" in page.inner_text("#startErr")) == (not ok)


@pytest.mark.parametrize("value,ok", [("2018-04", True), ("2018-4", False), ("2018/04", False), ("201804", False),
                                      ("1999-12", False), ("2030-01", False), (" 2018-04 ", True)])
def test_text_fallback_uses_the_same_rules(page, value, ok):
    use_text_fallback(page)
    set_dates(page, start=value)
    assert (applied_range(page)[0] == "2018-04") == ok
    assert (page.get_attribute("#start", "aria-invalid") == "true") == (not ok)


def test_text_fallback_enter_applies(page):
    use_text_fallback(page)
    page.fill("#start", "2015-03")
    page.press("#start", "Enter")
    assert applied_range(page)[0] == "2015-03"


def test_a_fixed_error_clears_its_message(page):
    set_dates(page, start="1990-01")
    assert page.inner_text("#startErr")
    set_dates(page, start="2005-01")
    assert page.inner_text("#startErr") == "" and page.get_attribute("#start", "aria-invalid") == "false"


def test_nothing_changes_until_apply_is_pressed(page):
    before = page.evaluate("JSON.stringify([state.bbox, state.startIdx, state.endIdx, state.series.map(r => r.value)])")
    page.fill("#start", "2015-01")
    page.dispatch_event("#start", "change")
    page.fill("#latMax", "50")
    page.fill("#latMin", "48")
    page.click("#h-area")                  # move focus away
    assert page.evaluate("JSON.stringify([state.bbox, state.startIdx, state.endIdx, state.series.map(r => r.value)])") == before
    page.click("#apply")
    assert applied_range(page)[0] == "2015-01" and page.evaluate("state.bbox.latMax") == 50


def test_enter_in_an_area_box_applies(page):
    page.fill("#latMin", "48")
    page.press("#latMin", "Enter")
    assert page.evaluate("state.bbox.latMin") == 48


def test_apply_button_is_on_its_own_line_below_the_controls(page):
    apply_box = page.locator("#apply").bounding_box()
    for sel in ("#start", "#end", "#latMax", "#lonMax", "#reset", "#island", "#drawmode"):
        b = page.locator(sel).bounding_box()
        assert apply_box["y"] >= b["y"] + b["height"] - 1, sel
    assert page.inner_text("#apply") == "Apply area and dates"


def test_apply_shows_a_confirmation_line(page):
    assert page.inner_text("#applied") == ""
    page.fill("#latMax", "50"); page.fill("#latMin", "48"); page.fill("#lonMin", "-58"); page.fill("#lonMax", "-54")
    set_dates(page, start="2010-01", end="2020-12")
    text = page.inner_text("#applied")
    assert text.startswith("Applied:") and "48.0 to 50.0°N" in text and "2010-01 to 2020-12" in text


def test_apply_keeps_a_visible_focus(page):
    page.focus("#apply")
    page.keyboard.press("Enter")
    assert page.evaluate("document.activeElement.id") == "apply"
    page.focus("#lonMax")
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.id") == "reset" or page.evaluate("document.activeElement.id") == "apply"
    page.focus("#apply")
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    assert page.evaluate("getComputedStyle(document.activeElement).outlineStyle") == "solid"


def test_apply_is_full_width_on_a_phone_and_no_sideways_scroll(browser, base):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    pg = ctx.new_page()
    pg.goto(base)
    pg.wait_for_selector(".cell")
    width = pg.evaluate("document.getElementById('apply').getBoundingClientRect().width")
    parent = pg.evaluate("document.getElementById('apply').parentElement.getBoundingClientRect().width")
    assert abs(width - parent) < 2
    pg.fill("#start", "1990-01")
    pg.click("#apply")
    assert pg.inner_text("#startErr") and pg.evaluate("document.documentElement.scrollWidth") <= 390
    ctx.close()


# ---------------------------------------------------------------- button states, chart label, wording
AREA_BUTTONS = ["#apply", "#reset", "#island", "#drawmode", "#mapArea", "#mapReset"]
DOWNLOAD_BUTTONS = ["#dlHot", "#dlSeries", "#dlPng", "#dlAnnualSvg", "#dlMonthSvg", "#dlValid"]


def colours(pg, sel):
    c = pg.evaluate(f"(() => {{ const s = getComputedStyle(document.querySelector('{sel}')); return [s.backgroundColor, s.color]; }})()")
    return _rgb(c[0]), _rgb(c[1])


@pytest.mark.parametrize("sel", ["#reset", "#island", "#drawmode", "#dlSeries", "#dlAnnualSvg", "#dlValid"])
def test_hover_gives_a_blue_fill_and_white_text(page, sel):
    page.click("#island") if sel == "#reset" else None      # so "Reset" is not the selected one
    if sel.startswith("#dl"):
        open_tab(page, "downloads")
    page.hover(sel)
    page.wait_for_timeout(150)
    bg, fg = colours(page, sel)
    assert bg[2] > bg[0] + 60 and fg == [255, 255, 255], (bg, fg)     # blue, white text
    assert _contrast(fg, bg) >= 4.5


@pytest.mark.parametrize("sel", AREA_BUTTONS[:4] + DOWNLOAD_BUTTONS)
def test_buttons_have_a_visible_keyboard_focus_with_3_to_1_contrast(page, sel):
    if sel.startswith("#dl"):
        open_tab(page, "downloads")
    page.focus(sel)
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.id") == sel[1:]
    style = page.evaluate("(() => { const s = getComputedStyle(document.activeElement); return [s.outlineStyle, s.outlineWidth, s.outlineColor]; })()")
    assert style[0] == "solid" and float(style[1].replace("px", "")) >= 2
    assert _contrast(_rgb(style[2]), (255, 255, 255)) >= 3


def test_pressed_state_is_darker_blue_with_white_text(page):
    page.hover("#island")
    page.mouse.down()
    bg, fg = colours(page, "#island")
    page.mouse.up()
    assert fg == [255, 255, 255] and bg[2] > bg[0] and _contrast(fg, bg) >= 4.5


def test_selected_quick_button_is_blue_pressed_and_says_selected(page):
    # at start the whole province is in use
    assert page.get_attribute("#reset", "aria-pressed") == "true" and "Selected" in page.inner_text("#reset")
    assert page.get_attribute("#island", "aria-pressed") == "false" and "Selected" not in page.inner_text("#island")
    page.click("#island")
    page.mouse.move(0, 0)
    assert page.get_attribute("#island", "aria-pressed") == "true" and "✓ Selected" in page.inner_text("#island")
    assert page.get_attribute("#reset", "aria-pressed") == "false"
    bg, fg = colours(page, "#island")
    assert bg[2] > bg[0] + 60 and fg == [255, 255, 255] and _contrast(fg, bg) >= 4.5
    # a typed area that is neither: no quick button is selected
    page.fill("#latMax", "50")
    page.click("#apply")
    assert page.get_attribute("#island", "aria-pressed") == "false" and page.get_attribute("#reset", "aria-pressed") == "false"


@pytest.mark.parametrize("width", [1400, 390])
def test_large_smoke_chart_labels_do_not_overlap(browser, base, width):
    ctx, pg = co_page(browser, base, co_years(13), width=width)
    a = pg.locator("#coBig .lbl-co-min").bounding_box()
    b = pg.locator("#coBig .lbl-fire-max").bounding_box()
    assert a and b
    gap = b["y"] - (a["y"] + a["height"])
    assert gap >= 4, gap
    ctx.close()


def test_wording_uses_the_sensor_period_not_kind(page):
    html = (APP / "index.html").read_text()
    assert "own kind" not in html and "same-kind" not in html
    assert "years in the same sensor period (MODIS or VIIRS)" in page.inner_text("#eranote")
    label = page.get_attribute("#heat button[aria-label^='Jun 2012:']", "aria-label")
    assert "years in the same sensor period (MODIS or VIIRS)" in label
    open_tab(page, "method")
    assert "years in the same sensor period (MODIS or VIIRS)" in page.inner_text("#method")
