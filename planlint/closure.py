"""Lint 9 — symbol closure.

When task A's work needs a symbol, a build target, a header or a build option
that task B produces, B must sit inside A's transitive dependency closure. When
it does not, A cannot compile or link on the day it is declared complete.

This is the class the README calls blind spot 11, and it cost this project three
real defects. All three were found by hand:

  * `g2Lib` linked `mcf5307::mcf5307`, which CPU-1 exports in Wave 3a, while
    BRD-0's closure was `{BRD-0, REPO-3, REPO-12}`;
  * REPO-9's gate read `Scheduler::Config`, and SCH-18 was outside its closure;
  * the repair of the first defect made a third: the `mcf5307::mcf5307` link
    moved behind an option defaulted OFF, and BRD-21 — whose `board.cpp` calls
    `mcf5307_exec` — did not depend on BRD-23, the task that turns it ON.

No graph rule can see any of the three. The declared edges stay acyclic, the
wave orders stay monotonic, and the `implicit` lint reads data suffixes and
directories only, so every CODE artifact is outside it.

**Reading "requires" and "produces" out of prose is a heuristic and this module
treats it as one.** It prefers RECALL: a missed violation costs a wave, and a
false positive costs a reader a minute. What the lint cannot state with
confidence it reports as a CANDIDATE, under its own rule and at WARNING, so a
reader can work the two buckets apart. Section "What the heuristic cannot see"
of the README states the limits.

The four ways a name is attributed to a producer:

  1. the `Files:` line's `targets` clause, and a backticked name after the word
     `library` or `target`;
  2. a producer verb — `exports`, `declares`, `defines`, `adds`, `creates`,
     `introduces`, `produces` — with the name after it in the same sentence. The
     task credited is the last identifier NAMED in that sentence before the
     verb, and the containing task when the sentence names none, so that
     `CPU-1 exports X` inside another task's block credits CPU-1;
  3. `` `X` … which CPU-1 exports `` anywhere in the document, including the
     prose outside every task block;
  4. the file convention: a qualified name `Ns::Member` is produced by every
     task whose `Files:` line creates `ns.h`, `ns.cpp` or `ns.nim`, compared
     without case. That is what attributes `Scheduler::Config` to the tasks that
     write `scheduler.h` and `scheduler.cpp`.

The four ways a name is read as consumed:

  1. a consumer verb — `links`, `reads`, `calls`, `uses`, `includes`,
     `compares`, `constructs`, `forwards to`, `takes the address of` — with the
     names after it in the same sentence. The run STOPS at the first backticked
     span that is not symbol-shaped, so a link list of three stays one list and
     a quoted command ends the run;
  2. `#include "x.h"` anywhere in the task block;
  3. a qualified name inside the `Check:` BLOCK with no verb in front of it.
     A check that names a type must compile against it, but the lint is
     guessing about the relation, so this route reports CANDIDATES only;
  4. a bare name whose prefix is a produced target: `mcf5307_exec` is a name of
     the `mcf5307` library, and that is how a C symbol reaches its producer.

A backticked span is masked out before a verb is looked for, so that the word
`Link` inside `option(G2_LINK_GAMMA "Link gamma" OFF)` is not a consumer verb.
A sentence never crosses a line, because a task header, a `Files:` line and a
`Depends:` line carry no full stop between them and would otherwise be one
sentence.
"""

import dataclasses
import re

from planlint import graph, registrar
from planlint.document import (
    backticked,
    canonical_path,
    fenced_line_indexes,
    inline_code_spans,
)
from planlint.finding import ERROR, WARNING, Finding, guard_no_input

CODE_SUFFIXES = (".h", ".hpp", ".hh", ".cpp", ".cc", ".c", ".nim", ".py")
HEADER_SUFFIXES = (".h", ".hpp", ".hh")

# A symbol, and not a path and not a sentence. A path carries a `/` or a `.`,
# and a prose span carries a space; neither shape reaches these patterns.
QUALIFIED = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)+$")
BARE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{2,}$")

IDENT = re.compile(r"\b[A-Z]{2,6}-\d+\b")

PRODUCER_VERB = re.compile(
    r"\b(?:exports?|exported|declares?|declared|defines?|defined|adds?|added|"
    r"creates?|created|introduces?|introduced|produces?|produced)\b"
)
CONSUMER_VERB = re.compile(
    r"\b(?:links?|linked|reads?|calls?|called|uses?|used|includes?|included|"
    r"instantiates?|forwards? to|takes the address of|constructs?|constructed|"
    r"derives? from|compares?|compared|implements?|implemented|overrides?)\b"
)
LIBRARY_NOUN = re.compile(r"\b(?:library|target)\b")
INCLUDE = re.compile(r"#include\s*[<\"]([^\">]+)[\">]")
OPTION_OFF = re.compile(r"option\(\s*([A-Za-z_][A-Za-z0-9_]*)[^)]*\bOFF\s*\)")
TURNS_ON = re.compile(r"turns?\s+\**`?([A-Za-z_][A-Za-z0-9_]*)`?\**\s+ON\b")
ATTRIBUTION = re.compile(
    r"`(?P<symbol>[^`]+)`[^`]{0,120}?\bwhich\s+(?P<ident>[A-Z]{2,6}-\d+)\s+"
    r"(?:exports?|declares?|defines?|adds?|creates?|introduces?|produces?)\b"
)
# A full stop CLOSES a sentence even when a bold marker follows it. The plan
# writes `… rather than tidiness.** Its gate reads …` and a splitter that wants
# whitespace straight after the stop reads that as ONE sentence — which put the
# hedge `rather than` in front of a plain consumption and demoted a real
# violation to a candidate.
SENTENCE_SPLIT = re.compile(r"(?<=\.)\*{0,2}\s+")

# A sentence that carries one of these describes a consumption that may not be
# one. The lint keeps the row — recall is the point — and moves it to the
# candidate bucket instead of asserting a violation.
HEDGES = (
    "does not",
    "do not",
    "did not",
    "cannot",
    "can not",
    "never",
    "no longer",
    "is not",
    "are not",
    "must not",
    "would have",
    "previous revision",
    "behind an option",
    "defaulted off",
    "rather than",
    "instead of",
)


@dataclasses.dataclass(frozen=True)
class Consumption:
    """One name a task's own text says its work needs."""

    symbol: str
    kind: str  # "symbol" or "header"
    verb: str  # "" when no verb stands in front of the name
    hedged: bool
    hedge: str
    line: int


@dataclasses.dataclass(frozen=True)
class GatedOption:
    """A build option declared OFF, and what it holds back."""

    name: str
    declarer: str
    symbols: frozenset
    scopes: tuple
    line: int


# ------------------------------------------------------------------- scanning


def mask_backticks(text):
    """The text with every quoted region blanked, and the inline spans beside it.

    The blanks keep every offset, so a verb found in the masked text has the
    position it has in the original. Masking is what stops `Link gamma` inside
    an `option(...)` string from reading as the verb `link`.

    A FENCED block is blanked whole and yields no span. A fence is a quoted
    region — an inline span that runs over several lines — so a verb printed
    inside a transcript is no more a consumer verb than one inside backticks.
    Reading a fence as a run of inline spans is defect L-5 and is what blinded
    the lint to everything after the first fence in a task body.
    """
    spans = []
    out = list(text)
    lines = text.split("\n")
    offset = 0
    fenced = fenced_line_indexes(lines)
    for index, line in enumerate(lines):
        if index in fenced:
            for position in range(offset, offset + len(line)):
                out[position] = " "
        offset += len(line) + 1
    for opener, closer, inner in inline_code_spans(text)[0]:
        spans.append((opener + 1, closer, inner))
        for index in range(opener, closer + 1):
            out[index] = " "
    return "".join(out), spans


def sentences(text, masked):
    """`(start, end)` for every sentence, never crossing a line.

    A task header, a `Files:` line and a `Depends:` line carry no full stop
    between them. Splitting on the full stop alone joins them into one sentence,
    and a verb on the header line then reaches a name on the `Files:` line.
    """
    out = []
    offset = 0
    for line in masked.split("\n"):
        start = 0
        for boundary in SENTENCE_SPLIT.finditer(line):
            out.append((offset + start, offset + boundary.start()))
            start = boundary.end()
        out.append((offset + start, offset + len(line)))
        offset += len(line) + 1
    return [(a, b) for a, b in out if b > a]


def hedge_in(text):
    """The first hedge a sentence carries, or the empty string."""
    lowered = text.lower()
    for marker in HEDGES:
        if marker in lowered:
            return marker
    return ""


def line_of(text, offset):
    return text.count("\n", 0, offset) + 1


# ------------------------------------------------------------------ producers


# A word the plan writes in backticks that names no artifact of its own: a CMake
# keyword, a C++ keyword, or a repository. A producer rule without this list
# credited `STATIC` and `static_assert` to whichever task's sentence held them.
NOT_A_SYMBOL = frozenset(
    {
        "STATIC", "SHARED", "MODULE", "OBJECT", "INTERFACE", "PUBLIC", "PRIVATE",
        "NAME", "ON", "OFF", "REQUIRED", "QUIET", "EXACT",
        "static_assert", "constexpr", "final", "noexcept", "override",
    }
)


def _first_symbol_after(spans, offset, end):
    """The first symbol-shaped backticked name after an offset, within reach.

    The reach is TWO spans, which is what `adds a `STATIC` library `mcf5307``
    needs and what stops a verb near the start of a sentence from crediting
    every name to the end of it. The producer side is where precision matters:
    a wrong producer sends a reader to the wrong task, while a wrong CONSUMER
    resolves to no producer and is dropped in silence.
    """
    reached = 0
    for span_start, _, inner in spans:
        if span_start < offset or span_start >= end:
            continue
        reached += 1
        if reached > 2:
            return ""
        if inner in NOT_A_SYMBOL:
            continue
        if QUALIFIED.match(inner) or BARE.match(inner):
            return inner
    return ""


def produced_targets(doc):
    """Every name the plan calls a build target or a library."""
    out = set()
    for task in doc.tasks:
        out.update(task.files_targets)
        masked, spans = mask_backticks(task.body_text)
        for match in LIBRARY_NOUN.finditer(masked):
            named = _first_symbol_after(spans, match.end(), len(masked))
            if named and BARE.match(named):
                out.add(named)
    # `mcf5307::mcf5307` is CMake's alias spelling of the target `mcf5307`. The
    # tail of a qualified name is a target only under that convention, or when
    # the tail is a target already: `Alpha::Config` is a type and `Config` is
    # not a build target.
    for symbol in produced_symbols(doc):
        head, _, tail = symbol.partition("::")
        if tail and head == tail and BARE.match(tail):
            out.add(tail)
    return out


def produced_symbols(doc):
    """`{symbol: [task, ...]}` for every name a producer verb attributes.

    The task credited is the LAST identifier the sentence names before the verb,
    and the containing task when the sentence names none. `CPU-1 exports X`
    inside BRD-23's block therefore credits CPU-1 and not BRD-23, which is what
    keeps a quoted fact from inflating a producer set.
    """
    out = {}

    def record(symbol, ident):
        if ident not in out.setdefault(symbol, []):
            out[symbol].append(ident)

    for task in doc.tasks:
        for item in task.files_targets:
            if BARE.match(item):
                record(item, task.ident)
        masked, spans = mask_backticks(task.body_text)
        for start, end in sentences(task.body_text, masked):
            for verb in PRODUCER_VERB.finditer(masked, start, end):
                named = [
                    m.group(0)
                    for m in IDENT.finditer(masked, start, verb.start())
                    if doc.has_task(m.group(0))
                ]
                owner = named[-1] if named else task.ident
                inner = _first_symbol_after(spans, verb.end(), end)
                if inner:
                    record(inner, owner)
            for noun in LIBRARY_NOUN.finditer(masked, start, end):
                inner = _first_symbol_after(spans, noun.end(), end)
                if inner and BARE.match(inner):
                    record(inner, task.ident)

    for match in ATTRIBUTION.finditer("\n".join(doc.lines)):
        symbol = match.group("symbol")
        ident = match.group("ident")
        if doc.has_task(ident) and (QUALIFIED.match(symbol) or BARE.match(symbol)):
            record(symbol, ident)

    return out


def type_producers(doc, symbol):
    """The tasks whose `Files:` line creates the file a qualified name lives in.

    `Scheduler::Config` lives in `scheduler.h` or `scheduler.cpp`. The compare
    ignores case, because the plan writes `mcuContext.h` for `McuContext`.
    """
    if "::" not in symbol:
        return []
    head = symbol.split("::", 1)[0].lower()
    out = []
    for task in doc.tasks:
        for path in task.files_paths:
            base = path.rsplit("/", 1)[-1]
            stem, dot, suffix = base.rpartition(".")
            if not dot or ("." + suffix) not in CODE_SUFFIXES:
                continue
            if stem.lower() == head and task.ident not in out:
                out.append(task.ident)
    return out


def header_producers(doc, header):
    """The tasks whose `Files:` line creates a header, matched on the basename.

    A `#include` names the basename and a `Files:` line names the path, so the
    basename is the only spelling the two share.
    """
    out = []
    for task in doc.tasks:
        for path in task.files_paths:
            if path.rsplit("/", 1)[-1] == header and task.ident not in out:
                out.append(task.ident)
    return out


def _repository_names(doc):
    """The last component of every repository section 3.1's table carries."""
    return {name.rsplit("/", 1)[-1] for name in doc.repositories}


def producers_of(doc, consumption, produced, targets):
    """`(producers, route)` — the tasks that produce a consumed name, and how.

    The ROUTE carries the confidence. A qualified name, a header, a build target
    and a `library_symbol` prefix each name one thing. **An UNQUALIFIED name does
    not**: `stateSize` is a method of the `Board` and a method of the DSP state,
    and both tasks declare one. A bare name therefore resolves through the
    producer map as a CANDIDATE, never as an assertion.
    """
    symbol = consumption.symbol
    if consumption.kind == "header":
        return header_producers(doc, symbol), "header"
    if "::" in symbol:
        if symbol in produced:
            return list(produced[symbol]), "qualified"
        last = symbol.rsplit("::", 1)[-1]
        if last in targets and last in produced:
            return list(produced[last]), "target"
        found = type_producers(doc, symbol)
        if found:
            return found, "qualified"
        if last in produced:
            return list(produced[last]), "bare"
        return [], "none"
    if symbol in targets and symbol in produced:
        # A name that is BOTH a build target and a repository is ambiguous in
        # its bare spelling: `every `mcf5307` task` means every task in the
        # repository, and `mcf5307::mcf5307` means the target. The qualified
        # spelling above stays an assertion; this one becomes a candidate.
        if symbol in _repository_names(doc):
            return list(produced[symbol]), "bare"
        return list(produced[symbol]), "target"
    # A C symbol carries its library as a prefix: `mcf5307_exec` belongs to
    # `mcf5307`. The LONGEST matching target wins, so a project with both
    # `g2` and `g2Lib` resolves to the one the name actually carries.
    matched = sorted(
        (t for t in targets if symbol.startswith(t + "_")), key=len, reverse=True
    )
    for target in matched:
        if target in produced:
            return list(produced[target]), "prefix"
    if symbol in produced:
        return list(produced[symbol]), "bare"
    return [], "none"


# ------------------------------------------------------------------ consumers


def consumptions(doc, task):
    """Every name a task's own text says its work needs, in document order."""
    text = task.body_text
    masked, spans = mask_backticks(text)
    ranges = sentences(text, masked)
    check_offset = _check_offset(task, text)

    found = {}

    def add(symbol, kind, verb, position):
        if symbol in found:
            return
        sentence = next(
            (r for r in ranges if r[0] <= position < r[1]), (position, position)
        )
        marker = hedge_in(text[sentence[0]:sentence[1]])
        found[symbol] = (
            position,
            Consumption(
                symbol=symbol,
                kind=kind,
                verb=verb,
                hedged=bool(marker),
                hedge=marker,
                line=task.line + line_of(text, position) - 1,
            ),
        )

    for match in INCLUDE.finditer(text):
        header = match.group(1).rsplit("/", 1)[-1]
        add(header, "header", "includes", match.start())

    for start, end in ranges:
        for verb in CONSUMER_VERB.finditer(masked, start, end):
            # Every name after the verb, and the run STOPS at the first
            # backticked span that is not symbol-shaped. `links `a`, `b` and `c``
            # is one list of three and must stay one; `It read `ctest …` and then
            # …` is a command and ends the run at the command.
            for span_start, _, inner in spans:
                if not verb.end() <= span_start < end:
                    continue
                if not (QUALIFIED.match(inner) or BARE.match(inner)):
                    break
                if inner not in NOT_A_SYMBOL:
                    add(inner, "symbol", verb.group(0), span_start)

    for span_start, _, inner in spans:
        if span_start < check_offset or not QUALIFIED.match(inner):
            continue
        add(inner, "symbol", "", span_start)

    return [item[1] for item in sorted(found.values(), key=lambda item: item[0])]


def _check_offset(task, text):
    """The offset in the body where the `Check:` BLOCK starts.

    `check_text` is a rebuilt string with the transcript fences dropped, so its
    offsets do not map back. The line number does.
    """
    if not task.check_line:
        return len(text) + 1
    wanted = task.check_line - task.line
    offset = 0
    for index, line in enumerate(text.split("\n")):
        if index == wanted:
            return offset
        offset += len(line) + 1
    return len(text) + 1


# -------------------------------------------------------------- gated options


def gated_options(doc):
    """Every build option a task declares OFF, with what it holds back.

    The option's LINE is the context, because the plan declares options inside a
    table row and a row is one line. The names on that line are what the option
    gates, and the `CMakeLists.txt` on that line gives the directory the option
    governs. A line that names no `CMakeLists.txt` falls back to every
    `CMakeLists.txt` the declaring task creates.
    """
    out = []
    for task in doc.tasks:
        for raw in task.body_text.split("\n"):
            match = OPTION_OFF.search(raw)
            if not match:
                continue
            names = backticked(raw)
            symbols = {
                name
                for name in names
                if QUALIFIED.match(name) or BARE.match(name)
            }
            scopes = _scopes_on(names) or _scopes_of(task)
            out.append(
                GatedOption(
                    name=match.group(1),
                    declarer=task.ident,
                    symbols=frozenset(symbols),
                    scopes=tuple(sorted(scopes)),
                    line=task.line,
                )
            )
    return out


def _scopes_on(names):
    return {
        canonical_path(name).rsplit("/", 1)[0]
        for name in names
        if name.endswith("/CMakeLists.txt")
    }


def _scopes_of(task):
    return {
        path.rsplit("/", 1)[0]
        for path in task.files_paths
        if path.endswith("/CMakeLists.txt")
    }


def option_enablers(doc):
    """`{option: [task, ...]}` for every task that turns an option ON."""
    out = {}
    for task in doc.tasks:
        for name in TURNS_ON.findall(task.body_text):
            out.setdefault(name, [])
            if task.ident not in out[name]:
                out[name].append(task.ident)
    return out


def _gates(option, consumption):
    """Whether an option holds back a consumed name."""
    symbol = consumption.symbol
    if symbol in option.symbols:
        return True
    tails = {s.rsplit("::", 1)[-1] for s in option.symbols}
    if symbol.rsplit("::", 1)[-1] in tails:
        return True
    return any(symbol.startswith(tail + "_") for tail in tails)


def _in_scope(task, option):
    return any(
        path == scope or path.startswith(scope + "/")
        for path in task.files_paths
        for scope in option.scopes
    )


# ----------------------------------------------------------------------- lint


def _closure_text(reachable):
    return ", ".join(sorted(reachable))


def _names(idents):
    return ", ".join(idents)


def run(doc):
    """Every consumption held against the consuming task's dependency closure.

    A breach is built as a `Finding` at the point where its rule is KNOWN, so
    that every rule this module can emit is a literal in a `Finding(rule=...)`
    call. `tests/test_mutation.py` reads the rule inventory out of this source
    with `ast`, and a rule that arrived as a variable would hide from the
    inventory and from the mutation that must cover it.
    """
    findings = []
    edges, _ = graph.build_edges(doc)
    produced = produced_symbols(doc)
    targets = produced_targets(doc)
    options = gated_options(doc)
    enablers = option_enablers(doc)
    enabling = {ident for idents in enablers.values() for ident in idents}
    examined = 0

    for task in doc.tasks:
        reachable = registrar.closure(doc, task.ident, edges)
        closure_text = _closure_text(reachable)

        for consumption in consumptions(doc, task):
            examined += 1
            breaches = []

            found, route = producers_of(doc, consumption, produced, targets)
            owners = [ident for ident in found if ident != task.ident]
            # The task that puts a name BEHIND an option defaulted OFF is not
            # consuming it. BRD-0 declares the `mcf5307::mcf5307` link and does
            # not link it, and a producer rule that reported the declarer would
            # report every gated link in the plan.
            gated_here = any(
                option.declarer == task.ident and _gates(option, consumption)
                for option in options
            )
            if owners and not gated_here and not set(owners) & reachable:
                breaches.append(
                    _producer_finding(task, consumption, owners, closure_text, targets)
                )

            for option in options:
                if task.ident == option.declarer or task.ident in enabling:
                    continue
                if not _gates(option, consumption) or not _in_scope(task, option):
                    continue
                turners = enablers.get(option.name, [])
                if not turners or set(turners) & reachable:
                    continue
                breaches.append(
                    _option_finding(task, consumption, option, turners, closure_text)
                )

            if not breaches:
                continue

            reason = _candidate_reason(consumption, route)
            if reason:
                findings.append(_candidate_finding(task, consumption, reason, breaches))
            else:
                findings.extend(breaches)

    return guard_no_input(
        "closure", findings, examined, "consumptions", "closure lint"
    )


def _producer_finding(task, consumption, owners, closure_text, targets):
    """The breach a name whose every producer is unreachable represents."""
    common = {
        "task": task.ident,
        "section": task.section,
        "line": consumption.line,
        "severity": ERROR,
    }
    if consumption.kind == "header":
        return Finding(
            rule="header-producer-unreachable",
            message=(
                "a task includes a header another task creates, and reaches no task "
                "that creates it. The include does not resolve on the day this task "
                "is declared complete"
            ),
            evidence=(
                f"{task.ident} includes `{consumption.symbol}`; it is created by "
                f"{_names(owners)}, and {task.ident}'s dependency closure "
                f"{{{closure_text}}} holds none of them"
            ),
            **common,
        )
    evidence = (
        f"{task.ident} names `{consumption.symbol}` ({consumption.verb or 'no verb'}); "
        f"it is produced by {_names(owners)}, and {task.ident}'s dependency closure "
        f"{{{closure_text}}} holds none of them"
    )
    tail = consumption.symbol.rsplit("::", 1)[-1]
    if tail in targets or consumption.symbol in targets:
        return Finding(
            rule="target-producer-unreachable",
            message=(
                "a task links a build target another task exports, and reaches no "
                "task that exports it. The link cannot resolve on the day this task "
                "is declared complete"
            ),
            evidence=evidence,
            **common,
        )
    return Finding(
        rule="symbol-producer-unreachable",
        message=(
            "a task names a symbol or a type another task produces, and reaches no "
            "task that produces it. The translation unit does not compile on the day "
            "this task is declared complete"
        ),
        evidence=evidence,
        **common,
    )


def _option_finding(task, consumption, option, turners, closure_text):
    """The breach a name behind an option nobody reachable turns ON represents."""
    scope = option.scopes[0] if option.scopes else "the declaring task's tree"
    return Finding(
        rule="gated-symbol-without-enabler",
        message=(
            "a task names something a build option holds back, and reaches no task "
            "that turns the option ON. The name is compiled out, and the link fails "
            "naming the symbol"
        ),
        task=task.ident,
        section=task.section,
        line=consumption.line,
        evidence=(
            f"{task.ident} names `{consumption.symbol}` "
            f"({consumption.verb or 'no verb'}); {option.declarer} puts it behind "
            f"`option({option.name} ... OFF)` in `{scope}`, {_names(turners)} turns "
            f"the option ON, and {task.ident}'s dependency closure {{{closure_text}}} "
            "holds none of them"
        ),
        severity=ERROR,
    )


def _candidate_finding(task, consumption, reason, breaches):
    """One row a reader adjudicates, in place of every breach the name carries.

    One row and not one for each breach: a hedged sentence is one uncertain
    reading, and reporting it twice trains a reader to skim.
    """
    return Finding(
        rule="symbol-closure-candidate",
        message=(
            "a task names something another task produces and reaches no producer, "
            "and the lint cannot state the relation with confidence. A candidate for "
            "a human to adjudicate: the requirement is real, or the sentence "
            "describes something the task does not do"
        ),
        task=task.ident,
        section=task.section,
        line=consumption.line,
        evidence=f"candidate — {reason}; {breaches[0].evidence}",
        severity=WARNING,
    )


def _candidate_reason(consumption, route):
    """Why a breach is a candidate and not an assertion, or the empty string."""
    if consumption.hedged:
        return f'the sentence hedges with "{consumption.hedge}"'
    if not consumption.verb:
        return "the check names it with no verb in front of it"
    if route == "bare":
        return (
            "the name is unqualified, so the producer may be a different "
            "declaration of the same name"
        )
    return ""
