"""Task REPO-5, the Python half of the ArtifactResolver.

Tier T0: every case here runs with ``NMG2_ARTIFACTS`` unset and needs no
firmware artifact of any kind.

Plan section 9.2, REPO-5. Design sections 4.2 and 18.5.

The C++ half lives at ``source/nord/g2/g2Lib/artifactResolver.{h,cpp}`` in the
``gearmulator`` fork and ``source/nord/g2/g2Lib/test/t0_artifact_resolver.cpp``
asserts the identical properties. The message literals below are written out in
full ON PURPOSE, exactly as the C++ test writes them out in full: comparing
against a full literal in each language is what makes "word for word and
identically in both languages" a falsifiable claim. Deriving them from the
module under test would assert only that the module equals itself.
"""

import pytest

from nmg2_tools.artifacts import resolve_artifacts

# The generated conftest below IMPORTS the real fixture rather than copying the
# text of tests/conftest.py. A copy would duplicate `pytest_plugins`, which
# pytest accepts only in the initial conftest, and -- worse -- it would let the
# real fixture rot while a stale copy went on passing.
_GENERATED_CONFTEST = "from tests.conftest import artifacts_dir  # noqa: F401\n"

# The expected messages, written out in full.
EXPECTED_UNSET = "firmware artifact not available (NMG2_ARTIFACTS unset)"
EXPECTED_BAD_PATH = "firmware artifact not available (NMG2_ARTIFACTS names no directory: /nmg2/no/such/directory/REPO-5)"


def test_unset_returns_empty_and_the_exact_message(monkeypatch):
    monkeypatch.delenv("NMG2_ARTIFACTS", raising=False)

    directory, why = resolve_artifacts()

    assert directory == ""
    assert why == EXPECTED_UNSET


def test_missing_directory_returns_message_two(monkeypatch):
    """Design section 4.2 gives the unset case and the missing-directory case
    DISTINCT messages, so the two results must NOT be equal."""
    monkeypatch.setenv("NMG2_ARTIFACTS", "/nmg2/no/such/directory/REPO-5")

    directory, why = resolve_artifacts()

    assert directory == ""
    assert why == EXPECTED_BAD_PATH


def test_empty_value_is_treated_as_unset(monkeypatch):
    """The C++ half must accept an empty value as unset, because Windows has no
    other way to remove a variable through ``_putenv_s``. The Python half agrees
    so that the two halves do not mean different things on the same input."""
    monkeypatch.setenv("NMG2_ARTIFACTS", "")

    assert resolve_artifacts() == ("", EXPECTED_UNSET)


def test_a_path_that_is_a_file_and_not_a_directory_returns_message_two(tmp_path, monkeypatch):
    not_a_directory = tmp_path / "artifacts.txt"
    not_a_directory.write_text("not a directory\n")
    expected = f"firmware artifact not available (NMG2_ARTIFACTS names no directory: {not_a_directory})"
    monkeypatch.setenv("NMG2_ARTIFACTS", str(not_a_directory))

    directory, why = resolve_artifacts()

    assert directory == ""
    assert why == expected


def test_directory_without_named_artifact_returns_message_three(tmp_path, monkeypatch):
    monkeypatch.setenv("NMG2_ARTIFACTS", str(tmp_path))

    directory, why = resolve_artifacts("firmware.bin")

    assert directory == ""
    assert why == f"firmware artifact not available (firmware.bin not found under NMG2_ARTIFACTS: {tmp_path})"


def test_message_three_wording_with_a_different_name(tmp_path, monkeypatch):
    """A second witness for message 3's wording. The test above pins the
    wording with ``firmware.bin``; a rewrite that happens to align with
    ``firmware.bin`` would slip through a single-test check. Message 3 is the
    most error-prone of the three because it echoes both ``name`` and the
    directory in one format string, so a second name exercises the format
    against a different interpolation and a third pair of substitution
    positions. The two tests are independent -- either one catches a drift
    the other misses."""
    monkeypatch.setenv("NMG2_ARTIFACTS", str(tmp_path))

    directory, why = resolve_artifacts("different_artifact.bin")

    assert directory == ""
    assert why == f"firmware artifact not available (different_artifact.bin not found under NMG2_ARTIFACTS: {tmp_path})"


def test_directory_with_named_artifact_returns_success(tmp_path, monkeypatch):
    artifact = tmp_path / "firmware.bin"
    artifact.write_text("not real firmware\n")
    monkeypatch.setenv("NMG2_ARTIFACTS", str(tmp_path))

    directory, why = resolve_artifacts("firmware.bin")

    assert directory == str(tmp_path)
    assert why == ""


def test_never_raises(monkeypatch, tmp_path):
    """Design section 4.2: the resolver never throws. The cases below are the
    inputs most likely to make a naive implementation raise."""
    # A NUL byte is not among these values on purpose: `os.environ` refuses to
    # hold one, so no caller can present that input and a case for it would test
    # the test harness rather than the module.
    for value in ("", "/nmg2/no/such/directory/REPO-5", "relative/path", "/"):
        monkeypatch.setenv("NMG2_ARTIFACTS", value)
        try:
            resolve_artifacts()
        except Exception as exc:  # noqa: BLE001 - the assertion IS that nothing escapes
            pytest.fail(f"resolve_artifacts() raised on {value!r}: {exc!r}")

    # The same rule on the ``name`` argument. A defensive ``raise`` on a path
    # separator in ``name`` would fire here: ``subdir/file.bin`` carries ``/``,
    # ``../etc/passwd`` carries ``..``, ``/absolute/path`` is absolute, and
    # ``./relative`` starts with a dot. ``tmp_path`` is a real directory so
    # the ``name`` path is actually consulted and message 3 can fire; without
    # that, the function would return at the unset -- or no-directory -- check
    # and the name would never reach the raise.
    for name in ("subdir/file.bin", "../etc/passwd", "/absolute/path", "./relative"):
        monkeypatch.setenv("NMG2_ARTIFACTS", str(tmp_path))
        try:
            resolve_artifacts(name)
        except Exception as exc:  # noqa: BLE001 - the assertion IS that nothing escapes
            pytest.fail(f"resolve_artifacts({name!r}) raised: {exc!r}")


def test_an_existing_directory_resolves(tmp_path, monkeypatch):
    """The negative case. Section 5.2 rule 6: every counter a test asserts to be
    zero needs a companion case that drives it above zero. Without this, all of
    the assertions above would hold for a resolver that always fails."""
    monkeypatch.setenv("NMG2_ARTIFACTS", str(tmp_path))

    directory, why = resolve_artifacts()

    assert directory == str(tmp_path)
    assert why == ""


# ---------------------------------------------------------------------------
# Task REPO-7, the Python half of the skip discipline.
#
# REPO-7 depends on REPO-5 and both are repo-track tasks, so extending this
# module and tests/conftest.py is a track-internal order and not a race. Plan
# section 7.4.2 gives that shape for every file with one owner and a later
# writer inside the same track.
#
# The plan gives REPO-7 only a ctest check. tests/conftest.py would
# otherwise ship with no check of its own, so the cases below drive it: the pure
# function directly, and the fixture through pytest's own `pytester`.
# ---------------------------------------------------------------------------

EXPECTED_SKIP_LINE = "SKIPPED: firmware artifact not available (NMG2_ARTIFACTS unset)"


def test_gated_skip_reason_is_the_exact_line_when_unset(monkeypatch):
    from nmg2_tools.artifacts import gated_skip_reason

    monkeypatch.delenv("NMG2_ARTIFACTS", raising=False)

    assert gated_skip_reason() == EXPECTED_SKIP_LINE


def test_gated_skip_reason_is_the_same_line_for_a_missing_directory(monkeypatch):
    from nmg2_tools.artifacts import gated_skip_reason

    monkeypatch.setenv("NMG2_ARTIFACTS", "/nmg2/no/such/directory/REPO-7")

    assert gated_skip_reason() == EXPECTED_SKIP_LINE


def test_gated_skip_reason_is_none_when_the_artifact_resolves(tmp_path, monkeypatch):
    """The negative case. Without it, `gated_skip_reason` could return the line
    unconditionally and both assertions above would still hold -- every gated
    test in the repository would then skip for ever and report nothing."""
    from nmg2_tools.artifacts import gated_skip_reason

    monkeypatch.setenv("NMG2_ARTIFACTS", str(tmp_path))

    assert gated_skip_reason() is None


def test_the_skip_line_is_the_prefix_and_the_message_and_not_a_second_literal():
    """The C++ half builds section 18.5's line by concatenating section 4.2's
    message onto the prefix, so that the message has one text. This asserts the
    Python half does the same rather than spelling the whole line out twice."""
    from nmg2_tools.artifacts import (
        ARTIFACT_UNSET_MESSAGE,
        GATED_SKIP_PREFIX,
        gated_skip_line,
    )

    assert gated_skip_line() == GATED_SKIP_PREFIX + ARTIFACT_UNSET_MESSAGE
    assert gated_skip_line() == EXPECTED_SKIP_LINE


def test_the_conftest_fixture_skips_with_the_exact_line(pytester, monkeypatch):
    """Drives tests/conftest.py itself. A gated test that cannot run must skip
    WITH A REASON, and the reason must be section 18.5's line word for word."""
    monkeypatch.delenv("NMG2_ARTIFACTS", raising=False)

    pytester.makeconftest(_GENERATED_CONFTEST)
    pytester.makepyfile(
        """
        def test_a_gated_test(artifacts_dir):
            raise AssertionError("the gated body must not run")
        """
    )

    result = pytester.runpytest("-rs")

    result.assert_outcomes(skipped=1, passed=0, failed=0)
    assert EXPECTED_SKIP_LINE in result.stdout.str()


def test_the_conftest_fixture_runs_the_body_when_the_artifact_resolves(pytester, tmp_path, monkeypatch):
    """The negative case for the fixture. Without it the fixture could skip
    unconditionally and the case above would still pass."""
    monkeypatch.setenv("NMG2_ARTIFACTS", str(tmp_path))

    pytester.makeconftest(_GENERATED_CONFTEST)
    pytester.makepyfile(
        """
        import os

        def test_a_gated_test(artifacts_dir):
            assert os.path.isdir(artifacts_dir)
        """
    )

    result = pytester.runpytest("-rs")

    result.assert_outcomes(passed=1, skipped=0, failed=0)
    assert EXPECTED_SKIP_LINE not in result.stdout.str()
