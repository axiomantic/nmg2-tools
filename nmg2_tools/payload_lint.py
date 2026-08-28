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

   A SUBMODULE GITLINK IS NOT A COMMITTED FILE AND IS NOT READ BY THIS
   CHECK. It is a mode-``160000`` index entry recording a commit sha in
   another repository, with no bytes in this one, so there is no provenance
   here for a register row to assert. The exclusion is decided by the mode
   git reports and never by the path: a real file committed at a
   submodule-looking name is a file and this clause answers for it.
   ``submodule_lint`` is what checks gitlinks, including the case -- a
   gitlink no ``.gitmodules`` section declares -- that this clause used to
   catch by accident and that nothing else was checking.

   Two CLASSES are described by RULE rather than by enumeration, so that
   making this clause fail does not turn the register into a roster of every
   file in the tree:

   - ``source`` -- project-authored code and build metadata, by suffix
     (``SOURCE_SUFFIXES``), by whole name (``SOURCE_BASENAMES``), or by the
     STEM of a ``.in`` configure-time template (``TEMPLATE_SUFFIX``). Bulk
     vendor payload does not arrive under one of these spellings; that
     arrival-shape question, and not "is it reviewed", is the test a candidate
     suffix has to pass, and the comment on ``SOURCE_SUFFIXES`` names the
     spellings that fail it and why.
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

   That exemption is the CLASS's and not the absence of a row. It used to be
   reachable only by a path the register had never heard of, because the
   ceiling was tested after the row lookup had already claimed the path. So
   writing a directory row over a tree TIGHTENED the ceiling onto every source
   file inside it: a 840,080-byte ``m68kops.c`` passed while nothing covered
   it and failed the moment ``Musashi/`` was registered. That is backwards --
   a row is a decision that a tree may be committed, not a decision that its
   source files are now bulk data -- and it is a reason not to write the row,
   which is the one thing this register must never give anyone. The ceiling
   therefore asks :func:`classify` on a registered path too, and an
   unregistered ``.cpp`` and a registered one answer the same.

4. PAYLOAD-PRIVATE-IN-PUBLIC: in a PUBLIC repository, a path whose register
   row is ``private`` is a failure. In a PRIVATE repository a ``private``
   row passes; the row exists precisely so a private repository, such as
   ``nmg2-artifacts``, may hold it.
5. PAYLOAD-REGISTER-MALFORMED: the register itself holds a row this module
   refuses -- a repo-scoped row that does not name the repository it is
   granted for, a row that names no home repository at all, a home repository
   outside the declared roster, or a visibility outside the accepted
   vocabulary. This is a failure of the REGISTER and not of any committed
   file, so it fails whatever the tree holds, and in either visibility. An
   unknown visibility is refused rather than read as ``public``, because
   reading a typo as the most permissive value is the silent failure this
   module exists to stop.
6. PAYLOAD-REGISTER-UNMATCHED, PAYLOAD-REGISTER-PENDING-SATISFIED,
   PAYLOAD-REGISTER-UNCHECKED, PAYLOAD-REGISTER-EMPTY,
   PAYLOAD-REGISTER-NO-FILES, PAYLOAD-REGISTER-NO-HOME-ROWS: the register is
   READ BACK against the tree, so that a row asserting a provenance for a path
   that is not there says so out loud. See "Reading the register back" below.

The register file format
-------------------------
A simple tab-separated text file, one row per line::

    <path><TAB><visibility><TAB><home>[<TAB>pending=<reason>]

``path`` is a repository-relative path. A path ending in ``/`` names a
directory and covers every path beneath it.

``home`` is a comma-separated list of ``owner/name`` repository slugs naming
the repositories this row is FOR -- the repositories in which it is expected
to match a committed path. It is REQUIRED on every row, and every slug in it
must appear in :data:`KNOWN_REPOSITORIES`. For the two repo-scoped
visibilities below it additionally NARROWS the grant, and must then name
exactly one repository. For every other visibility it narrows nothing: a
``public`` row still registers its path in whichever repository the path turns
up in. The field says where the row is CHECKED, not where it applies.

``pending=<reason>`` is the optional fourth field. See below.

``visibility`` is one of:

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

Reading the register back
-------------------------
Every clause above reads a committed file and asks the register about it. None
of them reads a REGISTER ROW and asks the tree about it, and that direction is
where this register spent five rows asserting nothing for months. Five
``gearmulator`` fixture rows carried the prefix ``g2Lib/`` where the
repository-relative path is ``source/nord/g2/g2Lib/``; a sixth named
``frame_sync_spin.asm``, a file that has never existed in that repository on
any branch. Each compared unequal against every committed path, so no
``PAYLOAD-UNREGISTERED`` finding was ever answered by one -- and nothing said
so, because **a row that matches nothing by accident and a row that matches
nothing on purpose looked identical**. The register legitimately carries rows
for files that have not landed yet, so "unmatched" could not simply be an
error.

The fix makes the difference EXPLICIT IN THE DATA rather than inferring it:

- Every row names its ``home`` repositories. In a home repository the row MUST
  match at least one committed path, or clause 6 reports
  ``PAYLOAD-REGISTER-UNMATCHED`` and names the row. A row whose home is wrong
  is loud for the same reason, in the repository it wrongly names.
- A row that is deliberately ahead of its file carries ``pending=<reason>``.
  The reason is prose a human audits; the marker is what moves the row out of
  the loud bucket, and it can only be added deliberately.
- ``pending`` is not a hiding place: a ``pending`` row that DOES match is
  ``PAYLOAD-REGISTER-PENDING-SATISFIED``, so the marker expires by itself when
  the file lands. Both buckets are checked, in both directions.

The check runs over the rows at home in ONE repository, so it needs to know
which repository it is looking at and it must not fall quiet when it does not:

- ``--repo`` absent, or naming a repository outside :data:`KNOWN_REPOSITORIES`
  -> ``PAYLOAD-REGISTER-UNCHECKED``. A new repository joining the set is a
  deliberate edit here, not a silent exemption for its whole tree.
- a register with no rows -> ``PAYLOAD-REGISTER-EMPTY``.
- a repository with no tracked files -> ``PAYLOAD-REGISTER-NO-FILES``. A loop
  over a vanished scope prints nothing and exits 0, which is byte for byte
  what a clean tree prints.
- a rostered repository no row is at home in -> ``PAYLOAD-REGISTER-NO-HOME-ROWS``.
  Without it the whole clause is vacuous in that repository and says so
  nowhere.

What a row asserts, and what it does not
----------------------------------------
A row asserts the provenance of BYTES IN THIS REPOSITORY. Read it against a
tree and exactly two conclusions are available:

- YOU MAY CONCLUDE that every row at home here matches at least one committed
  path WITH CONTENT, or carries an explicit ``pending=<reason>``. Clause 6
  makes the alternative loud. Because the population it matches against is
  :func:`_committed_files`, which excludes gitlinks, that holds for a
  directory row over a submodule too: a row whose only would-be matches are
  gitlinks matches nothing and is reported ``PAYLOAD-REGISTER-UNMATCHED``. An
  operator who writes ``source/3rdparty/RmlUi/`` believing they have
  registered the submodule is told they have registered nothing.
- YOU MAY NOT CONCLUDE that a directory row enumerates everything under that
  directory. Submodule gitlinks may sit beneath one, and they are NOT covered
  by it in any sense this register can assert -- they have no bytes here.
  ``gearmulator``'s ``source/3rdparty/`` row is the standing example: 66
  committed files and three gitlinks. The three draw no finding here, on
  purpose. ``submodule_lint`` owns them completely -- the URL authority table,
  ``SUBMODULE-UNDECLARED`` for a gitlink no section declares, and
  ``SUBMODULE-STALE-DECLARATION`` for a section with no gitlink -- so every
  gitlink reaches a named check that goes red without this register's help.

Reporting the coverage was considered and rejected. It would fire three times
on ``gearmulator`` for a non-defect, and the only way to quiet it would be to
narrow or not write the ``source/3rdparty/`` row -- a reason not to register a
tree, which is the one thing this register must never give anyone.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from nmg2_tools.gitindex import blob_paths

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
#
# The second row is the same class arriving under a different spelling. `.cxx`
# is C++ in exactly the sense `.cpp` is, `.nim` is the language one whole
# repository in this set is written in, and `CMakeLists.txt` is build metadata
# in exactly the sense `.toml` is. Every one of them is read line by line in
# review, which is the entire argument the class rests on, so their absence
# was an omission and not a decision.
#
# The third row is `.bat`: a shell script for `cmd.exe`, which is what `.sh`
# already is for a POSIX shell. `.sh` has been in this class since it was
# written, so excluding the Windows spelling of the same thing was an omission
# and not a decision. MEASURED before adding: of the tracked `.bat` files in
# the seven repositories, NONE sits in a tree whose register row is `public`
# and tight (`source/fst/`, `source/3rdparty/`, `source/HxDplugin/`,
# `source/vtuneSdk/`, `Musashi/`), so this class removes the ceiling's grip on
# no file that has one today.
#
# THE TEST THIS CLASS ACTUALLY RESTS ON is not "read line by line" -- `.lock`
# is in the set and nobody reads `uv.lock` line by line. It is: COULD BULK
# VENDOR PAYLOAD PLAUSIBLY ARRIVE UNDER THIS SPELLING? That is the test the
# `.asm`/`.inc` refusal below applies, and it is the one to apply to any
# future candidate.
#
# What is deliberately NOT here, because the same argument does NOT reach it:
#
# - `.asm` and `.inc`. A DISASSEMBLY of Clavia firmware is an `.asm` file, and
#   that is the shape this guard exists to notice. The register carries three
#   `.asm` fixture rows whose comment establishes, per file, that each is a
#   hand-written spin of a few instructions and not disassembled output --
#   evidence someone had to go and get. A class here would have made that
#   paragraph unnecessary by making the question unaskable. `mcf5307`'s
#   `tests/abi_smoke_symbols.inc` was held to exactly that bar and got a ROW,
#   not a class: see the register's comment on it.
# - `.sln`, `.vcxproj`, `.filters`, `.vcproj`, `.m4`, `.am`, `.bkl`, `.mms`,
#   `.unx`, `.gcc`, `.vc`. Autotools, MSVC and bakefile build forms. The
#   earlier statement of this refusal said they occur "ONLY inside third-party
#   directories", and that is FALSE AS WRITTEN: of the 720 tracked
#   `.in`/`.sln`/`.vcxproj`/`.vcproj`/`.m4`/`.am` paths across the seven
#   repositories, 7 sit outside every vendored tree the register names
#   [MEASURED 2026-08-28; `git ls-files` per repository, filtered against the
#   vendored-tree row prefixes; one unit is one tracked path]. The CAUTION the
#   sentence was defending is nevertheless correct and is why the refusal
#   stands: an MSVC class would exempt six files inside `source/HxDplugin/`,
#   a tree whose row is deliberately TIGHT, to quiet three files in one
#   directory of one repository. Three files are not a class. They get rows.
# - `.cfg`, `.html`, `.js`, `.txt`, `.def`, `.yml`. Suffixes generic enough
#   that extracted content arrives under them routinely.
SOURCE_SUFFIXES = frozenset(
    {
        ".py", ".c", ".h", ".cpp", ".hpp", ".sh", ".toml", ".lock",
        ".cc", ".cxx", ".hh", ".hxx", ".inl", ".mm", ".nim", ".cmake",
        ".bat",
    }
)
# The second row is FIXED, TOOL-DEFINED FILENAMES, in exactly the sense
# `CMakeLists.txt` already in this set is one. A basename is the narrowest
# predicate this module can express: it cannot be reached by choosing a
# directory name or a suffix, only by naming the file the thing the tool reads.
# `CMakePresets.json` is CMake's own fixed name -- and it is here rather than a
# `.json` suffix ON PURPOSE, because `g2demo/g2_modules.json` is 297,564 bytes
# of Clavia-derived data and a `.json` class would have swallowed it.
# `.clang-format` and `uncrustify.cfg` are the two code formatters' fixed
# config names; `.cfg` as a suffix is refused for the reason above.
# `.nim-version` is the Nim toolchain pin, build metadata in the sense
# `.gitignore` is.
SOURCE_BASENAMES = frozenset(
    {
        "LICENSE", ".gitignore", ".gitattributes", ".gitmodules",
        "CMakeLists.txt",
        "CMakePresets.json", ".clang-format", "uncrustify.cfg",
        ".nim-version",
    }
)

# A CONFIGURE-TIME TEMPLATE SUFFIX, handled by RE-READING THE STEM and never
# as a class of its own. `source/jucePluginLib/version.h.in` is a `.h` carrying
# `@VAR@` placeholders that CMake's `configure_file` substitutes; it is source
# in exactly the sense the `.h` it generates is.
#
# A BLANKET `.in` CLASS WAS REFUSED AND STAYS REFUSED. This is not that class,
# and the difference is the whole reason it is admissible: `firmware.bin.in`
# reads as `.bin`, classifies as nothing, and is still PAYLOAD-UNREGISTERED.
# The exemption is inherited from the stem or it does not exist, so a template
# can never be a way to put a suffix past this check.
TEMPLATE_SUFFIX = ".in"

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

# The repositories that share this one register file. A row's `home` field is
# checked against this roster, so a typo in a home slug is refused instead of
# naming a repository that is never linted -- which would move the silent
# bucket from the path field to the repository field and change nothing. A
# `--repo` outside the roster is likewise refused rather than read as "no rows
# are at home here, nothing to check": a repository joining the set is an edit
# to this tuple, made once, on purpose.
KNOWN_REPOSITORIES = (
    "axiomantic/nmg2-tools",
    "axiomantic/G2-Edit",
    "axiomantic/mc68k",
    "axiomantic/mcf5307",
    "axiomantic/dsp56300",
    "axiomantic/gearmulator",
    "axiomantic/nmg2-artifacts",
)

# The fourth field's one accepted form. A row carrying it declares that it is
# ahead of its file ON PURPOSE and says why. Nothing else moves a row out of
# the loud bucket, and the marker expires by itself: see
# PAYLOAD-REGISTER-PENDING-SATISFIED.
PENDING_PREFIX = "pending="

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
    if suffix == TEMPLATE_SUFFIX:
        # Read the STEM, not the template suffix. `dot > 0` above means the
        # stem is non-empty, so each step strips at least one character and the
        # recursion terminates; a bare `.in` never reaches here at all.
        return classify(posix_path[: -len(TEMPLATE_SUFFIX)])
    if suffix in SOURCE_SUFFIXES:
        return "source"
    if suffix in PROSE_SUFFIXES:
        return "prose"
    return None


class RegisterError(ValueError):
    """A register line the parser refuses to accept."""


class RegisterEntry:
    __slots__ = ("path", "visibility", "homes", "pending")

    def __init__(
        self,
        path: str,
        visibility: str,
        repo: str | tuple[str, ...] | list[str] | None = None,
        pending: str | None = None,
    ) -> None:
        self.path = path
        self.visibility = visibility
        if repo is None:
            self.homes: tuple[str, ...] = ()
        elif isinstance(repo, str):
            self.homes = (repo,)
        else:
            self.homes = tuple(repo)
        self.pending = pending

    @property
    def repo(self) -> str | None:
        """The ONE repository this row names, or ``None`` if it names none.

        A repo-scoped grant may name exactly one repository -- the parser
        refuses more, because the grant is strong and "granted in two places"
        is a sentence nobody meant to write. This property is that one slug.
        A row homed in several repositories is not scoped to any of them and
        answers ``None``; use :attr:`homes` to ask where a row is checked.
        """
        return self.homes[0] if len(self.homes) == 1 else None

    @property
    def is_pending(self) -> bool:
        return self.pending is not None

    def matches(self, posix_path: str) -> bool:
        """Does this row's OWN predicate cover ``posix_path``?

        Deliberately not :func:`_find_register_entry`, which answers a
        different question -- which row WINS for a path. A directory row
        shadowed for one path by a longer exact row still covers the rest of
        its subtree, and clause 6 asks whether the row covers anything at all.
        """
        if self.is_dir_rule:
            return posix_path.startswith(self.path)
        return posix_path == self.path

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
        if not self.homes or repo is None:
            return False
        return repo in self.homes

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
        if not self.homes or repo is None:
            return False
        return repo in self.homes

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
        if not self.homes or repo is None:
            return False
        return repo in self.homes


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

    EVERY row must carry the third ``home`` field, and every slug in it must be
    in :data:`KNOWN_REPOSITORIES`. Both refusals exist so that clause 6 cannot
    be evaded by omission: a row with no home would be checked in no
    repository, and a row homed to a repository that does not exist would be
    checked in one that is never linted. Either is the same silent bucket the
    clause was built to empty, reached through the home field instead of
    through the path.
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
            # A repo-scoped grant names exactly ONE repository. A comma here is
            # refused rather than read as a home list: "granted in two places"
            # is a sentence nobody meant to write, and the grants are the two
            # strongest rows the register can carry.
            if mark in line and (
                len(parts) < 3
                or parts[1].strip() != scoped_visibility
                or not parts[2].strip()
                or "," in parts[2]
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
        if len(parts) < 3 or not parts[2].strip():
            raise RegisterError(
                f"{register_path}:{lineno}: every row must carry a third, "
                "tab-separated `home` field naming the repositories this row "
                "is expected to match a committed path in, comma-separated: "
                f"{line!r}"
            )
        homes = tuple(
            slug.strip() for slug in parts[2].split(",") if slug.strip()
        )
        for slug in homes:
            if slug not in KNOWN_REPOSITORIES:
                raise RegisterError(
                    f"{register_path}:{lineno}: unknown home repository "
                    f"{slug!r}; the register is shared by "
                    f"{', '.join(KNOWN_REPOSITORIES)}: {line!r}"
                )
        pending = None
        if len(parts) > 3 and parts[3].strip():
            field = parts[3].strip()
            if not field.startswith(PENDING_PREFIX) or not field[
                len(PENDING_PREFIX) :
            ].strip():
                raise RegisterError(
                    f"{register_path}:{lineno}: the fourth field must read "
                    f"`{PENDING_PREFIX}<reason>` with a non-empty reason; it "
                    "is the only thing that moves a row out of the loud "
                    f"bucket, so it may not be blank: {line!r}"
                )
            pending = field[len(PENDING_PREFIX) :].strip()
        entries.append(RegisterEntry(path, visibility, homes, pending))
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
    """Return the tracked paths that HAVE CONTENT in this repository.

    A submodule gitlink is a mode-``160000`` index entry recording a commit
    sha in ANOTHER repository. There are no bytes here to have a provenance,
    so clause 2 demanding a register row asserting the provenance of one was
    a false positive by construction, and every submodule in the set arrived
    as one.

    THE TEST IS THE MODE GIT REPORTS, NOT THE PATH. A skip list of names that
    look submodule-like would be a roster where a predicate belongs, and a
    real file committed at such a name would walk straight through it.

    Gitlinks are not dropped into nothing. ``submodule_lint`` holds each one
    against a ``.gitmodules`` declaration and its URL authority table, and it
    reports a gitlink no section declares -- which is the case this clause
    used to catch by accident, and which nothing else was checking.
    """
    return blob_paths(repo_path)


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

        # `classify` is asked here as well as in the no-row branch above, so
        # that the class's ceiling exemption does not depend on whether a row
        # happens to cover the path. Without it, registering a vendored tree
        # is a way of making its source files fail a check they passed while
        # nothing had decided anything about them.
        if (
            size > SIZE_CEILING
            and not entry.allow_listed
            and classify(posix_path) is None
        ):
            failures.append(
                f"PAYLOAD-CEILING: {posix_path}: {size} bytes exceeds the "
                f"{SIZE_CEILING} byte ceiling and is not allow-listed"
            )

    return failures


def check_register_rows(
    committed_files: list[str],
    entries: list[RegisterEntry],
    repo: str | None = None,
) -> list[str]:
    """Read the REGISTER back against the tree -- clause 6.

    Every other clause walks committed files and asks the register about them.
    This one walks the rows at home in ``repo`` and asks the tree about them,
    which is the direction in which five rows asserted a provenance for paths
    that were not there and nothing ever said so.

    It is deliberately NOT folded into :func:`lint_committed_files`. That
    function answers a question about a LIST OF PATHS the caller chose, and it
    is called throughout the tests with a one-element list; a row check inside
    it would report every row in the register as unmatched against a list of
    one. Two questions, two functions, and clause 2 keeps the meaning it had.
    """
    failures: list[str] = []

    if repo is None or repo not in KNOWN_REPOSITORIES:
        # No repository, no rows at home, nothing checked -- and that must not
        # look like a clean run. The check fails CLOSED on an unidentified or
        # unrostered caller for the same reason the pch2 grant does.
        failures.append(
            "PAYLOAD-REGISTER-UNCHECKED: "
            f"{repo!r} is not one of the repositories this register is "
            f"declared for ({', '.join(KNOWN_REPOSITORIES)}), so no register "
            "row could be read back against this tree. Pass `--repo`, or add "
            "the repository to KNOWN_REPOSITORIES"
        )
        return failures

    if not entries:
        failures.append(
            "PAYLOAD-REGISTER-EMPTY: the register holds no rows; an empty "
            "register answers every path the same way a complete one answers "
            "a registered path, and exits 0"
        )
        return failures

    if not committed_files:
        failures.append(
            "PAYLOAD-REGISTER-NO-FILES: the tree lists no tracked files, so "
            "every clause looped over nothing and printed nothing, which is "
            "what a clean tree prints"
        )
        return failures

    at_home = [entry for entry in entries if repo in entry.homes]
    if not at_home:
        failures.append(
            f"PAYLOAD-REGISTER-NO-HOME-ROWS: no register row names {repo} in "
            "its `home` field, so this clause examined no row here and said "
            "so nowhere"
        )
        return failures

    for entry in at_home:
        matched = any(entry.matches(path) for path in committed_files)
        if not matched and not entry.is_pending:
            failures.append(
                f"PAYLOAD-REGISTER-UNMATCHED: {entry.path}: this row is at "
                f"home in {repo} and matches no committed path there, so it "
                "registers nothing. Correct the path, or mark the row "
                f"`{PENDING_PREFIX}<reason>` if the file is yet to land"
            )
        elif matched and entry.is_pending:
            failures.append(
                f"PAYLOAD-REGISTER-PENDING-SATISFIED: {entry.path}: this row "
                f"is marked `{PENDING_PREFIX}{entry.pending}` but now matches "
                f"a committed path in {repo}. Drop the marker; a pending row "
                "that is never re-read is the silent bucket in a new costume"
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
    return lint_committed_files(
        repo_path, committed, entries, visibility, repo
    ) + check_register_rows(committed, entries, repo)


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
    except OSError as error:
        # A register that is absent or unreadable is the most complete way for
        # this guard to know nothing, so it gets a named finding of its own
        # rather than a traceback from `read_text`. The two are both non-zero,
        # but only one of them says which check did not run.
        print(
            f"PAYLOAD-REGISTER-UNREADABLE: {args.register}: {error}",
            file=sys.stderr,
        )
        return 1

    for failure in failures:
        print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
