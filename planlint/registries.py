"""Lint 20 — a check target held against the repositories' real test registries.

The question this lint answers is the one a roster cannot: **does every
`Check:` target the plan names exist as something that can actually run?**

`docs/…impl.check-targets.txt` is generated from the plan by the same public
`planlint` API `checks._check_targets` reads it with, so set equality between
the two can now fail for exactly one reason — somebody skipped the generator.
That is a useful staleness alarm and it is not a check of the plan: both sides
of the comparison come from one document, and a `Check:` line naming a test
nothing registers satisfies it perfectly.

Three defects sat green under that comparison and are the reason this module
exists. Two are prose placeholders the extractor scoops out of a `Check:`
line — `pytest <path>` and `pytest tests/…` — which nothing can ever run and
which the roster comparison DEMANDS be present. The third is `abi_smoke`: the
plan's CPU-3 and its milestone M1 row both run `ctest -R ^abi_smoke$`, the task
is marked complete, and `mcf5307` registers the executable under the name
`t0_abi_smoke`. The `-R` pattern matches nothing.

REPOSITORY ATTRIBUTION, AND WHY THIS LINT NEEDS NONE
----------------------------------------------------

The plan does carry an attribution: section 7.1's track table binds each
task-identifier prefix to a repository, and `PlanDocument.track_repositories`
already parses it. It is not usable as a search key. The cells are PROSE —
`gearmulator fork`, `all seven`, `none — a scratch directory` — so turning a
prefix into the repository root a search would open needs a hand-maintained
translation table beside it, which is the roster defect one level down; and
three of the sixteen prefixes name no single repository even in prose.

So this lint takes the other route and searches EVERY repository it is given,
reporting a target found in NONE of them. That is strictly the right shape for
the question. "Is this target runnable anywhere?" needs no attribution to
answer and cannot mislabel: a name registered in any searched tree is
runnable, and a name registered in none is not. Attribution would only be
needed for a different question — "is it registered in the RIGHT repository?"
— which the plan cannot answer today.

This is also what separates the lint from `rule9`'s half B, which asks the
attributed question. `rule9.RepositoryIndex.owner_of` resolves a target to the
repository holding the source its task names, and when no tree holds that
source and no repository declares the name it returns `None` and half B
SKIPS — reading "registered nowhere" as "not built yet". That skip is the hole
this module closes: `abi_smoke` falls into it, because `mcf5307` holds
`tests/abi_smoke.cpp` under a registration with a different name.

WHAT "REGISTERED" MEANS HERE, AND WHERE IT IS WEAK
--------------------------------------------------

A name is registered when an `add_test(NAME <name> ...)` in a CMake SOURCE
file names it, read statically, plus the wrapper form `rule9` resolves. It is
never "listed by `ctest`": nothing here configures or builds. A registration
produced by a generated CMake file, or by a macro this resolver does not
unfold, reads as UNREGISTERED. Every finding says so, because a reader who
takes "registered nowhere" for "cannot possibly exist" will delete a working
test.

FAILING LOUDLY
--------------

A repository this lint cannot read must never read as clean, and "registered
in none of the trees I searched" must never be spelled the same as "I did not
search". Three mechanisms, and each covers a different failure:

  * No `--source-repo` at all — `cli.LINT_REQUIREMENTS` skips the lint and the
    report prints "the lint did not run and its result is unknown". The lint
    is never silently absent.
  * A root that is not a directory, or a CMake file that exists and cannot be
    read — `registry-unreadable`, ERROR. And the search is then INCOMPLETE, so
    every target that would have been reported as registered nowhere is
    reported under `registry-target-unresolved` instead, saying the answer is
    not known rather than that the answer is no.
  * Every searched repository contributing zero registrations —
    `registry-empty`, ERROR. A registry that holds nothing would make every
    target in the plan look unregistered, which is a broken search reported as
    a catastrophe.

A repository that legitimately registers nothing — `nmg2-tools` has no CMake
at all — is not a finding. It is named in the notice, which reports the
per-repository count so that a tree silently dropped from the search is
visible on a CLEAN run and not only on a dirty one.

SEVERITY
--------

A target whose owning task carries an anchored `**DONE` marker is an ERROR:
the work shipped and its check cannot fail. A target no complete task owns is
a WARNING — most of this plan is unbuilt, and a lint that is red on day one is
a lint an engineer turns off. A placeholder is an ERROR whatever its owner's
state, because no amount of later work makes `pytest <path>` runnable.
"""

import pathlib
import re

from planlint import checks
from planlint.finding import ERROR, WARNING, Finding, guard_no_input
from planlint.rule9 import CMAKE_NAMES, CMAKE_SUFFIX, WRAPPER

# A target the extractor lifted out of prose rather than out of a command. The
# angle brackets are the `<path>` metavariable convention and the ellipses are
# the plan's elision, in both its one-character and three-character spellings.
PLACEHOLDER = re.compile(r"[<>…]|\.\.\.")

PYTEST_PREFIX = "pytest "

# A directory whose contents are OUTPUT. A build tree carries generated
# `CTestTestfile.cmake` files, so reading one would make this lint's answer
# depend on whether somebody had configured that repository — a different
# result on a clean checkout than on a developer's machine, for the same plan
# and the same sources. It also races the sessions that write those trees.
BUILD_DIRECTORY = re.compile(r"^(?:build|cmake-build|out)(?:[-_.].*)?$|^\.git$")

# The sentence every finding carries about what was actually read. It is one
# constant because a reader who sees it on one rule and not another will read
# the silent rule as stronger evidence than it is.
STATIC_READ = (
    "`registered` here means named by an `add_test(NAME ...)` in a CMake "
    "source file, read statically; it is never a `ctest` listing, so a "
    "generated or macro-expanded registration reads as unregistered"
)


class Registry:
    """Every test name a set of repository trees registers, and what failed.

    `unreadable` is not an error return. It is carried beside the answer,
    because the caller must be able to tell a name that is absent from a
    complete search from a name that is absent from an incomplete one.
    """

    def __init__(self, roots):
        self.roots = {label: pathlib.Path(root) for label, root in roots.items()}
        self.names = {}
        self.sources = {}
        self.unreadable = []
        for label, root in self.roots.items():
            if not root.is_dir():
                self.unreadable.append((label, str(root), "not a directory"))
                self.names[label] = set()
                self.sources[label] = 0
                continue
            names, count, failures = self._read(root)
            self.names[label] = names
            self.sources[label] = count
            self.unreadable.extend(
                (label, path, reason) for path, reason in failures
            )

    @staticmethod
    def _read(root):
        names = set()
        texts = []
        wrappers = set()
        failures = []
        count = 0
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.name not in CMAKE_NAMES and path.suffix != CMAKE_SUFFIX:
                continue
            if any(
                BUILD_DIRECTORY.match(part)
                for part in path.relative_to(root).parts[:-1]
            ):
                continue
            count += 1
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as error:
                failures.append((str(path), str(error)))
                continue
            texts.append(text)
            names.update(checks.ADD_TEST.findall(text))
            for wrapper, parameter, body in WRAPPER.findall(text):
                if re.search(
                    r"add_test\s*\(\s*NAME\s+\$\{" + re.escape(parameter) + r"\}",
                    body,
                ):
                    wrappers.add(wrapper)
        for wrapper in wrappers:
            call = re.compile(
                r"^[ \t]*" + re.escape(wrapper) + r"\s*\(\s*([A-Za-z0-9_.\-]+)",
                re.MULTILINE,
            )
            for text in texts:
                names.update(call.findall(text))
        return names, count, failures

    @property
    def complete(self):
        """Whether every tree the caller named was read to the end."""
        return not self.unreadable

    @property
    def all_names(self):
        out = set()
        for names in self.names.values():
            out |= names
        return out

    def holds(self, relative):
        """Whether any searched tree holds a path, and which one."""
        for label, root in self.roots.items():
            if (root / relative).exists():
                return label
        return None

    def registers(self, name):
        for label, names in self.names.items():
            if name in names:
                return label
        return None

    def notice(self):
        parts = [
            f"{label}: {self.sources[label]} CMake registration source(s), "
            f"{len(self.names[label])} registered name(s)"
            for label in sorted(self.roots)
        ]
        state = "complete" if self.complete else "INCOMPLETE"
        return f"searched ({state}) — " + "; ".join(parts) + f". {STATIC_READ}."


def owners_of(origins):
    """The task identifiers whose `Check:` block names a target."""
    return sorted(
        origin.partition(":")[2] for origin in origins if origin.startswith("check:")
    )


def complete_tasks(doc):
    """Every task carrying an ANCHORED `**DONE` marker.

    Anchored, because `planlint.document` already draws that line: a `**DONE`
    inside a sentence is prose about completion and a marker that opens its own
    line is the claim.
    """
    return {marker.task for marker in doc.done_markers if marker.anchored}


def run(doc, source_repos=None):
    if not source_repos:
        # Reached only by a direct caller; `cli` skips the lint through
        # `LINT_REQUIREMENTS` and prints that its result is unknown.
        return guard_no_input(
            "registries",
            [
                Finding(
                    rule="registry-not-searched",
                    message=(
                        "no repository tree was given, so no target's "
                        "registration was decided. This is not a clean run"
                    ),
                    severity=ERROR,
                )
            ],
            0,
            "check targets",
            "registry lint",
        )

    registry = Registry(source_repos)
    findings = [
        Finding(
            rule="registry-unreadable",
            message=(
                "a registration source could not be read, so the search is "
                "INCOMPLETE and no absence below is decided"
            ),
            evidence=f"{label}: {path} ({reason})",
            severity=ERROR,
        )
        for label, path, reason in registry.unreadable
    ]

    if registry.complete and not registry.all_names:
        findings.append(
            Finding(
                rule="registry-empty",
                message=(
                    "every searched repository registered zero test names. A "
                    "search that finds no registrations at all reports every "
                    "target as unregistered; the search is broken, not the plan"
                ),
                evidence=registry.notice(),
                severity=ERROR,
            )
        )

    origins = checks.target_origins(doc)
    done = complete_tasks(doc)
    examined = 0

    for target in sorted(origins):
        examined += 1
        owners = owners_of(origins[target])
        shipped = any(owner in done for owner in owners)
        where = ", ".join(origins[target])
        owned = ", ".join(owners) if owners else "no task's Check: block"

        if PLACEHOLDER.search(target):
            findings.append(
                Finding(
                    rule="registry-target-is-placeholder",
                    message=(
                        "this `Check:` target is prose, not a target name. "
                        "Nothing can ever run it, and no repository can ever "
                        "register it, so the check it appears in cannot fail"
                    ),
                    task=owners[0] if owners else "",
                    evidence=f"target {target!r}; named by {owned}; origins: {where}",
                    severity=ERROR,
                )
            )
            continue

        if target.startswith(PYTEST_PREFIX):
            relative = target[len(PYTEST_PREFIX):].strip().split("::")[0]
            if registry.holds(relative):
                continue
            rule, message = _absence(
                registry,
                "registry-pytest-path-missing",
                (
                    "this `pytest` target names a path that exists in none of "
                    "the searched repositories, so the invocation collects "
                    "nothing"
                ),
            )
            findings.append(
                Finding(
                    rule=rule,
                    message=message,
                    task=owners[0] if owners else "",
                    evidence=(
                        f"target {target!r}; path {relative!r} found in none of "
                        f"{', '.join(sorted(registry.roots))}; named by {owned}"
                    ),
                    severity=ERROR if shipped else WARNING,
                )
            )
            continue

        if registry.registers(target):
            continue
        rule, message = _absence(
            registry,
            "registry-target-unregistered",
            (
                "no `add_test(NAME ...)` in any searched repository registers "
                f"this name, so `ctest -R` matches nothing. {STATIC_READ}"
            ),
        )
        findings.append(
            Finding(
                rule=rule,
                message=message,
                task=owners[0] if owners else "",
                evidence=(
                    f"target {target!r}; registered by none of "
                    f"{', '.join(sorted(registry.roots))}; named by {owned}; "
                    f"owning task complete: {'yes' if shipped else 'no'}"
                ),
                severity=ERROR if shipped else WARNING,
            )
        )

    return guard_no_input(
        "registries",
        findings,
        examined,
        "check targets",
        "registry lint",
        notice=registry.notice(),
    )


def _absence(registry, rule, message):
    """Name an absence for what it is: a decided no, or an unfinished search.

    One message for both hands the reader the wrong repair — "add the missing
    registration" when the real repair is "make the tree readable and run it
    again".
    """
    if registry.complete:
        return rule, message
    return (
        "registry-target-unresolved",
        (
            "the search was INCOMPLETE — see `registry-unreadable` — so this "
            "target's absence is NOT decided. It is unresolved, not "
            "unregistered, and the repair is to make the tree readable"
        ),
    )
