"""The Python half of the ArtifactResolver.

Tier T0: every case here runs with ``NMG2_ARTIFACTS`` unset and needs no
firmware artifact of any kind.

The C++ half lives at ``source/nord/g2/g2Lib/artifactResolver.{h,cpp}`` in the
``gearmulator`` fork and ``source/nord/g2/g2Lib/test/t0_artifact_resolver.cpp``
asserts the identical properties. The message literal below is written out in
full ON PURPOSE, exactly as the C++ test writes it out in full: comparing
against a full literal in each language is what makes "word for word and
identically in both languages" a falsifiable claim. Deriving it from the module
under test would assert only that the module equals itself.
"""

import pytest

from nmg2_tools.artifacts import resolve_artifacts

# The generated conftest below IMPORTS the real fixture rather than copying the
# text of tests/conftest.py. A copy would duplicate `pytest_plugins`, which
# pytest accepts only in the initial conftest, and -- worse -- it would let the
# real fixture rot while a stale copy went on passing.
_GENERATED_CONFTEST = "from tests.conftest import artifacts_dir  # noqa: F401\n"

EXPECTED_MESSAGE = "firmware artifact not available (NMG2_ARTIFACTS unset)"


def test_unset_returns_empty_and_the_exact_message(monkeypatch):
    monkeypatch.delenv("NMG2_ARTIFACTS", raising=False)

    directory, why = resolve_artifacts()

    assert directory == ""
    assert why == EXPECTED_MESSAGE


def test_missing_directory_gives_the_same_result(monkeypatch):
    """The unset case and the missing-directory case get ONE message, so the
    two results must be equal and not merely both falsey."""
    monkeypatch.delenv("NMG2_ARTIFACTS", raising=False)
    unset_result = resolve_artifacts()

    monkeypatch.setenv("NMG2_ARTIFACTS", "/nmg2/no/such/directory/REPO-5")
    missing_result = resolve_artifacts()

    assert missing_result == ("", EXPECTED_MESSAGE)
    assert missing_result == unset_result


def test_empty_value_is_treated_as_unset(monkeypatch):
    """The C++ half must accept an empty value as unset, because Windows has no
    other way to remove a variable through ``_putenv_s``. The Python half agrees
    so that the two halves do not mean different things on the same input."""
    monkeypatch.setenv("NMG2_ARTIFACTS", "")

    assert resolve_artifacts() == ("", EXPECTED_MESSAGE)


def test_a_path_that_is_a_file_and_not_a_directory_gives_the_same_result(tmp_path, monkeypatch):
    not_a_directory = tmp_path / "artifacts.txt"
    not_a_directory.write_text("not a directory\n")
    monkeypatch.setenv("NMG2_ARTIFACTS", str(not_a_directory))

    assert resolve_artifacts() == ("", EXPECTED_MESSAGE)


def test_never_raises(monkeypatch):
    """The resolver never throws. The cases below are the inputs most likely to
    make a naive implementation raise."""
    # A NUL byte is not among these values on purpose: `os.environ` refuses to
    # hold one, so no caller can present that input and a case for it would test
    # the test harness rather than the module.
    for value in ("", "/nmg2/no/such/directory/REPO-5", "relative/path", "/"):
        monkeypatch.setenv("NMG2_ARTIFACTS", value)
        try:
            resolve_artifacts()
        except Exception as exc:  # noqa: BLE001 - the assertion IS that nothing escapes
            pytest.fail(f"resolve_artifacts() raised on {value!r}: {exc!r}")


def test_an_existing_directory_resolves(tmp_path, monkeypatch):
    """The negative case. Every counter a test asserts to be zero needs a
    companion case that drives it above zero. Without this, all of the
    assertions above would hold for a resolver that always fails."""
    monkeypatch.setenv("NMG2_ARTIFACTS", str(tmp_path))

    directory, why = resolve_artifacts()

    assert directory == str(tmp_path)
    assert why == ""


# ---------------------------------------------------------------------------
# The Python half of the skip discipline.
#
# tests/conftest.py would otherwise ship with no check of its own, so the cases
# below drive it: the pure function directly, and the fixture through pytest's
# own `pytester`.
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
    """The C++ half builds the line by concatenating the message onto the
    prefix, so that the message has one text. This asserts the
    Python half does the same rather than spelling the whole line out twice."""
    from nmg2_tools.artifacts import (
        ARTIFACT_UNAVAILABLE_MESSAGE,
        GATED_SKIP_PREFIX,
        gated_skip_line,
    )

    assert gated_skip_line() == GATED_SKIP_PREFIX + ARTIFACT_UNAVAILABLE_MESSAGE
    assert gated_skip_line() == EXPECTED_SKIP_LINE


def test_the_conftest_fixture_skips_with_the_exact_line(pytester, monkeypatch):
    """Drives tests/conftest.py itself. A gated test that cannot run must skip
    WITH A REASON, and the reason must be the skip line word for word."""
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
