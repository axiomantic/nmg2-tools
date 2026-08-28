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

A SECOND CLAUSE READS THE INDEX, NOT THE TEXT.

Everything above walks ``.gitmodules`` and asks the authority table about the
URLs it finds. That direction cannot see a submodule that has no section:
the gitlink is in the tree, git will clone it, and no ``url =`` line exists
for the table to be asked about. Reading the text alone, such a submodule is
indistinguishable from no submodule at all.

Until now the payload lint caught that case by accident -- a gitlink reached
it as a path with no register row, and it reported PAYLOAD-UNREGISTERED for
it. That was a false positive for every DECLARED submodule in the set, and it
has been removed there, so the case it covered by accident is covered here on
purpose. SUBMODULE-UNDECLARED walks the mode-160000 index entries and reports
any the text does not declare.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from nmg2_tools.gitindex import gitlink_paths

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

# The `path = ` line of a `[submodule]` section. This is the field git itself
# matches a gitlink against -- NOT the section name, which is only a label and
# is free to differ from the path.
_PATH_RE = re.compile(r"^\s*path\s*=\s*(?P<path>\S.*?)\s*$")


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


def declared_paths(text: str) -> set[str]:
    """Return the ``path = `` values declared in a ``.gitmodules`` text."""
    paths: set[str] = set()
    for line in text.splitlines():
        m = _PATH_RE.match(line)
        if m:
            paths.add(m.group("path").rstrip("/"))
    return paths


def lint_undeclared_gitlinks(
    gitlinks: list[str], declared: set[str]
) -> list[str]:
    """Report each gitlink that no ``.gitmodules`` section declares.

    An undeclared gitlink is not a cosmetic defect. git clones a submodule
    from the URL in ``.gitmodules``; with no section there is no URL for the
    authority table to be asked about, so the whole of this module's first
    clause runs over a tree it cannot see. This is the one shape in which a
    submodule reaches a public repository with NOTHING having decided whose
    repository it is.
    """
    return [
        f"SUBMODULE-UNDECLARED: {path}: the index records a submodule "
        "gitlink here, but no `.gitmodules` section declares this path, so "
        "no URL reached the authority table"
        for path in gitlinks
        if path.rstrip("/") not in declared
    ]


def lint_repo_tree(repo_path: Path) -> tuple[list[str], list[str]]:
    """Lint the ``.gitmodules`` text AND the gitlinks the index actually holds.

    The two are read together on purpose. A missing ``.gitmodules`` used to
    return a clean pass, which is the same answer this function gives for a
    repository that genuinely has no submodules -- and one of those two is a
    tree with undeclared gitlinks in it.
    """
    gitmodules = repo_path / ".gitmodules"
    text = gitmodules.read_text() if gitmodules.is_file() else ""
    failures, notes = lint_gitmodules_text(text)

    try:
        gitlinks = gitlink_paths(repo_path)
    except (OSError, subprocess.CalledProcessError) as error:
        # FAIL CLOSED. A directory git cannot list is a directory in which
        # this clause checked nothing, and a clean pass would say the
        # opposite of that. It gets a named finding for the same reason
        # payload_lint's register clause refuses an unrostered `--repo`.
        failures.append(
            f"SUBMODULE-INDEX-UNREADABLE: {repo_path}: git could not list "
            f"the index here ({error}), so no gitlink was checked"
        )
        return failures, notes

    failures.extend(lint_undeclared_gitlinks(gitlinks, declared_paths(text)))
    return failures, notes


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
