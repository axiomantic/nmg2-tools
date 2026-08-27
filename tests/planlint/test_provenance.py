"""Tests for the provenance lint.

The lint asserts two properties and it is the tests' job to keep them apart,
because only one of them is about copying:

  * an IMPORTED ARTIFACT — a copyleft licence grant or SPDX identifier sitting
    in an MIT repository — is a fact about the bytes and is detected;
  * a MISSING RECORD is a fact about the prose. A module that restates an
    outside party's format and says nothing about where the format came from
    has no control on it at all.

Neither property is contamination. Reading a copyleft source leaves no trace in
the output, so no test here may be read as evidence that none was read.
"""

import unittest

from tests.planlint.support import fixture_path

from planlint import provenance


def run(tree):
    return provenance.run(fixture_path(tree))


class GoodTreeTest(unittest.TestCase):
    def test_the_good_tree_reports_nothing(self):
        result = run("repo_provenance_good")

        self.assertEqual(result.findings, [])
        self.assertEqual(result.examined, 4)
        self.assertEqual(
            result.examined_label,
            "files (0 excluded as the detector's own source, 0 excluded as "
            "planted evidence)",
        )

    def test_the_good_tree_is_not_clean_by_examining_nothing(self):
        """A tree the walk cannot see produces the same empty finding list as a
        tree with nothing wrong. The count separates them."""
        result = run("repo_provenance_good")

        self.assertEqual(result.failed, False)
        self.assertGreater(result.examined, 0)


class BadTreeTest(unittest.TestCase):
    def test_every_breach_is_reported_and_nothing_else(self):
        result = run("repo_provenance_bad")

        self.assertEqual(
            sorted((f.rule, f.evidence) for f in result.findings),
            [
                (
                    "imported-copyleft-artifact",
                    "`nmg2_tools/spdx_ok.py` line 1 carries an SPDX identifier naming "
                    "`GPL-2.0-or-later`",
                ),
                (
                    "imported-copyleft-artifact",
                    "`vendor/liblzo_copy.c` line 5 carries the grant text `is free "
                    "software; you can redistribute it and/or modify`",
                ),
                (
                    "incomplete-provenance-record",
                    "`nmg2_tools/half.py` carries the heading but no statement that no "
                    "line of another implementation is copied, transliterated or "
                    "paraphrased",
                ),
                (
                    "missing-provenance-record",
                    "`nmg2_tools/decoder.py` handles external binary data (`decode` is "
                    "annotated `bytes`) and its module docstring carries no line "
                    "reading `because the licence makes it matter`",
                ),
                (
                    "missing-provenance-record",
                    "`nmg2_tools/isa.py` names the copyleft licence `GPL-3.0` and its "
                    "module docstring carries no line reading `because the licence "
                    "makes it matter`",
                ),
            ],
        )

    def test_the_bad_tree_fails_the_run(self):
        self.assertEqual(run("repo_provenance_bad").failed, True)

    def test_a_complete_record_silences_only_the_record_rules(self):
        """`spdx_ok.py` carries a complete record AND an imported SPDX line. The
        record answers the record rules and answers nothing about the artifact,
        so exactly one finding names it."""
        named = sorted(
            f.rule
            for f in run("repo_provenance_bad").findings
            if "spdx_ok.py" in f.evidence
        )

        self.assertEqual(named, ["imported-copyleft-artifact"])


class PopulationTest(unittest.TestCase):
    """Which files the record obligation reaches, asserted rather than assumed.

    Under-inclusion is the failure that matters: a module the predicate never
    reaches is exempt in silence, which is the shape the lint exists to close.
    """

    def test_a_module_with_no_trigger_is_asked_for_no_record(self):
        """`plain.py` has no record and is not a finding. Were the obligation
        universal this would redden, and the record rules would then be
        satisfiable only by boilerplate."""
        result = run("repo_provenance_good")

        self.assertEqual([f for f in result.findings if "plain.py" in f.evidence], [])

    def test_test_code_is_outside_the_record_obligation(self):
        """`tests/reader_checks.py` is annotated `bytes` and carries no record.
        It is examined by the artifact scan and exempt from the record rules."""
        result = run("repo_provenance_good")

        self.assertEqual(
            [f for f in result.findings if "reader_checks.py" in f.evidence], []
        )

    def test_the_predicate_names_both_triggers_and_nothing_else(self):
        self.assertEqual(
            provenance.record_triggers(
                fixture_path("repo_provenance_bad") / "nmg2_tools" / "decoder.py"
            ),
            ["handles external binary data (`decode` is annotated `bytes`)"],
        )
        self.assertEqual(
            provenance.record_triggers(
                fixture_path("repo_provenance_bad") / "nmg2_tools" / "isa.py"
            ),
            ["names the copyleft licence `GPL-3.0`"],
        )
        self.assertEqual(
            provenance.record_triggers(
                fixture_path("repo_provenance_good") / "nmg2_tools" / "plain.py"
            ),
            [],
        )


class HouseFormTest(unittest.TestCase):
    """The record form is read off the records this repository already carries,
    not recalled. A change to the form that leaves any carrier behind reddens
    here, and so does a new carrier that this list does not name."""

    def test_every_shipped_record_satisfies_the_form_the_lint_requires(self):
        import pathlib

        package = pathlib.Path(provenance.__file__).resolve().parents[1] / "nmg2_tools"
        carriers = sorted(
            path.name
            for path in package.glob("*.py")
            if provenance.HEADING in path.read_text(encoding="utf-8")
        )

        self.assertEqual(
            carriers,
            [
                "checksum.py",
                "container.py",
                "dsp56k_dis.py",
                "flashimage.py",
                "lzo1x.py",
                "pch2.py",
                "pe.py",
                "rsrc.py",
                "sigscan.py",
                "synth_pch2.py",
            ],
        )
        for name in carriers:
            with self.subTest(module=name):
                self.assertEqual(provenance.record_defects(package / name), [])


class SelfScanTest(unittest.TestCase):
    """The lint held against the repository it ships in.

    A lint that is red on its own tree is a lint whose own project does not
    obey it, and until this test existed nothing read the two together: the
    fixture trees are written to be red or green on purpose, and
    `HouseFormTest` reads only the modules that already carry a record, so a
    module that carries none was outside every test here.
    """

    def result(self):
        import pathlib

        root = pathlib.Path(provenance.__file__).resolve().parents[1]
        return root, provenance.run(root)

    def test_no_shipped_module_of_this_repository_owes_a_record(self):
        _root, result = self.result()
        self.assertEqual(
            sorted(
                f.evidence
                for f in result.findings
                if f.rule in {"missing-provenance-record", "incomplete-provenance-record"}
            ),
            [],
        )

    def test_no_copyleft_grant_sits_anywhere_in_this_repository(self):
        """The artifact scan reads test code on purpose. The only copyleft
        grants this repository holds are the lint's own negative fixtures, and
        those declare themselves planted evidence, so the scan over the
        repository reports nothing at all."""
        _root, result = self.result()
        self.assertEqual(
            sorted(
                f.evidence
                for f in result.findings
                if f.rule == "imported-copyleft-artifact"
            ),
            [],
        )

    def test_the_lint_is_green_on_the_repository_it_ships_in(self):
        """The verdict a consumer reads. `planlint --repo . --only provenance`
        exits on `failed`, and a lint whose own repository fails it is a lint
        its own project does not obey."""
        _root, result = self.result()
        self.assertEqual([f.rule for f in result.findings], [])
        self.assertEqual(result.failed, False)

    def test_the_self_scan_is_not_clean_by_reading_nothing(self):
        """The two zeroes above need a known positive, and after the planted
        fixtures are excluded the repository itself no longer supplies one.

        Three separate things are asserted, because a scan that walked nothing,
        a scan that never reached the fixtures, and a scan whose text detector
        does not fire would all satisfy the zeroes in silence: the walk read
        files; it reached the planted trees and SAID SO in the label it prints;
        and the same fixture tree, scanned as its own root, is red. That last
        one is the known positive and it comes from the same population — the
        very files the self-scan excluded.
        """
        _root, result = self.result()

        self.assertGreater(result.examined, 0)
        self.assertNotIn(", 0 excluded as planted evidence", result.examined_label)

        planted = run("repo_provenance_bad")
        self.assertGreater(
            len([f for f in planted.findings if f.rule == "imported-copyleft-artifact"]),
            0,
        )

    def test_the_marker_cannot_exempt_a_tree_from_a_scan_aimed_at_it(self):
        """The exclusion would be an off switch if a directory could carry a
        marker and go unread by every scan. It cannot: the marker is read only
        when the directory sits BELOW the root."""
        self.assertEqual(
            sorted(
                path.name
                for path in fixture_path("repo_provenance_bad").iterdir()
                if path.name == provenance.PLANTED_EVIDENCE
            ),
            [provenance.PLANTED_EVIDENCE],
        )
        self.assertEqual(run("repo_provenance_bad").failed, True)


class EmptyTreeTest(unittest.TestCase):
    def test_a_tree_with_no_files_is_a_hard_error_and_never_a_pass(self):
        import tempfile

        with tempfile.TemporaryDirectory() as empty:
            result = provenance.run(empty)

        self.assertEqual([f.rule for f in result.findings], ["no-input"])
        self.assertEqual(result.failed, True)
        self.assertEqual(result.examined, 0)


if __name__ == "__main__":
    unittest.main()
