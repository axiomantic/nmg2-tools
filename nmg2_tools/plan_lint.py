"""Check a plan markdown document against nine internal-consistency rules.

Document format this module expects
------------------------------------
A task is a markdown heading line that holds a task ID. A task ID matches
``PREFIX-<n>`` (letters/digits, a dash, digits), for example ``T0-3``. A
task section runs from its heading line to the next heading line of the
same or shallower level, or to the end of the document.

Inside a task section this module reads four labelled fields, one per
line unless stated otherwise:

- ``Repo: <name>``            -- the repository the task's build tree
  belongs to (used by condition 2).
- ``Targets: <repo>, <repo>`` -- every repository the task forks,
  pushes to, or opens a pull request against (used by condition 5).
- ``Depends: <list>``          -- the task's dependencies (condition 9).
- ``Files:`` followed by indented list lines of the form
  ``- <repo>: <path>`` (one file per line), until a blank line or the
  next labelled field.
- ``Check:`` followed either by a fenced code block (three backticks)
  holding the check commands, or by a line of prose naming a failure
  mechanism (see condition 8).

COMMAND scope is: every line inside a ``Check:`` block, every command
cell in a milestone table row (a markdown table row where a cell holds
`` ` `` backtick-quoted shell text), and every fenced code block whose
first line does not begin with ``$ `` (a line beginning ``$ `` is a
recorded transcript of a command's output, not an instruction, and is
excluded).

FIELD scope is: ``Files:`` lines, ``Depends:`` lines, and task header
lines.

Path abbreviation expansion (applied before any path comparison)
------------------------------------------------------------------
Rule B: inside the ``gearmulator`` repository, ``g2Lib/``,
``g2JucePlugin/`` and ``g2TestConsole/`` abbreviate
``source/nord/g2/g2Lib/``, ``source/nord/g2/g2JucePlugin/`` and
``source/nord/g2/g2TestConsole/``. The two spellings name one file.

Rule C: in a ``Files:`` line, a path of the form ``.../name.ext`` means
the DIRECTORY of the ``Files:`` item immediately before it, with
``name.ext`` replacing that item's basename.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

TIER_PREFIXES = ("t0_", "t1_", "t2_", "dsp56k_", "cpu_")

# Same authority table as submodule_lint.py, plus the private artifacts repo,
# for condition 5's target-repository check.
KNOWN_REPOS = {
    "axiomantic/mcf5307",
    "axiomantic/nmg2-tools",
    "axiomantic/gearmulator",
    "axiomantic/dsp56300",
    "axiomantic/mc68k",
    "axiomantic/G2-Edit",
    "dsp56300/gearmulator",
    "dsp56300/dsp56300",
    "dsp56300/mc68k",
    "chrispurusha/G2-Edit",
    "axiomantic/nmg2-artifacts",
}

_TASK_ID_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9]*-\d+)\b")
_HEADING_RE = re.compile(r"^(#{1,6})\s+.*")
_FILES_ITEM_RE = re.compile(r"^\s*-\s*(?P<repo>[^:]+):\s*(?P<path>\S+)\s*$")
_DASH_R_RE = re.compile(r"-R\s+(\S+)")
_TARGET_RE = re.compile(r"--target[= ]\s*(\S+)")
_CTEST_TEST_LISTING_RE = re.compile(r"^\s*Test\s+#\d+:\s*(\S+)\s*$", re.MULTILINE)
_MECHANISM_WORDS = ("asserts", "fails", "negative case", "exits", "must fail")
_DEPENDS_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*-\d+$")


# --------------------------------------------------------------------------
# Path abbreviation expansion.
# --------------------------------------------------------------------------

_RULE_B_ABBREV = {
    "g2Lib/": "source/nord/g2/g2Lib/",
    "g2JucePlugin/": "source/nord/g2/g2JucePlugin/",
    "g2TestConsole/": "source/nord/g2/g2TestConsole/",
}


def expand_rule_b(repo: str, path: str) -> str:
    """Expand the gearmulator path abbreviations to their canonical form."""
    if repo != "gearmulator":
        return path
    for short, full in _RULE_B_ABBREV.items():
        if path.startswith(short):
            return full + path[len(short) :]
    return path


def expand_rule_c(path: str, previous_path: str | None) -> str:
    """Expand a ``.../name.ext`` path against the immediately preceding item."""
    if not path.startswith(".../"):
        return path
    name = path[len(".../") :]
    if previous_path is None:
        # No preceding item to take a directory from; leave unexpanded so
        # the caller sees an unresolved abbreviation rather than a false
        # equivalence.
        return path
    directory = previous_path.rsplit("/", 1)[0] if "/" in previous_path else ""
    return f"{directory}/{name}" if directory else name


# --------------------------------------------------------------------------
# Document model.
# --------------------------------------------------------------------------


@dataclass
class FileEntry:
    repo: str
    path: str
    lineno: int


@dataclass
class Task:
    task_id: str
    header_lineno: int
    repo: str | None = None
    targets: list[str] = field(default_factory=list)
    depends_raw: str | None = None
    depends_lineno: int | None = None
    files: list[FileEntry] = field(default_factory=list)
    check_lines: list[str] = field(default_factory=list)
    check_present: bool = False
    start: int = 0
    end: int = 0


@dataclass
class CommandOccurrence:
    text: str
    lineno: int


def parse_plan(text: str) -> tuple[list[Task], list[CommandOccurrence]]:
    """Parse the plan text into tasks and the COMMAND-scope occurrences."""
    lines = text.splitlines()
    n = len(lines)

    # Locate task headings.
    headings: list[tuple[int, int, str]] = []  # (lineno, level, task_id)
    for i, line in enumerate(lines):
        m = _HEADING_RE.match(line)
        if not m:
            continue
        id_match = _TASK_ID_RE.search(line)
        if id_match:
            headings.append((i, len(m.group(1)), id_match.group(1)))

    tasks: list[Task] = []
    for idx, (lineno, level, task_id) in enumerate(headings):
        end = n
        for later_lineno, later_level, _ in headings[idx + 1 :]:
            if later_level <= level:
                end = later_lineno
                break
        task = Task(task_id=task_id, header_lineno=lineno + 1, start=lineno, end=end)
        tasks.append(task)

    # Parse each task's body.
    for task in tasks:
        _parse_task_body(lines, task)

    # COMMAND-scope occurrences: every line inside a Check: block, every
    # command cell in a milestone table row, and every fenced block whose
    # first line does not begin with "$ ".
    commands = _extract_command_scope(lines)

    return tasks, commands


def _parse_task_body(lines: list[str], task: Task) -> None:
    i = task.start + 1
    end = task.end
    prev_file_path: str | None = None
    while i < end:
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("Repo:"):
            task.repo = stripped[len("Repo:") :].strip()
            i += 1
            continue

        if stripped.startswith("Targets:"):
            rest = stripped[len("Targets:") :].strip()
            task.targets = [t.strip() for t in rest.split(",") if t.strip()]
            i += 1
            continue

        if stripped.startswith("Depends:"):
            task.depends_raw = stripped[len("Depends:") :].strip()
            task.depends_lineno = i + 1
            i += 1
            continue

        if stripped.startswith("Files:"):
            i += 1
            prev_file_path = None
            while i < end:
                item_line = lines[i]
                if not item_line.strip():
                    break
                m = _FILES_ITEM_RE.match(item_line)
                if not m:
                    break
                repo = m.group("repo").strip()
                raw_path = m.group("path").strip()
                path = expand_rule_c(raw_path, prev_file_path)
                path = expand_rule_b(repo, path)
                task.files.append(FileEntry(repo=repo, path=path, lineno=i + 1))
                prev_file_path = path
                i += 1
            continue

        if stripped.startswith("Check:"):
            task.check_present = True
            i += 1
            # A fenced code block immediately below, or prose lines until a
            # blank line / next labelled field / next heading.
            if i < end and lines[i].strip().startswith("```"):
                i += 1
                while i < end and not lines[i].strip().startswith("```"):
                    task.check_lines.append(lines[i])
                    i += 1
                i += 1  # skip closing fence
            else:
                while i < end and lines[i].strip():
                    if _HEADING_RE.match(lines[i]):
                        break
                    task.check_lines.append(lines[i])
                    i += 1
            continue

        i += 1


def _extract_command_scope(lines: list[str]) -> list[CommandOccurrence]:
    commands: list[CommandOccurrence] = []
    i = 0
    n = len(lines)
    in_check_block = False
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("Check:"):
            in_check_block = True
            i += 1
            continue

        if stripped.startswith("```"):
            # Determine whether this fence starts a transcript (first
            # content line begins "$ ") or an instruction block.
            fence_start = i
            i += 1
            block_lines: list[tuple[int, str]] = []
            while i < n and not lines[i].strip().startswith("```"):
                block_lines.append((i, lines[i]))
                i += 1
            i += 1  # skip closing fence
            in_check_block = False
            is_transcript = bool(block_lines) and block_lines[0][1].lstrip().startswith(
                "$ "
            )
            if is_transcript:
                continue
            for lineno, block_line in block_lines:
                if block_line.strip():
                    commands.append(CommandOccurrence(text=block_line, lineno=lineno + 1))
            continue

        if "|" in line and ("ctest" in line or "pytest" in line or "--target" in line):
            # A milestone table row holding a command cell.
            commands.append(CommandOccurrence(text=line, lineno=i + 1))

        i += 1

    return commands


# --------------------------------------------------------------------------
# The nine conditions.
# --------------------------------------------------------------------------


def _files_text_blob(tasks: list[Task]) -> str:
    return "\n".join(f"{e.repo}: {e.path}" for task in tasks for e in task.files)


def check_c1(tasks: list[Task], commands: list[CommandOccurrence]) -> list[str]:
    failures = []
    blob = _files_text_blob(tasks)
    for occ in commands:
        for m in _DASH_R_RE.finditer(occ.text):
            name = m.group(1)
            if name.startswith(TIER_PREFIXES):
                continue
            if name in blob:
                continue
            failures.append(
                f"PLAN-C1: line {occ.lineno}: -R name '{name}' is not on the "
                "tier-prefix allow-list and appears in no task's Files: line"
            )
    return failures


def check_c2(
    tasks: list[Task],
    commands: list[CommandOccurrence],
    build_dirs: dict[str, str],
    complete_ids: set[str],
) -> list[str]:
    failures = []
    complete_tasks = [t for t in tasks if t.task_id in complete_ids]
    for task in complete_tasks:
        r_names = set()
        for line in task.check_lines:
            for m in _DASH_R_RE.finditer(line):
                r_names.add(m.group(1))
        if not r_names:
            continue
        repo = task.repo
        if repo is None or repo not in build_dirs:
            failures.append(
                f"PLAN-C2: task {task.task_id}: declared complete but has no "
                "registered build tree for its repository"
            )
            continue
        build_dir = build_dirs[repo]
        result = subprocess.run(
            ["ctest", "--test-dir", build_dir, "--no-tests=error", "-N"],
            capture_output=True,
            text=True,
        )
        registered = set(_CTEST_TEST_LISTING_RE.findall(result.stdout))
        for name in r_names:
            if name not in registered:
                failures.append(
                    f"PLAN-C2: task {task.task_id}: '{name}' is not a "
                    f"registered CTest test in build tree {build_dir}"
                )
    return failures


def check_c3(commands: list[CommandOccurrence]) -> list[str]:
    failures = []
    for occ in commands:
        if "ctest" in occ.text and "--no-tests=error" not in occ.text:
            failures.append(
                f"PLAN-C3: line {occ.lineno}: ctest invocation missing "
                "--no-tests=error"
            )
    return failures


def check_c4(commands: list[CommandOccurrence]) -> list[str]:
    failures = []
    for occ in commands:
        if "ctest" not in occ.text:
            continue
        tokens = occ.text.split()
        if "--" not in tokens:
            failures.append(
                f"PLAN-C4: line {occ.lineno}: ctest invocation forwards no "
                "arguments with --"
            )
    return failures


def check_c5(tasks: list[Task]) -> list[str]:
    failures = []
    for task in tasks:
        for repo in task.targets:
            if repo not in KNOWN_REPOS:
                failures.append(
                    f"PLAN-C5: task {task.task_id}: target repository "
                    f"'{repo}' is not in the repository table"
                )
    return failures


def check_c6(tasks: list[Task], commands: list[CommandOccurrence]) -> list[str]:
    failures = []
    blob = _files_text_blob(tasks)
    for occ in commands:
        for m in _TARGET_RE.finditer(occ.text):
            name = m.group(1)
            if name in blob:
                continue
            failures.append(
                f"PLAN-C6: line {occ.lineno}: --target '{name}' appears in "
                "no task's Files: line"
            )
    return failures


def check_c7(tasks: list[Task], owners: dict[tuple[str, str], str]) -> list[str]:
    failures = []
    claimants: dict[tuple[str, str], list[str]] = {}
    for task in tasks:
        for entry in task.files:
            key = (entry.repo, entry.path)
            claimants.setdefault(key, []).append(task.task_id)
    for key, claiming_tasks in claimants.items():
        if len(set(claiming_tasks)) <= 1:
            continue
        if key in owners:
            continue
        repo, path = key
        failures.append(
            f"PLAN-C7: {repo}:{path} is claimed by tasks "
            f"{', '.join(sorted(set(claiming_tasks)))} with no declared owner"
        )
    return failures


def check_c8(tasks: list[Task]) -> list[str]:
    failures = []
    for task in tasks:
        block_text = "\n".join(task.check_lines)
        if not task.check_present:
            failures.append(f"PLAN-C8: task {task.task_id}: has no Check: block")
            continue
        has_test_invocation = "ctest" in block_text or "pytest" in block_text
        has_mechanism = any(word in block_text for word in _MECHANISM_WORDS)
        if not has_test_invocation and not has_mechanism:
            failures.append(
                f"PLAN-C8: task {task.task_id}: Check: block holds no ctest "
                "or pytest invocation and names no failure mechanism"
            )
    return failures


def check_c9(tasks: list[Task]) -> list[str]:
    failures = []
    for task in tasks:
        if task.depends_raw is None:
            continue
        raw = task.depends_raw.strip()
        if raw.lower() == "none":
            continue
        ok = True
        for part in raw.split(","):
            part = part.strip()
            if not part:
                ok = False
                break
            if " to " in part:
                lo, _, hi = part.partition(" to ")
                if not (
                    _DEPENDS_TOKEN_RE.match(lo.strip())
                    and _DEPENDS_TOKEN_RE.match(hi.strip())
                ):
                    ok = False
                    break
            elif not _DEPENDS_TOKEN_RE.match(part):
                ok = False
                break
        if not ok:
            failures.append(
                f"PLAN-C9: task {task.task_id}: Depends: line '{task.depends_raw}' "
                "holds something other than identifiers, ranges, or 'none'"
            )
    return failures


_TEST_FILE_RE = re.compile(
    r"(^|/)(test_[^/]+\.py|[^/]+_test\.(cpp|cc)|"
    r"(?:" + "|".join(TIER_PREFIXES) + r")[^/]+\.(cpp|cc))$"
)


def check_reverse(tasks: list[Task], commands: list[CommandOccurrence]) -> list[str]:
    failures = []
    command_blob = "\n".join(occ.text for occ in commands)
    for task in tasks:
        for entry in task.files:
            if not _TEST_FILE_RE.search(entry.path):
                continue
            stem = Path(entry.path).stem
            if stem in command_blob or entry.path in command_blob:
                continue
            failures.append(
                f"PLAN-REVERSE: {entry.repo}:{entry.path} (task {task.task_id}) "
                "is created but never invoked by a Check: -R argument or a "
                "pytest path"
            )
    return failures


def check_checktargets(
    tasks: list[Task], repo: str, targets_file: Path
) -> list[str]:
    declared: set[str] = set()
    for raw_line in targets_file.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        declared.add(line)

    named: set[str] = set()
    for task in tasks:
        if task.repo != repo:
            continue
        for line in task.check_lines:
            for m in _DASH_R_RE.finditer(line):
                named.add(m.group(1))
            for m in re.finditer(r"pytest\s+(\S+)", line):
                named.add(f"pytest {m.group(1)}")

    if declared != named:
        missing = named - declared
        extra = declared - named
        detail = []
        if missing:
            detail.append(f"missing from file: {sorted(missing)}")
        if extra:
            detail.append(f"not named by any Check: line: {sorted(extra)}")
        return ["PLAN-CHECKTARGETS: " + "; ".join(detail)]
    return []


def load_owners(owners_path: Path) -> dict[tuple[str, str], str]:
    owners: dict[tuple[str, str], str] = {}
    for raw_line in owners_path.read_text().splitlines():
        line = raw_line.strip("\n")
        if not line.strip() or line.strip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        repo, path, owner_task = parts[0].strip(), parts[1].strip(), parts[2].strip()
        # Apply Rule B so an owners-file path in its short (gearmulator)
        # spelling still matches a Files: line's expanded canonical path.
        owners[(repo, expand_rule_b(repo, path))] = owner_task
    return owners


# --------------------------------------------------------------------------
# CLI.
# --------------------------------------------------------------------------


def lint_text(
    text: str,
    build_dirs: dict[str, str] | None = None,
    complete_ids: set[str] | None = None,
    owners: dict[tuple[str, str], str] | None = None,
) -> list[str]:
    """Run all nine conditions plus the reverse check over plan text."""
    build_dirs = build_dirs or {}
    complete_ids = complete_ids or set()
    owners = owners or {}

    tasks, commands = parse_plan(text)

    failures: list[str] = []
    failures += check_c1(tasks, commands)
    failures += check_c2(tasks, commands, build_dirs, complete_ids)
    failures += check_c3(commands)
    failures += check_c4(commands)
    failures += check_c5(tasks)
    failures += check_c6(tasks, commands)
    failures += check_c7(tasks, owners)
    failures += check_c8(tasks)
    failures += check_c9(tasks)
    failures += check_reverse(tasks, commands)
    return failures


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan_path", type=Path, help="path to the plan markdown document")
    parser.add_argument(
        "--build-dir",
        action="append",
        default=[],
        metavar="REPO=PATH",
        help="repeatable: the build tree of a repository, e.g. gearmulator=/path/build",
    )
    parser.add_argument(
        "--complete",
        default="",
        help="comma-separated list of task IDs the run declares complete",
    )
    parser.add_argument(
        "--owners",
        type=Path,
        default=None,
        help="path to the owners file (repository<TAB>path<TAB>owner-task)",
    )
    parser.add_argument(
        "--check-targets",
        action="append",
        default=[],
        metavar="REPO=PATH",
        help="repeatable: assert docs/check-targets.txt for REPO equals its "
        "plan-declared Check: targets",
    )
    args = parser.parse_args(argv)

    build_dirs = dict(item.split("=", 1) for item in args.build_dir)
    complete_ids = {t.strip() for t in args.complete.split(",") if t.strip()}
    owners = load_owners(args.owners) if args.owners else {}

    text = args.plan_path.read_text()
    failures = lint_text(text, build_dirs, complete_ids, owners)

    if args.check_targets:
        tasks, _ = parse_plan(text)
        for item in args.check_targets:
            repo, _, targets_path = item.partition("=")
            failures += check_checktargets(tasks, repo, Path(targets_path))

    for failure in failures:
        print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
