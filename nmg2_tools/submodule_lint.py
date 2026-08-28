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

A THIRD CLAUSE READS THE DECLARATION BACK AGAINST THE INDEX.

SUBMODULE-UNDECLARED runs from the index to the text. The reverse direction --
a section declaring a `path` the index holds no gitlink at -- was unchecked,
and it is a DIFFERENT defect, not the same one seen from the other side. Its
usual origin is a submodule removed by hand: `git rm --cached` drops the
gitlink and leaves the section standing, which is a documented git footgun.
What is left behind is a declaration that binds nothing: the authority table
is asked about a URL for a submodule that is not in the tree, so the check
reports a clean answer about a repository this one no longer pulls in.

THERE IS NO "NOT YET" CASE HERE, AND THAT IS WHY THIS IS A PLAIN ERROR.

The provenance register in `payload_lint` needed a `pending=<reason>` marker
because a row may legitimately precede its file: that register is ONE
hand-written file shared by seven repositories, so a row can name a path that
is real in a repository which has not landed it yet. `.gitmodules` is not that
kind of file. It describes ONE tree, it is maintained by git itself, and no
git operation writes a section without staging the gitlink in the same
commit -- `git submodule add` does both at once. A section with no gitlink is
therefore always wrong and never merely early. Giving it a `pending=` escape
would build a hiding place with no legitimate occupant, which is the silent
bucket this project keeps closing, in a new costume.

The parse is SECTION-AWARE for the same reason clause 2 keys on `path =` and
not on the section label: it must agree with git about what a declaration IS.
A `path =` line outside any `[submodule "..."]` section declares nothing to
git, so it must not be able to answer SUBMODULE-UNDECLARED either -- otherwise
a line git ignores could silence the clause. A section that declares no `path`
at all binds to no gitlink and is reported as SUBMODULE-DECLARATION-NO-PATH:
it is the same "declares nothing" defect arriving one field over.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
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

# The section header. git spells a submodule section `[submodule "<name>"]`,
# and the quoted name is a LABEL: it is conventionally the path and is under
# no obligation to be. Any other section header closes the submodule section
# that was open, so `path =` lines below it belong to something else.
_SUBMODULE_SECTION_RE = re.compile(r'^\s*\[submodule\s+"(?P<name>[^"]*)"\]\s*$')
_ANY_SECTION_RE = re.compile(r"^\s*\[")


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


@dataclass(frozen=True)
class Section:
    """One ``[submodule "<name>"]`` section of a ``.gitmodules`` file.

    ``path`` is ``None`` when the section declares no ``path = `` line. That
    is not the same as an empty path: git binds a section to a gitlink through
    this field alone, so a section without one binds to nothing at all, and
    the two cases get different findings.
    """

    name: str
    lineno: int
    path: str | None = None


def parse_sections(text: str) -> list[Section]:
    """Return the ``[submodule "..."]`` sections of a ``.gitmodules`` text.

    The parse is section-aware rather than a scan for ``path = `` lines,
    because this module must agree with git about what a declaration IS. git
    reads ``path`` only inside a submodule section; a ``path = `` line at top
    level, or under some other section, is not a declaration to git and must
    not be treated as one here either. A line-based scan would let a line git
    ignores answer :func:`lint_undeclared_gitlinks`, which is a way to silence
    that clause without declaring anything.

    A repeated ``path = `` inside one section takes the LAST value, which is
    what git's config parser does with a repeated single-valued key.
    """
    sections: list[Section] = []
    open_name: str | None = None
    open_lineno = 0
    open_path: str | None = None

    def close() -> None:
        nonlocal open_name
        if open_name is not None:
            sections.append(
                Section(name=open_name, lineno=open_lineno, path=open_path)
            )
            open_name = None

    for lineno, line in enumerate(text.splitlines(), start=1):
        header = _SUBMODULE_SECTION_RE.match(line)
        if header:
            close()
            open_name = header.group("name")
            open_lineno = lineno
            open_path = None
            continue
        if _ANY_SECTION_RE.match(line):
            # Some other section. It ENDS the submodule section that was open;
            # the keys below it are not this submodule's.
            close()
            continue
        if open_name is None:
            continue
        m = _PATH_RE.match(line)
        if m:
            open_path = m.group("path").rstrip("/")

    close()
    return sections


def declared_paths(text: str) -> set[str]:
    """Return the ``path = `` values declared by the text's submodule sections."""
    return {
        section.path
        for section in parse_sections(text)
        if section.path is not None
    }


def lint_stale_declarations(
    gitlinks: list[str], sections: list[Section]
) -> list[str]:
    """Report each section whose declaration binds to no gitlink -- clause 3.

    The mirror of :func:`lint_undeclared_gitlinks`, and a different defect
    from it. A section left behind by a submodule removed by hand still names
    a URL, so the authority table goes on answering about a repository this
    tree no longer pulls in, and the answer looks like a check that ran.

    There is no ``pending`` escape and there is deliberately no way to write
    one. See this module's docstring: git writes the section and stages the
    gitlink in the same operation, so a section ahead of its gitlink is not a
    state any git command produces.
    """
    present = {path.rstrip("/") for path in gitlinks}
    failures: list[str] = []
    for section in sections:
        if section.path is None:
            failures.append(
                f"SUBMODULE-DECLARATION-NO-PATH: line {section.lineno}: "
                f"section [submodule \"{section.name}\"] declares no `path = `, "
                "so git binds it to no gitlink and it declares nothing. The "
                "section name is a label, not a path"
            )
        elif section.path not in present:
            failures.append(
                f"SUBMODULE-STALE-DECLARATION: line {section.lineno}: "
                f"section [submodule \"{section.name}\"] declares "
                f"`path = {section.path}`, but the index records no submodule "
                "gitlink there, so this declaration binds nothing and its URL "
                "names a repository this tree does not pull in. Remove the "
                "section, or restore the gitlink"
            )
    return failures


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

    Both DIRECTIONS between the text and the index are checked here, and they
    are separate clauses because they are separate defects. A gitlink with no
    section reached the authority table with no URL
    (``SUBMODULE-UNDECLARED``); a section with no gitlink asked the authority
    table about a submodule that is not in this tree
    (``SUBMODULE-STALE-DECLARATION``). A ``.gitmodules`` can be wrong in both
    directions at once, and then both fire.

    Neither direction is checked when the index could not be read. That path
    returns early with ``SUBMODULE-INDEX-UNREADABLE`` rather than running the
    stale clause against an empty gitlink list, which would report every
    section in the file as stale and bury the one finding that is true.
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

    sections = parse_sections(text)
    failures.extend(lint_undeclared_gitlinks(gitlinks, declared_paths(text)))
    failures.extend(lint_stale_declarations(gitlinks, sections))
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
