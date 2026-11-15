"""Contract tests for files outside the pipeline: the Pages workflow, the README and the credits."""
import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from conftest import require_app_data

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text()
INDEX = (ROOT / "app" / "index.html").read_text()


# ---------------------------------------------------------------- GitHub Pages workflow
@pytest.fixture(scope="module")
def workflow():
    return yaml.safe_load((ROOT / ".github" / "workflows" / "pages.yml").read_text())


def test_workflow_runs_on_main_only_when_app_changes(workflow):
    on = workflow.get("on", workflow.get(True))        # YAML reads the key "on" as True
    assert on["push"]["branches"] == ["main"]
    assert "app/**" in on["push"]["paths"]
    assert not any(p.startswith(("pipeline", "data", "tests")) for p in on["push"]["paths"])


def test_workflow_publishes_only_the_app_folder(workflow):
    steps = workflow["jobs"]["deploy"]["steps"]
    upload = [s for s in steps if s.get("uses", "").startswith("actions/upload-pages-artifact")]
    assert len(upload) == 1 and upload[0]["with"]["path"] == "app"
    assert any(s.get("uses", "").startswith("actions/deploy-pages") for s in steps)
    assert workflow["permissions"] == {"contents": "read", "pages": "write", "id-token": "write"}


# ---------------------------------------------------------------- README
def test_readme_gives_the_intended_address_without_claiming_it_is_live():
    assert "https://portalzone.github.io/nl-fire-calendar/" in README
    assert "Settings" in README and "Source: GitHub Actions" in README and "public" in README
    assert not re.search(r"(?i)live site:\s*https", README)


@pytest.mark.parametrize("text", [README, INDEX])
def test_no_placeholders_left(text):
    for bad in ("TODO", "add the address here", "Replace this line", "placeholder text"):
        assert bad not in text


def test_readme_numbers_come_from_summary_json():
    require_app_data()
    s = json.loads((ROOT / "app" / "data" / "summary.json").read_text())
    for metric in ("cells", "hotspots"):
        r = s["ratios"][metric]
        assert f"{r['k']:.3f}" in README
        assert f"{round(r['cv_median_pct_err'])}%" in README
        assert f"{round(r['monthly_cv_median_pct_err'])}%" in README
    assert f"{len(s['series_rules']['fit_years'])} seasons" in README


def test_readme_names_what_is_not_included():
    assert "reported by agencies" in README and "single fires" in README


def test_readme_lists_every_download():
    for kind in ("CSV", "PNG", "SVG", "validation"):
        assert kind in README


# ---------------------------------------------------------------- CSA credit
@pytest.mark.parametrize("text", [README, INDEX])
def test_csa_credit_has_the_required_parts(text):
    flat = " ".join(text.split())
    assert "MOPITT" in flat and "Canadian instrument aboard NASA's Terra satellite" in flat
    assert "https://donnees-data.asc-csa.gc.ca/en/dataset/ef42819f-35bb-49c0-a368-1e61fa876ee6" in flat
    assert "Contains information licensed under the Open Government Licence – Canada." in flat
    assert "filtered the data to the island of Newfoundland and averaged it by month" in flat


# ---------------------------------------------------------------- what Git may pick up
def test_word_files_raw_data_and_zips_are_ignored():
    names = ["Harmonization of MODIS and VIIRS Hot Spots.docx", "nasa overview for hackathon.docx",
             "data/raw/modis/x.csv", "data/raw/csa/x.csv", "data/archive/x.zip", "x.zip"]
    out = subprocess.run(["git", "check-ignore", *names], cwd=ROOT, capture_output=True, text=True).stdout.split("\n")
    assert sorted(o for o in out if o) == sorted(names)
