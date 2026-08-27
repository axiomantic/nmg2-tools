"""Check that committed payloads stay inside the agreed size and location rules.

This check reads TRACKED FILES ONLY (the output of ``git ls-files``), which is
the INDEX and not the last commit -- so a staged-but-uncommitted file IS read,
and "committed" would be off by exactly that set. It
does not read workflow text and it implements no upload check; a separate
step of the plan owns checking what a workflow actually uploads. This
module only checks what is already sitting in the repository's git index.

It takes a ``--visibility public|private`` argument (default ``public``),
the same meaning it has in ``credential_lint.py``, and enforces these
independent conditions, each with its own failure name:

1. PAYLOAD-PCH2-LOCATION: a ``*.pch2`` file anywhere in a public repository
   outside ``nmg2_tools/testdata/pch2_synth/`` fails, unless the register
   holds a ``public pch2-exception`` row covering the path, in which case
   this clause passes.
2. PAYLOAD-UNREGISTERED: any committed file that carries neither a register
   row nor a by-rule classification fails, at any size, in either
   visibility. This is the guard's default answer, and it is the reason the
   guard can be trusted at all: a file the register has never heard of is
   exactly what a payload check exists to notice, so silence is never the
   response to one. A REPO-SCOPED row counts as a row only in the repository
   it names; anywhere else the register has not heard of the path, and this
   clause answers. ``.gitkeep`` files are exempt everywhere: they are
   directory markers, not payload, and a private repository uses one to make
   a registered but empty directory exist.

   Two CLASSES are described by RULE rather than by enumeration, so that
   making this clause fail does not turn the register into a roster of every
   file in the tree:

   - ``source`` -- project-authored code and build metadata, by suffix
     (``SOURCE_SUFFIXES``) or by whole name (``SOURCE_BASENAMES``). It is read
     line by line in review, and bulk vendor payload does not arrive as
     reviewed source.
   - ``prose`` -- markdown and reStructuredText (``PROSE_SUFFIXES``). Prose is
     PUBLIC by default. A prose file that must not be public carries an
     explicit row, which wins over the class; ``FINDINGS.md`` is the standing
     example.

   Neither class applies inside a directory named in
   ``PAYLOAD_DECLARED_DIRS``: there, the tree itself declares that its
   contents are data, so a ``.py`` under ``fixtures/`` is a fixture and not
   project source.

3. PAYLOAD-CEILING: a REGISTERED committed file above 65,536 bytes whose row
   is not ``allow-listed`` fails, in either visibility. The ceiling keys on
   the ROW and on nothing else. It used to key on a list of directory names,
   and a 297,564-byte file escaped it because its directory was not on that
   list; the answer was to retire the list, not to lengthen it. A file above
   the ceiling therefore says so in its row -- ``public allow-listed`` or
   ``private allow-listed`` -- and the size is a decision on the record. The
   two by-rule classes are exempt: the ceiling exists to notice bulk data,
   and the size of source or prose is a review concern.

4. PAYLOAD-PRIVATE-IN-PUBLIC: in a PUBLIC repository, a path whose register
   row is ``private`` is a failure. In a PRIVATE repository a ``private``
   row passes; the row exists precisely so a private repository, such as
   ``nmg2-artifacts``, may hold it.
5. PAYLOAD-REGISTER-MALFORMED: the register itself holds a row this module
   refuses -- a repo-scoped row that does not name the repository it is
   granted for, or a visibility outside the accepted vocabulary. This is a
   failure of the REGISTER and not of any committed file, so it fails
   whatever the tree holds, and in either visibility. An unknown visibility
   is refused rather than read as ``public``, because reading a typo as the
   most permissive value is the silent failure this module exists to stop.

The register file format
-------------------------
A simple tab-separated text file, one row per line::

    <path><TAB><visibility>[<TAB><repo>]

``path`` is a repository-relative path. A path ending in ``/`` names a
directory and covers every path beneath it. The optional third field is an
``owner/name`` repository slug that SCOPES the row to one repository; see
``public pch2-exception`` below. ``visibility`` is one of:

- ``public``                -- the path may be committed in a public
  repository, and is subject to the size ceiling.
- ``private``               -- the path is only for a private repository, and
  is subject to the size ceiling.
- ``public allow-listed``   -- public, and may exceed the size ceiling.
- ``private allow-listed``  -- private, and may exceed the size ceiling. This
  is how a private repository records a large payload as a DECISION rather
  than letting it pass because of where it sits.
- ``public fixture-repo``   -- the path is a synthetic repository tree used as
  a fixture by this project's own lints. Such a tree exists to IMITATE a
  violation: it holds ``.pch2`` files outside the synth corpus and
  deliberately over-ceiling blobs. Clauses 1 and 3 do not apply beneath it.
  The grant is strong, so it MUST name the repository it is granted for, on
  the same reasoning as ``public pch2-exception`` below.
- ``public pch2-exception`` -- the path is exempt from clause 1 ONLY. It is
  an operator-granted exception for a ``.pch2`` file whose provenance is
  unestablished. It grants NO size exemption: clause 3 still applies, so
  use ``public allow-listed`` for that and never assume one implies the
  other. It MUST carry the third ``repo`` field, because this register is
  ONE file shared by every repository: an unqualified row would except
  the path in all of them, and any repository could then silence
  clause 1 by choosing a directory name. The exception applies only when the
  caller passes a matching ``--repo``; an unidentified repository gets no
  exception, so the check fails CLOSED.

  That ``MUST`` is ENFORCED and not merely written here, at two levels. The
  parser REFUSES an exception row that names no repository (clause 5 above),
  so the malformed row cannot enter the register at all; and the grant test
  itself returns no exception for a row with no repository, so an entry
  built in code and never parsed cannot grant one either. The refusal is
  deliberate: a row that reads like a grant and silently grants nothing is
  the same unread rule in the other direction, and the operator who wrote it
  would never learn that the exception they believed they had is not there.

  One consequence of the tab-separated format: the space-separated fallback
  below carries two fields at most, so it can NEVER carry a repository. An
  exception row written with spaces is refused for that reason, however it
  reads.

Blank lines and lines starting with ``#`` are ignored.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SIZE_CEILING = 65_536

# The register SHIPS WITH THIS PACKAGE, so it is resolved against the module's
# own location and never against the process's working directory. A relative
# default here passes from the repository root and fails from every other
# directory -- green on a developer's machine, red in CI, in the shape of a
# defect in the code under test rather than in the path.
SHIPPED_REGISTER = Path(__file__).resolve().parent / "testdata" / "register.tsv"

PCH2_ALLOWED_DIR = "nmg2_tools/testdata/pch2_synth/"

# A directory whose name DECLARES that its contents are data. The by-rule
# classes below do not apply beneath one, so a `.py` under `fixtures/` is a
# fixture and needs a register row like any other fixture. This list no
# longer gates the byte ceiling: it did, and a 297,564-byte file escaped the
# ceiling because `g2demo/` was not on it. Lengthening the list would have
# been a roster where a predicate belongs.
PAYLOAD_DECLARED_DIRS = ("fixtures/", "corpus/", "golden/", "captures/", "testdata/")

# The `source` class: project-authored code and build metadata, read line by
# line in review. `.yml`/`.yaml` are deliberately ABSENT -- a 2.4 MB
# `schematic_data.yaml` of vendor-derived data is the shape that argument
# fails on, and workflow files are covered by a `.github/` register row.
SOURCE_SUFFIXES = frozenset(
    {".py", ".c", ".h", ".cpp", ".hpp", ".sh", ".toml", ".lock"}
)
SOURCE_BASENAMES = frozenset(
    {"LICENSE", ".gitignore", ".gitattributes", ".gitmodules"}
)

# The `prose` class. Prose is PUBLIC by default; an explicit row wins over
# the class, which is how a prose file that must stay private says so.
PROSE_SUFFIXES = frozenset({".md", ".rst"})

# The one accepted spelling of a clause 1 exception, and the substring that
# says a line MEANT to be one. A line that carries the mark but not the exact
# visibility is a malformed exception row, not an unrelated row.
PCH2_EXCEPTION_VISIBILITY = "public pch2-exception"
PCH2_EXCEPTION_MARK = "pch2-exception"

# A synthetic repository tree used as a fixture by this project's own lints.
FIXTURE_REPO_VISIBILITY = "public fixture-repo"
FIXTURE_REPO_MARK = "fixture-repo"

# A grant strong enough that it applies in ONE repository only, and must name
# it. The register is a single file shared by every repository, so an
# unqualified row would grant everywhere. Keyed by the substring that marks a
# line as MEANING one of these, so a line that carries the mark without the
# exact visibility is a malformed row and not an unrelated one.
REPO_SCOPED_VISIBILITIES = (FIXTURE_REPO_VISIBILITY, PCH2_EXCEPTION_VISIBILITY)
REPO_SCOPED_MARKS = {
    FIXTURE_REPO_MARK: FIXTURE_REPO_VISIBILITY,
    PCH2_EXCEPTION_MARK: PCH2_EXCEPTION_VISIBILITY,
}

VALID_VISIBILITIES = (
    "public",
    "private",
    "public allow-listed",
    "private allow-listed",
    PCH2_EXCEPTION_VISIBILITY,
    FIXTURE_REPO_VISIBILITY,
)


def _in_payload_declared_dir(posix_path: str) -> bool:
    parts = posix_path.split("/")
    for i in range(len(parts) - 1):
        if parts[i] + "/" in PAYLOAD_DECLARED_DIRS:
            return True
    return False


def classify(posix_path: str) -> str | None:
    """Name the by-rule class of a path, or ``None`` if it has none.

    ``None`` is the answer that makes clause 2 fail, so this function is the
    whole difference between a guard and a guard-shaped skip.
    """
    if _in_payload_declared_dir(posix_path):
        return None
    name = posix_path.rsplit("/", 1)[-1]
    if name in SOURCE_BASENAMES:
        return "source"
    dot = name.rfind(".")
    suffix = name[dot:] if dot > 0 else ""
    if suffix in SOURCE_SUFFIXES:
        return "source"
    if suffix in PROSE_SUFFIXES:
        return "prose"
    return None


class RegisterError(ValueError):
    """A register line the parser refuses to accept."""


class RegisterEntry:
    __slots__ = ("path", "visibility", "repo")

    def __init__(
        self, path: str, visibility: str, repo: str | None = None
    ) -> None:
        self.path = path
        self.visibility = visibility
        self.repo = repo

    @property
    def is_dir_rule(self) -> bool:
        return self.path.endswith("/")

    @property
    def allow_listed(self) -> bool:
        return self.visibility.endswith("allow-listed")

    @property
    def is_private(self) -> bool:
        return self.visibility.startswith("private")

    @property
    def is_repo_scoped(self) -> bool:
        return self.visibility in REPO_SCOPED_VISIBILITIES

    def applies_in(self, repo: str | None) -> bool:
        """Is this row a row AT ALL in the repository being linted?

        A repo-scoped row names the one repository it was granted for. In any
        OTHER repository it is not a weaker row -- it is NO row, and the
        register's answer for that path is the answer it gives a path it has
        never heard of. Reading it instead as a plain registration made the
        row's mere PRESENCE answer clause 2 everywhere, which is the same hole
        the scoping exists to close: this register is one file shared by seven
        repositories, so any of them could quiet the unregistered check for a
        whole tree by choosing a directory name another repository's row
        happens to cover. Clause 5 refuses a row that names no repository, so
        the ``self.repo is None`` arm is the second lock, for an entry built in
        code; ``repo is None`` is an unidentified caller, which gets nothing.
        """
        if not self.is_repo_scoped:
            return True
        if self.repo is None or repo is None:
            return False
        return repo == self.repo

    @property
    def fixture_repo(self) -> bool:
        return self.visibility == FIXTURE_REPO_VISIBILITY

    def fixture_repo_in(self, repo: str | None) -> bool:
        """Is this row a fixture-repo grant for the repository being linted?

        Fails closed on both sides, exactly as :meth:`pch2_excepted_in` does
        and for the same reason: the register is one shared file.
        """
        if not self.fixture_repo:
            return False
        if self.repo is None or repo is None:
            return False
        return repo == self.repo

    @property
    def pch2_excepted(self) -> bool:
        return self.visibility == PCH2_EXCEPTION_VISIBILITY

    def pch2_excepted_in(self, repo: str | None) -> bool:
        """Does this row except clause 1 for the repository being linted?

        A ``pch2-exception`` row applies ONLY in the repository it names, and
        it must name one. The register is one shared file, so a row that
        names no repository would except the path in all of them and let any of
        them silence this lint by choosing a directory name. Both an
        unqualified row (``self.repo`` is ``None``) and an unidentified
        caller (``repo`` is ``None``) therefore get no exception: this fails
        CLOSED on either side. ``load_register`` refuses the unqualified row
        outright; this test is the second lock, for an entry built in code.
        """
        if not self.pch2_excepted:
            return False
        if self.repo is None or repo is None:
            return False
        return repo == self.repo


def load_register(register_path: Path) -> list[RegisterEntry]:
    """Parse a register file into a list of :class:`RegisterEntry`.

    A ``public pch2-exception`` row is accepted in ONE form only: three
    tab-separated fields, the second exactly ``public pch2-exception`` and the
    third a non-empty ``owner/name`` slug. Anything else raises
    :class:`RegisterError` and names the line. The row is refused rather than
    quietly granting nothing, because a security-register row that reads like
    a grant and does nothing is the same silent hole in the other direction.
    Note that the space-separated fallback below produces two fields at most,
    so it can never carry the repository field: an exception row written with
    spaces is refused for that reason.
    """
    entries: list[RegisterEntry] = []
    for lineno, raw_line in enumerate(register_path.read_text().splitlines(), 1):
        line = raw_line.strip("\n")
        if not line.strip() or line.strip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            # Tolerate accidental runs of spaces instead of a literal tab.
            parts = line.split(None, 1)
        for mark, scoped_visibility in REPO_SCOPED_MARKS.items():
            if mark in line and (
                len(parts) < 3
                or parts[1].strip() != scoped_visibility
                or not parts[2].strip()
            ):
                raise RegisterError(
                    f"{register_path}:{lineno}: a `{scoped_visibility}` row "
                    "must carry a third, tab-separated `owner/name` field "
                    "naming the one repository it is granted for: "
                    f"{line!r}"
                )
        path = parts[0].strip()
        visibility = parts[1].strip()
        if visibility not in VALID_VISIBILITIES:
            raise RegisterError(
                f"{register_path}:{lineno}: unknown visibility "
                f"{visibility!r}; the register accepts only "
                f"{', '.join(VALID_VISIBILITIES)}: {line!r}"
            )
        repo = parts[2].strip() if len(parts) > 2 and parts[2].strip() else None
        entries.append(RegisterEntry(path, visibility, repo))
    return entries


def _find_register_entry(
    rel_path: str, entries: list[RegisterEntry], repo: str | None = None
) -> RegisterEntry | None:
    """Find the row that covers ``rel_path`` IN ``repo``, or ``None``.

    A row scoped to another repository is skipped here rather than returned
    and re-tested at each clause, so that a path it does not cover falls
    through to whatever broader row does -- and to no row at all when there is
    none.
    """
    best: RegisterEntry | None = None
    for entry in entries:
        if not entry.applies_in(repo):
            continue
        if entry.is_dir_rule:
            if rel_path.startswith(entry.path):
                if best is None or len(entry.path) > len(best.path):
                    best = entry
        else:
            if rel_path == entry.path:
                return entry
    return best


def _committed_files(repo_path: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def lint_committed_files(
    repo_path: Path,
    committed_files: list[str],
    entries: list[RegisterEntry],
    visibility: str = "public",
    repo: str | None = None,
) -> list[str]:
    """Return named failures for a given list of repository-relative paths."""
    failures: list[str] = []
    for rel_path in committed_files:
        posix_path = rel_path.replace("\\", "/")

        if posix_path.endswith(".gitkeep"):
            continue

        entry = _find_register_entry(posix_path, entries, repo)
        fixture_repo_exempt = entry is not None and entry.fixture_repo_in(repo)

        if visibility == "public" and posix_path.endswith(".pch2"):
            if (
                not posix_path.startswith(PCH2_ALLOWED_DIR)
                and not fixture_repo_exempt
                and not (entry is not None and entry.pch2_excepted_in(repo))
            ):
                failures.append(
                    f"PAYLOAD-PCH2-LOCATION: {posix_path}: .pch2 file outside "
                    f"{PCH2_ALLOWED_DIR}"
                )

        if entry is None:
            # The guard's default answer. A file with no row still gets one
            # chance -- a by-rule class -- and if it has none it is reported.
            # This branch used to be a bare `continue`, which is why two real
            # payload files were never mentioned by a check whose whole job
            # was to mention them.
            if classify(posix_path) is None:
                failures.append(
                    f"PAYLOAD-UNREGISTERED: {posix_path}: committed file with "
                    "no register row and no by-rule classification"
                )
            # A classified file is source or prose: no visibility question to
            # answer, and the ceiling does not police text.
            continue

        if fixture_repo_exempt:
            continue

        if visibility == "public" and entry.is_private:
            failures.append(
                f"PAYLOAD-PRIVATE-IN-PUBLIC: {posix_path}: register marks "
                "this path private, but it is committed in a public "
                "repository"
            )
            continue

        full_path = repo_path / rel_path
        try:
            size = full_path.stat().st_size
        except OSError:
            size = 0

        if size > SIZE_CEILING and not entry.allow_listed:
            failures.append(
                f"PAYLOAD-CEILING: {posix_path}: {size} bytes exceeds the "
                f"{SIZE_CEILING} byte ceiling and is not allow-listed"
            )

    return failures


def lint_repo_tree(
    repo_path: Path,
    register_path: Path,
    visibility: str = "public",
    repo: str | None = None,
) -> list[str]:
    entries = load_register(register_path)
    committed = _committed_files(repo_path)
    return lint_committed_files(repo_path, committed, entries, visibility, repo)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "repo_path", type=Path, help="path to the repository root to check"
    )
    parser.add_argument(
        "--register",
        type=Path,
        default=SHIPPED_REGISTER,
        help=f"path to the register file (default: {SHIPPED_REGISTER})",
    )
    parser.add_argument(
        "--visibility",
        choices=["public", "private"],
        default="public",
        help="repository visibility (default: public)",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help=(
            "the `owner/name` slug of the repository under test, as "
            "`github.repository` supplies it. A `public pch2-exception` "
            "register row that names a repository applies ONLY when this "
            "matches. Omitting it grants no scoped exception."
        ),
    )
    args = parser.parse_args(argv)

    try:
        failures = lint_repo_tree(
            args.repo_path, args.register, args.visibility, args.repo
        )
    except RegisterError as error:
        # A named finding and exit 1, the same shape as every other failure
        # this module reports. A traceback would say the same thing worse.
        print(f"PAYLOAD-REGISTER-MALFORMED: {error}", file=sys.stderr)
        return 1

    for failure in failures:
        print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
