"""Lint 1 — the dependency graph.

Section 7.6 assertions 2 and 3: every identifier a `Depends:` line names is a
task this plan defines, and the graph carries no strongly connected component of
size above one and no self-loop.

The `Depends:` parser is the part that matters most. A `Depends:` line holds
identifiers, ranges and annotations, and a parser that harvests every identifier
from the line makes an edge out of a scheduling note. That produced a false
cycle once already, so an identifier that sits in prose is reported as prose and
never becomes an edge.
"""

import dataclasses
import re

from planlint.document import RANGE, strip_markup
from planlint.finding import ERROR, Finding, guard_no_input

IDENT_ONLY = re.compile(r"^[A-Z]{2,6}-\d+$")
IDENT_LEAD = re.compile(r"^([A-Z]{2,6}-\d+)\s+(.+)$")
IDENT_ANY = re.compile(r"\b[A-Z]{2,6}-\d+\b")

# A sentence that opens with one of these is a marker the plan defines in
# section 1.4, or a wave note. It states a condition on the task and never an
# edge, so the identifier inside it is not a false edge.
MARKERS = ("PENDING", "CONDITIONAL", "WAVE", "OPERATOR", "THROWAWAY", "BLOCKED-ON-DESIGN")


def _sentences(text):
    parts = re.split(r"(?<=\.)\s+", text.strip())
    return [p for p in parts if p.strip()]


def parse_depends(text):
    """Split a `Depends:` value into declared edges and prose findings.

    Returns `(edges, findings)`. The findings carry no task or line; the caller
    that knows the task fills those in.
    """
    plain = strip_markup(text)
    if not plain or plain.lower().rstrip(".") in ("none", "nothing"):
        return [], []

    sentences = _sentences(plain)
    edges = []
    findings = []
    seen = set()

    def add(ident):
        if ident not in seen:
            seen.add(ident)
            edges.append(ident)

    for item in sentences[0].split(","):
        item = item.strip().rstrip(".").strip()
        if not item:
            continue
        match = RANGE.match(item)
        if match:
            low_track, low, high_track, high = match.groups()
            if low_track == high_track:
                for number in range(int(low), int(high) + 1):
                    add(f"{low_track}-{number}")
                continue
        if IDENT_ONLY.match(item):
            add(item)
            continue
        lead = IDENT_LEAD.match(item)
        if lead and not IDENT_ANY.search(lead.group(2)):
            # `REPO-15 for the T1 half only` — an edge with a qualifier.
            add(lead.group(1))
            continue
        for extra in IDENT_ANY.findall(item):
            findings.append(
                Finding(
                    rule="depends-prose",
                    message=(
                        "an identifier sits in prose on the `Depends:` line, so it is "
                        "not read as an edge; state it as an item or move the note off "
                        "the line"
                    ),
                    evidence=f"{item} → {extra}",
                    severity=ERROR,
                )
            )

    for sentence in sentences[1:]:
        stripped = sentence.strip()
        if stripped.upper().startswith(MARKERS):
            continue
        for extra in IDENT_ANY.findall(stripped):
            findings.append(
                Finding(
                    rule="depends-prose",
                    message=(
                        "an annotation on the `Depends:` line names a task; it is not "
                        "read as an edge, and a parser that read it would invent one"
                    ),
                    evidence=f"{stripped} → {extra}",
                    severity=ERROR,
                )
            )

    return edges, findings


def depends_ranges(text):
    """`{ident: range_text}` for every edge a `Depends:` RANGE produced.

    Section 1.3 rule 8 governs ranges only: a range is a convenience, not a
    licence, and it must not swallow a higher tier or a conditional task.
    """
    plain = strip_markup(text)
    sentences = _sentences(plain)
    if not sentences:
        return {}
    out = {}
    for item in sentences[0].split(","):
        item = item.strip().rstrip(".").strip()
        match = RANGE.match(item)
        if not match:
            continue
        low_track, low, high_track, high = match.groups()
        if low_track != high_track:
            continue
        for number in range(int(low), int(high) + 1):
            out[f"{low_track}-{number}"] = item
    return out


def build_edges(doc):
    """`{ident: [dependency, ...]}` plus the findings the parse produced.

    The parse findings are FILLED IN, not rebuilt. `dataclasses.replace` copies
    the rule instead of naming it a second time, so the rule inventory a reader
    or a test reads out of this module's source is the whole inventory: every
    `Finding(rule=...)` here carries a literal.
    """
    edges = {}
    findings = []
    for task in doc.tasks:
        declared, prose = parse_depends(task.depends_text)
        edges[task.ident] = declared
        for f in prose:
            findings.append(
                dataclasses.replace(
                    f, task=task.ident, section=task.section, line=task.line
                )
            )
    return edges, findings


def tarjan(edges):
    """Every strongly connected component, in discovery order."""
    index = {}
    low = {}
    stack = []
    on_stack = set()
    components = []
    counter = [0]

    def strong_connect(node):
        work = [(node, iter(edges.get(node, ())))]
        index[node] = low[node] = counter[0]
        counter[0] += 1
        stack.append(node)
        on_stack.add(node)
        while work:
            current, children = work[-1]
            advanced = False
            for child in children:
                if child not in edges:
                    continue
                if child not in index:
                    index[child] = low[child] = counter[0]
                    counter[0] += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, iter(edges.get(child, ()))))
                    advanced = True
                    break
                if child in on_stack:
                    low[current] = min(low[current], index[child])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[current])
            if low[current] == index[current]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == current:
                        break
                components.append(sorted(component))

    for node in edges:
        if node not in index:
            strong_connect(node)
    return components


def run(doc):
    edges, findings = build_edges(doc)

    for task in doc.tasks:
        for dependency in edges[task.ident]:
            if dependency == task.ident:
                findings.append(
                    Finding(
                        rule="self-loop",
                        message="a task names itself on its `Depends:` line",
                        task=task.ident,
                        section=task.section,
                        line=task.line,
                        evidence=f"Depends: {strip_markup(task.depends_text)}",
                    )
                )
            elif not doc.has_task(dependency):
                findings.append(
                    Finding(
                        rule="unknown-dependency",
                        message=(
                            "a `Depends:` line names an identifier this plan defines "
                            "in no task block"
                        ),
                        task=task.ident,
                        section=task.section,
                        line=task.line,
                        evidence=f"Depends: {strip_markup(task.depends_text)} → {dependency}",
                    )
                )

    for component in tarjan(edges):
        if len(component) < 2:
            continue
        head = doc.task(component[0])
        findings.append(
            Finding(
                rule="dependency-cycle",
                message=(
                    "a strongly connected component of size above one: these tasks "
                    "wait on each other and none of them can start"
                ),
                task=component[0],
                section=head.section if head else "",
                line=head.line if head else 0,
                evidence="strongly connected component: " + ", ".join(component),
            )
        )

    return guard_no_input(
        "graph", findings, len(doc.tasks), "task blocks", "graph lint"
    )
