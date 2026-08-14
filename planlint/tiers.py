"""Lint 3 — tier purity.

Section 7.6 assertion 1: every task block carries a tier on its header line.
Section 7.6 assertion 6: every T0 check runs with `NMG2_ARTIFACTS` unset, and a
T0 task that waits on a T1 or T2 task is a defect unless it is one of the
production or trigger edges section 5.2 rule 7 names.
Section 1.3 rule 8: a `Depends:` RANGE must not hold a task of a higher tier
than the depending task, and must not hold a conditional task.

A T0 task must be firmware-free. This lint reads the section 7.8 register for
the paths that carry Clavia content rather than carrying a list of its own,
because a second list is a list that goes stale.
"""

import re

from planlint import graph
from planlint.finding import ERROR, Finding, guard_no_input

TIER_ORDER = {"T0": 0, "T1": 1, "T2": 2}

# A task that states a disposition rather than a test tier. Section 1.4 names
# the marks; the spike, operator, deferred and upstream tasks run no test tier.
DISPOSITIONS = ("OPERATOR", "THROWAWAY", "DEFERRED", "UPSTREAM", "NO TIER")

# Section 5.2 rule 7 names the whole permitted set of T0-to-T1 edges. Any edge
# outside that set is a defect and this lint names it.
T0_TO_T1_EXEMPT = frozenset({"ORC-1", "PERF-6", "PERF-7"})

GATED = re.compile(r"NMG2_ARTIFACTS`?\s+(?:is\s+)?set\b", re.IGNORECASE)
REACHED_THROUGH = re.compile(r"reached through\s+`?NMG2_ARTIFACTS", re.IGNORECASE)


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


def run(doc):
    findings = []
    edges, _ = graph.build_edges(doc)
    private_paths = [row for row in doc.fixture_register if not row.public]

    for task in doc.tasks:
        upper = task.tier_text.upper()
        if not task.tiers and not any(word in upper for word in DISPOSITIONS):
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
            phrase = _sentence_holding(task.check_text, GATED) or _sentence_holding(
                task.check_text, REACHED_THROUGH
            )
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

            for row in private_paths:
                if row.named_by == task.ident:
                    continue
                if row.path and row.path in task.check_text + " " + task.files_text:
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

        here = max_tier(task)
        ranges = graph.depends_ranges(task.depends_text)
        for dependency in edges[task.ident]:
            other = doc.task(dependency)
            there = max_tier(other)
            if there is None or here is None:
                continue
            if pure_t0 and there > 0 and task.ident not in T0_TO_T1_EXEMPT:
                findings.append(
                    Finding(
                        rule="t0-depends-t1",
                        message=(
                            "a T0 task waits on a gated task, so its required check "
                            "cannot run in a public repository; section 5.2 rule 7 "
                            "names the whole permitted set and this edge is not in it"
                        ),
                        task=task.ident,
                        section=task.section,
                        line=task.line,
                        evidence=(
                            f"{task.ident} is {task.tier_text}; it depends on "
                            f"{dependency}, which is {other.tier_text}"
                        ),
                        severity=ERROR,
                    )
                )
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
