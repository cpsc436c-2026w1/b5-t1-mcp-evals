"""README drift: a README that names a script, a flag, a link or a heading the repo no longer has, gives a time
estimate, or loses a step's Goal box (2026-11-16). The checks are in tools/readme_checks.py at the repo root."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import readme_checks as rc  # noqa: E402

PAGES = ["index", "mcp"]


@pytest.mark.parametrize("page", PAGES)
def test_readme_commands_name_scripts_and_flags_that_exist(page):
    assert rc.check_commands(rc.READMES[page]) == []


@pytest.mark.parametrize("page", PAGES)
def test_readme_links_resolve_to_files_and_headings(page):
    assert rc.check_links(rc.READMES[page]) == []


@pytest.mark.parametrize("page", PAGES)
def test_readme_gives_no_durations(page):
    assert rc.check_durations(rc.READMES[page]) == []


@pytest.mark.parametrize("page", PAGES)
def test_readme_steps_each_open_with_a_goal_box(page):
    assert rc.check_step_boxes(rc.READMES[page]) == []


def test_duration_check_tells_time_estimates_from_ordinals_and_rates():
    for said in ("takes about 5 minutes", "wait 30 s", "a few minutes", "in 2 min", "an hour", "a 10-minute run",
                 "wait a minute"):
        assert rc.durations(said), said
    for said in ("a second terminal", "a second model", "the per-minute request limit", "120 requests a minute",
                 "300 made-up taxi trips", "9 cases", "about 30 lines"):
        assert not rc.durations(said), said


def test_checks_catch_a_broken_readme(tmp_path, monkeypatch):
    """The checks themselves: a README with each kind of drift gets one problem for each."""
    (tmp_path / "real.py").write_text("import argparse\nap = argparse.ArgumentParser()\nap.add_argument('--out')\n")
    (tmp_path / "other.md").write_text("# Other\n\n## 2. Set up (once)\n")
    bad = tmp_path / "README.md"
    bad.write_text("\n".join([
        "# Page", "", "```bash", "uv run python gone.py", "uv run python real.py --out x --nope", "```", "",
        "[a](missing.md) [b](other.md#2-set-up-once) [c](other.md#no-such-heading) [d](https://example.com)", "",
        "This takes about 5 minutes.", "", "### Step 1: one", "", "<details>",
        "<summary>What happens when you do this step</summary>", "", "You do it.", "</details>", "",
        "### Step 2: two", "", "No box here.", ""]))
    monkeypatch.setattr(rc, "ROOT", tmp_path)
    assert len(rc.check_commands(bad)) == 2  # gone.py, --nope
    assert len(rc.check_links(bad)) == 2  # missing.md, #no-such-heading
    assert len(rc.check_durations(bad)) == 1
    assert len(rc.check_step_boxes(bad)) == 2  # Step 1 without **Goal:**, Step 2 without a box
