#!/usr/bin/env python3
"""
Download MOPITT files from the CSA Open Data server.

The script reads the folder listing pages, so it does not need to know the
folder layout in advance. It can only look at pages, then download.

Step 1 (look, no download):
    python pipeline/download_mopitt.py --years 2013 --list
Step 2 (download):
    python pipeline/download_mopitt.py --years 2013 2018 --months 5 6 7 8 9

Files go to data/raw/csa/ by default. Files already downloaded are skipped, so
you can stop and run it again.

Only the standard library is used.
"""
import argparse
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser

BASE = "https://donnees-data.asc-csa.gc.ca/users/OpenData_DonneesOuvertes/pub/MOPITT/"
DATA_EXT = (".he5", ".csv", ".zip", ".gz", ".h5", ".hdf", ".nc")


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.links.append(v)


def make_context(insecure=False):
    """Build the HTTPS settings.
    1. truststore: uses the operating system certificate store (best on Mac).
    2. certifi: a bundled certificate list.
    3. insecure=True: skips certificate checks. Only for public, read-only data,
       and only when the other two fail. It is never the default."""
    import ssl
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        pass
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


CTX = make_context()


def fetch(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "nl-fire-calendar/1.0"})
            return urllib.request.urlopen(req, timeout=60, context=CTX)
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def list_page(url):
    html = fetch(url).read().decode("utf-8", "replace")
    p = Links()
    p.feed(html)
    out = []
    for href in p.links:
        if href.startswith(("?", "#", "mailto:")) or href in ("../", "/"):
            continue
        full = urllib.parse.urljoin(url, href)
        if not full.startswith(BASE):  # stay inside the MOPITT folder
            continue
        if full.rstrip("/") == url.rstrip("/") or len(full) < len(url):
            continue  # parent link
        out.append(full)
    return out


def year_of(name):
    """Year from a file name such as MOP02J-20130601-... or from a folder name such as 2013."""
    m = re.search(r"(?<!\d)(20\d{2})(?:0[1-9]|1[0-2])[0-3]\d(?!\d)", name)
    if m:
        return int(m.group(1))
    m = re.search(r"(?<!\d)(20\d{2})(?!\d)", name)
    return int(m.group(1)) if m else None


def month_of(name):
    # file names such as MOP02J-20130615-... carry YYYYMMDD
    m = re.search(r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])([0-3]\d)(?!\d)", name)
    return int(m.group(2)) if m else None


def crawl(url, years, depth=0, max_depth=4):
    """Yield data-file URLs. Only enter folders whose name does not clearly
    belong to a year we do not want."""
    for link in list_page(url):
        name = urllib.parse.unquote(link.rstrip("/").split("/")[-1])
        if link.endswith("/"):
            y = year_of(name)
            if y is not None and years and y not in years:
                continue
            if depth < max_depth:
                yield from crawl(link, years, depth + 1, max_depth)
        elif name.lower().endswith(DATA_EXT):
            yield link


# Island of Newfoundland box, with a small margin. MOPITT pixels are about 22 km,
# so a few readings near the Strait of Belle Isle can touch southern Labrador.
NL_BOX = {"lat_min": 46.4, "lat_max": 51.9, "lon_min": -59.7, "lon_max": -52.4}


def stream_filter(url, dest):
    """Read one big global CSV as it arrives and keep only rows inside the island box.
    The first two columns are latitude and longitude (see the CSA readme).
    A header line, if any, is kept. Returns (rows_seen, rows_kept)."""
    import io
    seen = kept = 0
    b = NL_BOX
    with fetch(url) as r, open(dest + ".part", "w", encoding="utf-8", newline="") as out:
        for line in io.TextIOWrapper(r, encoding="utf-8", errors="replace"):
            parts = line.split(",", 2)
            try:
                lat, lon = float(parts[0]), float(parts[1])
            except (ValueError, IndexError):
                out.write(line)  # header or text line
                continue
            seen += 1
            if b["lat_min"] <= lat <= b["lat_max"] and b["lon_min"] <= lon <= b["lon_max"]:
                out.write(line)
                kept += 1
    os.replace(dest + ".part", dest)
    return seen, kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, nargs="*", default=[], help="for example 2013 2018")
    ap.add_argument("--months", type=int, nargs="*", default=[5, 6, 7, 8, 9])
    ap.add_argument("--keep-full", action="store_true", help="save the whole global files (about 40 MB each) instead of only the NL rows")
    ap.add_argument("--all", action="store_true", help="every year and every month (can be very large)")
    ap.add_argument("--sizes", action="store_true", help="with --list: ask the server for file sizes and print the total")
    ap.add_argument("--out", default="data/raw/csa")
    ap.add_argument("--insecure", action="store_true", help="skip certificate checks (last resort, public data only)")
    ap.add_argument("--list", action="store_true", help="only list what would be downloaded")
    ap.add_argument("--max-files", type=int, default=0, help="stop after this many (0 = no limit)")
    a = ap.parse_args()
    global CTX
    if a.insecure:
        print("WARNING: certificate checks are off. Use this only for this public data.")
    CTX = make_context(a.insecure)

    if a.all:
        a.years = list(range(2000, 2027))
        a.months = list(range(1, 13))
    if not a.years:
        sys.exit("Give at least one year, for example --years 2013, or use --all")

    print("Looking at", BASE)
    found = []
    for url in crawl(BASE, set(a.years)):
        name = urllib.parse.unquote(url.split("/")[-1])
        y, m = year_of(name), month_of(name)
        if y is not None and y not in a.years:
            continue
        if m is not None and m not in a.months:
            continue
        found.append((url, name))
    print(f"{len(found)} files match years {a.years}, months {a.months}")
    if a.max_files:
        found = found[: a.max_files]

    if a.list and a.sizes and found:
        total = 0
        for url, _ in found:
            try:
                req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "nl-fire-calendar/1.0"})
                total += int(urllib.request.urlopen(req, timeout=60, context=CTX).headers.get("Content-Length", 0))
            except Exception:
                pass
        print(f"Total size of matching files: {total / 1e9:.2f} GB")

    if a.list or not found:
        for _, n in found[:40]:
            print("  ", n)
        if len(found) > 40:
            print(f"   ... and {len(found) - 40} more")
        if not found:
            print("Nothing matched. Run with --list and no month filter, or check the folder names on the CSA page.")
        return

    os.makedirs(a.out, exist_ok=True)
    done = skipped = failed = 0
    for k, (url, name) in enumerate(found, 1):
        dest = os.path.join(a.out, name)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            skipped += 1
            continue
        try:
            if a.keep_full:
                with fetch(url) as r, open(dest + ".part", "wb") as f:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
                os.replace(dest + ".part", dest)
            else:
                seen, kept = stream_filter(url, dest)
                if kept == 0:
                    print(f"  note: {name} had {seen} rows and none in the NL box")
            done += 1
        except Exception as e:
            failed += 1
            print("FAILED", name, e)
        if k % 10 == 0:
            print(f"  {k}/{len(found)}  downloaded {done}, skipped {skipped}, failed {failed}")
    print(f"Done. downloaded {done}, skipped {skipped}, failed {failed}. Folder: {a.out}")


if __name__ == "__main__":
    main()
