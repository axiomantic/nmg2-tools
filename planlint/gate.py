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
and states nothing about the case after it. A header that carries a section 5.1
tier is work this plan schedules whatever else the header says.

THE TABLE STATES A VERDICT FOR EVERY SUBSTITUTE AND EXCUSES NONE BY OMISSION.
THROWAWAY carries a row whose severity is ERROR: section 1.5's fourth column
gives a spike a check that runs on the operator's own machine against
`extracted/`, which is a check this plan can name, where OPERATOR's runs
"nowhere automatic", `deferred`'s runs nowhere at all and `upstream`'s runs in a
repository this project does not own. That fourth column is the discriminator,
and the pairs row W3-422 offers as its proof depend on spikes, so a table that
excused THROWAWAY would silence its own evidence. Leaving THROWAWAY OUT reached
the same verdict and stated none: an omission and an oversight produced the
identical silence, which is the shape this file exists to catch.

WHAT THE SET IS AND WHAT THE VERDICT IS ARE TWO QUESTIONS WITH TWO AUTHORS.
Section 1.5 is the one home of the substitute SET and says so, and it states no
verdict, because whether the act that closes a dependency is an engineering one
is a judgement the document does not make. So the set is READ from the document
— as lint 3 reads section 7.8's register rather than carrying a list of its own,
for the reason a second list goes stale — and the verdict is OWNED here. When
the set outruns the verdicts, that is REPORTED rather than resolved by falling
through. A document that states no section 1.5 table is silent: an absent table
names no substitutes and is not a table whose substitutes are all undisposed of.

WHAT IS READ OF THAT TABLE IS THE SUBSTITUTE NAME COLUMN AND NEVER WHAT A ROW
SAYS. Section 1.5 states the command that re-derives its own rows, so the column
is a computed set and not prose. Rewriting any row's meaning or check text keeps
this rule green; only adding, renaming or deleting a substitute reddens it.
"""

import dataclasses
import re

from planlint import graph
from planlint.finding import ERROR, WARNING, Finding, guard_no_input


@dataclasses.dataclass(frozen=True)
class Disposition:
    """One section 1.5 tier substitute and this lint's verdict on it.

    `why` is the substitute's own meaning as section 1.5 writes it, so the
    report states the plan's reason rather than this module's opinion of it.

    `severity` is REQUIRED, which is what makes the table total: a substitute
    cannot be carried here without a verdict, and a verdict cannot be given by
    leaving a row out. An omission and an oversight produced the identical
    silence, and that is the shape section 24.6 row W3-404 names.
    """

    substitute: str
    why: str
    severity: str


SUBSTITUTES = (
    Disposition(
        "THROWAWAY",
        "the task is a spike whose check the operator runs against `extracted/`",
        ERROR,
    ),
    Disposition(
        "OPERATOR",
        "the task needs an outward action only the operator may take",
        WARNING,
    ),
    Disposition(
        "deferred",
        "the task is listed and not scheduled, and has no check to run",
        WARNING,
    ),
    Disposition(
        "upstream",
        "the check is a pull request against a repository this project does not own",
        WARNING,
    ),
)


def disposition_of(task):
    """The row a task's header declares, or `None` when it declares no substitute.

    A header carrying a section 5.1 tier is answered before the table is read.
    Section 1.5's substitutes are what a header reaches for when it carries no
    tier, so a tier settles the question and the word beside it cannot reopen
    it. A header that names more than one substitute takes the first row that
    matches, so the answer does not depend on how the header ordered them.
    """
    if task.has_tier:
        return None
    for row in SUBSTITUTES:
        if re.search(rf"\b{row.substitute}\b", task.tier_text, re.IGNORECASE):
            return row
    return None


def undisposed(doc):
    """Every section 1.5 substitute the document names and this table does not.

    The document is the authority for the SET and this module for the VERDICT,
    because section 1.5 states what a substitute MEANS and never whether the
    act that closes it is an engineering one. A document that states no section
    1.5 table yields nothing: an absent table is a document that names no
    substitutes, not a document whose substitutes are all undisposed of.
    """
    known = {row.substitute.upper() for row in SUBSTITUTES}
    return [row for row in doc.substitute_register if row.substitute.upper() not in known]


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
            if row is None or row.severity == ERROR:
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
                    severity=row.severity,
                )
            )

    for row in undisposed(doc):
        findings.append(
            Finding(
                rule="substitute-without-a-disposition",
                message=(
                    "section 1.5 names a tier substitute this lint states no "
                    "disposition for. The two rules here are separated by what "
                    "the dependency declares about itself, so a substitute with "
                    "no row is decided by falling through to the engineering-work "
                    "rule, and that silence is indistinguishable from a verdict "
                    "someone took"
                ),
                section=doc.section_at(row.line),
                line=row.line,
                evidence=(
                    f"section 1.5 names {row.substitute} at line {row.line}; this "
                    "lint states no disposition for it, so a task declaring it is "
                    "read as work this plan schedules without that having been decided"
                ),
                severity=ERROR,
            )
        )

    return guard_no_input(
        "gate", findings, len(doc.tasks), "task bodies", "completion-gate lint"
    )
