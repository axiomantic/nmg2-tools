"""Shared test helpers."""

import pathlib

from planlint.document import PlanDocument

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


def fixture_path(name):
    return FIXTURES / name


def load_fixture(name):
    return PlanDocument.from_path(fixture_path(name))


def idents(findings):
    """The task identifiers a finding list names, in report order."""
    return [f.task for f in findings]


def rules(findings):
    return sorted({f.rule for f in findings})
