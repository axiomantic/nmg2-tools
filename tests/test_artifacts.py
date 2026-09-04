"""The Python half of the ArtifactResolver.

Tier T0: every case here runs with ``NMG2_ARTIFACTS`` unset and needs no
firmware artifact of any kind.

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
    """The unset case and the missing-directory case have DISTINCT messages,
    so the two results must NOT be equal."""
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
    """The resolver never throws. The cases below are the inputs most likely
    to make a naive implementation raise."""
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


# ---------------------------------------------------------------------------
# The gate opens on the FILES the gated body reads, not on the directory alone.
#
# A gate that answers RUN as soon as a directory resolves lets a gated body
# raise `FileNotFoundError` where a skip WITH A REASON is required. The reason
# is the resolver's message 3, which already exists and already names the
# missing artifact -- a fourth message would be a second text for one meaning.
#
# The distinction these cases hold apart, and it is the whole point of them:
#   artifact ABSENT           -> SKIP, naming the path.
#   artifact PRESENT but WRONG -> RUN, and the body FAILS.
# A gate that answered SKIP to the second would hide every broken artifact.
# ---------------------------------------------------------------------------

REQUIRED_REL = "dsp/g2_module_descriptors.csv"


def _expected_missing_line(directory) -> str:
    return (
        "SKIPPED: firmware artifact not available "
        f"({REQUIRED_REL} not found under NMG2_ARTIFACTS: {directory})"
    )


def test_gated_skip_reason_skips_when_a_required_artifact_is_absent(tmp_path, monkeypatch):
    """The defect itself. The directory resolves and the file is not in it, so
    the gate must report SKIP with the path in the reason -- not RUN."""
    from nmg2_tools.artifacts import gated_skip_reason

    monkeypatch.setenv("NMG2_ARTIFACTS", str(tmp_path))

    assert gated_skip_reason(REQUIRED_REL) == _expected_missing_line(tmp_path)


def test_gated_skip_reason_names_the_first_absent_artifact_of_several(tmp_path, monkeypatch):
    """A body that opens two files states two paths. The reason names the one
    that is missing, so an operator is sent to the file that is actually
    absent rather than to the first path in the list."""
    from nmg2_tools.artifacts import gated_skip_reason

    present = tmp_path / "g2demo" / "g2_modules.json"
    present.parent.mkdir()
    present.write_text("[]")
    monkeypatch.setenv("NMG2_ARTIFACTS", str(tmp_path))

    reason = gated_skip_reason("g2demo/g2_modules.json", REQUIRED_REL)

    assert reason == _expected_missing_line(tmp_path)


def test_gated_skip_reason_runs_when_a_required_artifact_is_present_but_malformed(
    tmp_path, monkeypatch
):
    """The ABSENT/WRONG distinction, at the gate. A present artifact whose
    CONTENT is garbage must still report RUN, so that the body reaches it and
    FAILS. A gate that read the content would turn every broken artifact into
    a silent skip, which is worse than the defect it replaces."""
    from nmg2_tools.artifacts import gated_skip_reason

    malformed = tmp_path / "dsp" / "g2_module_descriptors.csv"
    malformed.parent.mkdir()
    malformed.write_text("this is not a descriptor table\n")
    monkeypatch.setenv("NMG2_ARTIFACTS", str(tmp_path))

    assert gated_skip_reason(REQUIRED_REL) is None


def test_gated_skip_reason_reports_the_unset_line_before_it_looks_for_files(monkeypatch):
    """With the variable unset there is no directory to look in, so the reason
    is section 18.5's line word for word and NOT a message naming a path under
    an empty root."""
    from nmg2_tools.artifacts import gated_skip_reason

    monkeypatch.delenv("NMG2_ARTIFACTS", raising=False)

    assert gated_skip_reason(REQUIRED_REL) == EXPECTED_SKIP_LINE


def test_the_conftest_fixture_skips_when_a_declared_artifact_is_absent(pytester, tmp_path, monkeypatch):
    """The fixture end to end. A gated test declares the paths its body opens
    with the `artifacts` marker; the fixture skips with the message that names
    the absent one, and the body does not run."""
    monkeypatch.setenv("NMG2_ARTIFACTS", str(tmp_path))

    pytester.makeconftest(_GENERATED_CONFTEST)
    pytester.makeini("[pytest]\nmarkers =\n    artifacts(*paths): declared\n")
    pytester.makepyfile(
        f"""
        import pytest

        @pytest.mark.artifacts({REQUIRED_REL!r})
        def test_a_gated_test(artifacts_dir):
            raise AssertionError("the gated body must not run")
        """
    )

    result = pytester.runpytest("-rs")

    result.assert_outcomes(skipped=1, passed=0, failed=0)
    assert _expected_missing_line(tmp_path) in result.stdout.str()


def test_the_conftest_fixture_lets_a_malformed_artifact_reach_the_body_and_fail(
    pytester, tmp_path, monkeypatch
):
    """The planted failure, end to end. The declared artifact is PRESENT and
    its content is garbage. The fixture must not skip: the body runs, the
    parse fails, and the verdict the caller reads is FAILED."""
    monkeypatch.setenv("NMG2_ARTIFACTS", str(tmp_path))
    malformed = tmp_path / "dsp" / "g2_module_descriptors.csv"
    malformed.parent.mkdir()
    malformed.write_text("not,a,descriptor,table\n")

    pytester.makeconftest(_GENERATED_CONFTEST)
    pytester.makeini("[pytest]\nmarkers =\n    artifacts(*paths): declared\n")
    pytester.makepyfile(
        f"""
        import csv
        import os
        import pytest

        @pytest.mark.artifacts({REQUIRED_REL!r})
        def test_a_gated_test(artifacts_dir):
            path = os.path.join(artifacts_dir, {REQUIRED_REL!r})
            with open(path, newline="") as handle:
                rows = list(csv.DictReader(handle))
            assert [int(row["p_words_0x24"]) for row in rows] == [6]
        """
    )

    result = pytester.runpytest("-rs")

    result.assert_outcomes(failed=1, skipped=0, passed=0)
    assert "SKIPPED: firmware artifact not available" not in result.stdout.str()


# ---------------------------------------------------------------------------
# One root per fixture FAMILY.
#
# `NMG2_ARTIFACTS` named two unrelated fixture families at once -- the
# descriptor and panel tables on one side, the vendor installer images on the
# other -- and no single directory holds both, so one of the two families was
# always looking in the wrong tree. A family is a ROOT, so each family gets its
# own variable: `NMG2_<FAMILY>`, uppercased. The default family is `artifacts`,
# which yields `NMG2_ARTIFACTS` unchanged.
#
# The rule that makes this safe is that a family NEVER falls back to another
# family's root. A resolver that searched a second root on a miss would answer
# with a file whose provenance no reader could reconstruct.
# ---------------------------------------------------------------------------

DESCRIPTORS_FAMILY = "descriptors"


def test_a_family_resolves_through_its_own_variable(tmp_path, monkeypatch):
    monkeypatch.setenv("NMG2_DESCRIPTORS", str(tmp_path))

    directory, why = resolve_artifacts(family=DESCRIPTORS_FAMILY)

    assert directory == str(tmp_path)
    assert why == ""


def test_a_family_does_not_fall_back_to_the_base_variable(tmp_path, monkeypatch):
    """Provenance. `NMG2_ARTIFACTS` names a real directory and the family's own
    variable is unset. The family must report UNSET rather than answer with a
    directory belonging to a different family -- a resolver that searched a
    second root on a miss would make the source of a fixture unknowable."""
    monkeypatch.setenv("NMG2_ARTIFACTS", str(tmp_path))
    monkeypatch.delenv("NMG2_DESCRIPTORS", raising=False)

    directory, why = resolve_artifacts(family=DESCRIPTORS_FAMILY)

    assert directory == ""
    assert why == "firmware artifact not available (NMG2_DESCRIPTORS unset)"


def test_the_default_family_is_the_base_variable(tmp_path, monkeypatch):
    """The negative case for the rule above: naming the default family
    explicitly must be identical to naming no family at all, or every existing
    caller would change meaning."""
    monkeypatch.setenv("NMG2_ARTIFACTS", str(tmp_path))
    monkeypatch.delenv("NMG2_DESCRIPTORS", raising=False)

    assert resolve_artifacts(family="artifacts") == (str(tmp_path), "")


def test_a_family_message_two_names_the_family_variable(monkeypatch):
    monkeypatch.setenv("NMG2_DESCRIPTORS", "/nmg2/no/such/directory/FAMILY")

    directory, why = resolve_artifacts(family=DESCRIPTORS_FAMILY)

    assert directory == ""
    assert why == (
        "firmware artifact not available "
        "(NMG2_DESCRIPTORS names no directory: /nmg2/no/such/directory/FAMILY)"
    )


def test_a_family_message_three_names_the_family_variable(tmp_path, monkeypatch):
    monkeypatch.setenv("NMG2_DESCRIPTORS", str(tmp_path))

    directory, why = resolve_artifacts(REQUIRED_REL, family=DESCRIPTORS_FAMILY)

    assert directory == ""
    assert why == (
        "firmware artifact not available "
        f"({REQUIRED_REL} not found under NMG2_DESCRIPTORS: {tmp_path})"
    )


def test_gated_skip_reason_gates_on_the_family_root(tmp_path, monkeypatch):
    """`gated_skip_reason` keeps its meaning per family: the root that must
    resolve and the paths that must exist are the family's, not the base's."""
    from nmg2_tools.artifacts import gated_skip_reason

    monkeypatch.setenv("NMG2_ARTIFACTS", str(tmp_path))
    monkeypatch.delenv("NMG2_DESCRIPTORS", raising=False)

    assert gated_skip_reason(REQUIRED_REL, family=DESCRIPTORS_FAMILY) == (
        "SKIPPED: firmware artifact not available (NMG2_DESCRIPTORS unset)"
    )


def test_gated_skip_reason_names_the_absent_path_under_the_family_root(tmp_path, monkeypatch):
    """The negative case for the one above: the family root DOES resolve, so
    the reason must be message 3 naming the declared path, not the unset line."""
    from nmg2_tools.artifacts import gated_skip_reason

    monkeypatch.setenv("NMG2_DESCRIPTORS", str(tmp_path))

    assert gated_skip_reason(REQUIRED_REL, family=DESCRIPTORS_FAMILY) == (
        "SKIPPED: firmware artifact not available "
        f"({REQUIRED_REL} not found under NMG2_DESCRIPTORS: {tmp_path})"
    )


def test_gated_skip_reason_is_none_when_the_family_root_holds_the_path(tmp_path, monkeypatch):
    """Without this, every assertion above would hold for a per-family gate
    that skipped unconditionally."""
    from nmg2_tools.artifacts import gated_skip_reason

    present = tmp_path / "dsp" / "g2_module_descriptors.csv"
    present.parent.mkdir()
    present.write_text("p_ptr,x_words_0x1C,y_words_0x20,p_words_0x24\n")
    monkeypatch.setenv("NMG2_DESCRIPTORS", str(tmp_path))

    assert gated_skip_reason(REQUIRED_REL, family=DESCRIPTORS_FAMILY) is None


# The fixture half. A test declares its family by requesting that family's
# fixture -- the same parameter it already had to write to get a directory at
# all -- and declares the files its body opens with the `artifacts` marker.
# There are exactly two declarations and neither is a per-file table: nothing
# anywhere maps a path to a family.

_FAMILY_CONFTEST = "from tests.conftest import descriptors_dir  # noqa: F401\n"


def test_the_family_fixture_skips_with_the_family_variable_in_the_reason(
    pytester, tmp_path, monkeypatch
):
    monkeypatch.setenv("NMG2_ARTIFACTS", str(tmp_path))
    monkeypatch.delenv("NMG2_DESCRIPTORS", raising=False)

    pytester.makeconftest(_FAMILY_CONFTEST)
    pytester.makepyfile(
        """
        def test_a_gated_test(descriptors_dir):
            raise AssertionError("the gated body must not run")
        """
    )

    result = pytester.runpytest("-rs")

    result.assert_outcomes(skipped=1, passed=0, failed=0)
    assert "SKIPPED: firmware artifact not available (NMG2_DESCRIPTORS unset)" in result.stdout.str()


def test_the_family_fixture_runs_the_body_from_the_family_root(pytester, tmp_path, monkeypatch):
    """The negative case for the fixture, and the provenance case in one: the
    body runs, and the directory it is handed is the FAMILY's root even though
    `NMG2_ARTIFACTS` names a different existing directory."""
    family_root = tmp_path / "family"
    (family_root / "dsp").mkdir(parents=True)
    (family_root / "dsp" / "g2_module_descriptors.csv").write_text("p_ptr\n")
    base_root = tmp_path / "base"
    base_root.mkdir()
    monkeypatch.setenv("NMG2_ARTIFACTS", str(base_root))
    monkeypatch.setenv("NMG2_DESCRIPTORS", str(family_root))

    pytester.makeconftest(_FAMILY_CONFTEST)
    pytester.makeini("[pytest]\nmarkers =\n    artifacts(*paths): declared\n")
    pytester.makepyfile(
        f"""
        import pytest

        @pytest.mark.artifacts({REQUIRED_REL!r})
        def test_a_gated_test(descriptors_dir):
            assert descriptors_dir == {str(family_root)!r}
        """
    )

    result = pytester.runpytest("-rs")

    result.assert_outcomes(passed=1, skipped=0, failed=0)
    assert "SKIPPED: firmware artifact not available" not in result.stdout.str()


def test_the_family_fixture_skips_when_a_declared_path_is_absent_from_the_family_root(
    pytester, tmp_path, monkeypatch
):
    """The marker's paths are relative to the FAMILY's root. The declared file
    exists under `NMG2_ARTIFACTS` and not under the family root, so the verdict
    must be a skip naming the path under the family root."""
    family_root = tmp_path / "family"
    family_root.mkdir()
    base_root = tmp_path / "base"
    (base_root / "dsp").mkdir(parents=True)
    (base_root / "dsp" / "g2_module_descriptors.csv").write_text("p_ptr\n")
    monkeypatch.setenv("NMG2_ARTIFACTS", str(base_root))
    monkeypatch.setenv("NMG2_DESCRIPTORS", str(family_root))

    pytester.makeconftest(_FAMILY_CONFTEST)
    pytester.makeini("[pytest]\nmarkers =\n    artifacts(*paths): declared\n")
    pytester.makepyfile(
        f"""
        import pytest

        @pytest.mark.artifacts({REQUIRED_REL!r})
        def test_a_gated_test(descriptors_dir):
            raise AssertionError("the gated body must not run")
        """
    )

    result = pytester.runpytest("-rs")

    result.assert_outcomes(skipped=1, passed=0, failed=0)
    assert (
        "SKIPPED: firmware artifact not available "
        f"({REQUIRED_REL} not found under NMG2_DESCRIPTORS: {family_root})"
    ) in result.stdout.str()


# ---------------------------------------------------------------------------
# The SUITE announces its skips.
#
# Section 18.5 makes ONE gated test skip with a reason. It says nothing about
# the RUN, and the run is what a reader looks at: a suite reporting
# `929 passed, 12 skipped` shows a green summary over deliverables that were
# never exercised, and a skip whose silence is indistinguishable from success
# is not a gate. THE LIMIT: **a skip changes the verdict's WORDING and never
# its exit code.** Scoring it would change what `if pytest; then` means for
# every existing caller, which is a separate decision from making the skip
# visible, and this is only the second of the two.
#
# The sentence is `A skipped test is not a clean test.`
# ---------------------------------------------------------------------------


def test_the_skip_verdict_is_empty_when_nothing_skipped():
    """The negative case, and it is the one that matters most: a function that
    returned a verdict unconditionally would put a SKIPPED notice on a run that
    skipped nothing, and every positive case below would still pass."""
    from nmg2_tools.artifacts import skip_verdict

    assert skip_verdict({}) == ""


def test_the_skip_verdict_names_every_skipped_test_and_its_reason():
    from nmg2_tools.artifacts import skip_verdict

    assert skip_verdict(
        {
            "tests/test_modulemap.py::test_a": "SKIPPED: firmware artifact not available (NMG2_ARTIFACTS unset)",
            "tests/test_sigscan.py::test_b": "no descriptor table",
        }
    ) == (
        "SKIP VERDICT: 2 tests SKIPPED. A skipped test is not a clean test.\n"
        "  tests/test_modulemap.py::test_a — SKIPPED: firmware artifact not available (NMG2_ARTIFACTS unset)\n"
        "  tests/test_sigscan.py::test_b — no descriptor table"
    )


def test_the_skip_verdict_says_test_in_the_singular_for_one_skip():
    """The noun agrees with the count. A verdict reading `1 tests SKIPPED` is a
    verdict nobody trusts."""
    from nmg2_tools.artifacts import skip_verdict

    assert skip_verdict({"tests/test_x.py::test_one": "a reason"}) == (
        "SKIP VERDICT: 1 test SKIPPED. A skipped test is not a clean test.\n"
        "  tests/test_x.py::test_one — a reason"
    )


_VERDICT_CONFTEST = (
    "from tests.conftest import artifacts_dir  # noqa: F401\n"
    "from tests.conftest import pytest_terminal_summary  # noqa: F401\n"
)


def test_the_run_announces_a_gated_skip_and_the_exit_code_is_unchanged(
    pytester, monkeypatch
):
    """Drives the real hook in tests/conftest.py through a real pytest run.

    The exit-code assertion is half of this test and not a decoration: the
    borrowed limit is that the verdict's WORDING changes and its exit code does
    not, and a hook that failed the run would silently change what every
    existing caller of `pytest` means."""
    monkeypatch.delenv("NMG2_ARTIFACTS", raising=False)

    pytester.makeconftest(_VERDICT_CONFTEST)
    pytester.makepyfile(
        """
        def test_a_gated_test(artifacts_dir):
            raise AssertionError("the gated body must not run")
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(skipped=1, passed=0, failed=0)
    assert result.ret == 0
    assert (
        "SKIP VERDICT: 1 test SKIPPED. A skipped test is not a clean test."
        in result.stdout.str()
    )
    assert EXPECTED_SKIP_LINE in result.stdout.str()


def test_a_run_with_no_skips_prints_no_verdict(pytester, tmp_path, monkeypatch):
    """The negative case for the hook. Without it the hook could print the
    notice on every run and the case above would still pass."""
    monkeypatch.setenv("NMG2_ARTIFACTS", str(tmp_path))

    pytester.makeconftest(_VERDICT_CONFTEST)
    pytester.makepyfile(
        """
        import os

        def test_a_gated_test(artifacts_dir):
            assert os.path.isdir(artifacts_dir)
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1, skipped=0, failed=0)
    assert result.ret == 0
    assert "SKIP VERDICT" not in result.stdout.str()
