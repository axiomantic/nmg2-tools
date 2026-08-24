"""Lint 6 — self-consistency.

Every claim the plan states about itself must agree with what the plan holds. A
plan that miscounts itself is a plan whose reader cannot tell a repair from a
regression.

The lint evaluates a claim only when the document states it. It never invents a
claim, and it never reports a claim it did not find as a pass — an unstated
claim is simply not a claim, and the run-level guard reports a document that
states no claim at all as a hard error.

The cross-track claims need a DERIVATION and not a second reading. Section 7.6
assertion 13 states that the cross-track edge set derived from the graph equals
section 7.3's column exactly, so `planlint.graph` supplies one operand: the
`Depends:` parser there refuses to make an edge out of an identifier sitting in
prose, and a rule that built its own set out of section 7.3's column would be
reading the document twice and the graph never.
"""

import re

from planlint import graph
from planlint.document import track_of
from planlint.finding import ERROR, Finding, guard_no_input

WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}

CONDITIONAL_CLAIM = re.compile(r"\bOf the ([A-Za-z0-9]+) conditional tasks\b")
CROSS_TRACK_ROW = re.compile(r"crosses a track inside one wave", re.IGNORECASE)
THERE_ARE = re.compile(r"\bThere are ([A-Za-z0-9]+)\b")


TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}


def as_number(token):
    """A digit or an English number word, or `None`.

    Compound words are read as well, in the hyphenated form this document
    uses -- `twenty-two` is 22. Without this a figure that grows past twenty
    reports as its own tens word and the anchor rule accuses a document that
    is correct: `twenty-two` matched `twenty` and read as 20 while the tool
    derived 22, which is the instrument disagreeing with itself rather than
    with the text.
    """
    token = token.strip().replace(",", "")
    if token.isdigit():
        return int(token)
    lowered = token.lower()
    if lowered in WORDS:
        return WORDS[lowered]
    if lowered in TENS:
        return TENS[lowered]
    head, sep, tail = lowered.partition("-")
    if sep and head in TENS and tail in WORDS and 1 <= WORDS[tail] <= 9:
        return TENS[head] + WORDS[tail]
    return None


def run(doc):
    findings = []
    examined = 0
    text = "\n".join(doc.lines)

    actual_by_track = {}
    for task in doc.tasks:
        actual_by_track.setdefault(task.track, []).append(task.ident)

    for track, stated, line, label in doc.count_rows:
        examined += 1
        held = actual_by_track.get(track, [])
        if stated != len(held):
            findings.append(
                Finding(
                    rule="track-count-mismatch",
                    message=(
                        "a track row in section 24.1 states a task count the document "
                        "does not hold"
                    ),
                    section="24.1 Counts",
                    line=line,
                    evidence=(
                        f"section 24.1 says track {track} has {stated} tasks; the "
                        f"document holds {len(held)} ({', '.join(held) or 'none'})"
                    ),
                    severity=ERROR,
                )
            )

    if doc.stated_total_tasks is not None:
        stated_total, total_line = doc.stated_total_tasks
        examined += 1
        if stated_total != len(doc.tasks):
            findings.append(
                Finding(
                    rule="total-count-mismatch",
                    message="the stated total of task blocks is not the number parsed",
                    section="24.1 Counts",
                    line=total_line,
                    evidence=(
                        f"section 24.1 says {stated_total} task blocks; the document "
                        f"holds {len(doc.tasks)}"
                    ),
                    severity=ERROR,
                )
            )
        row_sum = sum(stated for _, stated, _, _ in doc.count_rows)
        if doc.count_rows and row_sum != stated_total:
            findings.append(
                Finding(
                    rule="total-is-not-the-sum",
                    message="the total row does not equal the sum of the track rows",
                    section="24.1 Counts",
                    line=total_line,
                    evidence=(
                        f"section 24.1's track rows sum to {row_sum}; its total row "
                        f"says {stated_total}"
                    ),
                    severity=ERROR,
                )
            )

    match = CONDITIONAL_CLAIM.search(text)
    if match:
        stated = as_number(match.group(1))
        if stated is not None:
            examined += 1
            held = len(doc.conditional_tasks)
            if stated != held:
                findings.append(
                    Finding(
                        rule="conditional-count-mismatch",
                        message=(
                            "the plan states a number of conditional tasks that "
                            "section 24.4's table does not hold"
                        ),
                        section="24.4 The conditional tasks",
                        line=text[: match.start()].count("\n") + 1,
                        evidence=(
                            f"the plan says {stated} conditional tasks; section 24.4's "
                            f"table holds {held}"
                        ),
                        severity=ERROR,
                    )
                )

    derived_any_wave = graph_cross_track_edges_any_wave(doc)
    derived = graph_cross_track_edges(doc)
    declared = declared_cross_track_edges(doc)
    tabled = table_cross_track_edges(doc)

    findings.extend(_cross_track_set(doc, derived, declared))
    examined += 1 if (derived or declared or doc.cross_track_edges) else 0

    findings.extend(_cross_track_table_set(doc, derived, tabled))
    examined += 1 if (derived or tabled or doc.cross_track_table) else 0

    # The two stated sites are already counted as examined claims above. The
    # widened reading is a second reading of the same two claims and not a
    # third claim, so it adds no count.
    findings.extend(_cross_wave_arrow_set(doc, derived_any_wave))

    findings.extend(_cross_track_claim(text, derived))
    examined += 1 if _cross_track_statement(text) else 0

    return guard_no_input("counts", findings, examined, "stated claims", "counts lint")


def _cross_track_statement(text):
    for index, line in enumerate(text.splitlines(), start=1):
        if CROSS_TRACK_ROW.search(line):
            found = THERE_ARE.search(line)
            if found:
                stated = as_number(found.group(1))
                if stated is not None:
                    return stated, index
    return None


def _in_one_wave(doc, source, target):
    """Whether both ends sit in one wave.

    An end the section 7.2 wave table places nowhere has no order to compare,
    so it is outside this subject; `planlint.waves` is what reports it.
    """
    here = doc.wave_of.get(source)
    there = doc.wave_of.get(target)
    return here is not None and there is not None and here[1] == there[1]


def graph_cross_track_edges_any_wave(doc):
    """`{(depender, dependency): line}` for every edge the `Depends:` GRAPH
    holds whose two ends sit in different tracks, in any wave.

    The line is the depending task's. An edge whose two ends share a track
    crosses no track — a self-loop is that case — so that one exclusion is
    here and the wave is not.

    An ARROW is held against this set. A row that states `A → B` is a claim
    about A's `Depends:` line, and no wave excuses the claim from being true.
    """
    edges, _ = graph.build_edges(doc)
    out = {}
    for task in doc.tasks:
        for dependency in edges[task.ident]:
            if track_of(dependency) == task.track:
                continue
            out[(task.ident, dependency)] = task.line
    return out


def graph_cross_track_edges(doc):
    """The same set narrowed to assertion 7's subject: both ends in one wave.

    An edge whose ends sit in different waves is outside that subject. It is
    not outside every subject — `_cross_wave_arrow_set` holds the stated form
    of it against the wider set above.
    """
    return {
        edge: line
        for edge, line in graph_cross_track_edges_any_wave(doc).items()
        if _in_one_wave(doc, *edge)
    }


def declared_cross_track_edges(doc):
    """The same set, read out of section 7.3's cross-track column.

    The line is the FIRST row that states the edge, and the exclusions are the
    ones above: an edge repeated across rows is one edge, and a row whose two
    ends share a track states no cross-track edge.
    """
    out = {}
    for row in doc.cross_track_edges:
        if track_of(row.source) == track_of(row.target):
            continue
        if not _in_one_wave(doc, row.source, row.target):
            continue
        out.setdefault((row.source, row.target), row.line)
    return out


def table_cross_track_edges(doc):
    """The same set again, read out of section 7.4's table.

    Assertion 7 names TWO sites and the column is only one of them, so this is
    a third operand and not a second reading of the second. The exclusions are
    the ones above, applied to a table whose rows mostly cross a wave: section
    7.4's subject is wider than assertion 7's.
    """
    out = {}
    for row in doc.cross_track_table:
        if track_of(row.source) == track_of(row.target):
            continue
        if not _in_one_wave(doc, row.source, row.target):
            continue
        out.setdefault((row.source, row.target), row.line)
    return out


def declared_cross_track_edges_across_waves(doc):
    """Section 7.3's column, restricted to the rows the wave filter excludes.

    Together with `declared_cross_track_edges` this partitions the column's
    cross-track arrows, so an arrow is judged by exactly one rule and a reader
    never gets the same edge reported twice.
    """
    return _edges_by_row(doc.cross_track_edges, doc, in_one_wave=False)


def table_cross_track_edges_across_waves(doc):
    """Section 7.4's table, restricted the same way, for the same reason."""
    return _edges_by_row(doc.cross_track_table, doc, in_one_wave=False)


def _edges_by_row(rows, doc, in_one_wave):
    """`{(source, target): line}` for the rows on one side of the wave filter.

    The line is the FIRST row that states the edge: an edge repeated across
    rows is one edge. A row whose two ends share a track states no cross-track
    edge and is on neither side.
    """
    out = {}
    for row in rows:
        if track_of(row.source) == track_of(row.target):
            continue
        if _in_one_wave(doc, row.source, row.target) is not in_one_wave:
            continue
        out.setdefault((row.source, row.target), row.line)
    return out


def _wave_phrase(doc, ident):
    label, order = doc.wave_of[ident]
    return f"both wave {label} (order {order})"


def _wave_side(doc, ident):
    placed = doc.wave_of.get(ident)
    if placed is None:
        return f"{ident} in no row of section 7.2's wave table"
    label, order = placed
    return f"{ident} in wave {label} (order {order})"


def _wave_span(doc, source, target):
    """Where the two ends sit, when they do not sit together.

    An end the wave table places nowhere is named as such. That end is why the
    span is spelled out per side rather than as one phrase: `_wave_phrase`
    raises on it, and every in-wave rule is silent on it, which is one of the
    ways a wrong arrow target stayed invisible.
    """
    return f"{_wave_side(doc, source)} and {_wave_side(doc, target)}"


def _cross_track_set(doc, derived, declared):
    """Section 7.6 assertion 13, in both directions.

    A check that reported only what the column omits would pass a column that
    states an edge no `Depends:` line declares, and section 7.3's own `cpu` row
    records that reading as the one a parser and a reader disagree about.
    """
    findings = []
    sections = {
        (row.source, row.target): row.section for row in doc.cross_track_edges
    }
    for source, target in sorted(set(derived) - set(declared)):
        task = doc.task(source)
        findings.append(
            Finding(
                rule="cross-track-edge-undeclared",
                message=(
                    "an edge crosses a track inside one wave and section 7.3's "
                    "cross-track column does not list it"
                ),
                task=source,
                section=task.section if task else "",
                line=derived[(source, target)],
                evidence=(
                    f"{source} → {target}, {_wave_phrase(doc, source)}; "
                    "section 7.3's cross-track column does not list it"
                ),
                severity=ERROR,
            )
        )
    for source, target in sorted(set(declared) - set(derived)):
        findings.append(
            Finding(
                rule="cross-track-edge-not-in-graph",
                message=(
                    "section 7.3's cross-track column states an edge inside one "
                    "wave that no `Depends:` line declares"
                ),
                task=source,
                section=sections.get((source, target), ""),
                line=declared[(source, target)],
                evidence=(
                    f"section 7.3's cross-track column lists {source} → "
                    f"{target}, {_wave_phrase(doc, source)}; {source}'s "
                    f"`Depends:` line does not name {target}"
                ),
                severity=ERROR,
            )
        )
    return findings


def _cross_track_table_set(doc, derived, tabled):
    """Section 7.6 assertion 7's SECOND site, in both directions.

    Assertion 7 asks for each edge in two places and a check that read one of
    them would report a plan complete while the other still omitted the edge.
    Section 7.4's own history is the argument: its table carried a row section
    7.3's column did not, five times over, and only prose noticed.
    """
    findings = []
    sections = {
        (row.source, row.target): row.section for row in doc.cross_track_table
    }
    for source, target in sorted(set(derived) - set(tabled)):
        task = doc.task(source)
        findings.append(
            Finding(
                rule="cross-track-edge-missing-from-7-4",
                message=(
                    "an edge crosses a track inside one wave and section 7.4's "
                    "table does not carry it"
                ),
                task=source,
                section=task.section if task else "",
                line=derived[(source, target)],
                evidence=(
                    f"{source} → {target}, {_wave_phrase(doc, source)}; "
                    "section 7.4's table does not carry it"
                ),
                severity=ERROR,
            )
        )
    for source, target in sorted(set(tabled) - set(derived)):
        findings.append(
            Finding(
                rule="cross-track-row-7-4-not-in-graph",
                message=(
                    "section 7.4's table carries an edge inside one wave that no "
                    "`Depends:` line declares"
                ),
                task=source,
                section=sections.get((source, target), ""),
                line=tabled[(source, target)],
                evidence=(
                    f"section 7.4's table carries {source} → {target}, "
                    f"{_wave_phrase(doc, source)}; {source}'s `Depends:` line "
                    f"does not name {target}"
                ),
                severity=ERROR,
            )
        )
    return findings


def _cross_wave_arrow_set(doc, derived_any_wave):
    """The two stated sites, held to the graph OUTSIDE assertion 7's subject.

    The rules above judge an edge only when its two ends sit in one wave, so a
    row that names a target the graph does not hold reports nothing as soon as
    the edge crosses a wave. That is a true pass over a narrower subject and it
    reads exactly like a clean one: the operands are non-empty and the count
    agrees. It was the reading that let eight wrong arrow targets stand.

    ONLY the direction that reads a STATED arrow is widened. Section 7.3's
    opening lists a track's contract inputs once for the track and does not
    repeat them per task, so the column omits cross-track graph edges in bulk
    and by design; a rule widened the other way would report every one of those
    omissions against a document obeying its own convention, and a rule that
    fires on correct input is worse than no rule.

    The limit, stated because the check does not establish what its name
    suggests: this does NOT assert that either site is complete outside one
    wave. It asserts only that what the two sites DO state is true.
    """
    findings = []
    sections = {
        (row.source, row.target): row.section for row in doc.cross_track_edges
    }
    declared = declared_cross_track_edges_across_waves(doc)
    for source, target in sorted(set(declared) - set(derived_any_wave)):
        findings.append(
            Finding(
                rule="cross-track-edge-not-in-graph-across-waves",
                message=(
                    "section 7.3's cross-track column states an edge across waves "
                    "that no `Depends:` line declares"
                ),
                task=source,
                section=sections.get((source, target), ""),
                line=declared[(source, target)],
                evidence=(
                    f"section 7.3's cross-track column lists {source} → "
                    f"{target}, {_wave_span(doc, source, target)}; {source}'s "
                    f"`Depends:` line does not name {target}"
                ),
                severity=ERROR,
            )
        )

    sections = {
        (row.source, row.target): row.section for row in doc.cross_track_table
    }
    tabled = table_cross_track_edges_across_waves(doc)
    for source, target in sorted(set(tabled) - set(derived_any_wave)):
        findings.append(
            Finding(
                rule="cross-track-row-7-4-not-in-graph-across-waves",
                message=(
                    "section 7.4's table carries an edge across waves that no "
                    "`Depends:` line declares"
                ),
                task=source,
                section=sections.get((source, target), ""),
                line=tabled[(source, target)],
                evidence=(
                    f"section 7.4's table carries {source} → {target}, "
                    f"{_wave_span(doc, source, target)}; {source}'s `Depends:` "
                    f"line does not name {target}"
                ),
                severity=ERROR,
            )
        )
    return findings


def _cross_track_claim(text, derived):
    """Section 7.6 assertion 7 states how many cross-track edges live inside one
    wave. The GRAPH is what the number must agree with.

    Section 7.3's column was the other operand until this revision and it
    cannot be one: the number and the column are two readings of the same
    document, and the column is the very thing assertion 13 holds against the
    graph.
    """
    statement = _cross_track_statement(text)
    if statement is None:
        return []
    stated, line = statement
    if stated == len(derived):
        return []
    listed = "; ".join(f"{a} → {b}" for a, b in sorted(derived)) or "none"
    return [
        Finding(
            rule="cross-track-edge-count-mismatch",
            message=(
                "section 7.6 assertion 7 states a number of cross-track edges inside "
                "one wave that the `Depends:` graph does not hold"
            ),
            section="7.6 The dependency and wave check",
            line=line,
            evidence=(
                f"section 7.6 assertion 7 says {stated} cross-track edges inside one "
                f"wave; the `Depends:` graph holds {len(derived)} ({listed})"
            ),
            severity=ERROR,
        )
    ]
