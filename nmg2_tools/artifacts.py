"""The Python half of the ``ArtifactResolver``.

The C++ half lives at ``source/nord/g2/g2Lib/artifactResolver.{h,cpp}`` in the
``gearmulator`` fork. Both halves are written together so that the two messages
cannot drift.

``resolve_artifacts()`` carries the same contract as the C++ half and three
distinct messages, one for each of the three conditions the C++ check names, so
that the Python extractor and the C++ extractor skip for the same reason in the
same words.
"""

import os
from typing import Optional

# The messages, WORD FOR WORD. The wording is fixed and the skip line below is
# built on top of them. They are distinct on
# purpose: one message covering two conditions tells an operator with a wrong
# path that their variable is unset, which sends them to the wrong file.
# Echoing the variable value unchanged is the whole point of message 2.
# A FAMILY is a root, not a file. `NMG2_ARTIFACTS` named two unrelated families
# at once -- the descriptor and panel tables on one side, the vendor installer
# images on the other -- and no single directory on any machine holds both, so
# one of the two was always resolved against the wrong tree. Each family
# therefore reads its OWN variable, `NMG2_<FAMILY>`, and the default family
# `artifacts` yields `NMG2_ARTIFACTS` unchanged by that same rule rather than by
# a special case.
#
# The variable name is DERIVED from the family and is not looked up in a table.
# A table mapping family to variable, or path to family, would be amended once
# per fixture and would be a missing predicate wearing a list's clothes.
#
# A family NEVER falls back to another family's root. A resolver that searched a
# second root on a miss would answer with a file whose provenance no reader
# could reconstruct, which is worse than the skip it replaces.
DEFAULT_ARTIFACT_FAMILY = "artifacts"


def artifact_variable(family: str = DEFAULT_ARTIFACT_FAMILY) -> str:
    """The environment variable a family reads."""
    return "NMG2_" + family.upper()


def _message_unset(variable: str) -> str:
    return f"firmware artifact not available ({variable} unset)"


def _message_no_directory(variable: str, value: str) -> str:
    return f"firmware artifact not available ({variable} names no directory: {value})"


def _message_not_found(name: str, variable: str, value: str) -> str:
    return f"firmware artifact not available ({name} not found under {variable}: {value})"


# The default family's variable and message 1, kept as names because callers and
# the C++ half both refer to them. They are DERIVED from the two functions above
# rather than spelled out a second time: a message with two texts is a message
# with two meanings, and the copy is the one that drifts.
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

    Never raises. This mirrors the C++ half, which states the no-exception rule
    on ``ArtifactResolver::resolve`` directly.
    """
    variable = artifact_variable(family)
    value = os.environ.get(variable)

    # An empty value counts as unset. Windows removes a variable by assigning it
    # the empty string, so a half that treated "" as a path would mean something
    # different on Windows than it means on Linux and macOS -- and the two halves
    # of this task would then disagree on the same input.
    if not value:
        return "", _message_unset(variable)

    # A path that does not exist, a path the process cannot stat, and a path that
    # exists but is not a directory all land here, and all of them give the SAME
    # message 2. `os.path.isdir` reports False rather than raising for every one
    # of them, so this function needs no exception handler to satisfy the
    # never-raises contract.
    if not os.path.isdir(value):
        return "", _message_no_directory(variable, value)

    # The directory exists. If a name was asked for and the file is not in the
    # directory, message 3 fires. The caller chose ``name`` and we echo it.
    if name is not None:
        candidate = os.path.join(value, name)
        if not os.path.isfile(candidate):
            return "", _message_not_found(name, variable, value)

    return value, ""


# ---------------------------------------------------------------------------
# The Python half of the skip discipline. The C++ half is
# `source/nord/g2/g2Lib/test/gatedFixture.h` in the `gearmulator` fork.
# ---------------------------------------------------------------------------

# The skip line is message 1 above with this prefix. The line is
# built by CONCATENATION and is not spelled out a second time: a message with two
# texts is a message with two meanings, and the one an implementer copies is the
# one that drifts. `gatedFixture.h` builds it the same way.
GATED_SKIP_PREFIX = "SKIPPED: "


def gated_skip_line(family: str = DEFAULT_ARTIFACT_FAMILY) -> str:
    """The line a gated test emits when it cannot run.

    The line names the family's own variable, which is the one an operator has
    to set to make the test run. A line that named the base variable for every
    family would send that operator to the wrong variable.
    """
    return GATED_SKIP_PREFIX + _message_unset(artifact_variable(family))


def gated_skip_reason(
    *required: str, family: str = DEFAULT_ARTIFACT_FAMILY
) -> Optional[str]:
    """Return the skip line when a gated test cannot run, or ``None`` when it can.

    ``required`` is the paths, relative to the artifacts root, that the gated
    body will OPEN. The gate is built from them and not from the directory
    alone, because a directory that resolves says nothing about whether the
    files in it exist. A gate that opens on the directory alone answers RUN to
    a body whose input is absent, and that body raises ``FileNotFoundError``
    where a skip WITH A REASON is required.

    ``None`` means every required artifact is present and the gated body must
    run. Any other return is a reason, never a silent pass.

    The gate reads names only. **A file that is PRESENT and WRONG resolves, so
    the body runs and FAILS**, which is the case this gate exists to protect
    and the reason this function never opens a file: a gate that read content
    could not tell a broken artifact from an absent one, and it would answer
    "unavailable" to both.

    Two reasons, taken from the three messages above rather than from a fourth
    text of this function's own:

    * the root does not resolve -- the skip line built on message 1, whatever
      ``required`` says, because there is no directory to look in;
    * the root resolves and a required path is not a file under it -- the
      prefix on message 3, which names that path.

    ``family`` selects WHICH root. The paths in ``required`` are relative to
    that family's root and are looked for there only.
    """
    directory, _why = resolve_artifacts(family=family)

    if not directory:
        return gated_skip_line(family)

    for name in required:
        _resolved, why = resolve_artifacts(name, family=family)
        if why:
            return GATED_SKIP_PREFIX + why

    return None


# ---------------------------------------------------------------------------
# The RUN's verdict on its own skips.
#
# `gated_skip_reason` above makes ONE test skip with a reason, and it stops
# there. What a reader actually looks at is the RUN, and a run whose summary
# line reports only passes and skips shows a green verdict over deliverables
# nothing exercised. A gate whose silence is indistinguishable from success is
# not a gate.
#
# THE LIMIT COMES ACROSS WITH THE PATTERN: a skip changes the verdict's WORDING
# and NEVER its exit code. Scoring a skip would change what `if pytest; then`
# means for every existing caller, and that is a separate decision from making
# the skip visible.
SKIP_VERDICT_SENTENCE = "A skipped test is not a clean test."


def skip_verdict(skipped: dict[str, str]) -> str:
    """The block a run prints about its own skips, or ``""`` when it skipped none.

    ``skipped`` maps a test's node id to the reason it did not run. The empty
    result is the whole point of the mapping being passed in rather than a
    count: a run that skipped nothing must print nothing, or the notice becomes
    noise every reader learns to skip past.
    """
    if not skipped:
        return ""

    noun = "test" if len(skipped) == 1 else "tests"
    header = f"SKIP VERDICT: {len(skipped)} {noun} SKIPPED. {SKIP_VERDICT_SENTENCE}"
    rows = [f"  {nodeid} — {reason}" for nodeid, reason in skipped.items()]

    return "\n".join([header, *rows])
