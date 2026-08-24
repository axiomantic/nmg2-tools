"""Lint 11 — anchored figures.

A figure the tool DERIVES may also be written out in prose, and a prose
restatement is invisible to the check that pins the derivation. That is this
project's signature defect wearing a costume: the derivation is right, the
derived value is checked, and the sentence beside it still states last month's
number. A stale claim then reads exactly like a current one.

The prose is reached through an ANCHOR and never through a scan for numbers.

    ... it is one of the <!-- derived: cross-track-edge-count -->sixteen edges
    section 7.6 assertion 7 counts.

That is section 14.3's own sentence, and it is a restatement of the derived
figure rather than a sentence that merely holds a number: its subject IS the
edge set assertion 7 counts.

The anchor is an HTML comment. A renderer that passes raw HTML through emits it
as a comment and contributes no visible text, which is what the plan's renderer
does; a renderer with raw HTML DISABLED escapes it and the reader sees it. The
checked token is the run of letters and digits IMMEDIATELY after the closing
`-->`, thus one anchor marks exactly one figure and the marking is decidable.

A scan for numbers is the alternative, and it is rejected because it cannot
tell a figure from an identifier that holds a digit — `W3` is the shape that
defeats it. What that instrument buys is COMPLETENESS, and completeness is not
what makes a check trustworthy: a confident wrong answer costs more than a
narrow right one. The trade is DECLARED rather than hidden, and the declaration
is mechanical: the lint reports how many anchors it examined, so an anchor set
that shrinks to nothing is a hard error and never a quiet pass.

WHAT AN ANCHOR MUST NOT BE ATTACHED TO is the judgement no rule here makes, and
the near-miss is the reason it is written down. Section 7.4 opens with "Fifteen
cross-track edges exist inside or around what was one wave, and five of them
are header reads". That sentence is NOT a restatement of this figure. Its
subject is section 7.4's OWN table — 27 rows, 12 of which name a header — and
its predicate reads "inside OR AROUND" one wave, so it deliberately keeps the
wave-crossing rows assertion 7's "crosses a track inside one wave" excludes.
Anchoring it would have obliged the writer to type "Sixteen" there for a green
run, and the lint would then hold a claim about a 27-row table VERIFIED at the
derived 16 — a false claim wearing a verified costume, which is worse than the
stale claim it replaced. It stays unanchored and 15/5 stays stale, until it is
deleted or a second derived key measures the table itself.
"""

import dataclasses
import re

from planlint import counts
from planlint.finding import ERROR, Finding, guard_no_input

# The comment body is captured LOOSELY and validated afterwards. A pattern that
# accepted only a well-formed key would not match a misspelled anchor at all,
# and an anchor the scanner cannot see reads exactly like an anchor that is not
# there.
# The token class carries the HYPHEN so that a compound number word is
# captured whole. Without it `twenty-two` was captured as `twenty`, read
# as 20, and reported stale against a derived 22 -- the rule accusing a
# document that was correct, which is worse than not checking at all.
ANCHOR = re.compile(r"<!--\s*derived:(?P<key>.*?)-->[ \t]*(?P<token>[A-Za-z0-9,-]*)")

# `{key: how the tool derives the figure}`. A key here with no anchor beside it
# in the document is a finding, so registering a figure obliges the prose that
# restates it to be anchored.
DERIVED = {
    "cross-track-edge-count": lambda doc: len(counts.graph_cross_track_edges(doc)),
}


@dataclasses.dataclass(frozen=True)
class Anchor:
    key: str
    token: str
    line: int


def anchors_in(doc):
    """Every anchor in the document, in reading order."""
    out = []
    for number, line in enumerate(doc.lines, start=1):
        for match in ANCHOR.finditer(line):
            out.append(
                Anchor(
                    key=match.group("key").strip(),
                    token=match.group("token"),
                    line=number,
                )
            )
    return out


def _unknown_key(doc, anchor):
    return Finding(
        rule="derived-figure-unknown-key",
        message="an anchor names a derived figure this tool does not compute",
        section=doc.section_at(anchor.line),
        line=anchor.line,
        evidence=(
            f"the anchor names `{anchor.key}`; this tool computes "
            + ", ".join(sorted(DERIVED))
        ),
        severity=ERROR,
    )


def _unparsed(doc, anchor):
    return Finding(
        rule="derived-figure-unparsed",
        message="an anchor marks a token that is not a number this tool reads",
        section=doc.section_at(anchor.line),
        line=anchor.line,
        evidence=(
            f"the anchor `{anchor.key}` is followed by no letter or digit, so it "
            "marks no figure"
            if not anchor.token
            else f"the anchor `{anchor.key}` marks `{anchor.token}`, which is "
            "neither a digit nor a number word this tool reads"
        ),
        severity=ERROR,
    )


def _stale(doc, anchor, stated, derived):
    return Finding(
        rule="derived-figure-stale",
        message=(
            "a prose restatement of a derived figure does not equal the value "
            "the tool derives"
        ),
        section=doc.section_at(anchor.line),
        line=anchor.line,
        evidence=(
            f"the anchor `{anchor.key}` restates the figure as `{anchor.token}`, "
            f"which reads as {stated}; the tool derives {derived}"
        ),
        severity=ERROR,
    )


def _unanchored(doc, key):
    """No LINE and no section: the defect is an absence, and a line number
    would send a reader to a place where nothing is wrong."""
    return Finding(
        rule="derived-figure-unanchored",
        message="a derived figure has no anchored restatement in the document",
        evidence=(
            f"the tool derives `{key}` as {DERIVED[key](doc)} and no "
            f"`<!-- derived: {key} -->` anchor names it"
        ),
        severity=ERROR,
    )


def run(doc):
    findings = []
    found = anchors_in(doc)
    for anchor in found:
        if anchor.key not in DERIVED:
            findings.append(_unknown_key(doc, anchor))
            continue
        stated = counts.as_number(anchor.token)
        if stated is None:
            findings.append(_unparsed(doc, anchor))
            continue
        derived = DERIVED[anchor.key](doc)
        if stated != derived:
            findings.append(_stale(doc, anchor, stated, derived))
    named = {anchor.key for anchor in found}
    findings.extend(_unanchored(doc, key) for key in sorted(set(DERIVED) - named))
    return guard_no_input(
        "anchors", findings, len(found), "anchored figures", "anchors lint"
    )
