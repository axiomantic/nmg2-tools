"""Task REPO-7, the skip discipline, Python side. Design section 18.5.

A firmware-gated test that cannot run must skip WITH A REASON. It must never
pass silently.

The C++ side of this discipline is
``source/nord/g2/g2Lib/test/gatedFixture.h`` in the ``gearmulator`` fork, and
``t0_skip_discipline`` is its check. This file holds no rule of its own: the
decision and the wording both live in :mod:`nmg2_tools.artifacts`, so that the
two languages skip for the same reason in the same words and there is one place
to change.
"""

import pytest

from nmg2_tools.artifacts import (
    DEFAULT_ARTIFACT_FAMILY,
    gated_skip_reason,
    resolve_artifacts,
)

# `pytester` lets tests/test_artifacts.py drive the fixture below in a real
# pytest run rather than assert about it from the outside. Plan section 18.7:
# a test that passes when the code is broken is worse than no test, and an
# untested fixture is exactly that.
pytest_plugins = ["pytester"]


def _family_fixture(family: str):
    """Build the ``<family>_dir`` fixture for one artifact family.

    A test states WHICH ROOT it needs by requesting that family's fixture, and
    states WHICH FILES its body opens with the ``artifacts`` marker. Those are
    the only two declarations, and neither is a per-file table: nothing anywhere
    maps a path to a family, so nothing has to be amended when a gated test
    starts reading one more file out of a root it already names.

    The fixture parameter is not a second declaration bolted on for this: a body
    cannot join a relative path without a root, so it already had to name one.
    What changed is that naming it now selects the root as well as receiving it.

    The skip reason is section 18.5's line WORD FOR WORD, prefix included. The
    prefix is carried inside the reason on purpose: pytest's own report line
    reads ``SKIPPED [1] file:line: <reason>``, so without it the required
    literal would never appear in the job output, and design section 18.5 step 2
    asks for the literal.

    The marker declaration lives on the test and not in this fixture because the
    fixture cannot know what any one body reads -- it is the one caller of
    :func:`gated_skip_reason` that has no paths of its own -- and a gate built
    from the directory alone crashes the body it was meant to protect. Paths are
    relative to THIS family's root.

    An undeclared test still gates on the root alone, which is the old behaviour
    and the honest one for a body that searches for its input rather than naming
    it.
    """

    @pytest.fixture(name=f"{family}_dir")
    def fixture(request) -> str:
        required: list[str] = []
        for marker in request.node.iter_markers("artifacts"):
            required.extend(marker.args)

        reason = gated_skip_reason(*required, family=family)

        if reason is not None:
            pytest.skip(reason)

        directory, _why = resolve_artifacts(family=family)
        return directory

    return fixture


# The families. This is the set of ROOTS the test suite reads from -- the domain
# the resolver is defined over -- and not an exception list: a new entry here is
# a new tree on disk with its own provenance, never a per-test amendment.
#
# `artifacts`   -- the firmware images, the recovered tables and the patch
#                  corpus, `NMG2_ARTIFACTS`.
# `descriptors` -- the module descriptor and editor panel tables recovered from
#                  the shipped software, `NMG2_DESCRIPTORS`.
# `installers`  -- the vendor installer images the extractor reads,
#                  `NMG2_INSTALLERS`.
#
# They are separate because NO ONE DIRECTORY holds all three. A single variable
# resolving all of them is wrong for at least two of them on every machine.
ARTIFACT_FAMILIES = (DEFAULT_ARTIFACT_FAMILY, "descriptors", "installers")

artifacts_dir = _family_fixture(DEFAULT_ARTIFACT_FAMILY)
descriptors_dir = _family_fixture("descriptors")
installers_dir = _family_fixture("installers")
