"""Lint 14 — condition 10, tests 1 and 4, of section 7.4.2's second-writer rule.

Section 7.6 assertion 8 makes a marked `Files:` entry a DECLARED SECOND WRITE,
and section 7.4.2 states five tests every such entry must pass. Two of the five
are decided here:

  * test 1 — `second-write-no-owner-row`: the document holds no owner row for
    the path the marker names. The marker's whole premise — that §7.4.2 holds
    a row for the pair — is refuted by the document it cites.
  * test 4 — `second-write-outside-class`: the writing task is outside the
    class the owner row states.

Tests 2 (`second-write-wrong-owner`), 3 (`second-write-outside-closure`) and 5
(`manifest-without-creator`) are not implemented here; this module reports
nothing about them rather than a verdict it cannot support.

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

Track tokens compare by prefix: "sched" covers a SCH- writer, "usbhost" covers
a USB- writer, because the plan writes the long word and the identifier carries
the short one. A token that is neither equal to nor prefixed by the track goes
undecided rather than excluded — guessing at "dsp" against "dsp56k" would be
inventing an ownership rule the plan does not state.

A bare claimant beside the marker is test 5's territory (`manifest-without-
creator`) and produces no finding here.
"""

import re

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

# A class sentence carries an "every ... task" limb. The words may stand
# apart — "every sch-track task" — so a containment test for the two-word
# phrase would read no real class. Word boundaries keep "Everybody else asks
# AAA-1" out: `everybody` is not the word `every`.
CLASS_LIMB = re.compile(r"\bevery\b.*\btask\b", re.DOTALL)

TRACK_LIMB = re.compile(r"\b([a-z0-9]+)-track\b")


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


def _track_of(ident):
    return ident.partition("-")[0].lower()


def run(doc):
    findings = []

    for task in doc.tasks:
        for item in task.files_items:
            if not has_marker(item):
                continue
            path = strip_marker(item)
            owner_ident = item[len(path) + 1:]
            finding = _adjudicate(doc, task, item, path, owner_ident)
            if finding is not None:
                findings.append(finding)

    # A plan whose tasks carry no marked entry is NORMAL, not an empty scan —
    # most tasks write only what they own. The guard keys on task bodies, the
    # unit `markers.run` guards on, so a document with no tasks at all is the
    # thing that fails loudly here.
    return guard_no_input(
        "secondwrite", findings, len(doc.tasks), "task bodies", "second-write lint"
    )


def _adjudicate(doc, task, item, path, owner_ident):
    path = canonical_path(path)
    if not doc.has_owner(path):
        return Finding(
            rule="second-write-no-owner-row",
            message=NO_ROW_MESSAGE,
            task=task.ident,
            section=task.section,
            line=task.line + 1,
            evidence=(
                f"`{path}` is marked @{owner_ident} by {task.ident}; section "
                "7.4.2 holds no owner row for it"
            ),
            severity=ERROR,
        )

    cell = doc.owner_cell(path) or ""
    named = doc.owner_of(path)
    if named is not None and named.ident == task.ident:
        # The owner writes by ownership. Its own class cannot exclude it,
        # because the class governs writers BESIDE the owner.
        return None

    mechanism = doc.mechanism_cell(path)
    if mechanism is None:
        # The owner table carries no mechanism column at all, so this
        # document states no class anywhere. Nothing was refused; nothing
        # was granted either. Undecided, never passed.
        return Finding(
            rule="second-write-class-undecided",
            message=UNDECIDED_MESSAGE,
            task=task.ident,
            section=task.section,
            line=task.line + 1,
            evidence=(
                f"`{path}` is marked @{owner_ident} by {task.ident}; the "
                "owner row carries no mechanism column, so no class is "
                "stated anywhere in it"
            ),
            severity=WARNING,
        )
    mechanism = strip_markup(mechanism)
    if not states_class(mechanism):
        return Finding(
            rule="second-write-outside-class",
            message=CLASSLESS_MESSAGE,
            task=task.ident,
            section=task.section,
            line=task.line + 1,
            evidence=(
                f"`{path}` is marked @{owner_ident} by {task.ident}; the "
                f"owner row names {cell or 'an unresolvable owner'} and "
                "states no class"
            ),
            severity=ERROR,
        )

    tracks = class_tracks(mechanism)
    if tracks and all(not (_track_of(task.ident) == t or t.startswith(_track_of(task.ident))) for t in tracks):
        return Finding(
            rule="second-write-outside-class",
            message=FOREIGN_TRACK_MESSAGE,
            task=task.ident,
            section=task.section,
            line=task.line + 1,
            evidence=(
                f"`{path}` is marked @{owner_ident} by {task.ident} of track "
                f"{_track_of(task.ident)}; the row's class names tracks: "
                + ", ".join(sorted(tracks))
            ),
            severity=ERROR,
        )

    return Finding(
        rule="second-write-class-undecided",
        message=UNDECIDED_MESSAGE,
        task=task.ident,
        section=task.section,
        line=task.line + 1,
        evidence=(
            f"`{path}` is marked @{owner_ident} by {task.ident}; the row's "
            f"class reads: {mechanism}"
        ),
        severity=WARNING,
    )
