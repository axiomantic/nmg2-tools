"""The Python half of task REPO-5's ``ArtifactResolver``.

Design section 4.2 is the definition site. The C++ half lives at
``source/nord/g2/g2Lib/artifactResolver.{h,cpp}`` in the ``gearmulator`` fork.
Both halves are written by ONE task so that the two messages cannot drift; plan
section 7.4.2 records that as the reason this file has REPO-5 as its owner.

Design section 4.2, on the Python half:

    ``axiomantic/nmg2-tools`` carries the Python equivalent,
    ``resolve_artifacts()``, with the same contract and three distinct messages,
    one for each of the three conditions REPO-5's check names, so that the Python
    extractor and the C++ extractor skip for the same reason in the same words.
"""

import os
from typing import Optional

# The THREE messages, WORD FOR WORD. Design section 4.2 fixes the wording and
# section 18.5 builds the skip line on top of them. The three are distinct on
# purpose: one message for two conditions told an operator with a wrong path that
# their variable was unset, which is a message that sends them to the wrong
# file. Echoing the variable value unchanged is the whole point of message 2.
ARTIFACT_UNSET_MESSAGE = "firmware artifact not available (NMG2_ARTIFACTS unset)"
ARTIFACT_ENVIRONMENT_VARIABLE = "NMG2_ARTIFACTS"


def _message_no_directory(value: str) -> str:
    return f"firmware artifact not available (NMG2_ARTIFACTS names no directory: {value})"


def _message_not_found(name: str, value: str) -> str:
    return f"firmware artifact not available ({name} not found under NMG2_ARTIFACTS: {value})"


def resolve_artifacts(name: Optional[str] = None) -> tuple[str, str]:
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

    Never raises. This mirrors the C++ half, where design section 4.2 states the
    no-exception rule on ``ArtifactResolver::resolve`` directly.
    """
    value = os.environ.get(ARTIFACT_ENVIRONMENT_VARIABLE)

    # An empty value counts as unset. Windows removes a variable by assigning it
    # the empty string, so a half that treated "" as a path would mean something
    # different on Windows than it means on Linux and macOS -- and the two halves
    # of this task would then disagree on the same input.
    if not value:
        return "", ARTIFACT_UNSET_MESSAGE

    # A path that does not exist, a path the process cannot stat, and a path that
    # exists but is not a directory all land here, and all three give the SAME
    # message 2. `os.path.isdir` reports False rather than raising for every one
    # of them, so this function needs no exception handler to satisfy the
    # never-raises contract -- and a handler that can never fire would be a branch
    # no test could drive.
    if not os.path.isdir(value):
        return "", _message_no_directory(value)

    # The directory exists. If a name was asked for and the file is not in the
    # directory, message 3 fires. The caller chose ``name`` and we echo it.
    if name is not None:
        candidate = os.path.join(value, name)
        if not os.path.isfile(candidate):
            return "", _message_not_found(name, value)

    return value, ""


# ---------------------------------------------------------------------------
# Task REPO-7, the Python half of the skip discipline. Design section 18.5,
# plan section 5.2 rules 2 and 3.
#
# REPO-7 depends on REPO-5 and both are repo-track tasks, so this section is a
# track-internal order and not a race. The C++ half is
# `source/nord/g2/g2Lib/test/gatedFixture.h` in the `gearmulator` fork.
# ---------------------------------------------------------------------------

# Section 18.5's skip line is section 4.2's message with this prefix. The line is
# built by CONCATENATION and is not spelled out a second time: a message with two
# texts is a message with two meanings, and the one an implementer copies is the
# one that drifts. `gatedFixture.h` builds it the same way.
GATED_SKIP_PREFIX = "SKIPPED: "


def gated_skip_line() -> str:
    """The line design section 18.5 step 2 requires a gated test to emit."""
    return GATED_SKIP_PREFIX + ARTIFACT_UNSET_MESSAGE


def gated_skip_reason() -> Optional[str]:
    """Return the skip line when a gated test cannot run, or ``None`` when it can.

    ``None`` means the artifact resolved and the gated body must run. Any other
    return is a reason, never a silent pass: design section 18.5 opens with "a
    firmware-gated test that cannot run must skip WITH A REASON. It must never
    pass silently."
    """
    directory, _why = resolve_artifacts()

    if directory:
        return None

    return gated_skip_line()
