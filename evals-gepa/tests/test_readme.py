"""README drift: a README that names a script, a flag, a link or a heading the repo no longer has, gives a time
estimate, or loses a step's Goal box (2026-11-16). The checks are in tools/readme_checks.py at the repo root."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import readme_checks as rc  # noqa: E402

PAGES = ["evals-gepa"]


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
