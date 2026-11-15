"""Tests for pipeline/download_mopitt.py, using a small web server on this computer."""
import functools
import http.server
import threading
from pathlib import Path

import pytest

import download_mopitt as dl

HEADER = "# Latitude, Longitude, COTotalColumn\n"


@pytest.fixture()
def server(tmp_path, monkeypatch):
    site = tmp_path / "site"          # the folder that is served; outputs go elsewhere
    site.mkdir()
    tmp_path = site
    (tmp_path / "2013").mkdir()
    (tmp_path / "2014").mkdir()
    day = lambda d, rows: (tmp_path / "2013" / f"MOP02J-{d}-L2V18.0.3.csv").write_text(HEADER + rows)
    day("20130601", "48.0,-55.0,2e18\n10.0,10.0,9e18\n48.5,-56.0,3e18\n")
    day("20130602", "10.0,10.0,9e18\n")
    day("20130715", "47.0,-54.0,2e18\n")
    (tmp_path / "2014" / "MOP02J-20140601-L2V18.0.3.csv").write_text(HEADER + "48.0,-55.0,1e18\n")
    (tmp_path / "2013" / "readme.txt").write_text("not data")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}/"
    monkeypatch.setattr(dl, "BASE", base)
    yield base
    httpd.shutdown()


def names(urls):
    return sorted(u.split("/")[-1] for u in urls)


def test_year_and_month_are_read_from_file_names():
    assert dl.year_of("MOP02J-20130601-L2V18.0.3.csv") == 2013
    assert dl.month_of("MOP02J-20130601-L2V18.0.3.csv") == 6
    assert dl.month_of("MOP02J-20131301-x.csv") is None       # month 13 is not valid
    assert dl.year_of("readme.txt") is None


def test_crawl_only_enters_requested_years(server):
    found = names(dl.crawl(server, {2013}))
    assert "MOP02J-20140601-L2V18.0.3.csv" not in found and len(found) == 3


def test_crawl_skips_non_data_files(server):
    assert "readme.txt" not in names(dl.crawl(server, {2013}))


def test_stream_filter_keeps_header_and_island_rows_only(server, tmp_path):
    dest = tmp_path / "out.csv"
    seen, kept = dl.stream_filter(server + "2013/MOP02J-20130601-L2V18.0.3.csv", str(dest))
    assert (seen, kept) == (3, 2)
    lines = dest.read_text().splitlines()
    assert lines[0].startswith("#") and len(lines) == 3


def test_list_mode_downloads_nothing(server, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["x", "--years", "2013", "--months", "6", "--list", "--out", str(tmp_path / "o")])
    dl.main()
    assert "2 files match" in capsys.readouterr().out
    assert not (tmp_path / "o").exists()


def test_download_writes_filtered_files_and_skips_existing(server, tmp_path, monkeypatch, capsys):
    out = tmp_path / "o"
    argv = ["x", "--years", "2013", "--months", "6", "7", "--out", str(out)]
    monkeypatch.setattr("sys.argv", argv)
    dl.main()
    assert len(list(out.glob("*.csv"))) == 3
    capsys.readouterr()
    dl.main()
    assert "downloaded 0, skipped 3" in capsys.readouterr().out


def test_month_filter(server, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["x", "--years", "2013", "--months", "7", "--list", "--out", str(tmp_path)])
    dl.main()
    assert "1 files match" in capsys.readouterr().out


def test_no_year_is_an_error(monkeypatch):
    monkeypatch.setattr("sys.argv", ["x"])
    with pytest.raises(SystemExit):
        dl.main()


def test_year_filter_works_when_all_files_are_in_one_flat_folder(tmp_path, monkeypatch, capsys):
    flat = tmp_path / "flat"
    flat.mkdir()
    for d in ("20130601", "20140601", "20150601"):
        (flat / f"MOP02J-{d}-L2V18.0.3.csv").write_text(HEADER + "48.0,-55.0,1e18\n")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(flat))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setattr(dl, "BASE", f"http://127.0.0.1:{httpd.server_address[1]}/")
    monkeypatch.setattr("sys.argv", ["x", "--years", "2014", "--list", "--out", str(tmp_path / "o")])
    dl.main()
    httpd.shutdown()
    assert "1 files match" in capsys.readouterr().out


def test_keep_full_saves_the_whole_file(server, tmp_path, monkeypatch):
    out = tmp_path / "full"
    monkeypatch.setattr("sys.argv", ["x", "--years", "2013", "--months", "6", "--keep-full", "--out", str(out)])
    dl.main()
    text = (out / "MOP02J-20130601-L2V18.0.3.csv").read_text()
    assert "10.0,10.0" in text          # a row outside the island is kept in this mode


def test_sizes_are_added_up_in_list_mode(server, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["x", "--years", "2013", "--list", "--sizes", "--out", str(tmp_path / "o")])
    dl.main()
    assert "Total size of matching files" in capsys.readouterr().out


def test_all_option_covers_every_year(server, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["x", "--all", "--list", "--out", str(tmp_path / "o")])
    dl.main()
    assert "4 files match" in capsys.readouterr().out


def test_nothing_matching_prints_a_hint(server, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["x", "--years", "1999", "--out", str(tmp_path / "o")])
    dl.main()
    assert "Nothing matched" in capsys.readouterr().out


def test_failed_download_is_counted_and_does_not_stop_the_run(server, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(dl.time, "sleep", lambda s: None)
    real = dl.stream_filter
    def flaky(url, dest):
        if "20130601" in url:
            raise OSError("network down")
        return real(url, dest)
    monkeypatch.setattr(dl, "stream_filter", flaky)
    monkeypatch.setattr("sys.argv", ["x", "--years", "2013", "--months", "6", "7", "--out", str(tmp_path / "o")])
    dl.main()
    out = capsys.readouterr().out
    assert "FAILED" in out and "failed 1" in out


def test_unreachable_server_gives_an_error_after_retries(monkeypatch):
    monkeypatch.setattr(dl.time, "sleep", lambda s: None)
    with pytest.raises(Exception):
        dl.fetch("http://127.0.0.1:1/")


def test_insecure_context_turns_checks_off_and_default_keeps_them():
    import ssl
    assert dl.make_context(insecure=True).verify_mode == ssl.CERT_NONE
    assert dl.make_context().verify_mode == ssl.CERT_REQUIRED
