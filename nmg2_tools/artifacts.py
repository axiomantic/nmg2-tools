"""The Python half of task REPO-5's ``ArtifactResolver``.

Design section 4.2 is the definition site. The C++ half lives at
``source/nord/g2/g2Lib/artifactResolver.{h,cpp}`` in the ``gearmulator`` fork.
Both halves are written by ONE task so that the two messages cannot drift; plan
section 7.4.2 records that as the reason this file has REPO-5 as its owner.

Design section 4.2, on the Python half:

    ``axiomantic/nmg2-tools`` carries the Python equivalent,
    ``resolve_artifacts()``, with the same contract and the same message, so
    that the Python extractor and the C++ extractor skip for the same reason in
    the same words.
"""

import os

# The message a failed resolve returns, WORD FOR WORD. Design section 4.2 fixes
# the wording and section 18.5 builds the skip line on top of it.
#
# It reads "unset" for BOTH failure cases -- the variable unset, and the
# variable naming a directory that is not there. That is the design's own
# decision: section 4.2 gives the two cases one message, and REPO-5's check
# requires "the result is the same". This constant is not the place to improve
# on it.
ARTIFACT_UNAVAILABLE_MESSAGE = "firmware artifact not available (NMG2_ARTIFACTS unset)"

ARTIFACT_ENVIRONMENT_VARIABLE = "NMG2_ARTIFACTS"


def resolve_artifacts() -> tuple[str, str]:
    """Resolve the directory that holds the Clavia-derived artifacts.

    Returns ``(directory, why)``.

    On success ``directory`` is the resolved directory and ``why`` is empty.
    On failure ``directory`` is empty and ``why`` is
    :data:`ARTIFACT_UNAVAILABLE_MESSAGE`.

    Never raises. This mirrors the C++ half, where design section 4.2 states the
    no-exception rule on ``ArtifactResolver::resolve`` directly.
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
    # result the plan's check requires of the unset case. `os.path.isdir` reports
    # False rather than raising for every one of them, so this function needs no
    # exception handler to satisfy the never-raises contract -- and a handler
    # that can never fire would be a branch no test could drive.
    if not os.path.isdir(value):
        return "", ARTIFACT_UNAVAILABLE_MESSAGE

    return value, ""
