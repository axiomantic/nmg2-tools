"""Check that every submodule URL names an authorised public repository.

This check is static. It reads no network. It parses the content of a
``.gitmodules`` file and holds each URL against a fixed authority table.

The authority table below is the same table the plan document states. Keep
it in sync with the plan by hand; this module does not read the plan.

THE SCOPE OF THE HARD FAILURE IS THE `axiomantic` ORGANIZATION, AND THE PLAN
STATES THE RULE TWICE IN TWO WIDTHS.

The recorded-fixture register states it as an allow-list: "any URL that does
not name a repository the repository table lists as PUBLIC". The task's own
check states it as a prohibition: the step "fails when a `.gitmodules` file in
the repository names `nmg2-artifacts`, or names any URL under `axiomantic` that
is private", and it requires the step to PASS on the `gearmulator` fork.

The two cannot both hold. The `.gitmodules` of the real fork declares
submodules that are third-party public repositories the table does not list and
never will, among them JUCE, cpp-terminal, clap-juce-extensions, RmlUi, freetype
and lunasvg. Under the allow-list reading the step fails on that fork for ever,
so the task could not pass its own check.

This module implements the PROHIBITION reading, which is the task gate:

  * a URL naming the private repository is a hard failure;
  * a URL under `axiomantic` that is not on the public list is a hard failure,
    because a repository of this project's own that is missing from the table
    is exactly the defect the table exists to catch;
  * a URL outside the `axiomantic` organization is REPORTED and is not a
    failure. It cannot be this project's private repository.

The contradiction is a plan defect and it is recorded here rather than
resolved silently.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PUBLIC = {
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
}

PRIVATE = {
    "axiomantic/nmg2-artifacts",
}

# Matches both URL forms:
#   https://github.com/<owner>/<repo>.git
#   git@github.com:<owner>/<repo>.git
_URL_RE = re.compile(
    r"^\s*url\s*=\s*(?:https://github\.com/|git@github\.com:)"
    r"(?P<owner>[^/]+)/(?P<repo>[^/\s]+?)(?:\.git)?\s*$"
)


def _repo_name(url_line: str) -> str | None:
    """Return ``owner/repo`` for a ``.gitmodules`` ``url = ...`` line, or None."""
    m = _URL_RE.match(url_line)
    if not m:
        return None
    return f"{m.group('owner')}/{m.group('repo')}"


def lint_gitmodules_text(text: str) -> tuple[list[str], list[str]]:
    """Return ``(failures, notes)`` for the given ``.gitmodules`` text.

    A failure fails the step. A note is printed and does not.
    """
    failures: list[str] = []
    notes: list[str] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        repo = _repo_name(line)
        if repo is None:
            continue
        if repo in PRIVATE:
            failures.append(
                f"SUBMODULE-PRIVATE: line {lineno}: {repo} is a private repository"
            )
        elif repo in PUBLIC:
            continue
        elif repo.startswith("axiomantic/"):
            failures.append(
                f"SUBMODULE-UNLISTED: line {lineno}: {repo} is not on the "
                "public authority list"
            )
        else:
            notes.append(
                f"SUBMODULE-THIRD-PARTY: line {lineno}: {repo} is outside the "
                "axiomantic organization and is not this project's to list"
            )
    return failures, notes


def lint_repo_tree(repo_path: Path) -> tuple[list[str], list[str]]:
    """Lint the ``.gitmodules`` file at the root of ``repo_path``, if any."""
    gitmodules = repo_path / ".gitmodules"
    if not gitmodules.is_file():
        return [], []
    return lint_gitmodules_text(gitmodules.read_text())


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "repo_path", type=Path, help="path to the repository root to check"
    )
    args = parser.parse_args(argv)

    failures, notes = lint_repo_tree(args.repo_path)
    for note in notes:
        print(note)
    for failure in failures:
        print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
