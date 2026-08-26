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

import pathlib
import re
import subprocess

from planlint.document import has_marker, inline_code_spans, strip_markup
from planlint.finding import ERROR, WARNING, Finding, guard_no_input


def _parse_build_dirs(build_dirs):
    """Parse build_dirs into a repo_map dict and validation findings."""
    if not build_dirs:
        return {}, []

    items = []
    if isinstance(build_dirs, str):
        raw_list = [build_dirs]
    elif isinstance(build_dirs, dict):
        items = list(build_dirs.items())
        raw_list = []
    else:
        raw_list = list(build_dirs)

    for entry in raw_list:
        if isinstance(entry, str):
            if "=" in entry:
                repo, p_str = entry.split("=", 1)
                items.append((repo.strip(), p_str.strip()))
            else:
                return {}, [
                    Finding(
                        rule="invalid-build-dir",
                        message=f"invalid --build-dir format: '{entry}', expected REPO=PATH",
                        severity=ERROR,
                        evidence=str(entry),
                    )
                ]
        elif isinstance(entry, (tuple, list)) and len(entry) == 2:
            items.append((str(entry[0]), str(entry[1])))

    repo_map = {}
    findings = []
    for repo, p_val in items:
        path = pathlib.Path(p_val)
        if not path.is_dir() or not (path / "CTestTestfile.cmake").is_file():
            findings.append(
                Finding(
                    rule="invalid-build-dir",
                    message=(
                        f"build directory for '{repo}' does not exist or lacks "
                        f"CTestTestfile.cmake: {path}"
                    ),
                    severity=ERROR,
                    evidence=str(path),
                )
            )
        else:
            repo_map[repo] = path

    return repo_map, findings


def _get_ctest_registered_tests(build_path):
    """Run `ctest --test-dir <build_path> --no-tests=error -N` and parse registered test names."""
    try:
        res = subprocess.run(
            ["ctest", "--test-dir", str(build_path), "--no-tests=error", "-N"],
            capture_output=True,
            text=True,
            check=False,
        )
        stdout = res.stdout or ""
        tests = set()
        for line in stdout.splitlines():
            match = re.search(r"Test\s+#\d+:\s*(.+)$", line)
            if match:
                test_name = match.group(1).strip()
                if test_name:
                    tests.add(test_name)
        return tests
    except Exception:
        return set()


def _check_registration(
    doc,
    task,
    name,
    registered_in_doc,
    repo_map,
    ctest_tests_by_repo,
    ident,
    section,
    line,
):
    """Check if test `name` (from `-R <name>`) is registered.

    When a build directory is supplied for a repository:
      - run `ctest --test-dir <build_path> --no-tests=error -N`, parse listing text for test names matching `-R <name>`,
      - upgrade `r-name-not-registered` findings from WARNING to ERROR if missing from CTest listing.
    When no build directory is supplied:
      - check if `name` is in registered_in_doc (`add_test(NAME ...)` in plan).
      - if missing from plan: report `r-name-not-registered` as WARNING.
    """
    applicable_repo = None
    if repo_map:
        if len(repo_map) == 1:
            applicable_repo = next(iter(repo_map))
        else:
            task_text = (task.body_text + " " + task.files_text) if task else ""
            for r in repo_map:
                r_short = r.rsplit("/", 1)[-1]
                if r in task_text or r_short in task_text or r in doc.repositories:
                    applicable_repo = r
                    break

    if applicable_repo and applicable_repo in ctest_tests_by_repo:
        ctest_tests = ctest_tests_by_repo[applicable_repo]
        if name not in ctest_tests:
            return Finding(
                rule="r-name-not-registered",
                message=(
                    "the test name is missing from the CTest listing in the supplied "
                    "build directory; section 7.7 clause 2 reads the live build tree"
                ),
                severity=ERROR,
                task=ident,
                section=section,
                line=line,
                evidence=f"-R {name}; missing from CTest listing in build directory",
            )
        return None

    if name not in registered_in_doc:
        return Finding(
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
            evidence=f"-R {name}; no `add_test(NAME {name} ...)` appears in this plan",
        )

    return None


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
# ANCHORED, because an unanchored argument is a prefix, and a prefix sweeps
# tests outside a task's own dependency closure. An anchored argument
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
# The one pattern for `add_test(NAME <name> ...)`. `planlint.rule9` reads it
# from here rather than carrying its own: the plan's prose and a repository's
# CMake ask the same question, and two patterns for one question are repaired
# one at a time.
#
# The lookahead requires one alphanumeric somewhere in the name, which is what
# separates a registration from the prose placeholder `add_test(NAME ...)`. The
# alternative repair — dropping `.` from the class — is worse: a dot is a legal
# character in a ctest name, and a class without it reads `add_test(NAME a.b)`
# as the name `a`, turning a rejection into a silent truncation.
#
# The space before the parenthesis is CMake's own grammar, so the CMake reader
# must accept it; a plan quoting a registration as its repository spells it
# reads as one registration and not as prose.
ADD_TEST = re.compile(
    r"add_test\s*\(\s*NAME\s+(?=[A-Za-z0-9_.\-]*[A-Za-z0-9])([A-Za-z0-9_.\-]+)"
)
PYTEST_PATH = re.compile(r"pytest\s+(\S+\.py)")
AXIOMANTIC = re.compile(r"\baxiomantic/[A-Za-z0-9_.\-]+")

# Section 7.7 allow-lists the `-R` arguments that are prefixes rather than
# registered test names. The list is written here, because an exemption kept in
# prose is an exemption no test can hold anything against.
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

    The spans are read by the fence-aware scanner. An unmatched backtick is
    literal text, so the remainder keeps every line it had.
    """
    out = []
    spans, _ = inline_code_spans(text)
    remainder = list(text)
    for opener, closer, inner in spans:
        if COMMAND_WORD.search(inner):
            out.append(inner.strip())
        for index in range(opener, closer + 1):
            remainder[index] = " "
    for line in "".join(remainder).splitlines():
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
    same argument as `-R ^t0_alpha$`; reading it as the name `'^t0_alpha` would
    report a test that exists as a test no `Files:` line creates.
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
    """Every name the plan says a task registers with `add_test(NAME ...)`.

    The scan reads TASK BLOCKS and nothing else, because section 1.3 rule 9
    names a task and a §24.6 defect-register row is not one. A document-wide
    scan makes the rule satisfiable by any sentence anywhere — a register row
    that quotes a registration silences the check for a test no task registers,
    which is a lint a sentence can talk out of a finding.
    """
    return set(ADD_TEST.findall("\n".join(task.body_text for task in doc.tasks)))


FAILURE_MECHANISMS = re.compile(
    r"\b(?:fail(?:s|ed|ing|ure)?|error|assert(?:ion)?|exit|panic|reject(?:s|ed|ion)?|raise|negative case|non-zero)\b",
    re.IGNORECASE,
)


def _origin_task(doc, origin):
    if origin.startswith("check:"):
        return doc.task(origin.split(":", 1)[1])
    return None


def run(doc, check_targets_path=None, build_dirs=None):
    findings = []
    pool = doc.files_name_pool()
    registered = registered_names(doc)
    segments = doc.scoped_segments()

    repo_map, build_dir_findings = _parse_build_dirs(build_dirs)
    findings.extend(build_dir_findings)

    ctest_tests_by_repo = {}
    for repo, b_path in repo_map.items():
        ctest_tests_by_repo[repo] = _get_ctest_registered_tests(b_path)

    examined = 0
    explicit_r = set()
    pytest_files = set()

    findings.extend(_check_non_empty_check_blocks(doc))
    if check_targets_path:
        findings.extend(_check_targets(doc, check_targets_path))

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
                else:
                    reg_finding = _check_registration(
                        doc,
                        task,
                        name,
                        registered,
                        repo_map,
                        ctest_tests_by_repo,
                        ident,
                        section,
                        line,
                    )
                    if reg_finding:
                        findings.append(reg_finding)

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


def _check_non_empty_check_blocks(doc):
    findings = []
    for task in doc.tasks:
        if not task.check_line or not task.check_text.strip():
            findings.append(
                Finding(
                    rule="non-empty-check-block",
                    message=(
                        "a task block carries no Check: block; section 1.1 requires "
                        "every task to state how its completion is verified"
                    ),
                    task=task.ident,
                    section=task.section,
                    line=task.line,
                    evidence=f"task {task.ident} has no Check: block",
                    severity=ERROR,
                )
            )
            continue

        text = task.check_text
        has_ctest_or_pytest = bool(re.search(r"\b(?:ctest|pytest)\b", text))
        has_failure_mech = bool(FAILURE_MECHANISMS.search(text))

        if not has_ctest_or_pytest and not has_failure_mech:
            findings.append(
                Finding(
                    rule="non-empty-check-block",
                    message=(
                        "a Check: block contains no ctest or pytest command and "
                        "names no explicit failure mechanism"
                    ),
                    task=task.ident,
                    section=task.section,
                    line=task.check_line,
                    evidence=f"Check: {text.splitlines()[0]}",
                    severity=ERROR,
                )
            )
    return findings


def _check_targets(doc, check_targets_path):
    findings = []
    path = pathlib.Path(check_targets_path)
    if not path.is_file():
        return [
            Finding(
                rule="check-targets-mismatch",
                message=f"check-targets file not found: {check_targets_path}",
                severity=ERROR,
                evidence=str(check_targets_path),
            )
        ]

    expected = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        expected.add(line)

    actual = set()
    segments = doc.scoped_segments()
    for segment in segments:
        for command in commands_in(segment.text):
            if "pytest" in command:
                for match in PYTEST_PATH.finditer(command):
                    pytest_target = match.group(0).rstrip(SENTENCE_TRAILING)
                    actual.add(pytest_target)
                if not PYTEST_PATH.search(command):
                    for match in re.finditer(r"\bpytest\s+(\S+)", command):
                        target = match.group(0).rstrip(SENTENCE_TRAILING)
                        actual.add(target)
            if "ctest" in command:
                for name in r_arguments(command):
                    if name not in PREFIX_ALLOW_LIST:
                        actual.add(name)

    missing_in_plan = sorted(expected - actual)
    extra_in_plan = sorted(actual - expected)

    for item in missing_in_plan:
        findings.append(
            Finding(
                rule="check-targets-mismatch",
                message=(
                    f"target '{item}' is listed in {check_targets_path} "
                    "but not found in plan Check: lines"
                ),
                severity=ERROR,
                evidence=f"missing in plan: {item}",
            )
        )
    for item in extra_in_plan:
        findings.append(
            Finding(
                rule="check-targets-mismatch",
                message=(
                    f"target '{item}' is present in plan Check: lines "
                    f"but not listed in {check_targets_path}"
                ),
                severity=ERROR,
                evidence=f"extra in plan: {item}",
            )
        )

    return findings


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
    """Section 7.4.2: every file more than one track can reach needs an owner.

    A MARKED entry is not a claimant. Section 7.4.2 states it verbatim — "A
    marked entry never raises `shared-path-without-owner`, because a marked
    entry is not a claim" — and that is stronger than stripping the marker and
    counting the entry anyway. Under the weaker reading one bare writer beside
    one marked writer is still two claimants, so the rule keeps firing on the
    very file the marker of section 1.1.1 rule D exists to declare, and the
    defect survives one layer down. So a marked entry never enters the map at
    all, and what the map counts is BARE claims of ownership only. Section
    7.4.2 states that too: "The ownership script compares BARE entries only."

    A path every writer marks therefore has no claimant here and this rule says
    nothing about it. Section 7.4.2 gives that case to
    `second-write-no-owner-row` and `manifest-without-creator`, which this tool
    does not implement.
    """
    claims = {}
    for task in doc.tasks:
        for path in set(task.files_paths):
            if has_marker(path):
                continue
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
