"""The Python half of the ``ArtifactResolver``.

The C++ half lives at ``source/nord/g2/g2Lib/artifactResolver.{h,cpp}`` in the
``gearmulator`` fork. Both halves are kept in step so that the two messages
cannot drift: the Python extractor and the C++ extractor skip for the same
reason in the same words.
"""

import os
from typing import Optional

# The message a failed resolve returns, WORD FOR WORD. The skip line is built on
# top of it.
#
# It reads "unset" for BOTH failure cases -- the variable unset, and the
# variable naming a directory that is not there. The two cases give one message
# deliberately, and the result must be the same for both. This constant is not
# the place to improve on it.
ARTIFACT_UNAVAILABLE_MESSAGE = "firmware artifact not available (NMG2_ARTIFACTS unset)"

ARTIFACT_ENVIRONMENT_VARIABLE = "NMG2_ARTIFACTS"


def resolve_artifacts() -> tuple[str, str]:
    """Resolve the directory that holds the Clavia-derived artifacts.

    Returns ``(directory, why)``.

    On success ``directory`` is the resolved directory and ``why`` is empty.
    On failure ``directory`` is empty and ``why`` is
    :data:`ARTIFACT_UNAVAILABLE_MESSAGE`.

    Never raises. This mirrors the C++ half, which states the no-exception rule
    on ``ArtifactResolver::resolve`` directly.
    """
    value = os.environ.get(ARTIFACT_ENVIRONMENT_VARIABLE)

    # An empty value counts as unset. Windows removes a variable by assigning it
    # the empty string, so a half that treated "" as a path would mean something
    # different on Windows than it means on Linux and macOS -- and the two halves
    # of this task would then disagree on the same input.
    if not value:
        return "", ARTIFACT_UNAVAILABLE_MESSAGE

    # A path that does not exist, a path the process cannot stat, and a path that
    # exists but is not a directory all land here, and all three give the SAME
    # result as the unset case. `os.path.isdir` reports
    # False rather than raising for every one of them, so this function needs no
    # exception handler to satisfy the never-raises contract -- and a handler
    # that can never fire would be a branch no test could drive.
    if not os.path.isdir(value):
        return "", ARTIFACT_UNAVAILABLE_MESSAGE

    return value, ""


# ---------------------------------------------------------------------------
# The Python half of the skip discipline. The C++ half is
# `source/nord/g2/g2Lib/test/gatedFixture.h` in the `gearmulator` fork.
# ---------------------------------------------------------------------------

# The skip line is the unavailable message with this prefix. The line is
# built by CONCATENATION and is not spelled out a second time: a message with two
# texts is a message with two meanings, and the one an implementer copies is the
# one that drifts. `gatedFixture.h` builds it the same way.
GATED_SKIP_PREFIX = "SKIPPED: "


def gated_skip_line() -> str:
    """The line a gated test emits when it cannot run."""
    return GATED_SKIP_PREFIX + ARTIFACT_UNAVAILABLE_MESSAGE


def gated_skip_reason() -> Optional[str]:
    """Return the skip line when a gated test cannot run, or ``None`` when it can.

    ``None`` means the artifact resolved and the gated body must run. Any other
    return is a reason, never a silent pass: a firmware-gated test that cannot
    run must skip WITH A REASON. It must never pass silently.
    """
    directory, _why = resolve_artifacts()

    if directory:
        return None

    return gated_skip_line()
