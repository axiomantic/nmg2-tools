"""Lint 14 — condition 10 of section 7.4.2's second-writer rule, all five tests.

Section 7.6 assertion 8 makes a marked `Files:` entry a DECLARED SECOND WRITE,
and section 7.4.2 states five tests every such entry must pass. All five are
decided here, and the tests are INDEPENDENT: one entry can fail several, and
each failure names its own repair.

  * test 1 — `second-write-no-owner-row`: the document holds no owner row for
    the path the marker names. The marker's whole premise — that §7.4.2 holds
    a row for the pair — is refuted by the document it cites.
  * test 2 — `second-write-wrong-owner`: the `<OWNER-ID>` the marker carries is
    not the owner that row names. An owner cell naming no task block leaves the
    comparison undecidable, and that is ANNOUNCED under
    `second-write-owner-undecided` rather than passed.
  * test 3 — `second-write-outside-closure`: the owner the marker names is
    outside the writing task's transitive `Depends:` closure. §7.4.2 puts the
    edge on the WRITING task's line and says the edge is part of the write.
  * test 4 — `second-write-outside-class`: the writing task is outside the
    class the owner row states.
  * test 5 — `manifest-without-creator`: no task claims the path BARE, so the
    file carries declared writers and no creator.

WHAT THE REPORT SAYS ABOUT ITS OWN COVERAGE. `coverage_notice` prints, on a
clean run as well as a dirty one, which of the five this lint decides — derived
from the `DISPATCH` table the run itself iterates, so a predicate that is not
wired in cannot be claimed. This module once implemented two of the five and
printed `secondwrite: clean`, which is indistinguishable from a run of all five
that found nothing; that is `cli`'s own rule about a skipped lint, one level
down. A notice changes the report's WORDING and never the exit code.

WHAT THE CLASS HALF DECIDES, AND WHAT IT LEAVES UNDECIDED. A class is prose —
"every sched-track task that adds a CONDITION to step 2" — and no lint reads
the edit a writer made out of a marker. Three branches, each stated:

  * a row that states NO class admits nobody. That is decidable from the row
    alone: ERROR.
  * every limb names a track the writing task is not of. A limb of the form
    "every <track>-track task that ..." cannot admit a foreign-track writer
    whatever edit it describes, so the exclusion is mechanical: ERROR.
  * otherwise admission turns on the edit-kind half, which is prose. Reported
    as `second-write-class-undecided`, never passed — a silence here reads
    exactly like an adjudication, and the two failures this rule exists for
    (SCH-34's dspJob write, DSP-20's dma.cpp write) both sat in this branch's
    neighbourhood while nothing reported them.

THE THIRD SHAPE: A ROW SATISFIED BY ORDER AND NOT BY OWNERSHIP. §7.4.2's
`g2TestConsole/` row spends its owner cell on `serial by wave` and calls itself
"the one shared path the plan resolves by ORDER rather than by OWNERSHIP". Read
as an ownership row it is neither a readable class nor undecidable prose: it
names a mechanism §7.2's wave table decides, and both halves of it are checked.

  * WHO THE OWNER IS, for test 2. The writer §7.2 places EARLIEST. A marker
    carrying that identifier names the row's owner; one carrying a later
    writer's does not, and that is `second-write-wrong-owner`.
  * WHO IS ADMITTED, for test 4. Every writer whose wave order no OTHER writer
    of the same path holds. "No two writers of one file share a wave" is the
    row's own sentence, and it is a property of the PATH's writer set and not
    of the directory row's — the row itself says two writers may share a wave
    while writing different files beneath it. Only the writers that COLLIDE
    are reported, each naming the other, because a writer that shares a wave
    with nobody has no repair to make.

The wave data comes from the DOCUMENT. A writer §7.2 places in no row leaves
both halves unresolved, and both say so — under `second-write-owner-undecided`
and `second-write-class-undecided` — rather than passing in silence.

WHERE THE CLASS IS READ FROM. From the ROW, not from one column of it. Section
7.4.2 states no rule that the class must sit in the mechanism cell, and the ten
`tests_<track>.cmake` rows state it in the OWNER cell.

HOW A TRACK TOKEN IS RESOLVED. Through section 7.1, which is the one home of
the track set: `every board-track task` names the row whose worktree name is
`nmg2-board`, and that row's prefix column reads `BRD`. The comparison is then
prefix against prefix. A token that names no section 7.1 row is not a track
token and is dropped — `per` comes out of "the ten per-track lists" — so a
class left with no resolved token excludes nobody and goes undecided.

A bare claimant beside the marker satisfies test 5 and produces no finding from
it; the marked entry's own test-4 verdict still stands.
"""

import re
import typing

from planlint import graph, registrar
from planlint.document import (
    canonical_path,
    has_marker,
    strip_marker,
    strip_markup,
)
from planlint.finding import ERROR, WARNING, Finding, guard_no_input

NO_ROW_MESSAGE = (
    "a completion marker asserts that section 7.4.2 holds an owner row for the "
    "(repository, path) pair, and the document holds none; the marker's own "
    "premise is refuted by the document it cites (condition-10 test 1)"
)

CLASSLESS_MESSAGE = (
    "the owner row states no class, so it admits no second writer at all; a "
    "row that names no class grants writes to nobody beyond the owner it "
    "names (condition-10 test 4)"
)

FOREIGN_TRACK_MESSAGE = (
    "every limb of the owner row's class names a track the writing task is "
    "not of, so no limb can admit it whatever edit it describes "
    "(condition-10 test 4)"
)

UNDECIDED_MESSAGE = (
    "whether the writing task is inside the class the owner row states turns "
    "on the edit the class describes, and that description is prose this lint "
    "does not read; reported UNDECIDED rather than passed (condition-10 test 4)"
)

NO_CREATOR_MESSAGE = (
    "no task claims this path BARE, so the manifest carries declared writers "
    "and no creator; a marked entry is not a claim of ownership, and a "
    "manifest with writers and no creator is a file nobody creates "
    "(condition-10 test 5)"
)

OUTSIDE_CLOSURE_MESSAGE = (
    "the owner the marker names is outside the writing task's transitive "
    "`Depends:` closure, so the path may not exist on the day the write is "
    "declared complete; the edge to the owner is part of the write "
    "(condition-10 test 3)"
)

WRONG_OWNER_MESSAGE = (
    "a completion marker asserts that the `<OWNER-ID>` it carries is the owner "
    "section 7.4.2's row names, and the row names another task; a declared "
    "second write against the wrong owner declares nothing (condition-10 "
    "test 2)"
)

OWNER_UNDECIDED_MESSAGE = (
    "the owner row's cell names no task block this tool can resolve, so "
    "whether the marker carries that row's owner turns on prose; reported "
    "UNDECIDED rather than passed (condition-10 test 2)"
)

ORDER_WRONG_OWNER_MESSAGE = (
    "the owner row resolves this path by ORDER rather than by ownership, so "
    "the owner it names is the writer section 7.2 places EARLIEST, and the "
    "`<OWNER-ID>` the marker carries is a later writer (condition-10 test 2)"
)

ORDER_OWNER_UNDECIDED_MESSAGE = (
    "the owner row resolves this path by ORDER, and section 7.2's wave table "
    "places some writer of the path in no row, so the earliest writer — the "
    "owner an order row names — cannot be resolved; reported UNDECIDED rather "
    "than passed (condition-10 test 2)"
)

ORDER_COLLISION_MESSAGE = (
    "the owner row admits a second writer by ORDER, and section 7.2 places "
    "this task in the same wave as another writer of the same path; two "
    "worktrees then hold one file at once, which is the one thing the order "
    "exists to prevent (condition-10 test 4)"
)

ORDER_ADMISSION_UNDECIDED_MESSAGE = (
    "the owner row admits a second writer by ORDER, and section 7.2's wave "
    "table places some writer of the path in no row, so whether two writers "
    "share a wave cannot be decided; reported UNDECIDED rather than passed "
    "(condition-10 test 4)"
)

# A class sentence carries an "every ... task" limb. The words may stand
# apart — "every sch-track task" — so a containment test for the two-word
# phrase would read no real class. Word boundaries keep "Everybody else asks
# AAA-1" out: `everybody` is not the word `every`.
CLASS_LIMB = re.compile(r"\bevery\b.*\btask\b", re.DOTALL)

TRACK_LIMB = re.compile(r"\b([a-z0-9]+)-track\b")

# An owner cell that names the section 7.2 WAVE TABLE as its resolver states an
# ORDER and not an owner. `serial by wave` is the form section 7.4.2 writes, and
# the anchor matched is the RESOLVER — "by wave" — rather than the adjective in
# front of it, so the predicate keys on the mechanism the cell names and not on
# one cell's spelling. A list of accepted spellings would be a roster amended
# once per case, which is this project's name for a missing predicate.
ORDER_CELL = re.compile(r"\bby wave\b")


def states_class(text):
    """Whether a mechanism cell states a class of second writers at all.

    A class limb reads "every <qualifiers> task that ...". The qualifiers may
    be long — "every sched-track task that adds a CONDITION" — so only the two
    anchor words and what stands between them are matched. "Everybody else
    asks AAA-1" contains neither anchor as a word and states no class;
    demanding more precision than that would parse the prose this predicate
    exists to refuse to read.
    """
    return CLASS_LIMB.search(text.lower()) is not None


def class_tracks(text):
    """The `<track>` set named by hyphenated track limbs, lowercased.

    `every sch-track task that ...` names `sch`. Only the hyphenated form is
    read, because that is the form the plan writes its classes in; a bare
    track name in other grammar is prose about the track, not a limb of the
    class.
    """
    return {token.lower() for token in TRACK_LIMB.findall(text.lower())}


def resolved_class_tracks(doc, text):
    """The class's `<track>-track` tokens that name a section 7.1 row, mapped
    to that row's identifier prefixes.

    Section 7.1 is the one home of the track set, and it holds both spellings
    the plan's prose uses: the worktree-name column carries `board` and the
    prefix column carries `BRD`. A comparison of the two as raw strings reads
    `"board".startswith("brd")` as False and rules a `BRD-` task outside a
    `board-track` class; resolving the token to its ROW and comparing the
    ROW's prefix reads the mapping the document states.

    A token that names no row is not a track token at all and is dropped —
    `per` comes out of the phrase "the ten per-track lists" and names no
    track. Dropping it is not an exception list: section 7.1 decides, and a
    fifteenth track is a fifteenth row and nothing else.
    """
    resolved = {}
    for token in class_tracks(text):
        prefixes = doc.track_prefixes.get(token)
        if prefixes is None:
            prefixes = next(
                (
                    row
                    for row in doc.track_prefixes.values()
                    if token.upper() in row
                ),
                None,
            )
        if prefixes:
            resolved[token] = prefixes
    return resolved


def states_order(cell):
    """Whether an owner cell resolves the path by ORDER rather than by owner.

    Section 7.4.2's `g2TestConsole/` row spends its owner cell on `serial by
    wave` and says in its own mechanism prose that this is "the one shared
    path the plan resolves by ORDER rather than by OWNERSHIP". Such a cell
    names no task, and reading it as an unresolvable owner reports as prose a
    mechanism the document states mechanically: no two writers of one file
    share a wave, and section 7.2 names every wave.
    """
    return ORDER_CELL.search(strip_markup(cell).lower()) is not None


def _track_of(ident):
    return ident.partition("-")[0].lower()


def bare_claims(doc):
    """Every canonical path some task claims BARE, over the whole document.

    Condition-10 test 5 asks whether the file a marker writes into has a
    CREATOR. A marked entry is not a claim of ownership — section 1.1.1 rule D
    — so it never enters this set, and a path every writer marks has no
    creator here however many writers it carries. Counting a marked entry
    would let the `conformance/CMakeLists.txt` shape pass, which is the whole
    defect the test names.

    The paths are CANONICAL, so a creator writing `g2Lib/x.cmake` satisfies a
    marker written against `source/nord/g2/g2Lib/x.cmake`: rules B and C make
    those one spelling, and a raw-string comparison would report a creator
    that is there.
    """
    return {
        canonical_path(item)
        for task in doc.tasks
        for item in task.files_items
        if not has_marker(item)
    }


def claimed_bare(path, claimed):
    """Whether a bare claim covers `path`: exact, then a `/`-suffixed prefix.

    A bare claim of a `/`-suffixed path CLAIMS EVERY PATH BENEATH IT. Section
    7.4.2 states that rule for its own rows — "a `/`-suffixed row owns every
    path beneath it" — and `document.owner_cell` already implements it, so a
    lookup here that read exact spellings only made ONE adjudication read the
    same `/` two ways: test 1 resolved the owner through a directory row and
    stayed silent, and test 5 missed the creator through the identical
    directory claim and fired.

    The `/` is what makes a claim a directory, and it is required: `planlint`
    without it claims a FILE, and `planlintx.py` is not beneath a file.
    """
    if path in claimed:
        return True
    return any(
        claim.endswith("/") and path.startswith(claim) for claim in claimed
    )


class Entry(typing.NamedTuple):
    """One marked `Files:` entry, with everything the five tests read.

    The tests take ONE argument so that the dispatch table below can hold them
    beside their table numbers. A table that could not hold them uniformly
    would have to be a hand-written list of numbers, and the coverage notice
    would then be a claim rather than a derivation.
    """

    doc: object
    task: object
    path: str
    owner_ident: str
    edges: dict
    claimed: frozenset
    # The repositories the writing task's track names, out of section 7.1.
    # Section 7.4.2 is keyed on the (repository, path) PAIR — it says so, and
    # it holds two `CMakeLists.txt` rows that "never merge" — so an owner
    # resolved without this half answers a mcf5307 task with the fork's owner.
    repositories: tuple
    # Every canonical path to the identifiers that write it, built once for
    # the document. An ORDER row is decided against the writer set of the
    # PATH, so the entry carries the whole map rather than re-deriving its
    # own slice of it.
    writers: dict

    @property
    def has_row(self):
        return self.doc.has_owner(self.path, self.repositories)

    def wave_positions(self):
        """`({ident: (label, order)}, [unplaced idents])` for this path's
        writers, out of section 7.2's table.

        The wave data comes from the DOCUMENT and from nothing else. A writer
        the table places in no row is returned in the second half rather than
        dropped: an order this lint cannot resolve is UNDECIDED, and a silent
        pass there would read exactly like an adjudication.
        """
        placed, unplaced = {}, []
        for ident in self.writers.get(self.path, ()):
            position = self.doc.wave_of.get(ident)
            if position is None:
                unplaced.append(ident)
            else:
                placed[ident] = position
        return placed, sorted(set(unplaced))

    def at(self, **fields):
        """A `Finding` located at this entry's `Files:` line.

        The CALLER spells `rule=` with a string literal, and this helper never
        supplies one. That is not a style choice: `tests/planlint/
        test_mutation.py` reads the package's whole rule inventory out of the
        source by looking for `rule=` keywords carrying literals, so a rule id
        built anywhere but at the call site goes invisible to the mechanism
        that checks every rule has a mutation behind it.
        """
        return Finding(
            task=self.task.ident,
            section=self.task.section,
            line=self.task.line + 1,
            **fields,
        )

    @property
    def marked_by(self):
        return f"`{self.path}` is marked @{self.owner_ident} by {self.task.ident}"


def run(doc):
    findings = []
    # Both built ONCE. `registrar.closure` builds the edge map itself when it
    # is not handed one, and the claim set reads every `Files:` line in the
    # document; per-entry rebuilds would repeat both for each marked entry.
    edges = graph.build_edges(doc)[0]
    claimed = frozenset(bare_claims(doc))

    # Every canonical path to the identifiers that write it, marked or bare.
    # An ORDER row is decided against the writer set of the PATH: the marked
    # half alone would miss the creator, and the bare half alone would miss
    # every second writer.
    #
    # Built HERE and not in a helper of its own. `tests/planlint/
    # test_marker_census.py` censuses every function that reads `files_items`
    # under its own name, and `run` is already one of them; a helper would be
    # a second consumer whose disposition — it STRIPS, exactly as `run` does —
    # would have to be registered in a file this pass does not own.
    writers = {}
    for task in doc.tasks:
        for item in task.files_items:
            written = strip_marker(item) if has_marker(item) else item
            writers.setdefault(canonical_path(written), []).append(task.ident)

    for task in doc.tasks:
        for item in task.files_items:
            if not has_marker(item):
                continue
            path = strip_marker(item)
            findings.extend(
                _adjudicate(
                    Entry(
                        doc=doc,
                        task=task,
                        path=canonical_path(path),
                        owner_ident=item[len(path) + 1:],
                        edges=edges,
                        claimed=claimed,
                        repositories=doc.track_repositories.get(
                            task.track, ()
                        ),
                        writers=writers,
                    )
                )
            )

    # A plan whose tasks carry no marked entry is NORMAL, not an empty scan —
    # most tasks write only what they own. The guard keys on task bodies, the
    # unit `markers.run` guards on, so a document with no tasks at all is the
    # thing that fails loudly here.
    return guard_no_input(
        "secondwrite",
        findings,
        len(doc.tasks),
        "task bodies",
        "second-write lint",
        notice=coverage_notice(),
    )


def _adjudicate(entry):
    """Every condition-10 finding ONE marked entry earns, in table order.

    The five tests of section 7.4.2 are INDEPENDENT, so this returns a list
    and not the first failure. An entry that names the wrong owner AND sits
    outside that owner's class fails two tests, and a reader who repaired only
    the one this returned would come back to the second.
    """
    findings = []
    for _, test in DISPATCH:
        finding = test(entry)
        if finding is not None:
            findings.append(finding)
    return findings


def _test_1(entry):
    """This section holds an owner row for the (repository, path) pair."""
    if entry.has_row:
        return None
    return entry.at(
        rule="second-write-no-owner-row",
        message=NO_ROW_MESSAGE,
        evidence=(
            f"{entry.marked_by}; section 7.4.2 holds no owner row for it"
        ),
        severity=ERROR,
    )


def _test_2(entry):
    """The `<OWNER-ID>` in the marker equals the owner the row names.

    A cell that names no task block states no owner this tool can resolve —
    section 7.4.2 carries `the operator` and `the plugin track` among others —
    and the comparison is then undecidable rather than satisfied. It is
    reported UNDECIDED, because a silence here reads exactly like a pass.

    The ROW is what this test reads, so a path with no row leaves it nothing
    to compare and it says nothing: the missing row is test 1's finding, and
    reporting it twice sends a reader to two repairs for one defect.
    """
    if not entry.has_row:
        return None
    named = entry.doc.owner_of(entry.path, entry.repositories)
    if named is None:
        cell = entry.doc.owner_cell(entry.path, entry.repositories) or ""
        if states_order(cell):
            return _order_owner(entry, cell)
        return entry.at(
            rule="second-write-owner-undecided",
            message=OWNER_UNDECIDED_MESSAGE,
            evidence=f"{entry.marked_by}; the owner cell reads: {cell}",
            severity=WARNING,
        )
    if named.ident == entry.owner_ident:
        return None
    return entry.at(
        rule="second-write-wrong-owner",
        message=WRONG_OWNER_MESSAGE,
        evidence=(
            f"{entry.marked_by}; section 7.4.2's row names {named.ident} as "
            "its owner"
        ),
        severity=ERROR,
    )


def _order_owner(entry, cell):
    """Test 2 under a row that resolves the path by ORDER.

    An order row names no owner and is not thereby undecidable: the owner of a
    path written serially is the writer that comes FIRST, and section 7.2's
    table says which that is. The marker's `<OWNER-ID>` is held against that
    writer.

    A TIE at the earliest position is not reported here. Two writers sharing
    one wave is the collision test 4 decides, and reporting it twice would
    send a reader to two repairs for one defect; a marker naming either of the
    tied writers names a writer the order really does place first.
    """
    placed, unplaced = entry.wave_positions()
    if unplaced:
        return entry.at(
            rule="second-write-owner-undecided",
            message=ORDER_OWNER_UNDECIDED_MESSAGE,
            evidence=(
                f"{entry.marked_by}; the owner cell reads: {cell}, and "
                "section 7.2's wave table places "
                f"{', '.join(unplaced)} in no row"
            ),
            severity=WARNING,
        )
    if not placed:
        return None
    first = min(order for _, order in placed.values())
    earliest = sorted(
        ident for ident, (_, order) in placed.items() if order == first
    )
    if entry.owner_ident in earliest:
        return None
    label = next(
        label for label, order in placed.values() if order == first
    )
    return entry.at(
        rule="second-write-wrong-owner",
        message=ORDER_WRONG_OWNER_MESSAGE,
        evidence=(
            f"{entry.marked_by}; the owner cell reads: {cell}, and the writer "
            f"section 7.2 places earliest is {', '.join(earliest)}, in wave "
            f"{label}"
        ),
        severity=ERROR,
    )


def _order_admission(entry):
    """Test 4 under a row that resolves the path by ORDER.

    The row states its own admission rule mechanically — "no two writers of
    one file share a wave" — and it is a property of the PATH's writer set and
    not of the directory row's. Two writers of one file in one wave put two
    worktrees on one file at once, which is the thing the order exists to
    prevent.

    Only the writers that COLLIDE are reported, and each names the other. A
    writer whose wave nobody else holds is admitted by the order the row
    states, and a finding against it would name no repair.
    """
    placed, unplaced = entry.wave_positions()
    if unplaced:
        return entry.at(
            rule="second-write-class-undecided",
            message=ORDER_ADMISSION_UNDECIDED_MESSAGE,
            evidence=(
                f"{entry.marked_by}; the owner row resolves this path by "
                "order, and section 7.2's wave table places "
                f"{', '.join(unplaced)} in no row"
            ),
            severity=WARNING,
        )
    here = placed.get(entry.task.ident)
    if here is None:
        return None
    sharers = sorted(
        ident
        for ident, (_, order) in placed.items()
        if order == here[1] and ident != entry.task.ident
    )
    if not sharers:
        return None
    return entry.at(
        rule="second-write-outside-class",
        message=ORDER_COLLISION_MESSAGE,
        evidence=(
            f"{entry.marked_by}; the owner row resolves this path by order, "
            f"and section 7.2 places {entry.task.ident} in wave {here[0]} "
            f"together with {', '.join(sharers)}"
        ),
        severity=ERROR,
    )


def _test_3(entry):
    """`<OWNER-ID>` is inside the writing task's transitive `Depends:` closure.

    Read from the MARKER and never from the row, so a path with no owner row
    is still held against it: the two are different defects and a document can
    carry either alone.

    An owner id naming no task block is in no closure. That is reported as
    this test's failure, with evidence saying which of the two shapes it is,
    because "add the edge" and "the task does not exist" send a reader to
    different repairs.
    """
    reachable = registrar.closure(entry.doc, entry.task.ident, entry.edges)
    if entry.owner_ident in reachable:
        return None
    if not entry.doc.has_task(entry.owner_ident):
        evidence = (
            f"{entry.marked_by}, and {entry.owner_ident} is no task block of "
            "this document"
        )
    else:
        evidence = (
            f"{entry.marked_by}, whose dependency closure is {{"
            + ", ".join(sorted(reachable))
            + "}"
        )
    return entry.at(
        rule="second-write-outside-closure",
        message=OUTSIDE_CLOSURE_MESSAGE,
        evidence=evidence,
        severity=ERROR,
    )


def _test_4(entry):
    """The writing task is inside the class the owner row states."""
    if not entry.has_row:
        return None
    doc, task, path = entry.doc, entry.task, entry.path
    cell = doc.owner_cell(path, entry.repositories) or ""
    named = doc.owner_of(path, entry.repositories)
    if named is not None and named.ident == task.ident:
        # The owner writes by ownership. Its own class cannot exclude it,
        # because the class governs writers BESIDE the owner.
        return None

    if named is None and states_order(cell):
        # The THIRD shape. The row admits by ORDER and not by a class, so the
        # class half has nothing to read: an owner cell stating an order names
        # the section 7.2 table as the admission rule, and that table is not
        # prose.
        return _order_admission(entry)

    mechanism = doc.mechanism_cell(path, entry.repositories)
    if mechanism is None:
        # The owner table carries no mechanism column at all, so this
        # document states no class anywhere. Nothing was refused; nothing
        # was granted either. Undecided, never passed.
        return entry.at(
            rule="second-write-class-undecided",
            message=UNDECIDED_MESSAGE,
            evidence=(
                f"{entry.marked_by}; the owner row carries no mechanism "
                "column, so no class is stated anywhere in it"
            ),
            severity=WARNING,
        )
    # The class is read from the ROW, not from one column of it. Section 7.4.2
    # states no rule that the class must sit in the mechanism cell, and the ten
    # `tests_<track>.cmake` rows state it in the OWNER cell while spending the
    # mechanism cell on why the row replaced a per-list roster. A reader of one
    # column reported "states no class" about a row whose first sentence states
    # the class.
    row = f"{cell} {strip_markup(mechanism)}".strip()
    if not states_class(row):
        return entry.at(
            rule="second-write-outside-class",
            message=CLASSLESS_MESSAGE,
            evidence=(
                f"{entry.marked_by}; the owner row names "
                f"{cell or 'an unresolvable owner'} and states no class"
            ),
            severity=ERROR,
        )

    resolved = resolved_class_tracks(doc, row)
    tracks = set(resolved)
    writer_prefix = _track_of(task.ident).upper()
    if tracks and all(
        writer_prefix not in prefixes for prefixes in resolved.values()
    ):
        return entry.at(
            rule="second-write-outside-class",
            message=FOREIGN_TRACK_MESSAGE,
            evidence=(
                f"`{path}` is marked @{entry.owner_ident} by {task.ident} of "
                f"track {_track_of(task.ident)}; the row's class names "
                "tracks: " + ", ".join(sorted(tracks))
            ),
            severity=ERROR,
        )

    return entry.at(
        rule="second-write-class-undecided",
        message=UNDECIDED_MESSAGE,
        evidence=f"{entry.marked_by}; the row's class reads: {row}",
        severity=WARNING,
    )


def _test_5(entry):
    """Some task claims the path BARE.

    Reported once per MARKED ENTRY and not once per path, because the entry is
    what a reader repairs and a per-path finding would name no `Files:` line
    to go and look at. Every writer of a creatorless manifest hears about it.
    """
    if claimed_bare(entry.path, entry.claimed):
        return None
    return entry.at(
        rule="manifest-without-creator",
        message=NO_CREATOR_MESSAGE,
        evidence=(
            f"{entry.marked_by}, and no task's `Files:` line claims it bare"
        ),
        severity=ERROR,
    )


# Section 7.4.2's condition-10 table has FIVE rows, and one unit is one row of
# that table. The number lives here rather than in a comment because
# `coverage_notice` READS it and prints what is missing: a mechanism checks it,
# so it fails loudly when the table and this module disagree.
CONDITION_10_TESTS = 5

# The dispatch table `_adjudicate` iterates, in the table's own order. It is
# also what `coverage_notice` derives the report's coverage line from, so a
# predicate that is not wired in here cannot be claimed by the notice: the
# announcement and the run read ONE table.
DISPATCH = (
    (1, _test_1),
    (2, _test_2),
    (3, _test_3),
    (4, _test_4),
    (5, _test_5),
)


def coverage_notice(decided=None):
    """The report line saying which of the five tests this run decides.

    A lint that implements two of five tests and prints `secondwrite: clean`
    is indistinguishable from one that ran all five and found nothing. `cli`
    already applies that reasoning to a lint the default run leaves out — "a
    report silent about a lint reads exactly like one in which that lint
    passed" — and a test WITHIN a lint is the same shape one level down.

    The decided set DEFAULTS to the dispatch table, so the notice is derived
    from what actually runs. It is a parameter only so the announcement itself
    has a known positive: handed a partial table it must SAY the remainder is
    unimplemented, and a test holds it to that.
    """
    decided = tuple(number for number, _ in DISPATCH) if decided is None else decided
    missing = [
        number
        for number in range(1, CONDITION_10_TESTS + 1)
        if number not in decided
    ]
    gap = ""
    if missing:
        noun = "Test" if len(missing) == 1 else "Tests"
        verb = "is" if len(missing) == 1 else "are"
        gap = (
            f" {noun} {', '.join(str(number) for number in missing)} {verb} "
            "NOT implemented and this report says nothing about them, so a "
            "clean run here is NOT a clean condition 10."
        )
    return (
        f"COVERAGE: section 7.4.2 condition 10 states {CONDITION_10_TESTS} "
        "tests; this lint decides tests "
        f"{', '.join(str(number) for number in sorted(decided))}.{gap} A "
        "branch that turns on the prose of a class or an owner cell is "
        "reported UNDECIDED and never passed."
    )
