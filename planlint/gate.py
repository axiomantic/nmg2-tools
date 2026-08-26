"""Lint 17 — the completion gate.

Section 24.6 row W3-422 states the hole this closes. Section 7.6 assertion 5
compares wave ORDER and never COMPLETION: a Wave-3a task whose dependency sits
in Wave 0 satisfies it forever, because 3a is greater than 0 whether or not the
Wave-0 task was ever started. Enforcement and absence of enforcement produced
the identical green.

THE PREDICATE IS THE DEPENDENCY GRAPH AND NOT THE WAVE, and the row says so in
its own acceptance clause: *"no task may carry a completion marker while a task
in its transitive dependency closure carries none"*. The wave table is a
schedule, and a wave holds tasks that do not depend on each other; a wave-level
gate would convict a marked task for an unmarked NEIGHBOUR it never waits on,
and would miss a dependency the table puts in the same wave. The pairs the row
names as its proof are `Depends:` pairs.

THE CLOSURE IS READ AT ITS EDGES, WHICH REPORTS THE SAME DOCUMENTS. Walk any
path from a marked task to an unmarked task in its closure and stop at the first
unmarked node: the node before it is marked, so the direct edge into it is
reported. A document this rule is silent on therefore holds no marked task with
an unmarked task anywhere in its closure. What the edge form drops is the
redundant restatement — the head of a chain named again for a gap two hops down,
which a reader repairs at the same one edge.

A STRUCK MARKER IS NOT A MARKER. `document._scan_done_markers` reads the
`**DONE` spelling, and `**~~DONE` does not carry it, so a withdrawn marker
reaches this lint as an absence. That is the whole of the strike rule here, and
it is not restated as a second scanner: two readers of one question can
disagree.

THE TWO RULES ARE SEPARATED BY WHAT THE DEPENDENCY DECLARES ABOUT ITSELF. Some
dependencies are not this plan's to finish — an outward act only the operator
may take, a task listed and not scheduled, a pull request against a repository
this project does not own. Reporting those at the same weight as unfinished
engineering work is how a rule trains a reader to ignore it. They are still
REPORTED, because the statement is true and a silence here reads exactly like
coverage; they carry their own rule id, their own severity and the plan's own
reason. Severity orders the report and never excuses a finding from the exit
code.

The discriminator is section 1.5's TIER SUBSTITUTE, read off the dependency's
own header, and never a roster of identifiers: a roster is amended once per case
and states nothing about the case after it. THROWAWAY is deliberately absent
from that table. Section 1.5 gives a spike a check the operator runs against
`extracted/`, so it is work this plan schedules — and the pairs row W3-422 offers
as its proof depend on spikes, so a table that excused THROWAWAY would silence
its own evidence. A header that carries a section 5.1 tier is work
this plan schedules whatever else the header says.
"""

import dataclasses
import re

from planlint import graph
from planlint.finding import ERROR, WARNING, Finding, guard_no_input


@dataclasses.dataclass(frozen=True)
class Disposition:
    """One section 1.5 tier substitute whose task this plan does not schedule.

    `why` is the substitute's own meaning as section 1.5 writes it, so the
    report states the plan's reason rather than this module's opinion of it.
    """

    substitute: str
    why: str


UNSCHEDULED = (
    Disposition(
        "OPERATOR",
        "the task needs an outward action only the operator may take",
    ),
    Disposition(
        "deferred",
        "the task is listed and not scheduled, and has no check to run",
    ),
    Disposition(
        "upstream",
        "the check is a pull request against a repository this project does not own",
    ),
)


def disposition_of(task):
    """The row a task's header declares, or `None` for work this plan schedules.

    A header carrying a section 5.1 tier is answered before the table is read.
    Section 1.5's substitutes are what a header reaches for when it carries no
    tier, so a tier settles the question and the word beside it cannot reopen
    it. A header that names more than one substitute takes the first row that
    matches, so the answer does not depend on how the header ordered them.
    """
    if task.has_tier:
        return None
    for row in UNSCHEDULED:
        if re.search(rf"\b{row.substitute}\b", task.tier_text, re.IGNORECASE):
            return row
    return None


def marker_lines(doc):
    """`{ident: line}` for the FIRST live completion marker each task carries."""
    found = {}
    for marker in doc.done_markers:
        found.setdefault(marker.task, marker.line)
    return found


def run(doc):
    findings = []
    edges, _ = graph.build_edges(doc)
    marked = marker_lines(doc)

    for task in doc.tasks:
        line = marked.get(task.ident)
        if line is None:
            continue
        for dependency in edges[task.ident]:
            other = doc.task(dependency)
            if other is None or other.ident in marked:
                continue
            head = (
                f"{task.ident} carries a completion marker at line {line}; "
                f"{other.ident} is on its `Depends:` line and carries none"
            )
            row = disposition_of(other)
            if row is None:
                findings.append(
                    Finding(
                        rule="done-marker-over-incomplete-dependency",
                        message=(
                            "a task is recorded complete while a task it waits "
                            "on is not. Section 7.6 assertion 5 compares wave "
                            "ORDER and never completion, so this pair satisfies "
                            "it and the work behind the marker rests on work "
                            "that was never started"
                        ),
                        task=task.ident,
                        section=task.section,
                        line=line,
                        evidence=head,
                        severity=ERROR,
                    )
                )
                continue
            findings.append(
                Finding(
                    rule="done-marker-over-a-dependency-this-plan-does-not-schedule",
                    message=(
                        "a task is recorded complete while a task it waits on "
                        "carries a section 1.5 tier substitute this plan does "
                        "not schedule. The pair is as real as any other and is "
                        "reported, but the act that closes it is not an "
                        "engineering one, so it is named apart from the work a "
                        "reader of this report can take"
                    ),
                    task=task.ident,
                    section=task.section,
                    line=line,
                    evidence=f"{head}. {other.ident} is declared {row.substitute}: {row.why}",
                    severity=WARNING,
                )
            )

    return guard_no_input(
        "gate", findings, len(doc.tasks), "task bodies", "completion-gate lint"
    )
