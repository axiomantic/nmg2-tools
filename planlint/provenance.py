"""Lint 18 — the provenance record.

`nmg2-tools` is MIT. Some of what it implements was first implemented by
somebody else under a copyleft licence, and the ruling on those formats is the
spec-only clean-room route. Until this lint existed, nothing mechanical checked
any part of that ruling.

WHAT THIS LINT CANNOT CHECK, stated first so that no reader mistakes a clean
run for a clean-room guarantee.

**It cannot detect that anyone read copyleft source.** Contamination leaves no
trace in the output. A transliterated decoder and an independently derived one
produce the same bytes, the same tests and the same diff, so no scan over this
repository can separate them. That is exactly why the WRITTEN RECORD is the
control and not a formality: the result cannot distinguish a clean derivation
from a contaminated one, and only the account of how it was obtained can.

It also cannot check that a record is TRUE. It reads the record's FORM. A
module that carries a complete, well-formed and false record passes this lint,
and a reviewer is the only thing that catches it.

And its record obligation reaches a module only through the two triggers below.
A module that restates an outside party's format while touching no `bytes` and
naming no copyleft licence is not asked for a record. That gap is real and it is
the reason the triggers are a UNION: each one only widens the population, so a
trigger can be added without any module losing an obligation it already had.

WHAT IT DOES CHECK.

  * `imported-copyleft-artifact` — a copyleft SPDX identifier or a copyleft
    licence GRANT sitting in a file of this MIT repository. This is a fact about
    the bytes. Naming `GPL-2.0` in prose is not a grant and is not a finding;
    the six provenance records this repository already carries all name a
    copyleft licence and none of them trips this rule.

  * `missing-provenance-record` — a shipped module the triggers reach whose
    module docstring carries no record.

  * `incomplete-provenance-record` — a record that carries the house heading and
    then omits an element of the form, so that it cannot be satisfied by the
    heading alone.

THE HOUSE FORM is `nmg2_tools/lzo1x.py`, this repository's first such record,
and the five that followed it. Three elements are required, and each of the six
carries all three:

    a heading whose line reads `..., because the licence makes it matter`;
    a statement of THIS repository's own licence;
    a statement that no line of another implementation is copied, transliterated
    or paraphrased.

`tests/planlint/test_provenance.py` holds those six against this lint, so the
form is read off the records that exist rather than recalled here.

THE TWO TRIGGERS, and why neither is a roster.

A roster of "files that must carry a record" amended once per case is a missing
predicate. So the obligation is derived from the module itself:

  1. it handles external binary data — a function signature annotated `bytes`,
     `bytearray` or `memoryview`;
  2. it names a copyleft licence — `GPL`, `LGPL`, `AGPL` or `CC-BY-SA`.

Trigger 2 is self-declaring and trigger 1 is not, which is why both are present:
`nmg2_tools/dsp56k_dis.py` decodes an instruction set out of `int` words and
trigger 1 never reaches it.

THE DETECTOR'S OWN SOURCE. This module states the grant phrases it looks for, so
it matches itself. A file carrying the sentinel `planlint-provenance-detector`
is excluded from the TEXT SCAN and the count of such files is printed beside the
examined count, because a silent exclusion and a clean scan read the same. The
sentinel is a predicate and not a list: nothing here names a path.
"""

import ast
import pathlib
import re

from planlint.finding import ERROR, Finding, guard_no_input

SENTINEL = "planlint-provenance-detector"

# The line every house record opens its provenance section with.
HEADING = "because the licence makes it matter"
# This repository's own licence, which a record must name.
OWN_LICENCE = "MIT"
# The record's load-bearing sentence. The span allows the sentence to wrap and
# to name the implementation it is about; every shipped record fits inside it.
NO_COPY = re.compile(
    r"no\s+line\s+of[\s\S]{0,240}?(?:copied|transliterated|paraphrased)", re.IGNORECASE
)

COPYLEFT_LICENCE = re.compile(
    r"\b(?:LGPL|AGPL|GPL)-[0-9]+(?:\.[0-9]+)?(?:-or-later|-only)?\b|\bCC-BY-SA(?:-[0-9.]+)?\b"
)
SPDX = re.compile(r"SPDX-License-Identifier:\s*(?P<identifier>[^\s*/#]+)")

# A licence GRANT, which is imported text. A prose mention of a licence NAME is
# not one, so a provenance record that names `GPL-2.0` does not trip this.
GRANT_PHRASES = (
    "is free software; you can redistribute it and/or modify",
    "under the terms of the gnu general public license",
    "gnu general public license as published by the free software foundation",
    "this program is distributed in the hope that it will be useful",
    "gnu affero general public license",
    "gnu lesser general public license",
)

BYTE_TYPES = ("bytes", "bytearray", "memoryview")

SKIP_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "node_modules",
    "venv",
}
# Test code is not a shipped implementation. It is still read by the artifact
# scan; only the record obligation stops at this boundary.
TEST_DIRECTORIES = {"test", "tests"}


def _walk(root):
    root = pathlib.Path(root)
    if not root.is_dir():
        return []
    out = []
    for path in sorted(root.rglob("*")):
        if any(part in SKIP_DIRECTORIES for part in path.parts):
            continue
        if any(part.endswith(".egg-info") for part in path.parts):
            continue
        if path.is_file():
            out.append(path)
    return out


def _text(path):
    return path.read_bytes().decode("utf-8", errors="ignore")


def _docstring(path):
    try:
        tree = ast.parse(_text(path), filename=str(path))
    except SyntaxError:
        return None
    return ast.get_docstring(tree) or ""


def _byte_signature(path):
    """The name of the first function whose signature names a byte type."""
    try:
        tree = ast.parse(_text(path), filename=str(path))
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        annotations = [
            argument.annotation
            for argument in node.args.args + node.args.kwonlyargs
            if argument.annotation is not None
        ]
        if node.returns is not None:
            annotations.append(node.returns)
        for annotation in annotations:
            rendered = ast.unparse(annotation)
            if any(name in rendered for name in BYTE_TYPES):
                return node.name
    return None


def record_triggers(path):
    """Why this module owes a provenance record, as a list of phrases.

    Empty means the obligation does not reach it. The list is a UNION: each
    entry widens the population and none of them narrows it.
    """
    path = pathlib.Path(path)
    triggers = []
    function = _byte_signature(path)
    if function is not None:
        triggers.append(f"handles external binary data (`{function}` is annotated `bytes`)")
    licence = COPYLEFT_LICENCE.search(_text(path))
    if licence is not None:
        triggers.append(f"names the copyleft licence `{licence.group(0)}`")
    return triggers


def record_defects(path):
    """What the record in this module's docstring is missing, given it has one.

    An empty list means the record carries every element of the house form. It
    means nothing at all about whether the record is TRUE.
    """
    docstring = _docstring(pathlib.Path(path)) or ""
    defects = []
    if OWN_LICENCE not in docstring:
        defects.append(
            "carries the heading but never names this repository's own licence"
        )
    if NO_COPY.search(docstring) is None:
        defects.append(
            "carries the heading but no statement that no line of another "
            "implementation is copied, transliterated or paraphrased"
        )
    return defects


def _imported_artifact(text):
    """`(line, evidence phrase)` for the first imported copyleft artifact."""
    for number, line in enumerate(text.splitlines(), start=1):
        found = SPDX.search(line)
        if found and COPYLEFT_LICENCE.search(found.group("identifier")):
            return number, f"carries an SPDX identifier naming `{found.group('identifier')}`"
        lowered = line.lower()
        for phrase in GRANT_PHRASES:
            if phrase in lowered:
                return number, f"carries the grant text `{phrase}`"
    return None


def run(root):
    root = pathlib.Path(root)
    files = _walk(root)
    findings = []
    excluded = 0

    for path in files:
        relative = str(path.relative_to(root))
        text = _text(path)

        if SENTINEL in text:
            excluded += 1
            continue

        artifact = _imported_artifact(text)
        if artifact is not None:
            line, phrase = artifact
            findings.append(
                Finding(
                    rule="imported-copyleft-artifact",
                    message=(
                        "a copyleft licence artifact sits in an MIT repository. A "
                        "grant or an SPDX identifier is imported text, not a fact "
                        "about a data format"
                    ),
                    section="the licence ruling",
                    line=line,
                    evidence=f"`{relative}` line {line} {phrase}",
                    severity=ERROR,
                )
            )

        if path.suffix != ".py":
            continue
        if any(part in TEST_DIRECTORIES for part in path.relative_to(root).parts[:-1]):
            continue

        triggers = record_triggers(path)
        if not triggers:
            continue
        docstring = _docstring(path) or ""
        if HEADING not in docstring:
            findings.append(
                Finding(
                    rule="missing-provenance-record",
                    message=(
                        "a shipped module restates something an outside party "
                        "implemented first and carries no account of how it was "
                        "written. The record is the only control there is: the code "
                        "a clean derivation produces and the code a contaminated one "
                        "produces are the same code"
                    ),
                    section="the licence ruling",
                    evidence=(
                        f"`{relative}` {' and '.join(triggers)} and its module "
                        f"docstring carries no line reading `{HEADING}`"
                    ),
                    severity=ERROR,
                )
            )
            continue
        for defect in record_defects(path):
            findings.append(
                Finding(
                    rule="incomplete-provenance-record",
                    message=(
                        "a provenance record carries the house heading and then omits "
                        "an element of the form, so the heading alone would satisfy "
                        "the check"
                    ),
                    section="the licence ruling",
                    evidence=f"`{relative}` {defect}",
                    severity=ERROR,
                )
            )

    return guard_no_input(
        "provenance",
        findings,
        len(files),
        f"files ({excluded} excluded as the detector's own source)",
        "provenance lint",
    )
