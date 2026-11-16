"""Checks that a tutorial README still matches the repo: commands, links, wording, step boxes. Standard library only,
so both folders' test suites (mcp/ and evals-gepa/) can import it. Each function returns a list of problems."""

from __future__ import annotations

import ast
import re
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
READMES = {"index": ROOT / "README.md", "mcp": ROOT / "mcp" / "README.md", "evals-gepa": ROOT / "evals-gepa" / "README.md"}

FENCE = re.compile(r"^\s*```")


def prose_lines(text: str) -> list[tuple[int, str]]:
    """(line number, line) for every line outside fenced code blocks."""
    out, inside = [], False
    for i, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            inside = not inside
            continue
        if not inside:
            out.append((i, line))
    return out


def fenced_blocks(text: str) -> list[tuple[str, int, list[str]]]:
    """(language, first line number, lines) for every fenced code block."""
    blocks, lang, start, body = [], None, 0, []
    for i, line in enumerate(text.splitlines(), 1):
        m = FENCE.match(line)
        if m and lang is None:
            lang, start, body = line.strip()[3:].strip(), i + 1, []
        elif m:
            blocks.append((lang, start, body))
            lang = None
        elif lang is not None:
            body.append(line)
    return blocks


def commands(text: str) -> list[tuple[int, str]]:
    """Commands a student runs: each line of a bash or powershell block (continuation lines joined), and each inline
    code span that starts with `uv run`. Returns (line number, command) with `cd` lines kept as they are."""
    out = []
    for lang, start, body in fenced_blocks(text):
        if lang not in ("bash", "powershell", "sh", "zsh"):
            continue
        cont = "\\" if lang != "powershell" else "`"
        joined, first = "", None
        for k, line in enumerate(body):
            first = start + k if first is None else first
            if line.rstrip().endswith(cont):
                joined += line.rstrip()[:-1] + " "
                continue
            joined += line
            if lang != "powershell" and _open_quote(joined):
                joined += "\n"  # a quoted argument goes on, as in `python -c "..."` over several lines
                continue
            if joined.strip():
                out.append((first, joined.strip()))
            joined, first = "", None
    for i, line in prose_lines(text):
        for span in re.findall(r"`([^`]+)`", line):
            if span.startswith("uv run "):
                out.append((i, span))
    return out


def _open_quote(cmd: str) -> bool:
    try:
        shlex.split(cmd)
        return False
    except ValueError:
        return True


def script_flags(path: Path) -> set[str]:
    """The option strings a script's argparse accepts (plus -h and --help when it uses argparse)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    flags = {a.value for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "add_argument"
             for a in n.args if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value.startswith("-")}
    return flags | {"-h", "--help"} if flags else flags


def task_params(path: Path) -> set[str]:
    """The parameters of the functions decorated with @task in an Inspect task file (what `-T name=value` sets)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {a.arg for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
            and any(getattr(d, "id", getattr(d, "attr", "")) == "task" for d in n.decorator_list) for a in n.args.args}


def check_commands(readme: Path) -> list[str]:
    """Every `uv run` command names a script that exists, with flags the script accepts."""
    problems, here = [], readme.parent
    dirs = [here]
    for n, cmd in commands(readme.read_text(encoding="utf-8")):
        if cmd.startswith("cd "):
            d = cmd.split(None, 1)[1].strip("'\"")
            dirs += [p for p in ((here / d).resolve(), (ROOT / d).resolve()) if p.is_dir()]
            continue
        if not cmd.startswith("uv run "):
            continue
        try:
            words = shlex.split(cmd)[2:]
        except ValueError:
            problems.append(f"{readme.name}:{n}: cannot parse `{cmd}`")
            continue
        while words and words[0].startswith("--"):  # uv's own options: --with pkg
            words = words[2:] if words[0] == "--with" else words[1:]
        if words[:1] == ["python"]:
            words = words[1:]
        if not words or words[0] in ("-m", "-c"):
            continue
        if words[:2] == ["inspect", "eval"]:
            script, args = words[2], words[3:]
        elif words[0].endswith(".py"):
            script, args = words[0], words[1:]
        else:
            continue  # a tool such as pytest, jupyter or `inspect view`
        found = next((d / script for d in dirs if (d / script).is_file()), None)
        if found is None:
            problems.append(f"{readme.name}:{n}: `{cmd}` names {script}, which does not exist")
            continue
        if words[0] == "inspect":
            params = task_params(found)
            for k, a in enumerate(args):
                if a == "-T" and k + 1 < len(args) and args[k + 1].split("=")[0] not in params:
                    problems.append(f"{readme.name}:{n}: `{cmd}`: {script} has no task parameter {args[k + 1]}")
            continue
        flags = script_flags(found)
        for a in args:
            if a.startswith("-") and a.split("=")[0] not in flags:
                problems.append(f"{readme.name}:{n}: `{cmd}`: {script} does not accept {a}")
    return problems


def github_anchors(md: Path) -> set[str]:
    """Heading anchors as GitHub makes them: lower case, punctuation removed, spaces to hyphens, -1, -2 for repeats."""
    seen: dict[str, int] = {}
    out = set()
    for _, line in prose_lines(md.read_text(encoding="utf-8")):
        m = re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
        if not m:
            continue
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", m.group(1))  # a link keeps its text
        text = re.sub(r"<[^>]+>", "", text).lower()
        slug = re.sub(r"[^\w\- ]", "", text).replace(" ", "-")
        n = seen.get(slug, 0)
        seen[slug] = n + 1
        out.add(slug if n == 0 else f"{slug}-{n}")
    return out


def check_links(readme: Path) -> list[str]:
    """Every relative link resolves to a file or folder in the repo, and an #anchor to a heading in that file."""
    problems = []
    for n, line in prose_lines(readme.read_text(encoding="utf-8")):
        line = re.sub(r"(?<!\[)`[^`]*`(?!\])", "", line)  # code spans that are not link text
        for target in re.findall(r"\]\(([^)\s]+)\)", line):
            if re.match(r"^[a-z]+:", target):
                continue  # https:, mailto:
            path, _, anchor = target.partition("#")
            dest = (readme.parent / path).resolve() if path else readme
            if not dest.exists():
                problems.append(f"{readme.name}:{n}: link {target}: {path} does not exist")
            elif not str(dest).startswith(str(ROOT)):
                problems.append(f"{readme.name}:{n}: link {target} leaves the repo")
            elif anchor and dest.suffix == ".md" and anchor not in github_anchors(dest):
                problems.append(f"{readme.name}:{n}: link {target}: no heading #{anchor} in {dest.name}")
    return problems


DURATION = re.compile(
    r"\b(?:\d+(?:\.\d+)?|a few|few|several|a couple of|one|two|three|four|five|ten|fifteen|twenty|thirty|sixty)"
    r"(?:\s*-\s*|\s+)?(?:s|secs?|seconds?|mins?|minutes?|hours?|hrs?|h)\b"
    r"|(?<!requests )(?<!calls )\b(?:a|an|half an)\s+(?:minute|hour)\b",
    re.I)


def durations(text: str) -> list[str]:
    """Time estimates in student text ("about 5 minutes", "30 s", "an hour"). "A second terminal" and
    "per-minute limit" are not durations."""
    return [m.group(0) for m in DURATION.finditer(text)]


def check_durations(readme: Path) -> list[str]:
    return [f"{readme.name}:{n}: duration {d!r}" for n, line in prose_lines(readme.read_text(encoding="utf-8"))
            for d in durations(line)]


def check_step_boxes(readme: Path) -> list[str]:
    """Every "### Step N" has a "What happens when you do this step" box whose first line starts with **Goal:**."""
    problems, lines = [], readme.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if not re.match(r"^### Step \d+\b", line):
            continue
        end = next((j for j in range(i + 1, len(lines)) if re.match(r"^#{1,3} ", lines[j])), len(lines))
        section = lines[i + 1:end]
        k = next((j for j, l in enumerate(section) if "<summary>What happens when you do this step</summary>" in l), None)
        if k is None:
            problems.append(f"{readme.name}:{i + 1}: {line.strip()} has no 'What happens when you do this step' box")
            continue
        first = next((l for l in section[k + 1:] if l.strip()), "")
        if not first.startswith("**Goal:**"):
            problems.append(f"{readme.name}:{i + 1}: {line.strip()}: the box starts {first[:40]!r}, not **Goal:**")
    return problems
