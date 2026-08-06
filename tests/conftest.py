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

from nmg2_tools.artifacts import gated_skip_reason, resolve_artifacts

# `pytester` lets tests/test_artifacts.py drive the fixture below in a real
# pytest run rather than assert about it from the outside. Plan section 18.7:
# a test that passes when the code is broken is worse than no test, and an
# untested fixture is exactly that.
pytest_plugins = ["pytester"]


@pytest.fixture
def artifacts_dir() -> str:
    """The directory holding the Clavia-derived artifacts, or a skip.

    The skip reason is section 18.5's line WORD FOR WORD, prefix included. The
    prefix is carried inside the reason on purpose: pytest's own report line
    reads ``SKIPPED [1] file:line: <reason>``, so without it the required
    literal would never appear in the job output, and design section 18.5 step 2
    asks for the literal.
    """
    reason = gated_skip_reason()

    if reason is not None:
        pytest.skip(reason)

    directory, _why = resolve_artifacts()
    return directory
