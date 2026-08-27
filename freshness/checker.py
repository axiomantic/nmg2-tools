"""Re-derive the facts a findings note rests on, and say when they have moved.

WHY THIS EXISTS. A note in `nmg2-findings` records a measurement. Work lands
that invalidates it, and the note keeps reading as current because nothing
connects the two. Six notes went stale within roughly a day of being written and
none announced it. One stale verdict — a finding recorded as "confirmed and
outstanding" that had been repaired the same day — reached the operator as an
instruction to strike a sound run-backed marker.

WHY A PROSE CONVENTION IS NOT ENOUGH. This project's own recorded rule already
says that a date does not rescue a stale claim: within a day of churn a date
discriminates nothing. The one mechanism that has ever caught this class here is
a registry that PINS a value and is CHECKED. That is what this is.

WHAT IT CANNOT DO, stated first so no clean run is mistaken for more than it is.
It checks that the facts a note DECLARED still hold. It cannot check that the
note's reasoning was sound, that the pins are the RIGHT facts to have pinned, or
that a note pinning one number is not silently wrong about a second number it
never pinned. A note is only as checkable as its pins, which is exactly why an
unpinned note is reported and never passed.

THE PIN FORMAT. A note declares what it rests on in a fenced block:

    ```pins
    # a comment
    repo   <path>  <sha>                  the commit still resolves AND is
                                          still an ancestor of that repo's HEAD
    file   <path>  sha256=<64 hex>        the artifact's bytes are unchanged
    file   <path>  bytes=<n>              the artifact's length is unchanged
    count  <n>     -- <shell command>     the command still prints that integer
    exit   <n>     -- <shell command>     the command still exits with that code
    output <text>  -- <shell command>     the command's stripped stdout is that
    ```

A `repo` or `file` pin splits on the LAST run of whitespace, so a path may carry
spaces. A command pin splits on the first ` -- `, so a command may carry
anything.

THE FOUR VERDICTS.

  OK            the fact was re-derived and it holds.
  MOVED         the fact was re-derived and it is different. The note is stale.
  UNRESOLVABLE  the fact could not be re-derived at all — a missing file, a
                repository that is not there, a command that failed. This is
                NOT a pass. A pin that cannot be checked and a pin that checks
                out produce the same silence otherwise, and that equivalence is
                the failure this tool was built against.
  MALFORMED     the line is not a pin. It is kept and reported rather than
                skipped, because a dropped line reads exactly like a note that
                declared fewer pins.

And a note carrying no pins at all is UNPINNED, which is a verdict and not an
absence of one.

RUNNING COMMANDS IS OPT-IN. A note is data, not an instruction. `run_commands`
is False by default and a command pin then reports UNRESOLVABLE — never OK. The
opt-in cannot turn into a silent pass in either direction: without it the pin is
loudly unchecked, and with it the pin is actually checked.
"""

import dataclasses
import hashlib
import pathlib
import shutil
import subprocess

OK = "OK"
MOVED = "MOVED"
UNRESOLVABLE = "UNRESOLVABLE"
MALFORMED = "MALFORMED"
UNPINNED = "UNPINNED"

# A note's verdict is the WORST of its pins, and this states the order rather
# than leaving it to be recalled. `MOVED` outranks `UNRESOLVABLE` because a fact
# known to have changed is a stronger claim about the note than one that could
# not be read.
VERDICT_ORDER = {MOVED: 0, UNRESOLVABLE: 1, MALFORMED: 2, OK: 3}

FENCE_OPEN = "```pins"
FENCE_CLOSE = "```"

PATH_KINDS = ("repo", "file")
COMMAND_KINDS = ("count", "exit", "output")
KINDS = tuple(sorted(PATH_KINDS + COMMAND_KINDS))

# The timeout is per pin. A pin whose command hangs would otherwise stall the
# whole corpus, and a checker that never finishes reports nothing at all.
COMMAND_TIMEOUT = 600


@dataclasses.dataclass(frozen=True)
class Pin:
    """One declared fact. `kind` is `?` for a line that is not a pin."""

    kind: str
    subject: str
    expected: str
    line: int
    raw: str = ""


@dataclasses.dataclass(frozen=True)
class PinResult:
    pin: Pin
    verdict: str
    detail: str


@dataclasses.dataclass(frozen=True)
class NoteResult:
    path: pathlib.Path
    results: list

    @property
    def verdict(self):
        """UNPINNED when the note declared nothing, else the worst pin."""
        if not self.results:
            return UNPINNED
        return min((r.verdict for r in self.results), key=VERDICT_ORDER.__getitem__)


def parse_pins(text):
    """Every line inside every ```pins fence, as a `Pin`.

    A line that cannot be read is returned with `kind == "?"` rather than
    dropped: a dropped line and a note that declared fewer pins produce the same
    report, and the second is a claim the note never made.
    """
    pins = []
    inside = False
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not inside:
            if stripped == FENCE_OPEN:
                inside = True
            continue
        if stripped == FENCE_CLOSE:
            inside = False
            continue
        if not stripped or stripped.startswith("#"):
            continue
        pins.append(_parse_line(stripped, number))
    return pins


def _parse_line(line, number):
    kind, _, rest = line.partition(" ")
    rest = rest.strip()
    if kind in PATH_KINDS and rest:
        subject, _, expected = rest.rpartition(" ")
        if subject and expected:
            return Pin(kind=kind, subject=subject.strip(), expected=expected, line=number)
    if kind in COMMAND_KINDS and " -- " in rest:
        expected, _, subject = rest.partition(" -- ")
        if subject.strip():
            return Pin(
                kind=kind,
                subject=subject.strip(),
                expected=expected.strip(),
                line=number,
            )
    return Pin(kind="?", subject="", expected="", line=number, raw=line)


def resolve(pin, run_commands=False):
    """Re-derive one pin. Never raises: an unreadable fact is a verdict."""
    if pin.kind == "repo":
        return _resolve_repo(pin)
    if pin.kind == "file":
        return _resolve_file(pin)
    if pin.kind in COMMAND_KINDS:
        return _resolve_command(pin, run_commands)
    return PinResult(
        pin=pin,
        verdict=MALFORMED,
        detail=f"'{pin.raw}' is not a pin: the kind must be one of "
        f"{', '.join(KINDS)}",
    )


def _git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _resolve_repo(pin):
    root = pathlib.Path(pin.subject)
    if shutil.which("git") is None:
        return PinResult(pin, UNRESOLVABLE, "git is not on PATH")
    if not root.is_dir() or _git(root, "rev-parse", "--git-dir").returncode != 0:
        return PinResult(pin, UNRESOLVABLE, f"{root} is not a git checkout")
    resolved = _git(root, "rev-parse", "--verify", "--quiet", f"{pin.expected}^{{commit}}")
    if resolved.returncode != 0:
        return PinResult(
            pin,
            UNRESOLVABLE,
            f"{pin.expected} does not resolve to a commit in {root}",
        )
    head = _git(root, "rev-parse", "HEAD")
    if head.returncode != 0:
        return PinResult(pin, UNRESOLVABLE, f"{root} has no HEAD to compare against")
    head = head.stdout.strip()
    ancestor = _git(root, "merge-base", "--is-ancestor", pin.expected, "HEAD")
    if ancestor.returncode == 0:
        return PinResult(pin, OK, f"{pin.expected} is an ancestor of HEAD {head}")
    return PinResult(
        pin,
        MOVED,
        f"{pin.expected} resolves but is not an ancestor of HEAD {head}",
    )


def _resolve_file(pin):
    attribute, _, value = pin.expected.partition("=")
    known = (attribute == "sha256" and len(value) == 64) or (
        attribute == "bytes" and value.isdigit()
    )
    if not known:
        return PinResult(
            pin,
            MALFORMED,
            "a file pin must read `sha256=<64 hex>` or `bytes=<n>`, "
            f"and '{pin.expected}' reads neither",
        )
    path = pathlib.Path(pin.subject)
    if not path.is_file():
        return PinResult(pin, UNRESOLVABLE, f"no such file: {path}")
    payload = path.read_bytes()
    if attribute == "sha256":
        now = hashlib.sha256(payload).hexdigest()
        if now == value:
            return PinResult(pin, OK, f"sha256 is still {now}")
        return PinResult(pin, MOVED, f"sha256 was {value}, is now {now}")
    now = len(payload)
    if now == int(value):
        return PinResult(pin, OK, f"length is still {now} bytes")
    return PinResult(pin, MOVED, f"length was {value} bytes, is now {now} bytes")


def _resolve_command(pin, run_commands):
    if pin.kind in ("count", "exit") and not _is_integer(pin.expected):
        noun = "count" if pin.kind == "count" else "exit"
        return PinResult(
            pin,
            MALFORMED,
            f"a {noun} pin's figure must be an integer, and "
            f"'{pin.expected}' is not",
        )
    if not run_commands:
        return PinResult(
            pin,
            UNRESOLVABLE,
            "the command was not run: --run-commands was not given",
        )
    try:
        done = subprocess.run(
            pin.subject,
            shell=True,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return PinResult(
            pin, UNRESOLVABLE, f"the command did not finish in {COMMAND_TIMEOUT}s"
        )
    if pin.kind == "exit":
        if done.returncode == int(pin.expected):
            return PinResult(pin, OK, f"the command still exits {done.returncode}")
        return PinResult(
            pin,
            MOVED,
            f"the exit code was {pin.expected}, is now {done.returncode}",
        )
    # A failed command is not evidence that the figure changed. Reporting MOVED
    # here would turn a broken pipeline into a false claim about the note.
    if done.returncode != 0:
        return PinResult(pin, UNRESOLVABLE, f"the command exited {done.returncode}")
    printed = done.stdout.strip()
    if pin.kind == "output":
        if printed == pin.expected:
            return PinResult(pin, OK, f"the output is still '{printed}'")
        return PinResult(
            pin, MOVED, f"the output was '{pin.expected}', is now '{printed}'"
        )
    if not _is_integer(printed):
        return PinResult(
            pin,
            UNRESOLVABLE,
            f"the command printed '{printed}', which is not an integer",
        )
    if int(printed) == int(pin.expected):
        return PinResult(pin, OK, f"the count is still {printed}")
    return PinResult(pin, MOVED, f"the count was {pin.expected}, is now {printed}")


def _is_integer(text):
    return bool(text) and (text[1:] if text[0] in "+-" else text).isdigit()


def check_note(path, run_commands=False):
    text = pathlib.Path(path).read_text(encoding="utf-8")
    return NoteResult(
        path=pathlib.Path(path),
        results=[resolve(pin, run_commands) for pin in parse_pins(text)],
    )


@dataclasses.dataclass(frozen=True)
class CorpusResult:
    roots: list
    notes: list
    run_commands: bool

    @property
    def resolved(self):
        """Pins the run actually decided, moved or not. A malformed line and an
        unresolvable pin are NOT counted: neither decided anything."""
        return sum(
            1
            for note in self.notes
            for result in note.results
            if result.verdict in (OK, MOVED)
        )

    @property
    def exit_code(self):
        """Never 0 on 'nothing to check'.

        The two guards are stated separately rather than derived from one
        another. An empty corpus and a corpus of unpinned notes both currently
        fail through the verdict loop as well, and that overlap is deliberate:
        weakening any one of the three cannot make a run that checked nothing
        report success.
        """
        if not self.notes:
            return 1
        if self.resolved == 0:
            return 1
        if any(note.verdict != OK for note in self.notes):
            return 1
        return 0

    def _tally(self):
        counts = {}
        for note in self.notes:
            counts[note.verdict] = counts.get(note.verdict, 0) + 1
        return counts

    def report(self):
        head = "\n".join(f"freshness: {root}" for root in self.roots)
        lines = [
            head,
            f"           {len(self.notes)} note(s) examined, "
            f"{self.resolved} pin(s) resolved",
            "",
        ]
        for note in self.notes:
            lines.append(self._note_lines(note))
        if self.notes:
            lines.append("")
        lines.append(self._verdict())
        return "\n".join(lines) + "\n"

    def _note_lines(self, note):
        name = self._display(note.path)
        if not note.results:
            return (
                f"{name}: {UNPINNED}\n"
                "      the note declares no pins, so no claim in it can be "
                "re-derived. An unpinned note is not a checked note."
            )
        noun = "pin" if len(note.results) == 1 else "pins"
        out = [f"{name}: {note.verdict} ({len(note.results)} {noun})"]
        for result in note.results:
            out.append(
                f"  [{result.verdict}] {result.pin.kind} "
                f"line {result.pin.line} — {result.detail}"
            )
            # The command is printed only when the pin did not hold, so that a
            # reader who must act can act without opening the note.
            if result.verdict != OK and result.pin.kind in COMMAND_KINDS:
                out.append(f"      command: {result.pin.subject}")
        return "\n".join(out)

    def _display(self, path):
        for root in self.roots:
            if root.is_dir():
                try:
                    return str(path.relative_to(root))
                except ValueError:
                    continue
        return str(path)

    def _verdict(self):
        if not self.notes:
            return (
                "RESULT: NO NOTES EXAMINED. The checker found nothing to check, "
                "which is a hard error and never a pass."
            )
        if self.resolved == 0:
            return (
                "RESULT: NO PINS RESOLVED. Every note examined declared nothing "
                f"this run could re-derive ({len(self.notes)} note(s)). Nothing "
                "to check is never a pass."
            )
        counts = self._tally()
        if set(counts) == {OK}:
            return (
                f"RESULT: {counts[OK]} note(s) fresh, every pin re-derived."
            )
        parts = [
            f"{counts[verdict]} {verdict}"
            for verdict in (MOVED, UNRESOLVABLE, MALFORMED, UNPINNED, OK)
            if verdict in counts
        ]
        return (
            f"RESULT: {', '.join(parts)}. A stale note does not announce "
            "itself; this is the announcement."
        )


def check_corpus(paths, run_commands=False):
    """Every `.md` file under every named path, each with its own verdict.

    The population is the FILES ON DISK and not a list of notes that declared
    pins, so a note nobody pinned is examined and reported rather than absent
    from the report.
    """
    roots = [pathlib.Path(p) for p in paths]
    notes = []
    for root in roots:
        if root.is_dir():
            found = sorted(root.rglob("*.md"))
        else:
            found = [root]
        for path in found:
            notes.append(check_note(path, run_commands))
    return CorpusResult(roots=roots, notes=notes, run_commands=run_commands)
