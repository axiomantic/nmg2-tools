"""Task REPO-5, the Python half of the ArtifactResolver.

Tier T0: every case here runs with ``NMG2_ARTIFACTS`` unset and needs no
firmware artifact of any kind.

Plan section 9.2, REPO-5. Design sections 4.2 and 18.5.

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

EXPECTED_MESSAGE = "firmware artifact not available (NMG2_ARTIFACTS unset)"


def test_unset_returns_empty_and_the_exact_message(monkeypatch):
    monkeypatch.delenv("NMG2_ARTIFACTS", raising=False)

    directory, why = resolve_artifacts()

    assert directory == ""
    assert why == EXPECTED_MESSAGE


def test_missing_directory_gives_the_same_result(monkeypatch):
    """Design section 4.2 gives the unset case and the missing-directory case
    ONE message, so the two results must be equal and not merely both falsey."""
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


def test_an_existing_directory_resolves(tmp_path, monkeypatch):
    """The negative case. Section 5.2 rule 6: every counter a test asserts to be
    zero needs a companion case that drives it above zero. Without this, all of
    the assertions above would hold for a resolver that always fails."""
    monkeypatch.setenv("NMG2_ARTIFACTS", str(tmp_path))

    directory, why = resolve_artifacts()

    assert directory == str(tmp_path)
    assert why == ""
