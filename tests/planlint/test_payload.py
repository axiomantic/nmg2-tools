"""Tests for the artifact-boundary lint (sections 3.2, 7.8, 22.4).

No Clavia-authored content reaches a public repository by ANY route: a commit, a
fixture path, a test vector, a `.gitmodules` entry, or a continuous-integration
step that uploads a build artifact. The last route is the one a lint that reads
committed files only cannot see at all.
"""

import unittest

from tests.planlint.support import fixture_path, load_fixture

from planlint import payload


def run(tree, **kwargs):
    doc = load_fixture("clean_plan.md")
    kwargs.setdefault("register", doc.fixture_register)
    return payload.run(fixture_path(tree), **kwargs)


class PayloadLintTest(unittest.TestCase):
    def test_the_good_tree_reports_nothing(self):
        result = run("repo_public_good")

        self.assertEqual(result.findings, [])
        self.assertEqual(result.examined, 6)

    def test_every_breach_route_is_reported_and_nothing_else(self):
        result = run("repo_public_bad")

        self.assertEqual(
            sorted((f.rule, f.evidence) for f in result.findings),
            [
                (
                    "no-clavia-payload-oversize",
                    "`fixtures/over_ceiling.bin` is 65537 bytes, above the 65536-byte "
                    "ceiling, and section 7.8's register carries no allow-listed row "
                    "for it",
                ),
                (
                    "no-clavia-payload-pch2",
                    "`patches/demo_bank.pch2` is outside "
                    "`nmg2_tools/testdata/pch2_synth/`, the only directory in a public "
                    "repository where a `*.pch2` file may live",
                ),
                (
                    "no-clavia-upload",
                    "`.github/jobs/oracle.yml` step `actions/cache` carries path "
                    "`corpus/pch2`, which intersects a corpus",
                ),
                (
                    "no-clavia-upload",
                    "`.github/workflows/ci.yml` step `actions/upload-artifact` carries "
                    "path `build/golden/captures`, which intersects a capture",
                ),
                (
                    "no-private-submodule",
                    "`.gitmodules` names "
                    "`https://github.com/axiomantic/nmg2-artifacts.git`",
                ),
            ],
        )

    def test_a_file_exactly_at_the_ceiling_passes_and_one_byte_above_fails(self):
        result = run("repo_public_bad")
        oversize = [f for f in result.findings if f.rule == "no-clavia-payload-oversize"]

        self.assertEqual(
            [f.evidence for f in oversize],
            [
                "`fixtures/over_ceiling.bin` is 65537 bytes, above the 65536-byte "
                "ceiling, and section 7.8's register carries no allow-listed row for it"
            ],
        )
        self.assertEqual(payload.DEFAULT_CEILING, 65536)

    def test_an_allow_listed_register_row_exempts_a_file_above_the_ceiling(self):
        result = run("repo_public_bad")
        evidence = " ".join(f.evidence for f in result.findings)

        # The tree must still report something. An empty haystack makes the
        # assertion below pass while the lint examines nothing.
        self.assertIn("fixtures/over_ceiling.bin", evidence)
        self.assertNotIn("conformance/corpus/move_group.json", evidence)

    def test_without_the_allow_listed_row_the_same_file_is_reported(self):
        result = run("repo_public_bad", register=[])

        self.assertIn(
            "`conformance/corpus/move_group.json` is 65602 bytes, above the "
            "65536-byte ceiling, and section 7.8's register carries no allow-listed "
            "row for it",
            [f.evidence for f in result.findings],
        )

    def test_a_private_repository_is_where_the_payload_belongs(self):
        result = run("repo_public_bad", public=False)

        self.assertEqual(result.findings, [])

    def test_an_empty_tree_is_a_hard_error(self):
        result = payload.run(fixture_path("repo_public_good") / "no_such_dir")

        self.assertEqual(
            [(f.rule, f.message) for f in result.findings],
            [("no-input", "the payload lint examined 0 committed files")],
        )
        self.assertEqual(result.examined, 0)


if __name__ == "__main__":
    unittest.main()
