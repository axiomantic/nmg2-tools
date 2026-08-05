"""Lint 2 — wave ordering.

Section 7.6 assertion 5: every task's wave order is greater than or equal to the
order of every task it depends on. The section 7.2 wave TABLE is the field this
lint reads. No task block carries a `Wave:` field and the diagram above the table
is for a human.
"""

from planlint import graph
from planlint.finding import ERROR, Finding, guard_no_input


def run(doc):
    findings = []
    edges, _ = graph.build_edges(doc)

    for task in doc.tasks:
        if task.ident not in doc.wave_of:
            findings.append(
                Finding(
                    rule="task-without-wave",
                    message=(
                        "the section 7.2 wave table places this task in no row, so "
                        "assertion 5 has no order to compare"
                    ),
                    task=task.ident,
                    section=task.section,
                    line=task.line,
                    evidence=f"the section 7.2 wave table names {task.ident} in no row",
                    severity=ERROR,
                )
            )

    for ident, (label, _order) in sorted(doc.wave_of.items()):
        if not doc.has_task(ident):
            findings.append(
                Finding(
                    rule="wave-without-task",
                    message="the section 7.2 wave table names a task this plan defines nowhere",
                    task=ident,
                    section="7.2 The waves",
                    evidence=f"wave {label} names {ident}; no task block defines it",
                    severity=ERROR,
                )
            )

    for task in doc.tasks:
        here = doc.wave_of.get(task.ident)
        if here is None:
            continue
        for dependency in edges[task.ident]:
            there = doc.wave_of.get(dependency)
            if there is None:
                continue
            if here[1] < there[1]:
                findings.append(
                    Finding(
                        rule="wave-order",
                        message=(
                            "a task starts in an earlier wave than a task it waits on, "
                            "so the work cannot begin when the table says it does"
                        ),
                        task=task.ident,
                        section=task.section,
                        line=task.line,
                        evidence=(
                            f"{task.ident} is wave {here[0]} (order {here[1]}); "
                            f"it depends on {dependency}, which is wave {there[0]} "
                            f"(order {there[1]})"
                        ),
                        severity=ERROR,
                    )
                )

    return guard_no_input(
        "waves", findings, len(doc.wave_of), "wave-table entries", "wave lint"
    )
