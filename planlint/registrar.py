"""Lint 8 — registrar reachability.

A `Check:` line that runs `ctest -R <name>` can only pass when two other things
already exist: the source that carries the test, and the CMake registration that
puts the name in the build's test list. Both belong to some task. When either
task sits OUTSIDE the depending task's transitive dependency closure, the check
cannot pass on the day the task is declared complete.

That is the mirror of a check that cannot fail, and it is just as expensive: the
engineer meets a failure that says nothing about the work, and learns to
disbelieve the check.

The registrar of a test source is read from the plan, not from a table of
special cases: it is the task whose `Files:` line creates the `CMakeLists.txt`
of the directory that holds the source. That rule holds for `tests/` in
`mcf5307`, for `g2Lib/test/` in the `gearmulator` fork and for
`dsp56kEmu/test/` in the `dsp56300` fork, so the lint moves between repositories
without editing.
"""

from planlint import checks, graph
from planlint.document import has_marker
from planlint.finding import ERROR, Finding, guard_no_input


def closure(doc, ident, _edges=None):
    """The task and every task it transitively waits on."""
    edges = _edges if _edges is not None else graph.build_edges(doc)[0]
    seen = set()
    stack = [ident]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        for dependency in edges.get(current, ()):
            if dependency not in seen and doc.has_task(dependency):
                stack.append(dependency)
    return seen


def creators_of(doc, name):
    """Every `(task, item)` whose `Files:` entry creates a name, in document order.

    A LIST and not a first match. A first-match read ignores the directory, so
    with two same-named test files in two directories the second is invisible
    and the verdict depends on file position. The lint cannot tell which source
    the name resolves to, so every candidate must be reachable and none of them
    may be excused.

    An EMPTY name matches nothing. A `Files:` entry naming a directory has an
    empty basename, and matching it would resolve `-R ^$` to a task that creates
    no test at all.

    A MARKED entry creates nothing. Section 1.1.1 rule D says a marked entry is
    not a claim of ownership: `<path>@<OWNER-ID>` names the file's owner and
    declares that THIS task only changes it. The marker sits after the suffix,
    so `t0_beta.cpp@BBB-1` still splits to the stem `t0_beta` and the second
    writer was read as the creator — which reported the OWNER for not reaching
    its own second writer, on the one form section 7.6 assertion 8 requires.

    SKIP and not STRIP, for the reason `checks._shared_paths` skips: the owner
    declares the file on a line of its own, so skipping loses no creator, while
    stripping would put the second writer back into the answer under a
    different spelling. Where NO unmarked entry names the file, the lookup is
    empty and `registrar-unknown` reports it — loudly, and as the defect it is.

    An UNMARKED second write is untouched. It is a bare claim of ownership over
    a file another task also claims, and it stays a creation that has to be
    reachable.
    """
    if not name:
        return []
    out = []
    for task in doc.tasks:
        for item in task.files_items:
            if has_marker(item):
                continue
            base = item.rsplit("/", 1)[-1]
            if not base:
                continue
            stem = base.rsplit(".", 1)[0] if "." in base else base
            if stem == name or base == name:
                out.append((task, item))
    return out


def registrars_of(doc, item):
    """The tasks that CREATE the `CMakeLists.txt` governing an item.

    An item with no directory is a build target its own task declares, so that
    task is its registrar.

    **A creator, and not every later writer.** Section 7.4.2 draws that line
    itself: it names an OWNER for each registration list and calls every other
    writer a DECLARED SECOND WRITER — "a registrar CREATES the list and
    registers nothing; a registering task CHANGES the list and registers
    exactly its own names".

    The same section's registration rule then OBLIGES every registering task to
    name the list on its own `Files:` line, because a registration is a change
    and section 1.1 defines `Files:` as what a task creates **or changes**.
    Reading each declarer as a creator therefore made the compliant form the
    form this lint rejects, and made every writer of a list a registrar that
    every other writer had to reach. That is why the dsp tasks never carried the
    declaration the rule asks of them: the document was right and the tool was
    wrong.

    **The rule is not weakened, only aimed.** The owner must still sit inside
    the depending task's closure, and a task that reaches no owner is still an
    ERROR. Where section 7.4.2 states no owner the lint cannot tell a creator
    from a writer, so it keeps the conservative reading and answers every
    declarer — and `shared-path-without-owner` is the ERROR that a shared list
    carries no owner row, so the narrow reading never hides a missing one.
    """
    if "/" not in item:
        return []
    directory = item.rsplit("/", 1)[0]
    wanted = f"{directory}/CMakeLists.txt"
    owner = doc.owner_of(wanted)
    if owner is not None:
        return [(owner, wanted)]
    return [(task, wanted) for task in doc.tasks if wanted in task.files_items]


def run(doc):
    findings = []
    edges, _ = graph.build_edges(doc)
    examined = 0

    for task in doc.tasks:
        if not task.check_text:
            continue
        names = []
        for command in checks.commands_in(task.check_text):
            for name in checks.r_arguments(command):
                if name not in checks.PREFIX_ALLOW_LIST and name not in names:
                    names.append(name)
        if not names:
            continue
        reachable = closure(doc, task.ident, edges)

        for name in names:
            examined += 1
            found = creators_of(doc, name)
            if not found:
                findings.append(
                    Finding(
                        rule="registrar-unknown",
                        message=(
                            "no task creates a source or a target for the name this "
                            "check runs, so no registrar can be identified at all"
                        ),
                        task=task.ident,
                        section=task.section,
                        line=task.check_line,
                        evidence=(
                            f"-R {name}; no `Files:` line creates a source or a "
                            "target for that name"
                        ),
                        severity=ERROR,
                    )
                )
                continue

            reported = set()
            for creator, item in found:
                if creator.ident not in reachable:
                    findings.append(
                        Finding(
                            rule="creator-outside-closure",
                            message=(
                                "the task that creates the test source is not in this "
                                "task's dependency closure, so the source does not "
                                "exist when this check runs"
                            ),
                            task=task.ident,
                            section=task.section,
                            line=task.check_line,
                            evidence=(
                                f"-R {name} needs {creator.ident}, which creates "
                                f"`{item}`; {creator.ident} is not in {task.ident}'s "
                                "dependency closure"
                            ),
                            severity=ERROR,
                        )
                    )

                for owner, cmake in registrars_of(doc, item):
                    if owner.ident in reachable or (owner.ident, cmake) in reported:
                        continue
                    reported.add((owner.ident, cmake))
                    findings.append(
                        Finding(
                            rule="registrar-outside-closure",
                            message=(
                                "the task that registers this directory's tests is not "
                                "in this task's dependency closure, so nothing puts the "
                                "name in the build's test list and the check cannot pass"
                            ),
                            task=task.ident,
                            section=task.section,
                            line=task.check_line,
                            evidence=(
                                f"-R {name} needs {owner.ident}, which creates "
                                f"`{cmake}`; {owner.ident} is not in {task.ident}'s "
                                "dependency closure"
                            ),
                            severity=ERROR,
                        )
                    )

    return guard_no_input(
        "registrar", findings, examined, "`-R` arguments", "registrar lint"
    )
