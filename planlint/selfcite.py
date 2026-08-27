"""Lint 19 — line-number citations into this document.

A row of section 24.6 states where a file is named: *"`tests/abi_stub.c` on
**4** (lines 4018, 4316, 4694, 9271)"*. Nothing in this toolchain read those
numbers, and the plan is APPEND-ONLY in normal operation — §24.6 grows a row per
pass — so every figure below an insertion point is invalidated by the next
write, in silence. `anchors` reports clean over such a document and so does
`structure`, because neither one resolves a number against the line it names.

The defect is expensive for the reason it is quiet: in the row above, the first
THREE figures are right — they sit above the insertion point — and only the
fourth is wrong. Three quarters of a citation being correct is what makes it
read as a careful measurement, and the wrong quarter points into the part of the
document that moves most.

WHAT IS RECOGNISED, AND WHY NOT MORE. A scan for four-digit numbers is the
instrument this rule refuses, and the document supplies its own reasons: it
carries a CRC (`0x8926`), sha fragments (`ae9157e`), and line references into
OTHER files (`source/MCF5307UM.textlayer.txt:9046`, `(textlayer:9247)`). A rule
that convicted those would be turned off within a week, and a lint an engineer
turns off checks nothing. What is recognised instead is the document's own
citation IDIOM and nothing else: a parenthesised `(line N)` or `(lines N, M,
...)`. Every occurrence of that idiom is EXAMINED, including one whose subject
cannot be decided — see the next paragraph — so the narrowing happens at
recognition, where it can be stated, and never inside the resolution, where it
would look like a pass.

WHAT A CITATION MUST CLAIM. A bare number claims nothing and cannot be resolved.
This lint reads the SUBJECT off the nearest preceding backticked path with
nothing else backticked in between, which is how the document already writes it,
and the claim is then decidable: *line N is a `Files:` line naming this path*.
A citation with no such subject is REPORTED as `line-citation-unresolvable`
rather than passed, because a citation the lint skipped and a citation it found
sound print the same nothing.

WHAT IS OUT OF SCOPE, SAID OUT LOUD. A line reference into ANOTHER document —
the `path:NNNN` form — is not recognised and is checked by nothing here;
resolving it would need that document, which this lint does not take. The
report says so on every run, clean or dirty. The stated COUNT beside a citation
(*"on **4**"*) is likewise not this lint's: it is a claim about a population,
which is `counts`'s subject, and reading it here would put two rules in one
message.

ONE UNIT IS ONE CITED LINE NUMBER. Findings and the examined count are the same
unit on purpose, so the ratio between them is a number a reader can use.
"""

import dataclasses
import re

from planlint.finding import ERROR, Finding, guard_no_input

# The idiom, and the whole population. `\d` at the head keeps `(lines of the
# transcript)` out; the body runs to the closing parenthesis so that the
# trailing prose of `(line 4694, CPU-29's own)` is captured and then discarded
# by the number reader rather than silently truncating the match.
CITATION = re.compile(r"\(lines?\s+(?P<body>\d[^)]{0,240})\)")

# The subject, hunted LEFTWARD from the citation and anchored at its opening
# parenthesis. The gap admits no backtick, so the match is the NEAREST
# backticked token and never a distant one that happens to look like a path; no
# parenthesis, so one citation cannot reach across another; and NO NEWLINE, so a
# citation whose subject would have to be found on an earlier line is reported
# unresolvable rather than bound to whatever the previous paragraph ended with.
# The citation BODY may still wrap — that is the scan's business, above — and
# only the binding is held to one line.
SUBJECT = re.compile(r"`(?P<path>[^`\s]*\.[A-Za-z0-9_+-]+)`(?P<gap>[^`()\n]*)\Z")

# How far back the subject is hunted. The document's own longest form —
# a path, ` on `, a bolded count — fits inside this with room to spare, and a
# window without a bound would let a citation bind to a path a sentence away.
WINDOW = 96

FILES_PREFIX = "Files: "


@dataclasses.dataclass(frozen=True)
class Citation:
    """A line-number citation. `path` is empty when no subject was decidable."""

    path: str
    figures: tuple
    line: int
    text: str


def _figures(body):
    """The leading run of comma-separated integers.

    `4694, CPU-29's own` states one figure and then says something else about
    it. Reading past the first non-number would turn prose into figures.
    """
    found = []
    for part in body.split(","):
        part = part.strip()
        if not part.isdigit():
            break
        found.append(int(part))
    return tuple(found)


def citations_in(doc):
    """Every line-number citation in the document, in reading order.

    The scan runs over the WHOLE text and not line by line. Prose in this
    document wraps, so a citation and its subject routinely sit on different
    lines; a line-scoped scanner reads such a citation as absent, and an absent
    citation and a sound one print the same nothing. The reported line is where
    the citation OPENS, which is where a reader looks for it.
    """
    text = "\n".join(doc.lines)
    out = []
    for match in CITATION.finditer(text):
        figures = _figures(match.group("body"))
        if not figures:
            continue
        subject = SUBJECT.search(text[max(0, match.start() - WINDOW) : match.start()])
        out.append(
            Citation(
                path=subject.group("path") if subject else "",
                figures=figures,
                line=text.count("\n", 0, match.start()) + 1,
                text=" ".join(match.group(0).split()),
            )
        )
    return out


def _names(text, path):
    """Whether a `Files:` line names `path`.

    The lookahead is what separates `tests/abi_stub.c` from a longer path that
    merely starts with it; the document writes `<path>@<OWNER-ID>` and comma
    separators, so the character after a named path is never a path character.
    """
    return re.search(re.escape(path) + r"(?![A-Za-z0-9_./+-])", text) is not None


def files_lines_naming(doc, path):
    """Every line number whose `Files:` line names `path`."""
    return [
        number
        for number, line in enumerate(doc.lines, start=1)
        if line.startswith(FILES_PREFIX) and _names(line, path)
    ]


def _what_line_holds(doc, figure):
    """What the cited line actually is, in the words the repair needs."""
    if figure < 1 or figure > len(doc.lines):
        return f"the document ends at line {len(doc.lines)}"
    text = doc.lines[figure - 1]
    if not text.strip():
        return f"line {figure} is blank"
    if not text.startswith(FILES_PREFIX):
        return f"line {figure} is not a `Files:` line"
    return f"line {figure} is a `Files:` line that does not name it"


def _where_it_really_is(truth, path):
    if not truth:
        return "no `Files:` line in this document names that path"
    noun = "line" if len(truth) == 1 else "lines"
    return f"that path is named by the `Files:` {noun} " + ", ".join(
        str(number) for number in truth
    )


def _unresolvable(doc, citation):
    return Finding(
        rule="line-citation-unresolvable",
        message="a line-number citation states no file this tool can resolve",
        section=doc.section_at(citation.line),
        line=citation.line,
        evidence=(
            f"the citation `{citation.text}` is preceded by no backticked path, "
            "so what its numbers claim is not decidable"
        ),
        severity=ERROR,
    )


def _unresolved(doc, citation, figure, truth):
    return Finding(
        rule="line-citation-unresolved",
        message="a cited line number does not name what the citation claims",
        section=doc.section_at(citation.line),
        line=citation.line,
        evidence=(
            f"the citation `{citation.text}` claims line {figure} is a `Files:` "
            f"line naming `{citation.path}`; {_what_line_holds(doc, figure)}; "
            f"{_where_it_really_is(truth, citation.path)}"
        ),
        severity=ERROR,
    )


def run(doc):
    findings = []
    examined = 0
    for citation in citations_in(doc):
        examined += len(citation.figures)
        if not citation.path:
            findings.append(_unresolvable(doc, citation))
            continue
        truth = files_lines_naming(doc, citation.path)
        for figure in citation.figures:
            if figure not in truth:
                findings.append(_unresolved(doc, citation, figure, truth))
    return guard_no_input(
        "selfcite",
        findings,
        examined,
        "cited line numbers",
        "selfcite lint",
        notice=(
            "a line reference into ANOTHER document — the `path:NNNN` form — is "
            "out of scope and is examined by nothing here."
        ),
    )
