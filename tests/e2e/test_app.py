"""Browser tests for app/index.html, using Playwright.

Run the pipeline first so that app/data/ exists. The tests start their own small web
server for the app folder. A made-up CO file is injected so the CO panel can be tested
without the real MOPITT download.
"""
import functools
import http.server
import json
import threading
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parent.parent.parent
APP = ROOT / "app"

pytestmark = pytest.mark.skipif(not (APP / "data" / "summary.json").exists(),
                                reason="run pipeline/build_harmonized.py first")


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
    page.click("#selComplete")
    assert "other" in page.inner_text("#cmp") and "VIIRS-era" in page.inner_text("#cmp")


# ---------------------------------------------------------------- comparison wording
def test_low_counts_give_no_verdict(page):
    page.click("#selLatest")      # Nov 1-7: zero cells
    text = page.inner_text("#cmp")
    assert "typical" in text.lower() or "no verdict" in text.lower() or "too few" in text.lower()
    assert "Well above" not in text


def test_wording_says_other_years_not_earlier_years(page):
    page.click("#selComplete")
    assert "earlier" not in page.inner_text("#cmp")


# ---------------------------------------------------------------- inputs: equivalence classes and boundaries
@pytest.mark.parametrize("bad", ["April 2018", "04/2018", "2018-13", "2018-00", "", "abcd-ef", "2018-4"])
def test_bad_date_strings_show_a_message_and_revert(page, bad):
    before = page.input_value("#start")
    page.fill("#start", bad)
    page.dispatch_event("#start", "change")
    assert "Dates must look like" in page.inner_text("#msg")
    assert page.input_value("#start") == before
    assert page.locator(".cell").count() >= 300


def test_dates_outside_the_record_are_clamped(page):
    page.fill("#start", "1990-01")
    page.dispatch_event("#start", "change")
    assert page.input_value("#start") == "2000-11"


def test_start_after_end_is_swapped_and_shown(page):
    page.fill("#start", "2020-06")
    page.dispatch_event("#start", "change")
    page.fill("#end", "2019-06")
    page.dispatch_event("#end", "change")
    assert page.input_value("#start") <= page.input_value("#end")


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
    with page.expect_download() as d:
        page.click("#dlHot")
    lines = Path(d.value.path()).read_text().strip().splitlines()
    assert len(lines) - 1 == shown
    assert lines[0].startswith("date,")


def test_series_download_has_area_and_era_columns(page):
    with page.expect_download() as d:
        page.click("#dlSeries")
    head = Path(d.value.path()).read_text().splitlines()[0].split(",")
    for c in ("area_south", "area_north", "era", "partial_month", "terra_only", "count_type"):
        assert c in head


# ---------------------------------------------------------------- CO panel
def test_co_panel_shows_one_chart_per_year(page):
    assert page.is_visible("#coCard") and page.locator("#coChart > div").count() == 2


def test_co_panel_lists_months_left_out(page):
    assert "Mar 2012 (8 days)" in page.inner_text("#coNote")


def test_co_panel_warns_when_area_is_not_the_island(page):
    assert "not the island" in page.inner_text("#coNote")
    page.click("#island")
    assert "not the island" not in page.inner_text("#coNote")


def test_co_table_matches_the_data(page):
    page.click("#coCard summary")
    assert "2.01" in page.inner_text("#coTable") and "–" in page.inner_text("#coTable")


def test_co_measure_switch(page):
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
    assert not pg.is_visible("#coCard") and errors == []
    pg.close()


def test_co_file_with_only_empty_values_hides_the_panel(browser, base):
    pg = browser.new_page()
    pg.route("**/data/co_monthly.json*", lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"months": [{"year": 2013, "month": 1, "co_total_1e18": None, "co_surface_ppbv": None, "days_with_data": 3}]})))
    pg.goto(base)
    pg.wait_for_selector(".cell")
    assert not pg.is_visible("#coCard")
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
    text = page.inner_text("#method")
    assert "only presumed vegetation" not in text.lower()
    assert "agrees" not in text.lower()
    assert "Yearly ratio range" in text and "Month error" in text


def test_validation_chart_has_alt_text(page):
    assert len(page.get_attribute("img", "alt")) > 20
