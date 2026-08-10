"""Lint 10 — section 1.3 rule 9, made executable in both of its halves.

Section 1.3 rule 9 reads, verbatim:

    Every name a `Check:` line passes to `ctest -R` must appear in some task's
    `Files:` line, and that task must register the name with
    `add_test(NAME <name> ...)`. A check whose regular expression matches
    nothing is not a weak check; it is a check that cannot fail.

The rule has two clauses and, until this module, neither was decidable on its
own terms. `planlint.checks` asserts clause 1 (`r-name-not-created`) and answers
clause 2 by asking whether the string `add_test(NAME <name>` appears ANYWHERE in
the plan document — a WARNING that says the plan does not STATE a registration,
not that no registration EXISTS. A plan that never states one and a repository
that never carries one are the same colour under that reading.

BRD-21 is what the gap costs. Its `Files:` line names `g2Lib/board.h`,
`.../board.cpp` and `g2Lib/test/t0_board_surface.cpp` and no registration list;
its `Check:` line runs `ctest --test-dir build --no-tests=error -R
^t0_board_surface$`. The task was declared complete, the source was committed,
and `t0_board_surface` was registered nowhere. Rule 10's `--no-tests=error`
makes that exit 8 rather than 0, so the check is loud rather than silent — but
only when somebody runs it, and nothing in the plan's own toolchain did.

So this lint has two halves, and they fail for different reasons.

HALF A — plan-internal, decidable from the plan alone.

  `rule9a-name-not-created`    clause 1: no `Files:` line creates the name.
  `rule9a-no-registration-list`
                               clause 2, made declarable by section 7.4.2's
                               boxed registration RULE: "a task whose `Check:`
                               line passes a name to `ctest -R` declares, on its
                               own `Files:` line, the registration list it edits
                               to register that name". Neither the checking task
                               nor any task that creates the named source names
                               such a list.

  A registration list is recognised by shape and not by a roster, because
  section 7.4.2 states a class: `tests_<track>.cmake` and
  `conformance_<track>.cmake`, and the `CMakeLists.txt` of a `test/`, `tests/`
  or `conformance/` directory. The `@<OWNER-ID>` marker of section 1.1.1 rule D
  is split off before the path is read, exactly as that rule orders.

HALF B — cross-repository, and it is the half that catches BRD-21.

  `rule9b-not-registered`      the name is not registered by any
                               `add_test(NAME <name> ...)` reachable in the
                               repository that owns it, and the task that owns
                               the name is COMPLETE.

  COMPLETE is read from the repository and never from the plan, by two
  independent signals: the test source the plan names is present in the tree, or
  the repository's own `docs/check-targets.txt` declares the name. That file
  states its own rule — "THE FILE DECLARES THE TARGETS OF THE TASKS DECLARED
  COMPLETE, AND NO OTHERS" — so it is a completion signal the repository
  publishes about itself.

  Scoping to complete tasks is not a softening. Most of this plan is unbuilt; a
  half that reported every unwritten test would report 150 findings on day one,
  and a lint that is red before any work is done is a lint an engineer turns
  off. The defect this half exists for is a name whose task SHIPPED and whose
  registration did not.

  A registration is resolved STATICALLY, and a literal `add_test(NAME <name>` is
  not the only form. `source/dsp56kEmu/test/CMakeLists.txt` wraps it:

      function(dsp56k_add_test _name)
          add_test(NAME ${_name} COMMAND ${_name})
      endfunction()
      dsp56k_add_test(dsp56k_peripheral_type)

  Seven dsp names are registered that way. A grep for the literal form reports
  all seven as unregistered, which is a false alarm of exactly the size of the
  real finding — so the wrapper is resolved rather than special-cased.
"""

import pathlib
import re

from planlint import checks
from planlint.document import strip_marker
from planlint.finding import ERROR, Finding, guard_no_input

# Section 7.4.2 names the registration lists as a CLASS: `tests_<track>.cmake`
# inside `g2Lib/test/`, `tests/tests_cpu.cmake` or
# `conformance/conformance_cpu.cmake` in `mcf5307`, and
# `source/dsp56kEmu/test/CMakeLists.txt` in the `dsp56300` fork.
REGISTRATION_LIST_BASENAME = re.compile(r"^(?:tests|conformance)_[A-Za-z0-9_]+\.cmake$")
REGISTRATION_DIRECTORIES = frozenset({"test", "tests", "conformance"})

SOURCE_SUFFIXES = (".cpp", ".c", ".cc", ".nim", ".py")

CMAKE_NAMES = ("CMakeLists.txt",)
CMAKE_SUFFIX = ".cmake"

LITERAL_ADD_TEST = re.compile(r"add_test\s*\(\s*NAME\s+([A-Za-z0-9_.\-]+)")
WRAPPER = re.compile(
    r"^[ \t]*(?:function|macro)\s*\(\s*([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\s*\)"
    r"(.*?)^[ \t]*end(?:function|macro)\s*\(",
    re.DOTALL | re.MULTILINE | re.IGNORECASE,
)


def is_registration_list(item):
    """Whether a `Files:` entry names a file that registers tests."""
    item = strip_marker(item)
    base = item.rsplit("/", 1)[-1]
    if REGISTRATION_LIST_BASENAME.match(base):
        return True
    if base in CMAKE_NAMES:
        parts = item.split("/")
        return len(parts) >= 2 and parts[-2] in REGISTRATION_DIRECTORIES
    return False


def r_names_of(task):
    """Every name a task's `Check:` block passes to `ctest -R`, in order.

    A `-R` outside a `ctest` invocation is not the rule's subject, and the two
    prefix arguments section 7.7 allow-lists are not registered names.
    """
    out = []
    for command in checks.commands_in(task.check_text):
        if not re.search(r"\bctest\b", command):
            continue
        for name in checks.r_arguments(command):
            if name and name not in checks.PREFIX_ALLOW_LIST and name not in out:
                out.append(name)
    return out


def creators_of(doc, name):
    """Every `(task, item)` whose `Files:` entry creates the name."""
    out = []
    for task in doc.tasks:
        for raw in task.files_items:
            item = strip_marker(raw)
            base = item.rsplit("/", 1)[-1]
            if not base:
                continue
            stem = base.rsplit(".", 1)[0] if "." in base else base
            if stem == name or base == name:
                out.append((task, item))
    return out


# ------------------------------------------------------------------- half B


def _cmake_files(root):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name in CMAKE_NAMES or path.suffix == CMAKE_SUFFIX:
            if ".git/" in str(path):
                continue
            yield path


def registered_names(root):
    """Every test name the repository registers, resolved statically.

    Two forms, and the second is not an edge case: literal
    `add_test(NAME <name> ...)`, and a wrapper function or macro whose body
    registers its own first argument.
    """
    root = pathlib.Path(root)
    names = set()
    wrappers = {}
    texts = []
    for path in _cmake_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        texts.append(text)
        names.update(LITERAL_ADD_TEST.findall(text))
        for wrapper_name, parameter, body in WRAPPER.findall(text):
            if re.search(
                r"add_test\s*\(\s*NAME\s+\$\{" + re.escape(parameter) + r"\}", body
            ):
                wrappers[wrapper_name] = True
    for name in wrappers:
        call = re.compile(
            r"^[ \t]*" + re.escape(name) + r"\s*\(\s*([A-Za-z0-9_.\-]+)",
            re.MULTILINE,
        )
        for text in texts:
            names.update(call.findall(text))
    return names


def check_targets(root):
    """The names the repository itself declares as belonging to complete tasks."""
    path = pathlib.Path(root) / "docs" / "check-targets.txt"
    if not path.is_file():
        return set()
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("pytest "):
            continue
        out.add(line)
    return out


class RepositoryIndex:
    """The repositories half B reads, and what each one already carries."""

    def __init__(self, roots):
        self.roots = {label: pathlib.Path(path) for label, path in roots.items()}
        self.registered = {
            label: registered_names(path) for label, path in self.roots.items()
        }
        self.declared = {
            label: check_targets(path) for label, path in self.roots.items()
        }

    def owner_of(self, paths, name):
        """The repository a name belongs to, and the source that decided it.

        The plan's `Files:` path is the evidence, and the repository that holds
        the file is the answer. No table of repository prefixes is kept, because
        a table is a second statement of something the trees already say.
        """
        for path in paths:
            for label, root in self.roots.items():
                if (root / path).exists():
                    return label, path
        for label, declared in self.declared.items():
            if name in declared:
                return label, ""
        return None, ""


def _source_paths(found):
    out = []
    for _, item in found:
        base = item.rsplit("/", 1)[-1]
        if any(base.endswith(suffix) for suffix in SOURCE_SUFFIXES):
            out.append(item)
    return out


def run(doc, source_repos=None):
    findings = []
    examined = 0
    index = RepositoryIndex(source_repos) if source_repos else None

    for task in doc.tasks:
        if not task.check_text:
            continue
        for name in r_names_of(task):
            examined += 1
            found = creators_of(doc, name)

            # ------------------------------------------------- half A, clause 1
            if not found:
                findings.append(
                    Finding(
                        rule="rule9a-name-not-created",
                        message=(
                            "section 1.3 rule 9 clause 1: no task's `Files:` line "
                            "creates this name, so the regular expression matches "
                            "nothing and the check cannot fail"
                        ),
                        task=task.ident,
                        section=task.section,
                        line=task.check_line,
                        evidence=f"-R {name}; no `Files:` line creates it",
                        severity=ERROR,
                    )
                )
            else:
                # --------------------------------------------- half A, clause 2
                candidates = [task] + [creator for creator, _ in found]
                declarers = [
                    candidate
                    for candidate in candidates
                    if any(is_registration_list(item) for item in candidate.files_items)
                ]
                if not declarers:
                    creators = ", ".join(sorted({c.ident for c, _ in found}))
                    findings.append(
                        Finding(
                            rule="rule9a-no-registration-list",
                            message=(
                                "section 1.3 rule 9 clause 2, in the form section "
                                "7.4.2's boxed RULE gives it: a task whose `Check:` "
                                "passes a name to `ctest -R` declares the registration "
                                "list it edits on its own `Files:` line. Neither this "
                                "task nor any task that creates the source names one, "
                                "so no task in the plan says it registers the name"
                            ),
                            task=task.ident,
                            section=task.section,
                            line=task.check_line,
                            evidence=(
                                f"-R {name}; created by {creators}; no `Files:` line "
                                "among them names a `tests_*.cmake`, a "
                                "`conformance_*.cmake` or a test-directory "
                                "`CMakeLists.txt`"
                            ),
                            severity=ERROR,
                        )
                    )

            # ------------------------------------------------------- half B
            if index is None:
                continue
            label, path = index.owner_of(_source_paths(found), name)
            if label is None:
                # Nothing in any tree carries the source and no repository
                # declares the name: the task has not run. Rule 9 binds a
                # registration that must exist by the time the task completes,
                # so an unbuilt task is not a violation of it.
                continue
            if name in index.registered[label]:
                continue
            findings.append(
                Finding(
                    rule="rule9b-not-registered",
                    message=(
                        "section 1.3 rule 9 clause 2, read against the repository: "
                        "the task is complete — its test source is in the tree, or "
                        "the repository's own `docs/check-targets.txt` declares the "
                        "name — and no `add_test(NAME ...)` in that repository "
                        "registers it. `ctest -R` matches nothing, so the check "
                        "cannot fail"
                    ),
                    task=task.ident,
                    section=task.section,
                    line=task.check_line,
                    evidence=(
                        f"-R {name}; repository `{label}` carries "
                        f"`{path or 'the declared check target'}` and registers no "
                        f"`add_test(NAME {name} ...)`"
                    ),
                    severity=ERROR,
                )
            )

    return guard_no_input(
        "rule9", findings, examined, "`ctest -R` names", "rule 9 lint"
    )
