"""Lint 4 — check vacuity.

`ctest --test-dir build -R <name>` exits 0 when the pattern matches no test. This
was measured on the installed toolchain. A check whose regular expression matches
nothing is therefore not a weak check: it is a check that cannot fail, and it
manufactures confidence.

The lint asserts, in BOTH directions:

  * every name a `Check:` line passes to `-R` is created by some task's `Files:`
    line, and some task registers it with `add_test(NAME <name> ...)`;
  * every test file a `Files:` line creates is invoked by some `-R` argument, or
    by a `pytest` invocation for the Python half.

It also reports a `ctest` invocation with no `--no-tests=error`, a `ctest`
invocation that forwards arguments with `--` (CTest rejects that form), a
`--target` that no `Files:` line creates, a repository section 3.1's table does
not carry, and a path that more than one task claims with no owner in section
7.4.2.
"""

import re

from planlint.document import BACKTICKED, strip_markup
from planlint.finding import ERROR, WARNING, Finding, guard_no_input

# A command word alone is a noun. `A `ctest` invocation carries no flag` is
# the plan stating a rule; an invocation carries at least one argument.
COMMAND_WORD = re.compile(r"\b(?:ctest|cmake|pytest|python3?|gh|cc|c\+\+)\b\s+\S")
# Outside backticks, a command word counts only when a FLAG follows it. `ORC-1's
# ctest half runs in the fork` is prose, and reading it as an unflagged
# invocation is a false positive in exactly the direction that trains a reader
# to ignore the lint.
COMMAND_LINE = re.compile(r"\b(?:ctest|cmake|pytest|python3?|gh)\b(?=\s+-).*$")
R_ARGUMENT = re.compile(r"(?<![\w-])-R\s+(\S+)")
# Section 7.7: every `-R` argument that is not on the prefix allow-list is
# ANCHORED, because an unanchored argument is a prefix. `-R t_isp1181` matched
# three registered tests and `-R mcf5307_conformance` matched five, so a task's
# gate swept tests outside its own dependency closure. An anchored argument
# names exactly one test, and the anchors are stripped before the name is
# compared against the `Files:` pool.
ANCHORS = re.compile(r"^\^(?P<name>.*?)\$$")
# `$` is a shell metacharacter, so quoting an anchored argument is the natural
# way to write it. One MATCHED pair of shell quotes is removed before the
# anchors are read. A quote with no partner is not a quoted argument and is left
# as written, so it keeps failing the pool lookup rather than being repaired.
SHELL_QUOTED = re.compile(r"^(?P<quote>['\"])(?P<inner>.+)(?P=quote)$")
TARGET_ARGUMENT = re.compile(r"--target\s+(\S+)")
FORWARDED = re.compile(r"(?:^|\s)--(?:\s|$)")
NO_TESTS_ERROR = "--no-tests=error"
ADD_TEST = re.compile(r"add_test\(\s*NAME\s+([A-Za-z0-9_.\-]+)")
PYTEST_PATH = re.compile(r"pytest\s+(\S+\.py)")
AXIOMANTIC = re.compile(r"\baxiomantic/[A-Za-z0-9_.\-]+")

# Section 7.7: two `-R` arguments are prefixes and not registered test names.
# The list has exactly two entries, and an exemption in prose is what made the
# previous revision's claim untestable.
PREFIX_ALLOW_LIST = frozenset({"t1_", "t2_oracle"})

TRAILING = ".,;:`'\")]"
# Sentence punctuation only. The quote characters are held back, because an
# argument is unquoted BEFORE the remaining punctuation is stripped: stripping
# the closing quote first turns a quoted pair into an unbalanced one.
SENTENCE_TRAILING = ".,;:)]"


def commands_in(text):
    """Every command string a segment holds.

    A backticked span is a command when it names a command word. The text that
    remains after the spans are removed is scanned line by line, because an
    invocation written without backticks is still an invocation — and it is the
    one most likely to have lost a flag.
    """
    out = []
    for span in BACKTICKED.findall(text):
        if COMMAND_WORD.search(span):
            out.append(span.strip())
    remainder = BACKTICKED.sub(" ", text)
    for line in remainder.splitlines():
        match = COMMAND_LINE.search(line)
        if match:
            out.append(match.group(0).strip())
    return out


def r_arguments(command):
    """Every `-R` argument, with a `^…$` anchor pair stripped.

    An anchored argument names exactly the test between the anchors, so the
    name a `Files:` line must create is the same either way. A half-anchored
    argument is NOT an anchor pair and is returned as written, so it still
    fails the pool lookup rather than being silently accepted.

    One matched pair of shell quotes is removed first. `-R '^t0_alpha$'` is the
    same argument as `-R ^t0_alpha$`, and reading it as the name `'^t0_alpha`
    reported a test that exists as a test no `Files:` line creates.
    """
    out = []
    for raw in R_ARGUMENT.findall(command):
        quoted = SHELL_QUOTED.match(raw.rstrip(SENTENCE_TRAILING))
        name = quoted.group("inner") if quoted else raw
        name = name.rstrip(TRAILING)
        match = ANCHORS.match(name)
        out.append(match.group("name") if match else name)
    return out


def target_arguments(command):
    return [m.rstrip(TRAILING) for m in TARGET_ARGUMENT.findall(command)]


def registered_names(doc):
    """Every name the plan says a task registers with `add_test(NAME ...)`."""
    return set(ADD_TEST.findall("\n".join(doc.lines)))


def _origin_task(doc, origin):
    if origin.startswith("check:"):
        return doc.task(origin.split(":", 1)[1])
    return None


def run(doc):
    findings = []
    pool = doc.files_name_pool()
    registered = registered_names(doc)
    segments = doc.scoped_segments()

    examined = 0
    explicit_r = set()
    pytest_files = set()

    for segment in segments:
        task = _origin_task(doc, segment.origin)
        ident = task.ident if task else ""
        section = task.section if task else segment.origin
        line = task.check_line if task else segment.line

        for command in commands_in(segment.text):
            examined += 1

            if re.search(r"\bctest\b", command):
                if NO_TESTS_ERROR not in command:
                    findings.append(
                        Finding(
                            rule="ctest-without-no-tests-error",
                            message=(
                                "a `ctest` invocation carries no `--no-tests=error`, so "
                                "a pattern that matches nothing exits 0 and the check "
                                "cannot fail; section 1.3 rule 10"
                            ),
                            task=ident,
                            section=section,
                            line=line,
                            evidence=command,
                            severity=ERROR,
                        )
                    )
                if FORWARDED.search(command):
                    findings.append(
                        Finding(
                            rule="ctest-forwards-arguments",
                            message=(
                                "a `ctest` invocation forwards arguments with `--`; "
                                "CTest rejects that form and the engineer meets a hard "
                                "error, then invents an invocation of their own"
                            ),
                            task=ident,
                            section=section,
                            line=line,
                            evidence=command,
                            severity=ERROR,
                        )
                    )

            for name in r_arguments(command):
                if name in PREFIX_ALLOW_LIST:
                    continue
                explicit_r.add(name)
                if name not in pool:
                    findings.append(
                        Finding(
                            rule="r-name-not-created",
                            message=(
                                "a `-R` argument names a test that no task's `Files:` "
                                "line creates; the pattern matches nothing"
                            ),
                            task=ident,
                            section=section,
                            line=line,
                            evidence=f"-R {name}; no `Files:` line creates that name",
                            severity=ERROR,
                        )
                    )
                elif name not in registered:
                    findings.append(
                        Finding(
                            rule="r-name-not-registered",
                            message=(
                                "the plan states no `add_test(NAME ...)` for this "
                                "name anywhere. Section 7.7 clause 2 reads the truth "
                                "from `ctest -N` against a build tree; with no build "
                                "tree this lint reads the document, so the finding "
                                "says the plan does not state the registration"
                            ),
                            severity=WARNING,
                            task=ident,
                            section=section,
                            line=line,
                            evidence=(
                                f"-R {name}; no `add_test(NAME {name} ...)` appears "
                                "in this plan"
                            ),
                        )
                    )

            for target in target_arguments(command):
                if target not in pool:
                    findings.append(
                        Finding(
                            rule="target-not-created",
                            message=(
                                "a `--target` argument names a target that no task's "
                                "`Files:` line creates, so the build step fails before "
                                "the check is reached"
                            ),
                            task=ident,
                            section=section,
                            line=line,
                            evidence=(
                                f"--target {target}; no `Files:` line creates that target"
                            ),
                            severity=ERROR,
                        )
                    )

            for path in PYTEST_PATH.findall(command):
                pytest_files.add(path.rstrip(TRAILING).rsplit("/", 1)[-1])

    findings.extend(_reverse_direction(doc, explicit_r, pytest_files))
    findings.extend(_repositories(doc))
    findings.extend(_shared_paths(doc))

    return guard_no_input(
        "checks", findings, examined, "commands in scope", "check lint"
    )


def _reverse_direction(doc, explicit_r, pytest_files):
    """A registered test that nothing runs is an `-R` that matches nothing,
    seen from the other side."""
    findings = []
    for task in doc.tasks:
        for path in task.test_files:
            base = path.rsplit("/", 1)[-1]
            stem = base.rsplit(".", 1)[0]
            if base.endswith(".py"):
                if base in pytest_files:
                    continue
                evidence = (
                    f"`{path}` is created and no `Check:` line runs `pytest` against it"
                )
            else:
                if stem in explicit_r:
                    continue
                evidence = f"`{path}` is created and no `Check:` line names `-R {stem}`"
            findings.append(
                Finding(
                    rule="test-file-never-invoked",
                    message=(
                        "a test file is created and never invoked; a registered test "
                        "that nothing runs is invisible to a forward-only lint"
                    ),
                    task=task.ident,
                    section=task.section,
                    line=task.line,
                    evidence=evidence,
                    severity=ERROR,
                )
            )
    return findings


def _repositories(doc):
    """Section 3.1.1: every repository any task names must be in the table."""
    findings = []
    for task in doc.tasks:
        for name in sorted(set(AXIOMANTIC.findall(task.body_text))):
            if name in doc.repositories:
                continue
            findings.append(
                Finding(
                    rule="repository-not-in-layout",
                    message=(
                        "a task names a repository that section 3.1's table does not "
                        "carry; a repository outside the table is outside the "
                        "visibility rule, the organization rule and every lint"
                    ),
                    task=task.ident,
                    section=task.section,
                    line=task.line,
                    evidence=f"names `{name}`; section 3.1's table does not carry it",
                    severity=ERROR,
                )
            )
    return findings


def _shared_paths(doc):
    """Section 7.4.2: every file more than one track can reach needs an owner."""
    claims = {}
    for task in doc.tasks:
        for path in set(task.files_paths):
            claims.setdefault(path, []).append(task.ident)
    findings = []
    for path, owners in sorted(claims.items()):
        if len(owners) < 2 or doc.has_owner(path):
            continue
        findings.append(
            Finding(
                rule="shared-path-without-owner",
                message=(
                    "more than one task claims a path and section 7.4.2 names no "
                    "owner; an agent with no list to join guesses"
                ),
                task="",
                section="7.4.2 Every shared file has one owner",
                line=doc.task(owners[0]).line,
                evidence=(
                    f"`{path}` is claimed by {', '.join(owners)}; section 7.4.2 names "
                    "no owner for it"
                ),
                severity=ERROR,
            )
        )
    return findings
