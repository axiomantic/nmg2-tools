"""Resolve Clavia-derived artifact roots, and gate tests on their presence.

The C++ half is ``source/nord/g2/g2Lib/artifactResolver.{h,cpp}`` in the
``gearmulator`` fork. The two must skip for the same reason in the same words.
"""

import os
from typing import Optional

# A FAMILY is a root, not a file. Each family reads its OWN variable,
# `NMG2_<FAMILY>`, DERIVED from the family name rather than looked up in a
# table. `NMG2_ARTIFACTS` once named two unrelated families at once -- the
# descriptor and panel tables, and the vendor installer images -- and no single
# directory holds both, so one was always resolved against the wrong tree.
#
# A family NEVER falls back to another family's root: a resolver that searched a
# second root on a miss answers with a file whose origin no reader can
# reconstruct, which is worse than the skip it replaces.
DEFAULT_ARTIFACT_FAMILY = "artifacts"


def artifact_variable(family: str = DEFAULT_ARTIFACT_FAMILY) -> str:
    """The environment variable a family reads."""
    return "NMG2_" + family.upper()


# Three distinct messages, one per condition. One message covering two
# conditions tells an operator with a wrong path that their variable is unset,
# which sends them to the wrong file. Messages 2 and 3 echo the value unchanged.
def _message_unset(variable: str) -> str:
    return f"firmware artifact not available ({variable} unset)"


def _message_no_directory(variable: str, value: str) -> str:
    return f"firmware artifact not available ({variable} names no directory: {value})"


def _message_not_found(name: str, variable: str, value: str) -> str:
    return f"firmware artifact not available ({name} not found under {variable}: {value})"


ARTIFACT_ENVIRONMENT_VARIABLE = artifact_variable()
ARTIFACT_UNSET_MESSAGE = _message_unset(ARTIFACT_ENVIRONMENT_VARIABLE)


def resolve_artifacts(
    name: Optional[str] = None, family: str = DEFAULT_ARTIFACT_FAMILY
) -> tuple[str, str]:
    """Resolve the directory that holds the Clavia-derived artifacts.

    Returns ``(directory, why)``.

    On success ``directory`` is the resolved directory and ``why`` is empty.
    On failure ``directory`` is empty and ``why`` is one of three distinct
    messages, one per condition:

    1. ``NMG2_ARTIFACTS`` unset or empty -- :data:`ARTIFACT_UNSET_MESSAGE`.
    2. The path it names does not exist or is not a directory -- message 2
       (echoing the variable's value unchanged).
    3. The directory exists but the named artifact is not in it -- message 3
       (echoing the variable's value unchanged).

    ``name`` is the artifact the caller asked for and only message 3 reads it.

    Never raises, matching the C++ half.
    """
    variable = artifact_variable(family)
    value = os.environ.get(variable)

    # An empty value counts as unset: Windows removes a variable by assigning it
    # the empty string, so treating "" as a path would make the two halves
    # disagree on the same input.
    if not value:
        return "", _message_unset(variable)

    # Nonexistent, unstattable and not-a-directory all give message 2.
    # `os.path.isdir` returns False rather than raising for every one of them,
    # which is how this function meets the never-raises contract with no handler.
    if not os.path.isdir(value):
        return "", _message_no_directory(variable, value)

    if name is not None:
        candidate = os.path.join(value, name)
        if not os.path.isfile(candidate):
            return "", _message_not_found(name, variable, value)

    return value, ""


# The skip discipline. The C++ half is
# `source/nord/g2/g2Lib/test/gatedFixture.h` in the `gearmulator` fork, which
# builds the same line by the same concatenation.
GATED_SKIP_PREFIX = "SKIPPED: "


def gated_skip_line(family: str = DEFAULT_ARTIFACT_FAMILY) -> str:
    """The line a gated test emits when it cannot run.

    The line names the family's own variable, which is the one an operator has
    to set to make the test run.
    """
    return GATED_SKIP_PREFIX + _message_unset(artifact_variable(family))


def gated_skip_reason(
    *required: str, family: str = DEFAULT_ARTIFACT_FAMILY
) -> Optional[str]:
    """Return the skip line when a gated test cannot run, or ``None`` when it can.

    ``required`` is the paths, relative to the family's root, that the gated
    body will OPEN. The gate is built from them and not from the directory
    alone: a directory that resolves says nothing about whether the files in it
    exist, and a gate on the directory alone answers RUN to a body whose input
    is absent, which then raises ``FileNotFoundError`` instead of skipping.

    The gate reads names only. **A file that is PRESENT and WRONG resolves, so
    the body runs and FAILS.** A gate that read content could not tell a broken
    artifact from an absent one and would report "unavailable" for both.
    """
    directory, _why = resolve_artifacts(family=family)

    if not directory:
        return gated_skip_line(family)

    for name in required:
        _resolved, why = resolve_artifacts(name, family=family)
        if why:
            return GATED_SKIP_PREFIX + why

    return None


# A skip changes the run verdict's WORDING and NEVER its exit code. Scoring a
# skip would change what `if pytest; then` means for every existing caller.
SKIP_VERDICT_SENTENCE = "A skipped test is not a clean test."


def skip_verdict(skipped: dict[str, str]) -> str:
    """The block a run prints about its own skips, or ``""`` when it skipped none.

    ``skipped`` maps a test's node id to the reason it did not run.
    """
    if not skipped:
        return ""

    noun = "test" if len(skipped) == 1 else "tests"
    header = f"SKIP VERDICT: {len(skipped)} {noun} SKIPPED. {SKIP_VERDICT_SENTENCE}"
    rows = [f"  {nodeid} — {reason}" for nodeid, reason in skipped.items()]

    return "\n".join([header, *rows])
