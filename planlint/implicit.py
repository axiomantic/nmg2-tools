"""Lint 7 — implicit dependency detection.

A task that writes into, or reads from, an artifact another task creates, where
no `Depends:` edge exists.

This is the class three rounds of careful reading kept missing, and it is
invisible to Tarjan by construction: the edge was never declared, so no graph
holds it. The instance that made the rule was REPO-15 writing into
`axiomantic/nmg2-artifacts`, which REPO-4 creates, while REPO-4 declares
REPO-15 — a real cycle with one of its two edges unwritten.

The heuristic reports CANDIDATES with their evidence. Precision matters less
than not missing the class, so a reader adjudicates each row. The candidate
whose missing edge would CLOSE a cycle is reported under its own rule, because
that one is never a false positive worth ignoring.
"""

import re

from planlint import graph, registrar
from planlint.finding import ERROR, Finding, WARNING, guard_no_input

# A data artifact, not a translation unit. Source and headers are code: two
# tasks naming the same header is an ownership question, and section 7.4.2 plus
# the check lint already answer it.
ARTIFACT_SUFFIXES = (
    ".txt", ".csv", ".json", ".sha256", ".timebase", ".coverage",
    ".count", ".asm", ".bin", ".pch2",
)
REPOSITORY = re.compile(r"\baxiomantic/[A-Za-z0-9_.\-]+")
FORK_COMMAND = re.compile(r"gh repo fork\s+\S+/([A-Za-z0-9_.\-]+)\s+--org\s+axiomantic")


def is_artifact(item):
    return item.endswith("/") or item.lower().endswith(ARTIFACT_SUFFIXES)


def artifact_creators(doc):
    """`{artifact: creator}` for every artifact exactly one task creates.

    A path two tasks claim is an ownership question and not an implicit edge,
    so it is left to the check lint's `shared-path-without-owner` rule.
    """
    claims = {}
    for task in doc.tasks:
        for item in set(task.files_paths):
            if is_artifact(item):
                claims.setdefault(item, []).append(task.ident)
    return {item: owners[0] for item, owners in claims.items() if len(owners) == 1}


def repository_creators(doc):
    """`{repository: creator}` read from the task that brings it into being.

    A repository is created by the task whose header names it, or by the task
    whose check runs `gh repo fork ... --org axiomantic`.
    """
    out = {}
    for task in doc.tasks:
        for name in REPOSITORY.findall(task.name):
            out.setdefault(name, task.ident)
        for repo in FORK_COMMAND.findall(task.body_text):
            out.setdefault(f"axiomantic/{repo}", task.ident)
    return out


def run(doc):
    findings = []
    edges, _ = graph.build_edges(doc)
    tracked = {}
    tracked.update(artifact_creators(doc))
    tracked.update(repository_creators(doc))

    closures = {task.ident: registrar.closure(doc, task.ident, edges) for task in doc.tasks}

    for task in doc.tasks:
        body = task.body_text
        # One finding for each missing EDGE, not for each artifact. Two artifacts
        # of the same creator are one undeclared dependency, and reporting it
        # twice trains a reader to skim.
        by_creator = {}
        for item, creator in sorted(tracked.items()):
            if creator == task.ident or item not in body:
                continue
            if creator in closures[task.ident]:
                continue
            by_creator.setdefault(creator, []).append(item)

        for creator, items in sorted(by_creator.items()):
            named = ", ".join(f"`{item}`" for item in items)
            if task.ident in closures.get(creator, set()):
                findings.append(
                    Finding(
                        rule="implicit-dependency-would-cycle",
                        message=(
                            "a task uses an artifact another task creates, declares no "
                            "path to it, and the creator already waits on this task. "
                            "The undeclared edge closes a cycle that no graph holds"
                        ),
                        task=task.ident,
                        section=task.section,
                        line=task.line,
                        evidence=(
                            f"{task.ident} names {named}, which {creator} creates; "
                            f"{task.ident} declares no path to {creator}, and "
                            f"{creator} already depends on {task.ident}, so the "
                            "missing edge would close a cycle"
                        ),
                        severity=ERROR,
                    )
                )
            else:
                findings.append(
                    Finding(
                        rule="implicit-dependency",
                        message=(
                            "a task uses an artifact another task creates and declares "
                            "no path to it. A candidate for a human to adjudicate: the "
                            "edge is real, or the mention is a reference"
                        ),
                        task=task.ident,
                        section=task.section,
                        line=task.line,
                        evidence=(
                            f"{task.ident} names {named}, which {creator} creates; "
                            f"{task.ident} declares no path to {creator}"
                        ),
                        severity=WARNING,
                    )
                )

    return guard_no_input(
        "implicit", findings, len(tracked), "tracked artifacts",
        "implicit-dependency lint",
    )
