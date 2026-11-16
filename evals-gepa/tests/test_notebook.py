"""tutorial.ipynb, Run All, on the stand-in: the extras did not stay off, and the first cell asked for the token
although it was in .env (2026-11-16)."""
import os

import nbformat
import pytest
from nbclient import NotebookClient

import stand_in_gateway


def run_all(kit_copy, env: dict) -> nbformat.NotebookNode:
    nb = nbformat.read(kit_copy / "tutorial.ipynb", as_version=4)
    old = dict(os.environ)
    os.environ.clear()
    os.environ.update(env)  # the kernel starts with this environment
    try:
        NotebookClient(nb, kernel_name="python3", timeout=300, resources={"metadata": {"path": str(kit_copy)}}).execute()
    finally:
        os.environ.clear()
        os.environ.update(old)
    return nb


def outputs(cell) -> str:
    return "".join(o.get("text", "") + "".join(o.get("data", {}).get("text/plain", "")) for o in cell.get("outputs", []))


@pytest.mark.parametrize("token_in", ["env", "dotenv"])
def test_run_all_on_the_stand_in_skips_the_extras_and_reads_dotenv(stand_in, kit_copy, tmp_path, token_in):
    from conftest import kit_env

    env = kit_env(stand_in, tmp_path)
    env.pop("B5T1_NO_DOTENV")  # the notebook must read a .env file like a student's laptop
    if token_in == "dotenv":
        env.pop("KB_MCP_TOKEN")  # only in .env: a getpass prompt would fail the run
        (kit_copy.parent / ".env").write_text(f"KB_MCP_TOKEN={stand_in_gateway.TOKEN}\n", encoding="utf-8")
    nb = run_all(kit_copy, env)  # raises CellExecutionError on any error cell

    code = [c for c in nb.cells if c.cell_type == "code"]
    assert not [o for c in code for o in c.outputs if o.output_type == "error"]
    assert "KB_MCP_TOKEN is set" in outputs(code[0])
    extras = [c for c in code if "if not RUN_" in c.source]
    assert extras and all(outputs(c).startswith("Skipped") for c in extras)
    assert stand_in.calls_by_model.get("gpt-6-luna", 0) == 0
    compare_line = next(l for c in code for l in outputs(c).splitlines() if l.startswith("check: the after score"))
    assert compare_line.endswith("yes")  # after >= before on the held-out cases
