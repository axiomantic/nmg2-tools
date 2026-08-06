"""Parser for the NMG2 implementation plan.

The plan states its own structure in section 1.1: a task block is a bold header
line that carries an identifier, a name and a tier, and then the fields `Files:`,
`Design:`, `Depends:` and `Check:`.

Section 7.7 states the scope a check lint may read. This module implements that
scope, because a scope stated in prose and not in code is a scope no lint obeys:

  * every `Check:` BLOCK, which ends at the next task header, the next Markdown
    heading, or the end of the document;
  * every command in a milestone table row;
  * every fenced block whose first line does NOT open with `$ `.

A fenced block that opens with `$ ` is a shell transcript. It is a record of a
measurement and never an instruction, and the exclusion has precedence over the
`Check:` block that holds it.
"""

import dataclasses
import pathlib
import re

# A task header carries an identifier, a name and — when the plan obeys its own
# section 7.6 assertion 1 — a tier. The tier group is optional so that a header
# with no tier still parses as a task; the tier lint is what reports it. A header
# that did not parse at all would hand its whole block to the task above it.
TASK_HEADER = re.compile(
    r"^\*\*(?P<ident>[A-Z]{2,6}-\d+) · (?P<name>.+?)\*\*(?: — (?P<tier>.+?))?\s*$"
)
HEADING = re.compile(r"^(?P<hashes>#{1,6}) +(?P<text>.+?)\s*$")
FIELD = re.compile(r"^(?P<field>Files|Design|Depends|Check): ?(?P<value>.*)$")
FENCE = re.compile(r"^\s*```")
IDENT = re.compile(r"\b([A-Z]{2,6}-\d+)\b")
TABLE_ROW = re.compile(r"^\s*\|(?P<cells>.+)\|\s*$")
TABLE_RULE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
MILESTONE_CELL = re.compile(r"^\*\*(M\d+)\*\*$")
RANGE = re.compile(r"^([A-Z]{2,6})-(\d+) +to +([A-Z]{2,6})-(\d+)$")

TEST_SOURCE_SUFFIXES = (".cpp", ".c", ".cc", ".nim", ".py")

# Section 1.1.1 rule B: inside the `gearmulator` fork three directories are
# abbreviated, and the two spellings name ONE file. A lint that compares the
# strings as written reads `g2Lib/test/t0_alloc.cpp` and
# `source/nord/g2/g2Lib/test/CMakeLists.txt` as unrelated directories — which is
# how 34 tasks came to write into a registrar directory none of them declared.
PATH_PREFIXES = {
    "g2Lib/": "source/nord/g2/g2Lib/",
    "g2JucePlugin/": "source/nord/g2/g2JucePlugin/",
    "g2TestConsole/": "source/nord/g2/g2TestConsole/",
}
ELLIPSIS = ".../"


def canonical_path(item):
    """Expand the abbreviations of section 1.1.1 rule B.

    The ellipsis of rule C needs the previous item and is expanded by
    `expand_files_items`, which has it.
    """
    for short, full in PATH_PREFIXES.items():
        if item.startswith(short):
            return full + item[len(short):]
    return item


def expand_files_items(items):
    """A `Files:` list with rules B and C applied, in order.

    Rule C: `.../name.ext` repeats the DIRECTORY of the item before it. An
    ellipsis with no previous directory cannot be expanded and is returned as
    written, so it fails a path comparison loudly instead of resolving to
    something plausible.
    """
    out = []
    previous = None
    for item in items:
        if item.startswith(ELLIPSIS):
            if previous and "/" in previous:
                item = previous.rsplit("/", 1)[0] + "/" + item[len(ELLIPSIS):]
            else:
                out.append(item)
                continue
        item = canonical_path(item)
        out.append(item)
        previous = item
    return out


def strip_markup(text):
    """Remove bold markers and backticks, and collapse whitespace."""
    text = text.replace("**", "")
    text = text.replace("`", "")
    return " ".join(text.split())


# ------------------------------------------------------- the backtick scanner
#
# Defect L-5. A single regex, `` `([^`]+)` ``, paired backticks across a whole
# task body. A fenced block opens with THREE backticks, so the regex swallowed
# the fence BODY as one span and left two backticks over — and every pairing
# after that point was inverted. Prose read as a quoted span, and every quoted
# name read as prose. Everything after the first fence in a task body was
# invisible.
#
# It was measured, not theorised: adding transcripts to five task bodies moved
# the plan from 169 warnings to 166. The count fell while text was added, which
# is the shape a scanner going blind always has, and it reads as an improvement.
#
# Two rules replace the regex, and both of them WIDEN what is seen:
#
#   1. A fenced block is a REGION, not a run of inline spans. It yields no
#      backticked names at all, because a backtick inside a fence is a literal
#      character and delimits nothing. Section 7.7 already treats a fence as its
#      own scope unit — `scoped_segments` hands the non-transcript ones to the
#      check lint whole, and holds the `$ ` transcripts back as records of a
#      measurement. Reading a transcript's printed output as a run of symbol
#      names would attribute a producer to whatever a tool happened to print.
#   2. An inline span never crosses a LINE BREAK, and an unmatched backtick is
#      literal text. That is CommonMark's own reading, and it is what stops one
#      stray backtick from swallowing the remainder of a body. `sentences()`
#      already refuses to cross a line for the same reason.
#
# An UNTERMINATED fence is deliberately NOT a region. Letting it run to the end
# of the text would hide every task below it, which is the failure this scanner
# exists to end. It stays visible and `planlint.structure` reports it.


def fenced_line_indexes(lines):
    """The index of every line inside a CLOSED fence, both markers included.

    A fence with no partner is absent from the result on purpose. `_scan_fences`
    reads the document the same way, so the two agree, and nothing below a
    broken fence is hidden from any lint.
    """
    inside = set()
    open_at = None
    for index, line in enumerate(lines):
        if not FENCE.match(line):
            continue
        if open_at is None:
            open_at = index
        else:
            inside.update(range(open_at, index + 1))
            open_at = None
    return inside


def _scan_line(line, offset, spans, unmatched):
    """Pair the backticks of ONE line. Whatever is left over is literal."""
    ticks = [index for index, char in enumerate(line) if char == "`"]
    position = 0
    while position + 1 < len(ticks):
        opener, closer = ticks[position], ticks[position + 1]
        if closer == opener + 1:
            # An empty span names nothing. The first tick is literal and the
            # second one is offered to the next name, which is what the old
            # `[^`]+` did by requiring a character between the two.
            unmatched.append(offset + opener)
            position += 1
            continue
        spans.append((offset + opener, offset + closer, line[opener + 1:closer]))
        position += 2
    for leftover in ticks[position:]:
        unmatched.append(offset + leftover)


def inline_code_spans(text):
    """`(spans, unmatched)` for a run of text.

    A span is `(opening tick offset, closing tick offset, the text between)`.
    `unmatched` carries the offset of every backtick with no partner on its own
    line, which is what `planlint.structure` reports rather than absorbing.
    """
    lines = text.split("\n")
    fenced = fenced_line_indexes(lines)
    spans = []
    unmatched = []
    offset = 0
    for index, line in enumerate(lines):
        if index not in fenced:
            _scan_line(line, offset, spans, unmatched)
        offset += len(line) + 1
    return spans, unmatched


def backticked(text):
    """Every inline backticked name, in order. The fence-aware `findall`."""
    return [inner for _, _, inner in inline_code_spans(text)[0]]


@dataclasses.dataclass(frozen=True)
class Segment:
    """A run of text the lint scope admits."""

    origin: str
    text: str
    line: int


@dataclasses.dataclass(frozen=True)
class FixtureRow:
    """One row of the section 7.8 recorded-fixture register."""

    fixture: str
    path: str
    named_by: str
    repository: str
    public: bool
    allow_listed: bool
    line: int


@dataclasses.dataclass
class TaskBlock:
    ident: str
    track: str
    number: int
    name: str
    tier_text: str
    line: int
    section: str
    header_text: str = ""
    files_text: str = ""
    design_text: str = ""
    depends_text: str = ""
    check_text: str = ""
    check_line: int = 0
    body_text: str = ""
    body_line: int = 0

    @property
    def tiers(self):
        """The tier set. `T0 and T1` is two tiers, not one."""
        return frozenset(re.findall(r"\bT[0-2]\b", self.tier_text))

    @property
    def has_tier(self):
        return bool(self.tiers)

    @property
    def files_items(self):
        """Every backticked item the `Files:` line names, in order.

        The abbreviations of section 1.1.1 rules B and C are expanded here, so
        that every consumer compares one spelling. A build target carries no
        directory and passes through untouched.
        """
        return expand_files_items(backticked(self.files_text))

    @property
    def files_targets(self):
        """The items the `Files:` line calls build targets rather than paths."""
        match = re.search(r"\btargets?\b", self.files_text)
        if not match:
            return []
        return backticked(self.files_text[match.end():])

    @property
    def files_paths(self):
        targets = set(self.files_targets)
        return [item for item in self.files_items if item not in targets]

    @property
    def test_files(self):
        """The paths that are test translation units or test scripts.

        A test file is what the reverse direction of the section 7.7 lint asserts
        is invoked by some `Check:` line. A registered test nothing runs is the
        same defect as an `-R` that matches nothing, seen from the other side.
        """
        out = []
        for path in self.files_paths:
            if "*" in path:
                continue
            base = path.rsplit("/", 1)[-1]
            stem, _, suffix = base.rpartition(".")
            if not stem or ("." + suffix) not in TEST_SOURCE_SUFFIXES:
                continue
            if re.match(r"^(t[0-2]_|t_|test_)", stem) or stem.endswith("_test"):
                out.append(path)
        return out


class PlanDocument:
    """The plan, parsed."""

    def __init__(self, lines, name):
        self.name = name
        self.lines = lines
        self.tasks = []
        self._by_ident = {}
        self._fences = []
        self._headings = []
        self._tables = []
        self.wave_of = {}
        self.conditional_tasks = set()
        self.repositories = {}
        self.fixture_register = []
        self.owned_paths = {}
        self.cross_track_edges = []
        self.count_rows = []
        self.stated_total_tasks = None
        self._parse()

    # ------------------------------------------------------------------ load

    @classmethod
    def from_text(cls, text, name="<text>"):
        return cls(text.splitlines(), name)

    @classmethod
    def from_path(cls, path):
        path = pathlib.Path(path)
        return cls(path.read_text(encoding="utf-8").splitlines(), str(path))

    # ----------------------------------------------------------------- parse

    def _parse(self):
        self._scan_fences()
        self._scan_headings()
        self._scan_tasks()
        self._scan_tables()

    def _scan_fences(self):
        """Record every fenced block and whether it is a shell transcript."""
        open_at = None
        for index, line in enumerate(self.lines):
            if not FENCE.match(line):
                continue
            if open_at is None:
                open_at = index
            else:
                body = self.lines[open_at + 1:index]
                first = next((b for b in body if b.strip()), "")
                self._fences.append(
                    {
                        "start": open_at,
                        "end": index,
                        "transcript": first.lstrip().startswith("$ "),
                        "body": body,
                    }
                )
                open_at = None

    def _in_fence(self, index):
        for fence in self._fences:
            if fence["start"] <= index <= fence["end"]:
                return fence
        return None

    def _scan_headings(self):
        for index, line in enumerate(self.lines):
            if self._in_fence(index):
                continue
            match = HEADING.match(line)
            if match:
                self._headings.append((index, match.group("text")))

    def _section_at(self, index):
        found = ""
        for line_index, text in self._headings:
            if line_index <= index:
                found = strip_markup(text)
            else:
                break
        return found

    def _scan_tasks(self):
        starts = []
        for index, line in enumerate(self.lines):
            if self._in_fence(index):
                continue
            match = TASK_HEADER.match(line)
            if not match:
                continue
            starts.append((index, match))

        for position, (index, match) in enumerate(starts):
            end = starts[position + 1][0] if position + 1 < len(starts) else len(self.lines)
            for heading_index, _ in self._headings:
                if index < heading_index < end:
                    end = heading_index
                    break
            ident = match.group("ident")
            track, _, number = ident.partition("-")
            task = TaskBlock(
                ident=ident,
                track=track,
                number=int(number),
                name=match.group("name").strip(),
                tier_text=(match.group("tier") or "").strip(),
                header_text=self.lines[index].strip(),
                line=index + 1,
                section=self._section_at(index),
                body_line=index + 1,
                body_text="\n".join(self.lines[index:end]),
            )
            self._fill_fields(task, index + 1, end)
            self.tasks.append(task)
            self._by_ident[ident] = task

    def _fill_fields(self, task, start, end):
        """Read the four fields. `Check:` is a BLOCK and runs to `end`."""
        for index in range(start, end):
            if self._in_fence(index):
                continue
            match = FIELD.match(self.lines[index])
            if not match:
                continue
            field = match.group("field")
            value = match.group("value").strip()
            if field == "Files":
                task.files_text = value
            elif field == "Design":
                task.design_text = value
            elif field == "Depends":
                task.depends_text = value
            elif field == "Check":
                task.check_line = index + 1
                task.check_text = self._block_text(index, end, value)
                return

    def _block_text(self, start, end, first_value):
        """Join a block, dropping every transcript fence it holds."""
        out = [first_value]
        index = start + 1
        while index < end:
            fence = self._in_fence(index)
            if fence:
                if not fence["transcript"]:
                    out.extend(self.lines[fence["start"] + 1:fence["end"]])
                index = fence["end"] + 1
                continue
            out.append(self.lines[index])
            index += 1
        while out and not out[-1].strip():
            out.pop()
        return "\n".join(out).rstrip()

    # ---------------------------------------------------------------- tables

    def _scan_tables(self):
        index = 0
        while index < len(self.lines):
            if self._in_fence(index) or not TABLE_ROW.match(self.lines[index]):
                index += 1
                continue
            start = index
            rows = []
            while index < len(self.lines) and TABLE_ROW.match(self.lines[index]):
                if not TABLE_RULE.match(self.lines[index]):
                    cells = [c.strip() for c in self.lines[index].strip().strip("|").split("|")]
                    rows.append((index + 1, cells))
                index += 1
            if rows:
                self._tables.append(
                    {"line": start + 1, "rows": rows, "section": self._section_at(start)}
                )

        for table in self._tables:
            header = [strip_markup(c).lower() for c in table["rows"][0][1]]
            body = table["rows"][1:]
            if header[:3] == ["wave", "order", "the tasks in it"]:
                self._read_wave_table(body)
            elif header[:2] == ["task", "condition"]:
                self._read_conditional_table(body)
            elif header[:2] == ["repository", "visibility"]:
                self._read_repository_table(body)
            elif header[:5] == ["fixture", "path", "named by", "repository", "visibility"]:
                self._read_fixture_table(body)
            elif header[:2] == ["track", "tasks"]:
                self._read_counts_table(body)
            elif header[:2] == ["path", "owner"]:
                self._read_owner_table(body)
            elif len(header) > 2 and header[2].startswith("cross-track"):
                self._read_cross_track_table(body)

    def _read_wave_table(self, body):
        for line, cells in body:
            if len(cells) < 3:
                continue
            label = strip_markup(cells[0])
            try:
                order = int(strip_markup(cells[1]))
            except ValueError:
                continue
            for ident in expand_identifiers(cells[2]):
                self.wave_of[ident] = (label, order)

    def _read_conditional_table(self, body):
        for _, cells in body:
            ident = strip_markup(cells[0])
            if re.fullmatch(r"[A-Z]{2,6}-\d+", ident):
                self.conditional_tasks.add(ident)

    def _read_repository_table(self, body):
        for _, cells in body:
            names = backticked(cells[0])
            if not names:
                continue
            visibility = "PRIVATE" if "PRIVATE" in cells[1] else "PUBLIC"
            self.repositories[names[0]] = visibility

    def _read_fixture_table(self, body):
        for line, cells in body:
            path_cell = cells[1]
            names = backticked(path_cell)
            path = names[0] if names else strip_markup(path_cell)
            owner = IDENT.search(cells[2])
            repo_names = backticked(cells[3])
            visibility = cells[4]
            self.fixture_register.append(
                FixtureRow(
                    fixture=strip_markup(cells[0]),
                    path=path,
                    named_by=owner.group(1) if owner else "",
                    repository=repo_names[0] if repo_names else strip_markup(cells[3]),
                    public="PRIVATE" not in visibility.upper(),
                    allow_listed="allow-listed" in visibility.lower(),
                    line=line,
                )
            )

    def _read_owner_table(self, body):
        """Section 7.4.2: the shared paths that are not CMake lists."""
        for _, cells in body:
            for path in backticked(cells[0]):
                self.owned_paths[canonical_path(path)] = strip_markup(cells[1])

    def owner_cell(self, path):
        """The section 7.4.2 owner cell for a path, as written, or `None`.

        A row whose path ends in `/` is a DIRECTORY row and owns every path
        beneath it — section 7.4.2 says so, and `g2JucePlugin/` and
        `g2TestConsole/` are the two that rely on it. A file row owns exactly
        the path it names, and it WINS over a directory row that also covers
        the path, because it is the more specific statement.
        """
        if path in self.owned_paths:
            return self.owned_paths[path]
        for owned, cell in self.owned_paths.items():
            if owned.endswith("/") and path.startswith(owned):
                return cell
        return None

    def has_owner(self, path):
        """Whether section 7.4.2 names an owner for a path."""
        return self.owner_cell(path) is not None

    def owner_of(self, path):
        """The task section 7.4.2 names as the OWNER of a path, or `None`.

        The owner is the FIRST identifier in the cell, and every later one is a
        DECLARED SECOND WRITER. Section 7.4.2 writes that shape out —
        `**DSP-0**, with **DSP-1** as the one declared second writer` — and it
        states the difference the identifiers carry: **a registrar CREATES the
        list and registers nothing; a registering task CHANGES the list and
        registers exactly its own names.**

        A cell that names no task block states no owner this tool can resolve.
        Section 7.4.2 carries several — `the plugin track`, `the operator`,
        `append only` — so the answer is `None` and the caller keeps whatever
        reading it holds for a path the document leaves unowned.
        """
        cell = self.owner_cell(path)
        if cell is None:
            return None
        found = IDENT.search(cell)
        if not found or not self.has_task(found.group(1)):
            return None
        return self.task(found.group(1))

    def _read_cross_track_table(self, body):
        """Section 7.3: `A -> B, C; D -> E` is three edges, not two tokens."""
        for _, cells in body:
            for group in strip_markup(cells[2]).split(";"):
                head, arrow, tail = group.partition("\u2192")
                if not arrow:
                    head, arrow, tail = group.partition("->")
                if not arrow:
                    continue
                sources = re.findall(r"[A-Z]{2,6}-\d+", head)
                if not sources:
                    continue
                source = sources[-1]
                for target in re.findall(r"[A-Z]{2,6}-\d+", tail):
                    self.cross_track_edges.append((source, target))

    def _read_counts_table(self, body):
        for line, cells in body:
            label = strip_markup(cells[0])
            value = strip_markup(cells[1])
            number = re.search(r"\d+", value)
            if not number:
                continue
            if "total task blocks" in label.lower():
                self.stated_total_tasks = (int(number.group(0)), line)
                continue
            prefix = re.search(r"\(([A-Z]{2,6})\)", label)
            if prefix:
                self.count_rows.append((prefix.group(1), int(number.group(0)), line, label))

    # ----------------------------------------------------------------- scope

    def scoped_segments(self):
        """Every segment section 7.7 lets a check lint read."""
        segments = []
        covered = set()
        for task in self.tasks:
            if not task.check_text:
                continue
            segments.append(Segment(f"check:{task.ident}", task.check_text, task.check_line))
        for task in self.tasks:
            for index in range(task.line - 1, task.line - 1 + task.body_text.count("\n") + 1):
                covered.add(index)
        for table in self._tables:
            for line, cells in table["rows"]:
                match = MILESTONE_CELL.match(cells[0])
                if match:
                    segments.append(
                        Segment(f"milestone:{match.group(1)}", " | ".join(cells), line)
                    )
        for fence in self._fences:
            if fence["transcript"] or fence["start"] in covered:
                continue
            segments.append(
                Segment(
                    f"fence:{fence['start'] + 1}",
                    "\n".join(fence["body"]) + "\n",
                    fence["start"] + 1,
                )
            )
        return segments

    # --------------------------------------------------------------- lookups

    def task(self, ident):
        return self._by_ident.get(ident)

    def has_task(self, ident):
        return ident in self._by_ident

    @property
    def idents(self):
        return set(self._by_ident)

    def files_name_pool(self):
        """Every name a `Files:` line puts into circulation.

        Both the item as written and its basename without a suffix, because a
        `Check:` line names `t0_alpha` and the `Files:` line names
        `test/t0_alpha.cpp`.

        An EMPTY name is never put into circulation. A `Files:` entry that names
        a DIRECTORY has an empty basename, and the empty string in the pool is
        what let `ctest -R ^$` resolve: the anchors strip to nothing, the pool
        answered yes, and the ERROR gate passed. A `Files:` line creates no name
        that is nothing.
        """
        pool = {}
        for task in self.tasks:
            for item in task.files_items:
                for name in (item, item.rsplit("/", 1)[-1]):
                    if not name:
                        continue
                    pool.setdefault(name, []).append(task.ident)
                    stem = name.rsplit(".", 1)[0]
                    if not stem:
                        continue
                    pool.setdefault(stem, []).append(task.ident)
        return pool


def expand_identifiers(cell):
    """Expand a cell of identifiers and ranges into a list.

    `AAA-1 to AAA-3; BBB-2` is five tokens on paper and four identifiers in fact.
    """
    out = []
    text = strip_markup(cell)
    for group in re.split(r"[;,]", text):
        item = group.strip()
        if not item:
            continue
        match = RANGE.match(item)
        if match:
            low_track, low, high_track, high = match.groups()
            if low_track != high_track:
                continue
            for number in range(int(low), int(high) + 1):
                out.append(f"{low_track}-{number}")
            continue
        if re.fullmatch(r"[A-Z]{2,6}-\d+", item):
            out.append(item)
    return out
