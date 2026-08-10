"""The section 1.1.1 rule D marker census, COMPUTED from the source.

A `Files:` entry may declare a write to a file another task owns, and such an
entry is MARKED — `<path>@<OWNER-ID>`. A marked entry is not a claim of
ownership, so a consumer that reads `Files:` data strips the marker, skips the
entry, or keeps the marker on purpose because it needs the `<OWNER-ID>`. Not
every consumer does one of the three.

That fact used to live in a hand-written comment in `planlint/document.py`. The
comment was written three times and was wrong twice, and it failed the same way
both times: it was built by grepping two property names, so it named a correct
set of buckets over an INCOMPLETE set of readers. A list kept by hand in a
comment is a claim with no mechanism behind it. This file is the mechanism.

Two things are computed here rather than restated:

  * the ACCESSOR SET — every attribute through which `Files:` data leaves the
    parser. It is not typed out. It is grown to a fixed point from one seed,
    `files_text`, which `_fill_fields` is asserted to be the only sink of the
    `Files:` field. Any member of `TaskBlock` or `PlanDocument` that reads an
    accessor is itself an accessor, because its result carries the same marked
    strings onward. `files_paths`, `test_files` and `files_name_pool` all enter
    the set that way, and each one is a reader the two earlier grep-built
    censuses missed;
  * the CENSUS — every function in the package that reads an accessor, with the
    handling it applies.

The expected table below is the only hand-written part, and it is what makes
the check able to fail. A new consumer is a row the table does not carry, and a
consumer that changes its handling is a row whose verdict no longer matches.
Both name the function in the failure.

The five verdicts:

  STRIPS   the function calls `strip_marker`, or passes items to an item-level
           helper that calls it.
  SKIPS    the same, for `has_marker`, which drops the entry instead. This is
           what section 7.4.2 asks for, and it is stronger than stripping: one
           bare writer beside one marked writer is still two claimants under a
           stripping reading.
  PARSES   the function builds the item list out of the raw `Files:` text. It
           carries the marker forward on purpose. Stripping HERE would destroy
           the owner id that the unbuilt rules of section 7.4.2 need, so the
           marker survives the parser by design.
  NEITHER  the function compares the marked spelling as written, so a marked
           entry can silently fail to match. See `TaskBlock.test_files`, which
           reads the suffix of `tests/test_packaging.py@REPO-2` as `.py@REPO-2`.

  READS-RAW-TEXT
           the function reads `files_text`, the raw field text, and not a parsed
           item, and it is not itself an accessor.

           This bucket names what is MEASURED and nothing further. It was called
           MARKER-TOLERANT-BY-CONSTRUCTION, and that was a verdict the check
           never reached: containment is not verified. A function whose body is
           `return task.files_text == "..."` reads the raw text, is the OPPOSITE
           of tolerant, and lands here. Under the old name such a function
           arrived as an unnamed row that went red with a WRONG VERDICT already
           filled in, and the cheapest way back to green was to paste that
           verdict into the table below. The name now states the measurement, so
           pasting it claims only what was measured.

           Tolerance is a property of the CONSUMER and not of the bucket. The
           marker is a SUFFIX — `MARKER` is anchored with `$`, which is asserted
           below — so the bare path remains a substring of the raw text and a
           consumer that CONTAINS-tests it still finds the path. Both of today's
           two members do contain-test. A new member has to be read before that
           is believed of it.

The limits of the method, stated so that no reader over-reads the result. There
are three, and the first is OPEN.

  * The ROUTE. This tracks the ATTRIBUTE route, which is the only route the
    package uses today. A consumer that re-parsed the `Files:` line out of
    `body_text` for itself would be outside the closure and no row here would
    report it. The `FIELD` assertion below does NOT close this: a re-parser
    writes its own regex and never names `FIELD`. Nor does such a consumer need
    to recognise the field name at all — `body_text` is
    `"\\n".join(self.lines[index:end])` taken from the task header down, so it
    already holds the `Files:` line verbatim, marker and all. The residual
    stands.
  * The SCOPE. `functions_in` walks `FunctionDef` and `AsyncFunctionDef` only,
    so a read at MODULE level or in a CLASS body belongs to no function and
    yields no row. `ModuleScopeReadTest` below asserts that the package holds no
    such read, which keeps this limit latent instead of silent.
  * The FILE SET. `module_sources` used to glob ONE level of the package and
    skip `__init__.py`, so a subpackage, or a consumer written into an
    `__init__.py`, was invisible. It now walks the tree and reads every module.

Nothing here is fixed. The NEITHER consumers are a structural follow-up, not
this file's business. This file makes them VISIBLE and keeps them counted. Their
number is counted below and is written into no comment.
"""

import ast
import pathlib
import unittest

from planlint import document

PACKAGE = pathlib.Path(document.__file__).parent

# The seed. `_fill_fields` is asserted below to assign the `Files:` value here
# and nowhere else, which is what lets the closure start from one name.
SEED = "files_text"

# Every attribute through which `Files:` data leaves the parser, grown from the
# seed. Six, not the four a grep for two property names finds.
EXPECTED_ACCESSORS = frozenset(
    {
        "files_text",
        "files_items",
        "files_targets",
        "files_paths",
        "test_files",
        "files_name_pool",
    }
)

# The census. `module.Class.function` for a method, `module.function` for a
# module-level one, against the handling the function applies.
EXPECTED_CENSUS = {
    # ------------------------------------------------------------- document
    "document.TaskBlock.files_items": "PARSES",
    "document.TaskBlock.files_targets": "PARSES",
    "document.TaskBlock.files_paths": "NEITHER",
    "document.TaskBlock.test_files": "NEITHER",
    "document.PlanDocument.files_name_pool": "NEITHER",
    # --------------------------------------------------------------- checks
    "checks._check_registration": "READS-RAW-TEXT",
    "checks.run": "NEITHER",
    "checks._reverse_direction": "NEITHER",
    "checks._shared_paths": "SKIPS",
    # -------------------------------------------------------------- closure
    "closure.produced_targets": "NEITHER",
    "closure.produced_symbols": "NEITHER",
    "closure.type_producers": "NEITHER",
    "closure.header_producers": "NEITHER",
    "closure._scopes_of": "NEITHER",
    "closure._in_scope": "NEITHER",
    # ------------------------------------------------------------- implicit
    "implicit.artifact_creators": "NEITHER",
    # ------------------------------------------------------------ registrar
    "registrar.creators_of": "NEITHER",
    "registrar.registrars_of": "NEITHER",
    # ---------------------------------------------------------------- rule9
    "rule9.creators_of": "STRIPS",
    "rule9.run": "STRIPS",
    # ---------------------------------------------------------------- tiers
    "tiers.run": "READS-RAW-TEXT",
}

# The two item-level helpers the marker reading is named by. A helper takes ONE
# entry and reads no accessor of its own, so a function that calls it is handing
# its entries over rather than ignoring them.
MARKER_FUNCTIONS = {"STRIPS": "strip_marker", "SKIPS": "has_marker"}

# The two property names both earlier censuses were grepped for.
GREP_NAMES = frozenset({"files_items", "files_paths"})

# The readers that method cannot reach. This is the ONLY place the set is
# written, and it is held against a DERIVATION below rather than restated in
# prose anywhere else — a file written to end hand-maintained lists must not
# carry two of them. Every member is a NEITHER, and each reaches the `Files:`
# line through an accessor the grep never names.
GREP_BLIND_READERS = frozenset(
    {
        "checks.run",  # through `files_name_pool`
        "checks._reverse_direction",  # through `test_files`
        "closure.produced_targets",  # through `files_targets`
        "closure.produced_symbols",  # through `files_targets`
    }
)


def module_sources():
    """`{module name: syntax tree}` for EVERY module in the package.

    The whole tree, not one level of it, and `__init__.py` is read like any
    other module. A one-level glob that skipped that name could not see a
    consumer in a subpackage or a consumer written into an `__init__.py`.

    The key is the dotted path below the package, so `document.py` stays
    `document` and a nested module reads `sub.mod`. Keying on `path.stem` would
    have collapsed two `__init__.py` files onto one key.
    """
    return {
        ".".join(path.relative_to(PACKAGE).with_suffix("").parts): ast.parse(
            path.read_text(encoding="utf-8")
        )
        for path in sorted(PACKAGE.rglob("*.py"))
    }


def functions_in(tree):
    """`{qualified name: (node, name stack)}` for every function in a module.

    A nested function is carried under the name of the function that holds it,
    so the census can never report a bare `record` or `add` that a reader cannot
    find. A `lambda` and a comprehension open no scope: a read inside one belongs
    to the named function that holds it, which is the function a reader has to go
    and look at.
    """
    found = {}

    def descend(node, stack):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found[".".join(stack + [child.name])] = (child, stack + [child.name])
                descend(child, stack + [child.name])
            elif isinstance(child, ast.ClassDef):
                descend(child, stack + [child.name])

    descend(tree, [])
    return found


def attributes_read(node):
    """Every attribute name the body of a function READS, its own body only.

    A nested function is excluded: its reads belong to the nested function. A
    STORE is excluded too, so `task.files_text = value` in `_fill_fields` is not
    mistaken for a reader of the field it fills.
    """
    names = set()

    def descend(current):
        for child in ast.iter_child_nodes(current):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(child, ast.Attribute) and isinstance(child.ctx, ast.Load):
                names.add(child.attr)
            descend(child)

    descend(node)
    return names


def reads_outside_functions(tree, accessors):
    """Every accessor a module reads OUTSIDE the body of any function.

    A module-level statement and a class body both sit outside every function,
    so `functions_in` gives them no entry and the census can report no row for
    them. A `lambda` and a comprehension open no function, so a read inside one
    at module level is found here. This walk descends INTO a class body on
    purpose and stops at a function, which is where `functions_in` takes over.
    """
    names = set()

    def descend(current):
        for child in ast.iter_child_nodes(current):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(child, ast.Attribute) and isinstance(child.ctx, ast.Load):
                if child.attr in accessors:
                    names.add(child.attr)
            descend(child)

    descend(tree)
    return names


def calls_in(node):
    """Every simple name the body of a function CALLS, its own body only.

    `strip_marker(x)` and `document.strip_marker(x)` both answer `strip_marker`,
    so the reading does not depend on how the import is spelled.
    """
    names = set()

    def descend(current):
        for child in ast.iter_child_nodes(current):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Name):
                    names.add(func.id)
                elif isinstance(func, ast.Attribute):
                    names.add(func.attr)
            descend(child)

    descend(node)
    return names


def accessor_set(trees):
    """Every attribute that carries `Files:` data, grown from the seed.

    A member of `TaskBlock` or `PlanDocument` that reads an accessor becomes one
    itself, because whatever it returns is built out of the same marked strings.
    The loop runs to a fixed point, so the order the members are declared in does
    not change the answer.
    """
    members = {}
    for name, (node, stack) in functions_in(trees["document"]).items():
        if len(stack) == 2 and stack[0] in ("TaskBlock", "PlanDocument"):
            members[stack[1]] = attributes_read(node)

    found = {SEED}
    while True:
        grown = set(found)
        for name, reads in members.items():
            if reads & found:
                grown.add(name)
        if grown == found:
            return frozenset(found)
        found = grown


def item_level_helpers(tree, marker_function, accessors):
    """The functions of one module that apply `marker_function` to ONE entry.

    A helper calls the marker function and reads NO accessor. That second half is
    what separates a helper from a consumer. `rule9.is_registration_list` takes an
    item and strips it, so `rule9.run` handing its items to it is delegation.
    `checks._shared_paths` also calls a marker function, but it reads
    `files_paths` itself, so it is a consumer; `checks.run` calling it says
    nothing about how `checks.run` treats the data IT reads.
    """
    helpers = set()
    while True:
        grown = set(helpers)
        for name, (node, stack) in functions_in(tree).items():
            if attributes_read(node) & accessors:
                continue
            called = calls_in(node)
            if marker_function in called or called & grown:
                grown.add(stack[-1])
        if grown == helpers:
            return helpers
        helpers = grown


def census(trees, accessors):
    """`{qualified name: verdict}` for every reader of an accessor."""
    out = {}
    for module, tree in trees.items():
        helpers = {
            verdict: item_level_helpers(tree, marker, accessors)
            for verdict, marker in MARKER_FUNCTIONS.items()
        }
        for name, (node, stack) in functions_in(tree).items():
            reads = attributes_read(node) & accessors
            if not reads:
                continue
            called = calls_in(node)
            verdict = None
            for candidate, marker in MARKER_FUNCTIONS.items():
                if marker in called or called & helpers[candidate]:
                    verdict = candidate
                    break
            if verdict is None:
                if reads == {SEED}:
                    # PARSES is STRUCTURAL, not a name match. Testing
                    # `stack[-1] in accessors` alone read the NAME, so a
                    # function called `files_items` in any module of the package
                    # was classified as the parser of the field. An accessor is
                    # a member of `TaskBlock` or `PlanDocument` in `document`,
                    # which is the same condition `accessor_set` grows the set
                    # under, so the two now agree.
                    parses = (
                        module == "document"
                        and len(stack) == 2
                        and stack[0] in ("TaskBlock", "PlanDocument")
                        and stack[-1] in accessors
                    )
                    verdict = "PARSES" if parses else "READS-RAW-TEXT"
                else:
                    verdict = "NEITHER"
            out[f"{module}.{name}"] = verdict
    return out


class MarkerSeedTest(unittest.TestCase):
    """The closure starts at one attribute. This class asserts that it may."""

    def test_the_files_field_is_assigned_to_one_attribute_only(self):
        """`_fill_fields` puts the `Files:` value in `files_text` and nowhere
        else. Every later accessor is therefore reachable from that one name."""
        tree = ast.parse(
            pathlib.Path(document.__file__).read_text(encoding="utf-8")
        )
        assigned = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            if ast.unparse(node.test) != "field == 'Files'":
                continue
            for statement in node.body:
                if isinstance(statement, ast.Assign):
                    assigned.extend(ast.unparse(t) for t in statement.targets)

        self.assertEqual(assigned, ["task.files_text"])

    def test_one_module_reads_the_files_line_out_of_the_document(self):
        """The `FIELD` regex is the only route from the raw text to a field. A
        second user would be a reader outside the accessor closure, and the
        census would not see it.

        The name is looked for in the syntax tree and not in the text, so that a
        comment that merely SPEAKS about `FIELD` does not read as a user of it.

        Both spellings count, exactly as `calls_in` counts both. `FIELD` after a
        `from planlint.document import FIELD` is an `ast.Name`; `document.FIELD`
        after a `from planlint import document` is an `ast.Attribute`. Reading
        the first only would have let the second import a user in silence, which
        is the one route this assertion exists to close.
        """
        users = []
        for name, tree in module_sources().items():
            for node in ast.walk(tree):
                named = isinstance(node, ast.Name) and node.id == "FIELD"
                attributed = isinstance(node, ast.Attribute) and node.attr == "FIELD"
                if named or attributed:
                    users.append(name)
                    break

        self.assertEqual(sorted(users), ["document"])

    def test_the_marker_is_a_suffix(self):
        """This is what lets a `files_text` reader contain-test the raw text.
        The bare path stays a substring, so the test still matches it.

        Both sides of the containment derive from the ONE marked spelling and
        from the package. The line compared two string literals before, so no
        change to `MARKER` or to `strip_marker` could redden it, and it was the
        line that underwrote the whole READS-RAW-TEXT reading.
        """
        marked = "a/b.cmake@DSP-0"
        raw = f"Files: `{marked}`, `c/d.txt`"
        bare = document.strip_marker(marked)

        self.assertEqual(document.MARKER.pattern, r"@[A-Z]{2,6}-\d+$")
        self.assertEqual(bare, "a/b.cmake")
        # SUFFIX, asserted as the prefix relation and not as a second literal.
        # What stripping removes comes off the END, so the bare path is a prefix
        # of the marked spelling and therefore a substring of any text carrying
        # it. This is the property the test is named for, and it is the property
        # the READS-RAW-TEXT reading rests on.
        self.assertNotEqual(bare, marked)
        self.assertTrue(marked.startswith(bare))
        self.assertIn(bare, raw)


class AccessorClosureTest(unittest.TestCase):
    """The accessor set is grown, not typed out."""

    def test_the_accessor_set_is_the_one_this_file_names(self):
        self.assertEqual(accessor_set(module_sources()), EXPECTED_ACCESSORS)

    def test_the_seed_alone_is_not_the_answer(self):
        """An accessor set that collapsed to the seed would make the census
        read `files_text` only, and every parsed-item consumer would vanish from
        it silently. That is the shape of both earlier incomplete censuses."""
        found = accessor_set(module_sources())

        self.assertEqual(len(found), 6)
        self.assertEqual(sorted(found - {SEED}), [
            "files_items",
            "files_name_pool",
            "files_paths",
            "files_targets",
            "test_files",
        ])


class ModuleScopeReadTest(unittest.TestCase):
    """The census carries one row per FUNCTION, so a read that belongs to no
    function has no row at all. Such a read is not reported as a wrong verdict.
    It is not reported. `PATHS = [p for t in DOC.tasks for p in t.files_paths]`
    at module scope produced zero rows and no failure.

    This asserts the package holds no such read, which is what keeps the scope
    limit of `functions_in` latent rather than silent.
    """

    def test_no_accessor_is_read_outside_a_function_body(self):
        trees = module_sources()
        accessors = accessor_set(trees)
        offenders = {}
        for module, tree in trees.items():
            found = reads_outside_functions(tree, accessors)
            if found:
                offenders[module] = sorted(found)

        self.assertEqual(offenders, {})


class MarkerCensusTest(unittest.TestCase):
    """The census the package states, against the census this file expects."""

    # The mapping is 21 rows. A truncated diff would hide the very row that
    # moved, which is the failure this file exists to make loud.
    maxDiff = None

    def computed(self):
        return census(module_sources(), accessor_set(module_sources()))

    def test_the_package_holds_exactly_the_consumers_this_file_names(self):
        """A consumer added to the package is a name this assertion reports,
        and a consumer removed is a name it reports as absent.

        The two sets are reported apart from each other and not as one list
        difference, so the failure NAMES the function instead of naming the
        position it took in a sorted list.
        """
        found = self.computed()
        added = sorted(set(found) - set(EXPECTED_CENSUS))
        removed = sorted(set(EXPECTED_CENSUS) - set(found))

        self.assertEqual(
            {"consumers this file does not name": added,
             "consumers this file names that are gone": removed},
            {"consumers this file does not name": [],
             "consumers this file names that are gone": []},
        )

    def test_every_consumer_handles_the_marker_the_way_this_file_states(self):
        found = self.computed()
        changed = {
            name: (EXPECTED_CENSUS[name], verdict)
            for name, verdict in sorted(found.items())
            if name in EXPECTED_CENSUS and verdict != EXPECTED_CENSUS[name]
        }

        self.assertEqual(changed, {})

    def test_the_whole_mapping_is_the_expected_one(self):
        """The two assertions above name a new consumer and a changed verdict
        separately, so a failure says which of the two happened. This one holds
        the mapping whole, so neither can be weakened without the other
        noticing."""
        self.assertEqual(self.computed(), EXPECTED_CENSUS)

    def test_the_counts_the_comment_no_longer_carries(self):
        """`planlint/document.py` used to state these numbers in prose, and the
        prose was wrong twice. They are counted from the source here instead, so
        that moving a consumer between the buckets is a failure and not a
        comment that quietly goes stale."""
        found = self.computed()
        tally = {verdict: 0 for verdict in EXPECTED_CENSUS.values()}
        for verdict in found.values():
            tally[verdict] = tally.get(verdict, 0) + 1

        # FOURTEEN NEITHER rows, COUNTED. The readers a grep for two property
        # names cannot reach are named ONCE, by `GREP_BLIND_READERS`, and are
        # derived rather than restated by the test below; they are not listed
        # again here. This comment states no list and no arithmetic, because a
        # second hand-kept list in the file written to end hand-kept lists is
        # the defect, and this file shipped two that disagreed. The first tally
        # typed into it was wrong and failed here, which is the mechanism
        # working on its own author.
        self.assertEqual(
            tally,
            {
                "PARSES": 2,
                "STRIPS": 2,
                "SKIPS": 1,
                "READS-RAW-TEXT": 2,
                "NEITHER": 14,
            },
        )

    def test_the_readers_a_grep_for_two_property_names_misses(self):
        """The named reason this check exists. Both earlier censuses were built
        by grepping `files_items` and `files_paths`, so a consumer that reaches
        the `Files:` line through any OTHER accessor was invisible to them.

        The set is DERIVED — a NEITHER consumer whose body names neither grepped
        property — and held against the one written list. The derivation reads
        `attributes_read` only and never reads a verdict rule, so this is not a
        test agreeing with itself; `GREP_BLIND_READERS` remains the expectation.

        No count appears in the name of this test. Two hand-typed lists stood
        here and in the tally comment above, both labelled "four" and naming
        DIFFERENT sets, whose union was five. The list is now written once.
        """
        trees = module_sources()
        accessors = accessor_set(trees)
        found = census(trees, accessors)

        blind = set()
        for module, tree in trees.items():
            for name, (node, _) in functions_in(tree).items():
                qualified = f"{module}.{name}"
                if found.get(qualified) != "NEITHER":
                    continue
                if attributes_read(node) & GREP_NAMES:
                    continue
                blind.add(qualified)

        self.assertEqual(sorted(blind), sorted(GREP_BLIND_READERS))


if __name__ == "__main__":
    unittest.main()
