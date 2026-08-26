"""Lint 3 — tier purity.

Section 7.6 assertion 1: every task block carries a tier on its header line.
Section 7.6 assertion 6: every T0 check runs with `NMG2_ARTIFACTS` unset, and a
T0 task holding a higher-tier task in its dependency CLOSURE is a defect unless
the edge satisfies every conjunct of section 5.2 rule 7's admissibility
predicate. This lint DECIDES the predicate. It consults no roster of admitted
identifiers, because a roster is amended once per edge and states nothing about
the edge after it.
Section 1.3 rule 8: a `Depends:` RANGE must not hold a task of a higher tier
than the depending task, and must not hold a conditional task.

A T0 task must be firmware-free. This lint reads the section 7.8 register for
the paths that carry Clavia content rather than carrying a list of its own,
because a second list is a list that goes stale.

WHAT THE PREDICATE HERE DECIDES, AND WHAT IT LEAVES UNDECIDED. Conjunct (a) is
decided in full: the gate sentence and the named paths are both in the check's
own text, and section 7.8's register states each path's visibility. Conjunct (b)
is decided ONLY for the paths a `Check:` line NAMES and that section 7.8's
register carries; the document states nowhere which paths a check reads without
naming, and it states no repository for a path the register omits, so both are
read as UNDECIDED and neither is reported. Conjunct (c) — that the T1 task's
gated half contributes nothing the check reads — is NOT DECIDED AT ALL: nothing
in the document marks, per path, which of a T1 task's outputs its gated half
produces, and a rule that guessed would report a verdict it cannot support. An
edge this lint admits has therefore been shown to satisfy (a), and to satisfy
(b) for every path it names; it has been shown nothing about (c). Only an
execution with `NMG2_ARTIFACTS` unset settles the rest, which is what section
3.1's fourth column buys.
"""

import collections
import re

from planlint import graph, registrar
from planlint.document import backticked, strip_marker
from planlint.finding import ERROR, Finding, guard_no_input

TIER_ORDER = {"T0": 0, "T1": 1, "T2": 2}

GATED = re.compile(r"NMG2_ARTIFACTS`?\s+(?:is\s+)?set\b", re.IGNORECASE)
REACHED_THROUGH = re.compile(r"reached through\s+`?NMG2_ARTIFACTS", re.IGNORECASE)


def dispositions(doc):
    """Every section 1.5 tier substitute, read off the document's own table.

    A header that states a substitute rather than a section 5.1 tier is not an
    untiered header. WHICH WORDS THOSE ARE IS SECTION 1.5's TO SAY: it calls
    itself the one home of the set and states the command that re-derives its
    rows, so a tuple here would be that table copied into Python — a second
    roster, amended by hand, that goes stale in silence. `gate` reads the same
    register for the same reason, and this lint reads section 7.8's register
    for it.

    A document that states no section 1.5 table names no substitutes, so every
    untiered header in it is a missing tier. That is the reading `gate`'s
    `undisposed` gives an absent table: an absent table is silence, and silence
    admits nothing.
    """
    return {row.substitute.upper() for row in doc.substitute_register}


def max_tier(task):
    if not task or not task.tiers:
        return None
    return max(TIER_ORDER[t] for t in task.tiers)


def _sentence_holding(text, pattern):
    for line in text.splitlines():
        for sentence in re.split(r"(?<=\.)\s+", line):
            if pattern.search(sentence):
                return sentence.strip().rstrip(".").strip()
    return ""


def _gate_phrase(task):
    return _sentence_holding(task.check_text, GATED) or _sentence_holding(
        task.check_text, REACHED_THROUGH
    )


def _private_rows_named(private_rows, task, text):
    """Every section 7.8 PRIVATE row whose path a text names.

    One implementation serves the `t0-reads-private-fixture` rule and conjunct
    (a)'s second clause, which are the same question asked at two sites; two
    implementations of one question can disagree, and this one may not.
    """
    return [
        row
        for row in private_rows
        if row.named_by != task.ident and row.path and row.path in text
    ]


def _repository_visibility(doc):
    """Section 3.1's visibility, keyed by the name section 7.8's register uses.

    Section 3.1 names a repository `owner/name` and the register names it bare.
    """
    return {
        name.rsplit("/", 1)[-1]: visibility
        for name, visibility in doc.repositories.items()
    }


def _produced_paths(doc, task):
    """Every path this document attributes to a task.

    Both sources are read. A `Files:` line is the task's own claim, and section
    7.8's `Named by` column carries fixtures no `Files:` line repeats.
    """
    out = {strip_marker(path) for path in task.files_paths}
    out |= {
        row.path
        for row in doc.fixture_register
        if row.named_by == task.ident and row.path
    }
    return sorted(out)


def _names_path(check_items, path):
    """Whether a `Check:` line's backticked items name a path.

    The items are matched rather than the raw text: a short path is a substring
    of ordinary prose, and a match on prose reports a read that does not happen.
    A register row ending in `/` is a directory and covers what sits beneath it.
    """
    return any(
        item == path or (path.endswith("/") and item.startswith(path))
        for item in check_items
    )


def _inadmissible(doc, task, other, private_rows, repositories):
    """Why section 5.2 rule 7 refuses this edge, or an empty list.

    The module docstring states which conjuncts this decides and which it does
    not. An empty list means no conjunct this function CAN decide is broken; it
    does not mean the edge satisfies rule 7.
    """
    reasons = []

    phrase = _gate_phrase(task)
    if phrase:
        reasons.append(
            f"Conjunct (a) fails: the check is conditioned on the artifact — {phrase}."
        )
    for row in _private_rows_named(private_rows, task, task.check_text):
        reasons.append(
            f"Conjunct (a) fails: the check names `{row.path}`, which the section "
            "7.8 register marks PRIVATE."
        )

    rows_by_path = {row.path: row for row in doc.fixture_register if row.path}
    check_items = backticked(task.check_text)
    for path in _produced_paths(doc, other):
        if not _names_path(check_items, path):
            continue
        row = rows_by_path.get(path)
        if row is None:
            # The register states no repository for it, so conjunct (b) is
            # UNDECIDED here. Undecided is reported as nothing rather than as an
            # admission: a rule that answered would answer without evidence.
            continue
        if repositories.get(row.repository) == "PRIVATE":
            reasons.append(
                f"Conjunct (b) fails: the check names `{path}`, which {other.ident} "
                f"produces and the section 7.8 register places in `{row.repository}`, "
                f"a repository section 3.1's table marks PRIVATE."
            )
    return reasons


def _route(doc, edges, start, target):
    """The shortest declared route from one task to another, `start` excluded.

    This narrates an edge; it does not decide one. `registrar.closure` is the
    single authority for membership, so that the set the lint judges and the set
    a reader is shown cannot be computed two ways and drift apart.
    """
    queue = collections.deque([(start, [])])
    seen = {start}
    while queue:
        current, path = queue.popleft()
        for dependency in edges.get(current, ()):
            if dependency in seen or not doc.has_task(dependency):
                continue
            route = path + [dependency]
            if dependency == target:
                return route
            seen.add(dependency)
            queue.append((dependency, route))
    return [target]


def run(doc):
    findings = []
    edges, _ = graph.build_edges(doc)
    private_paths = [row for row in doc.fixture_register if not row.public]
    repositories = _repository_visibility(doc)
    substitutes = dispositions(doc)

    for task in doc.tasks:
        upper = task.tier_text.upper()
        if not task.tiers and not any(word in upper for word in substitutes):
            findings.append(
                Finding(
                    rule="missing-tier",
                    message=(
                        "the header line states no test tier and no disposition, so "
                        "section 5.2 rule 1 says the task is not ready to execute"
                    ),
                    task=task.ident,
                    section=task.section,
                    line=task.line,
                    evidence=task.header_text,
                    severity=ERROR,
                )
            )

        pure_t0 = task.tiers == frozenset({"T0"})

        if pure_t0:
            phrase = _gate_phrase(task)
            if phrase:
                findings.append(
                    Finding(
                        rule="t0-gated-check",
                        message=(
                            "a T0 check is gated on the firmware artifact; T0 is the "
                            "only required tier and it must run with NMG2_ARTIFACTS unset"
                        ),
                        task=task.ident,
                        section=task.section,
                        line=task.check_line,
                        evidence=phrase,
                        severity=ERROR,
                    )
                )

            for row in _private_rows_named(
                private_paths, task, task.check_text + " " + task.files_text
            ):
                findings.append(
                    Finding(
                        rule="t0-reads-private-fixture",
                        message=(
                            "a T0 task reaches a fixture the section 7.8 register "
                            "marks PRIVATE; a required check may hold no Clavia byte"
                        ),
                        task=task.ident,
                        section=task.section,
                        line=task.check_line or task.line,
                        evidence=(
                            f"reads `{row.path}`, which the section 7.8 register "
                            f"marks PRIVATE (named by {row.named_by})"
                        ),
                        severity=ERROR,
                    )
                )

            reachable = registrar.closure(doc, task.ident, edges) - {task.ident}
            for dependency in sorted(reachable):
                other = doc.task(dependency)
                there = max_tier(other)
                if there is None or there == 0:
                    continue
                reasons = _inadmissible(
                    doc, task, other, private_paths, repositories
                )
                if not reasons:
                    continue
                route = _route(doc, edges, task.ident, dependency)
                if len(route) == 1:
                    where = f"it depends on {dependency}, which is {other.tier_text}"
                else:
                    where = (
                        f"it reaches {dependency} through {' → '.join(route[:-1])}, "
                        f"and {dependency} is {other.tier_text}"
                    )
                findings.append(
                    Finding(
                        rule="t0-depends-t1",
                        message=(
                            "a T0 task holds a higher-tier task in its dependency "
                            "closure and the edge fails a conjunct of section 5.2 "
                            "rule 7, so the required check does not return the same "
                            "verdict on a machine that never held the artifact"
                        ),
                        task=task.ident,
                        section=task.section,
                        line=task.line,
                        evidence=(
                            f"{task.ident} is {task.tier_text}; {where}. "
                            + " ".join(reasons)
                        ),
                        severity=ERROR,
                    )
                )

        here = max_tier(task)
        ranges = graph.depends_ranges(task.depends_text)
        for dependency in edges[task.ident]:
            other = doc.task(dependency)
            there = max_tier(other)
            if there is None or here is None:
                continue
            if dependency in ranges and there > here:
                findings.append(
                    Finding(
                        rule="range-holds-higher-tier",
                        message=(
                            "a `Depends:` range swallows a task of a higher tier; "
                            "section 1.3 rule 8 says the range is split instead"
                        ),
                        task=task.ident,
                        section=task.section,
                        line=task.line,
                        evidence=(
                            f"the range `{ranges[dependency]}` holds {dependency}, "
                            f"which is {other.tier_text}; {task.ident} is {task.tier_text}"
                        ),
                        severity=ERROR,
                    )
                )
            if dependency in ranges and dependency in doc.conditional_tasks:
                findings.append(
                    Finding(
                        rule="range-holds-conditional",
                        message=(
                            "a `Depends:` range swallows a conditional task, so the "
                            "depending task waits on work that may never run"
                        ),
                        task=task.ident,
                        section=task.section,
                        line=task.line,
                        evidence=(
                            f"the range `{ranges[dependency]}` holds {dependency}, "
                            "which section 24.4 marks conditional"
                        ),
                        severity=ERROR,
                    )
                )

    return guard_no_input("tiers", findings, len(doc.tasks), "task blocks", "tier lint")
