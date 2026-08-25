"""Lint 15 — a `Check:` predicate that names a mechanism the default build removes.

Section 7.7 measurement 7: the default build is Release, Release defines
`NDEBUG`, and `NDEBUG` removes every `assert()`. A check whose verdict rests on
an assertion firing therefore reports PASS against a tree in which the property
was never written. Measurement 8, the `gearmulator` fork transcript, is OWED
AND NOT TAKEN, and the `authority` field says so rather than citing it as
taken.

The rule reaches a task through the REPOSITORY its track writes into, which
section 7.1's table states and this module reads out of the document. A block
is convicted only when EVERY repository its track writes into is one this
mechanism binds: a block in a track that also writes into an unmeasured
repository may be describing the work there, and section 7.7 forbids applying
a measured behaviour outside its own transcript. Neither the tracks nor the
repositories appear in `run()`; a list of tracks in the rule body would be
section 7.1's table copied into Python.

The mechanism list is a DATA TABLE this module iterates and never a pattern in
`run()`. Section 24.6 row W3-404 states the reason in its own words — "a roster
amended once per case is a missing predicate" — and a lint that hardcoded the
one `assert()` regex would be row W3-4's roster rewritten in Python. Adding
member two is a row and a fixture, never a second rule and never an edit here.

The sparing side is `kept_by`, and it is THREE ROWS because section 7.7 gives
three legal forms and calls silence "not a fourth". The rule shipped with the
first form alone while citing the whole section as its authority, so it
convicted the two blocks that took the SECOND — BRD-7, which records nine bare
`assert()`s replaced by a helper "compiled in every build type", and DSP-7,
whose live clause reads the registers back through "an observable no build type
deletes". A rule that convicts the blocks that did the right thing trains a
reader to ignore it, and sparing is the direction a wrong lint fails in.

The discriminating fields are LITERAL patterns and not English. Row W3-405
measured what an English description costs: no `kept_by` row reaches `Release`
or `NDEBUG`, which are the settings that REMOVE the mechanism, and form 2
requires a SURVIVAL word beside its phrase because "deleted in every build type
that defines NDEBUG" carries the same five words and states the opposite.

A `~~`-struck span is masked before any of those patterns is applied, in BOTH
directions. The document strikes and quotes rather than deleting, so struck
text is a record of what a predicate USED TO SAY: a struck clause stops
convicting and a struck sparing phrase stops excusing. Without this a
strike-based repair could not be confirmed by the instrument that flags it,
and every repair in this document takes that form.
"""

import dataclasses
import re

from planlint.document import sentences
from planlint.finding import ERROR, Finding, guard_no_input


@dataclasses.dataclass(frozen=True)
class NotTheMechanism:
    """A span that carries a mechanism's SPELLING and is provably not it.

    This is not a narrowing of `clause_pattern`. Section 24.6 row W3-405
    refused to narrow that pattern "until the count resembles the roster" and
    row W3-408 restates the refusal. An entry here states, in `reason`, why the
    flagged thing CANNOT be a defect of this class — and the test of the two
    apart is whether the reason survives being written down with no count
    beside it. Every entry's reason survives that.
    """

    name: str
    pattern: str
    reason: str


@dataclasses.dataclass(frozen=True)
class KeptBy:
    """One of the THREE legal forms §7.7 gives a `Check:` block.

    §7.7's boxed rule does not offer one escape and a default. It states that a
    block stating a debug-only behaviour "has exactly three legal forms": it
    names the build type that keeps the mechanism; or it converts the property
    to an OBSERVABLE the check reads in any build type; or it says in words that
    the property is unchecked in the default build and names the task that
    checks it. "Silence is not a fourth form."

    The shipped rule implemented the FIRST and cited the whole section as its
    authority, so it convicted blocks that took one of the other two — the
    sparing side, which is the direction a wrong lint fails in and the one that
    trains a reader to ignore the rule. A tuple of NAMED rows rather than one
    regex is what keeps the three apart: a single field holding three unrelated
    concepts is how the next reader gets it wrong, and a reason that must stand
    written down with no count beside it is the same discipline
    `not_the_mechanism` already carries.

    This is NOT the narrowing §24.6 rows W3-405 and W3-408 refused. That
    refusal is about `clause_pattern`, which no row here touches. These rows
    implement the other two legal forms OF THE RULE THE LINT ALREADY CLAIMS TO
    ENFORCE.
    """

    name: str
    pattern: str
    reason: str


@dataclasses.dataclass(frozen=True)
class Predicate:
    """One QUESTION the lint asks of a block, and the rule it answers under.

    Two questions reach the same mechanism and they are not the same question.

    `names` is the NOUN question: every SPELLING a block reaches for, the call
    and the English nouns beside it. Section 24.6 rows W3-405 and W3-408 refuse
    to narrow it "until the count resembles the roster", and it is not narrowed
    here.

    `rests its verdict on the not-firing of` is the SHAPE question, and it is
    the one section 7.7's boxed RULE actually states: "No `Check:` line may
    state its predicate as 'an assertion fires' or 'no assertion fires' without
    naming the build type that keeps `assert()`." It reads the shape of the
    verdict rather than the spelling of a noun.

    Each carries its own `rule`, its own `severity` and its own message
    fragment, and `run()` names none of the three. A rule id spelled in the rule
    body is the roster defect in its smallest form: the body would then know how
    many rules there are, and adding the second would be an edit to it.
    """

    rule: str
    names: str
    clause_pattern: str
    severity: str


@dataclasses.dataclass(frozen=True)
class RemovedMechanism:
    """One mechanism a build setting deletes, and how a block names it.

    `clause_pattern` reads every SPELLING a block reaches for — the call
    `assert()` and the English nouns beside it. IN THIS DOCUMENT THE NOUN IS
    OFTEN NOT THE MECHANISM: a block writing "the assertion is that the model
    rejects the access" names a test case, and section 7.7's rule does not
    reach it.

    THAT IS STATED HERE RATHER THAN REPAIRED BY NARROWING THE PATTERN. This
    docstring once claimed the pattern read "the MECHANISM — the call and its
    noun — and not the English verb `asserts`", which was the record of an
    intention the pattern did not carry out; section 24.6 row W3-408 measured
    the gap. THE CLAIM IS WHAT MOVED, because row W3-405 refused to narrow
    `clause_pattern` "until the count resembles the roster" and row W3-408
    restates that refusal: narrowing to make a count look right is the roster
    written in Python.

    What the module excludes instead is `not_the_mechanism` — spellings that
    are provably NOT this mechanism, each carrying its own reason — and
    `repositories`, the scope section 7.7 gives the rule. Both are columns on
    this row. Adding member two is a row and a fixture, never a second rule.
    """

    mechanism: str
    predicates: tuple
    removed_by: str
    kept_by: tuple
    authority: str
    not_the_mechanism: tuple
    repositories: tuple


REMOVED_MECHANISMS = (
    RemovedMechanism(
        mechanism="assert()",
        predicates=(
            Predicate(
                rule="check-predicate-removed-by-default-build",
                names="names",
                # NOT NARROWED. §24.6 row W3-405 refused that "until the count
                # resembles the roster" and row W3-408 restates the refusal.
                # The measured count against the live document is 40, which
                # resembles no roster, so the refusal stands and the answer to
                # the shape question is the row BELOW rather than an edit here.
                clause_pattern=r"(?i)\bassert\(\)|\bassert(?:ion|ions)\b",
                severity=ERROR,
            ),
            Predicate(
                rule="check-verdict-rests-on-an-assertion-not-firing",
                names="rests its verdict on the not-firing of",
                # §7.7's boxed RULE, read as the SHAPE of the verdict rather
                # than the spelling of a noun. Against the live document this
                # returns ONE block — DSP-20 — and DSP-20 is the block that
                # rule names.
                clause_pattern=r"(?i)\bno assertion (?:trips|fires)\b"
                r"|\bwithout asserting\b|\basserts no assertion\b",
                severity=ERROR,
            ),
        ),
        removed_by="NDEBUG",
        # §7.7's three legal forms, one row each. No row reaches `Release` or
        # `NDEBUG`: those are the settings that REMOVE the mechanism, and a
        # form reaching either would spare exactly the blocks whose own prose
        # diagnoses the defect.
        kept_by=(
            KeptBy(
                name="form 1 — it names the build type that keeps the mechanism",
                pattern=r"(?i)\bdebug\s+build\b|\bdebug-only\b|\bRelWithDebInfo\b"
                r"|\bCMAKE_BUILD_TYPE\s*=\s*Debug\b",
                reason=(
                    "§7.7: the block \"names `-DCMAKE_BUILD_TYPE=Debug` on a "
                    "command inside the same block\", so the translation unit "
                    "the check reads keeps the mechanism"
                ),
            ),
            KeptBy(
                name=(
                    "form 2 — it converts the property to an observable read in "
                    "any build type"
                ),
                # The survival word is REQUIRED and it is what makes the
                # phrase a sparing one. "deleted in every build type that
                # defines NDEBUG" carries the same five words and states the
                # opposite; a pattern that read the phrase alone would spare
                # the block whose own prose names the removal, which is the
                # failure `kept_by` exists to refuse.
                pattern=r"(?i)\b(?:compiled|present|read|readable|available"
                r"|observable|survives|kept)\b[^.]{0,60}"
                r"\b(?:in (?:every|any) build type"
                r"|no build type (?:deletes|removes|strips|omits))\b",
                reason=(
                    "§7.7: the block \"converts the property to an OBSERVABLE "
                    "the check reads in any build type — a returned value, a "
                    "`g2::Status`, a counter, a file\", so no build setting can "
                    "delete the thing the verdict rests on"
                ),
            ),
            KeptBy(
                name=(
                    "form 3 — it says the property is unchecked in the default "
                    "build and names the task that checks it"
                ),
                # BOTH halves, and the second is the document's own task
                # identifier GRAMMAR — `planlint.document.IDENT` — and never a
                # list of track prefixes. §7.7 requires the block to name the
                # task; a roster of prefixes here would be §7.1's table copied
                # into this row, which row W3-404 calls a missing predicate.
                pattern=r"(?i)\bunchecked in the default build\b[^.]{0,80}"
                r"\b[A-Z]{2,6}-\d+\b",
                reason=(
                    "§7.7: the block \"says in words that the property is "
                    "unchecked in the default build and names the task that "
                    "checks it\", so the gap is stated rather than left silent, "
                    "and §7.7 says silence is not a fourth form"
                ),
            ),
        ),
        # The citation is HALF OWED and it says so. §7.7 records of
        # measurement 8 — the `gearmulator` fork transcript — "THIS TRANSCRIPT
        # IS OWED AND NOT TAKEN", and a field reading "measurements 7 and 8"
        # asserted a measured behaviour that has not been measured. §7.7's
        # instruction for that state is CONSERVATIVE: it does not exempt the
        # fork, it forbids a `Check:` there from resting on an assertion. So
        # the repair is an honest citation and the fork stays in scope.
        authority=(
            "§7.7 measurement 7, TAKEN for `dsp56300`; §7.7 measurement 8, the "
            "`gearmulator` fork transcript, is OWED AND NOT TAKEN, and what binds "
            "the fork until it exists is §7.7's own standing instruction that no "
            "`Check:` there may rest on an assertion"
        ),
        not_the_mechanism=(
            NotTheMechanism(
                name="a static assertion",
                pattern=r"(?i)\bstatic[_\s]assert(?:ion|ions|s)?\b",
                reason=(
                    "NDEBUG does not remove static_assert: it is a compile-time "
                    "construct present in every build type, and this class is a "
                    "mechanism the default build removes"
                ),
            ),
            NotTheMechanism(
                name="a citation of one of the plan's own graph assertions",
                pattern=r"(?i)\bassertions?\s+\d+\b",
                reason=(
                    "a numbered assertion is one of section 7.6's own graph "
                    "invariants, a sentence in this document that planlint "
                    "checks, and no build type deletes a sentence"
                ),
            ),
        ),
        # Section 7.7: the rule "binds each repository from its own
        # transcript". These are the two the section reaches — measurement 7
        # measures the `dsp56300` default build, and measurement 8's owed
        # transcript is replaced, until it is taken, by the section's own
        # standing instruction that no `Check:` in the `gearmulator` fork may
        # rest on an assertion. `mcf5307` is a Nim-driven CMake project whose
        # default build type the section says is NOT measured, and `NDEBUG` has
        # no meaning at all in `nmg2-tools`, which is a pytest project.
        repositories=("dsp56300 fork", "gearmulator fork"),
    ),
)


# A `~~`-struck span, across line breaks. The document's convention is to
# strike and quote rather than delete — §1.3 rule 12 — so struck text is a
# record of what a predicate USED TO SAY and never a live predicate. A lint
# that read through the markers could not confirm a strike-based repair, which
# is the form every repair in this document takes.
STRUCK = re.compile(r"~~.+?~~", re.DOTALL)


def _mask(text, patterns):
    """`text` with the WORD CHARACTERS of every named span blanked.

    Length, punctuation and line breaks are preserved, so an offset in the
    masked text is the same offset in the original. That is what lets a finding
    quote the document's own sentence rather than the blanked one, and it is
    why the mask blanks characters instead of deleting them.
    """
    for pattern in patterns:
        text = pattern.sub(lambda match: re.sub(r"\w", " ", match.group(0)), text)
    return text


def _sentence_at(text, offset):
    """The sentence of `text` that holds `offset`, quoted verbatim.

    The offset comes from the MASKED text and the sentence from the original,
    which is the whole reason `_mask` preserves length.
    """
    body = text.strip()
    offset -= len(text) - len(text.lstrip())
    position = 0
    for sentence in sentences(text):
        start = body.index(sentence, position)
        position = start + len(sentence)
        if start <= offset < position:
            return sentence
    return body


def _block_lines(doc, task):
    """The `Check:` BLOCK as document lines, with each line's number.

    The extent is the `Check:` line THROUGH THE END OF THE TASK BODY, because a
    sparing phrase can sit anywhere in the body, and it is the extent
    `check_text` holds and what section 7.7.1 condition 8 means by the term.

    It must be the SAME extent, and not merely the same range. `check_text` is
    built with every `$ ` transcript fence dropped and the `Check: ` field
    label stripped, so a reader that re-walked the raw lines could quote a
    shell transcript as the predicate the detection flagged — a record of a
    measurement, which `planlint.document` states is never an instruction, and
    a line the detection never read. The two exclusions are reproduced here.

    `doc._in_fence` is a private member and it is used deliberately: the
    transcript flag lives only there. The public `fenced_line_indexes` does not
    discriminate a transcript from any other fence, so it would exclude the
    non-transcript fences `check_text` KEEPS and reintroduce the same
    disagreement in the other direction.

    The label is not stripped by a second reading of `FIELD`, which is the
    document's own regex and has exactly one user by assertion. The parser
    already wrote the stripped value down: it is the FIRST line of
    `check_text`, so that is what the `Check:` line contributes here.
    """
    end = task.line + len(task.body_text.split("\n"))
    check_value = task.check_text.splitlines()[0]
    block = []
    for number in range(task.check_line, end):
        fence = doc._in_fence(number - 1)
        if fence and fence["transcript"]:
            continue
        text = check_value if number == task.check_line else doc.lines[number - 1]
        block.append((number, text))
    return block


def _clause(doc, task, pattern, masks):
    """The line and the sentence a match sits on, quoted verbatim.

    A reader told a `Check:` is unfalsifiable and not shown the sentence goes
    looking for it. The search runs over the MASKED line and the quote comes
    out of the original, so a withdrawn span can neither be reported nor
    quoted.
    """
    block = _block_lines(doc, task)
    # The mask runs over the JOINED block and never line by line: a struck span
    # may open on one line and close on another, and a per-line mask would see
    # one unpaired marker on each of them and blank neither. The mask preserves
    # length and never touches a line break, so the split realigns exactly.
    masked = _mask("\n".join(text for _, text in block), masks).split("\n")
    for (number, text), masked_text in zip(block, masked):
        match = pattern.search(masked_text)
        if not match:
            continue
        return number, _sentence_at(text, match.start())
    return task.check_line, task.check_text.splitlines()[0].strip()


def run(doc, mechanisms=REMOVED_MECHANISMS):
    findings = []
    examined = 0

    for task in doc.tasks:
        if not task.check_line or not task.check_text.strip():
            continue
        examined += 1
        # The repositories the document itself places this task's track in.
        # An EMPTY answer on either side makes no exclusion, and both silences
        # mean the same thing: an exclusion must be PROVABLE, and neither a row
        # that states no scope nor a document that states no track table proves
        # a task out of scope. A lint that went quiet on a silence would fail
        # exactly like a lint that is not there.
        stated = doc.track_repositories.get(task.track, ())

        for mechanism in mechanisms:
            if (
                stated
                and mechanism.repositories
                and not set(stated) <= set(mechanism.repositories)
            ):
                continue
            masks = (STRUCK,) + tuple(
                re.compile(item.pattern) for item in mechanism.not_the_mechanism
            )
            masked = _mask(task.check_text, masks)
            # §7.7 gives its three legal forms to the BLOCK and not to a
            # spelling, so the sparing side is read once and both questions
            # answer to it.
            if any(re.search(form.pattern, masked) for form in mechanism.kept_by):
                continue
            for predicate in mechanism.predicates:
                clause_pattern = re.compile(predicate.clause_pattern)
                if not clause_pattern.search(masked):
                    continue
                line, evidence = _clause(doc, task, clause_pattern, masks)
                findings.append(
                    Finding(
                        rule=predicate.rule,
                        message=(
                            f"a Check: predicate {predicate.names} "
                            f"{mechanism.mechanism}, which "
                            f"{mechanism.removed_by} removes from the default build, so the "
                            "check reports PASS against a tree in which the property was "
                            "never written; the block states none of the three legal "
                            "forms that would keep it "
                            f"({mechanism.authority})"
                        ),
                        task=task.ident,
                        section=task.section,
                        line=line,
                        evidence=evidence,
                        severity=predicate.severity,
                    )
                )

    return guard_no_input(
        "removed", findings, examined, "Check: blocks", "removed-mechanism lint"
    )
