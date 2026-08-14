"""Lint 6 — self-consistency.

Every count the plan states about itself must agree with its own rows. A plan
that miscounts itself is a plan whose reader cannot tell a repair from a
regression.

The lint evaluates a claim only when the document states it. It never invents a
claim, and it never reports a claim it did not find as a pass — an unstated
count is simply not a claim, and the run-level guard reports a document that
states no count at all as a hard error.
"""

import re

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


def as_number(token):
    """A digit or an English number word, or `None`."""
    token = token.strip().replace(",", "")
    if token.isdigit():
        return int(token)
    return WORDS.get(token.lower())


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

    findings.extend(_cross_track_claim(doc, text, lambda: None))
    examined += 1 if _cross_track_statement(text) else 0

    return guard_no_input("counts", findings, examined, "stated counts", "counts lint")


def _cross_track_statement(text):
    for index, line in enumerate(text.splitlines(), start=1):
        if CROSS_TRACK_ROW.search(line):
            found = THERE_ARE.search(line)
            if found:
                stated = as_number(found.group(1))
                if stated is not None:
                    return stated, index
    return None


def _cross_track_claim(doc, text, _unused):
    """Section 7.6 assertion 7 states how many cross-track edges live inside one
    wave. Section 7.3's column is what the number must agree with."""
    statement = _cross_track_statement(text)
    if statement is None:
        return []
    stated, line = statement
    inside = [
        (source, target)
        for source, target in doc.cross_track_edges
        if source in doc.wave_of
        and target in doc.wave_of
        and doc.wave_of[source][1] == doc.wave_of[target][1]
    ]
    if stated == len(inside):
        return []
    listed = "; ".join(f"{a} → {b}" for a, b in inside) or "none"
    return [
        Finding(
            rule="cross-track-edge-count-mismatch",
            message=(
                "section 7.6 assertion 7 states a number of cross-track edges inside "
                "one wave that section 7.3's column does not hold"
            ),
            section="7.6 The dependency and wave check",
            line=line,
            evidence=(
                f"section 7.6 assertion 7 says {stated} cross-track edges inside one "
                f"wave; section 7.3's column holds {len(inside)} ({listed})"
            ),
            severity=ERROR,
        )
    ]
