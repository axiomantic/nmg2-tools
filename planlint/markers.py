"""Lint 12 — the union half of section 24.6's citation form.

Section 24.6 states what a `DONE` marker means: the commits its citation NAMES
touched every path the task's `Files:` line declares that this machine could
resolve, and the citation names which commit covered which path. The second
half of that sentence was amended on 2026-08-19, because the first form of it
was satisfiable by a citation that named almost none of the work it rested on.
A marker stating a commit COUNT while quoting only the NEWEST sha passed it: the
newest sha is typically a small later fix, the commit that created most of the
declared paths goes unnamed, and a reader who checks the one sha finds most of
the `Files:` line uncovered and cannot tell a citation that is SHORT from one
that is FALSE.

Markers stood in that state for as long as they did precisely because no rule
read them: to every gate this project runs, a short citation and a whole one
produced the same output. That is the defect this module ends.

Two rules, and they are not one rule:

  * `done-marker-path-uncited` — a declared path that no cited entry names.
    This is the union rule of the citation form, read in the direction the form
    states.
  * `done-marker-citation-not-in-form` — a marker that carries no entry at all,
    so which commit covers which declared path is UNDECIDED. It is REPORTED and
    not passed. A marker predating the form assigns no path to any commit, and
    a rule that fell silent on it would report clean over the markers that
    carry the most risk.

WHAT THIS LINT DOES NOT DECIDE. Whether a named sha really touched the path it
claims is a question about a repository and not about this document; the
`citations` lint asks it. And the citation form itself does not establish that
the task's `Check:` passes — section 24.6 says so in its own words, and no pass
that wrote one of these citations ran a `Check:` command.
"""

from planlint.document import canonical_path, has_marker, strip_marker
from planlint.finding import ERROR, WARNING, Finding, guard_no_input


def is_comparable_path(item):
    """Whether a `Files:` entry names ONE file a commit could touch.

    Three shapes are outside the compare, and each is a limit rather than a
    lapse:

      * a GLOB names a SET of files. No entry names it literally, so a literal
        set comparison has no operand at all. `conformance/corpus/move_*.json`
        is the plan's own case.
      * a name with no directory separator and no suffix names a REPOSITORY and
        not a file. REPO-14 declares `nmg2-tools` and DSP-0 declares
        `dsp56300`, and a commit cannot touch either.
      * a build target, which the caller removes by reading `files_paths`.

    Section 24.6 asks for such an entry to be named in a trailing `NOT PATHS:`
    clause. That clause is PROSE — CPU-5's reads "the five
    `mcf5307_conformance_*` entries on the `Files:` line are BUILD TARGETS" —
    and a rule that tried to parse it would decide admissibility from a sentence
    rather than from the entry. This predicate reads the ENTRY instead, so it
    states the same exclusion out of the operand itself.
    """
    if "*" in item:
        return False
    base = item.rsplit("/", 1)[-1]
    return "/" in item or "." in base


def comparable_paths(task):
    """The declared paths of a task, in the spelling the compare uses.

    Section 1.1.1 rules B and C are already expanded by `files_paths`. Rule D's
    `@<OWNER-ID>` marker is stripped HERE: a marked entry is not a claim of
    ownership, but the write it declares still happened, so the path belongs in
    the compare with the marker off. Leaving it on would compare two spellings
    of one file and report every second write in the plan.
    """
    out = []
    for item in task.files_paths:
        path = strip_marker(item) if has_marker(item) else item
        if is_comparable_path(path) and path not in out:
            out.append(path)
    return out


def cited_paths(marker):
    """Every path the marker's entries name, canonically spelled."""
    return {
        canonical_path(path) for entry in marker.entries for path in entry.paths
    }


def _entry_list(marker):
    return "; ".join(
        f"`{entry.repository}` `{entry.sha}`" for entry in marker.entries
    )


def run(doc):
    findings = []

    for marker in doc.done_markers:
        task = doc.task(marker.task)
        if task is None:
            continue
        declared = comparable_paths(task)
        if not declared:
            continue
        section = task.section

        if not marker.entries:
            findings.append(
                Finding(
                    rule="done-marker-citation-not-in-form",
                    message=(
                        "a completion marker states no per-path citation, so "
                        "which commit covers which declared path is UNDECIDED. "
                        "This is reported rather than passed, because a silence "
                        "here reads exactly like coverage. Section 24.6's form "
                        "is `<owner>/<repo>`, then the commit sha, then `→`, "
                        "then the declared paths that commit touched, with "
                        "entries separated by `;`"
                    ),
                    task=marker.task,
                    section=section,
                    line=marker.line,
                    evidence=(
                        f"the marker carries no `→` entry, so the coverage of "
                        f"{len(declared)} declared path"
                        f"{'' if len(declared) == 1 else 's'} is undecided: "
                        + ", ".join(f"`{path}`" for path in declared)
                    ),
                    severity=WARNING,
                )
            )
            continue

        cited = cited_paths(marker)
        count = len(marker.entries)
        for path in declared:
            if path in cited:
                continue
            findings.append(
                Finding(
                    rule="done-marker-path-uncited",
                    message=(
                        "a completion marker's citation names no commit for a "
                        "path the task's `Files:` line declares. The marker's "
                        "whole claim is that the commits it names touched every "
                        "declared path, so a path no entry names leaves a "
                        "reader unable to tell a citation that is SHORT from "
                        "one that is FALSE"
                    ),
                    task=marker.task,
                    section=section,
                    line=marker.line,
                    evidence=(
                        f"`{path}` is declared by the `Files:` line of "
                        f"{marker.task} and named by none of the {count} cited "
                        f"entr{'y' if count == 1 else 'ies'}: "
                        f"{_entry_list(marker)}"
                    ),
                    severity=ERROR,
                )
            )

    return guard_no_input(
        "markers", findings, len(doc.tasks), "task bodies", "marker lint"
    )
