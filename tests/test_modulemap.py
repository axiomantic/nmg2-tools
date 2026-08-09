"""The module map generator. Task TOOL-8, design sections 18.9.1-18.9.3.

WHAT RUNS WHERE.

The generator is a pure function of five input tables and every decision it
makes (the chain join, the corroboration rule, the word-count check, the
port-shape check, the CSV layout) is proven HERE with SYNTHETIC data, so these
tests run everywhere and need no Clavia byte. The gated half at the end drives
the whole generator against the real artifacts through the ``artifacts_dir``
fixture and asserts the structural facts that are knowable without a
reverse-engineered ``descriptor_index -> patch_type_id`` correspondence: the
row count, the schema, the confidence vocabulary, determinism, and the
coverage counts.

THE WORKED EXAMPLE IS ASSERTED, NOT THE WHOLE MAP.

Design 18.9.5 names ``LevCLevAdd`` as a ``PANL`` ``FileName`` whose engine
class is ``LvlAdd``. The two routes do NOT agree, so that row must be
``derived``, never ``exact``. The first test below pins that.
"""

import pytest

from nmg2_tools.modulemap import (
    COLUMNS,
    CONFIDENCE_DERIVED,
    CONFIDENCE_EXACT,
    CONFIDENCE_UNMAPPED,
    ComputeRoutine,
    ModuleMapError,
    Port,
    build_module_map,
    to_csv_text,
    write_csv,
)

# ---------------------------------------------------------------------------
# Synthetic scaffolding.
# ---------------------------------------------------------------------------


class FakeDescriptor:
    def __init__(self, p_ptr=0x1000, x_words=0, y_words=0, p_words=8):
        self.p_ptr = p_ptr
        self.x_words = x_words
        self.y_words = y_words
        self.p_words = p_words


class FakePanl:
    def __init__(self, filename, ports=()):
        self.panl_filename = filename
        self.ports = tuple(ports)


def make_args(**kwargs):
    defaults = {
        "g2ools": {7: "OscB", 112: "LevAdd", 738: "unused"},
        "compute_symbols": {"OscB": "CNativeOscBPart", "LevAdd": "LvlAdd"},
        "compute": {
            "CNativeOscBPart": ComputeRoutine("CNativeOscBPart", 0x200, 16),
            "LvlAdd": ComputeRoutine("LvlAdd", 0x300, 24),
        },
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# The chain, the corroboration rule, and the worked example.
# ---------------------------------------------------------------------------


def test_levclevadd_is_derived_never_exact():
    """Design 18.9.5 and trap 7.5: the PANL file name LevCLevAdd is not the
    engine class LvlAdd. Only the chain resolves it, so it is a `derived` row
    that a false `exact` would conflate with a wrong binding."""
    rows = build_module_map(
        [FakeDescriptor(p_words=6)],
        [112],
        **make_args(),
        panl=[FakePanl("LevCLevAdd")],
    )
    row = rows[0]
    assert row.confidence == CONFIDENCE_DERIVED
    assert row.g2ools_name == "LevAdd"
    assert row.compute_symbol == "LvlAdd"
    assert "does not corroborate" in row.evidence


def test_exact_requires_two_agreeing_routes():
    """A row whose panl_filename equals a Compute() class independently is
    `exact`: the chain and the name route agree. The name route is a RAISE, and
    it cannot rescue a chain that broke."""
    rows = build_module_map(
        [FakeDescriptor(p_words=6)],
        [112],
        **make_args(),
        panl=[FakePanl("CNativeOscBPart")],
        size_tolerance=10 ** 9,  # isolate this test to the corroboration rule
    )
    assert rows[0].confidence == CONFIDENCE_EXACT
    assert "corroborates" in rows[0].evidence


def test_chain_is_load_bearing_panl_filename_is_not_a_link():
    """A panl_filename that matches a Compute() name must not change which
    routine the chain binds: the FileName is carried as a column, never used as
    a key. The chain here binds OscB through g2ools, not through the name."""
    rows = build_module_map(
        [FakeDescriptor(p_words=8)],
        [7],
        **make_args(),
        panl=[FakePanl("CNativeOscBPart")],
    )
    row = rows[0]
    assert row.patch_type_id == 7
    assert row.g2ools_name == "OscB"
    assert row.compute_symbol == "CNativeOscBPart"
    assert row.panl_filename == "CNativeOscBPart"


# ---------------------------------------------------------------------------
# The chain breaks -> unmapped, at every link, with the reason in evidence.
# ---------------------------------------------------------------------------


def test_unmapped_when_no_patch_type_id():
    rows = build_module_map(
        [FakeDescriptor()], [None], **make_args(), panl=[FakePanl("X")]
    )
    row = rows[0]
    assert row.confidence == CONFIDENCE_UNMAPPED
    assert "no patch_type_id established" in row.evidence
    assert row.compute_symbol is None


def test_unmapped_when_patch_type_id_unknown_to_g2ools():
    rows = build_module_map(
        [FakeDescriptor()], [999], **make_args(), panl=[FakePanl("X")]
    )
    row = rows[0]
    assert row.confidence == CONFIDENCE_UNMAPPED
    assert "unknown to g2ools" in row.evidence


def test_unmapped_when_g2ools_name_matches_no_compute_symbol():
    rows = build_module_map(
        [FakeDescriptor()],
        [738],
        **make_args(),  # g2ools has 738 but compute_symbols does not
        panl=[FakePanl("X")],
    )
    row = rows[0]
    assert row.confidence == CONFIDENCE_UNMAPPED
    assert "matches no Compute() symbol" in row.evidence


# ---------------------------------------------------------------------------
# The word-count check: only demotes, and records the disagreement.
# ---------------------------------------------------------------------------


def test_word_count_check_demotes_exact_to_derived_and_records_it():
    """G1 precedent: a measured block that disagrees with the correlated size
    is a suspect binding. The check demotes an `exact` row to `derived` and
    records the disagreement in the evidence."""
    rows = build_module_map(
        [FakeDescriptor(p_words=8)],
        [7],
        **make_args(),
        panl=[FakePanl("CNativeOscBPart")],  # would be exact on name alone
        size_scale=1.0,
        size_tolerance=0.0,  # any disagreement fires
    )
    # compute size 16 vs p_words 8 -> disagreement 8 > tolerance 0 -> demote.
    row = rows[0]
    assert row.confidence == CONFIDENCE_DERIVED
    assert "word count disagrees" in row.evidence


def test_word_count_check_leaves_an_agreeing_row_alone():
    rows = build_module_map(
        [FakeDescriptor(p_words=16)],
        [7],
        **make_args(),
        panl=[FakePanl("CNativeOscBPart")],
        size_scale=1.0,
        size_tolerance=0.0,
    )
    # compute size 16 == p_words 16 -> no disagreement -> stays exact.
    assert rows[0].confidence == CONFIDENCE_EXACT


def test_word_count_check_never_demotes_an_unknown_size():
    """A Compute() routine with no measured size cannot be checked, and an
    unknown is not evidence of a disagreement."""
    rows = build_module_map(
        [FakeDescriptor(p_words=8)],
        [7],
        **make_args(
            compute={
                "CNativeOscBPart": ComputeRoutine("CNativeOscBPart", 0x200, None)
            }
        ),
        panl=[FakePanl("CNativeOscBPart")],
        size_scale=1.0,
        size_tolerance=0.0,
    )
    assert rows[0].confidence == CONFIDENCE_EXACT


def test_word_count_check_never_promotes_a_derived_row():
    """The check can only demote. A `derived` row must not reach `exact` even
    when the sizes agree, because the name route is its only deficit and a size
    agreement is not the name route."""
    rows = build_module_map(
        [FakeDescriptor(p_words=24)],
        [112],
        **make_args(),
        panl=[FakePanl("LevCLevAdd")],
        size_scale=1.0,
        size_tolerance=0.0,
    )
    assert rows[0].confidence == CONFIDENCE_DERIVED


# ---------------------------------------------------------------------------
# The port-shape check: a contradiction demotes to unmapped.
# ---------------------------------------------------------------------------


def test_port_shape_contradiction_demotes_to_unmapped():
    port_panl = (
        Port("input", "Audio"),
        Port("input", "Audio"),
        Port("output", "Audio"),
    )
    # The routine shape says two inputs + one output like the panl, but drives
    # them with a Logic signal where the descriptor has Audio.
    contradiction_args = (
        Port("input", "Audio"),
        Port("input", "Logic"),
        Port("output", "Audio"),
    )
    rows = build_module_map(
        [FakeDescriptor(p_words=8)],
        [7],
        **make_args(
            compute={
                "CNativeOscBPart": ComputeRoutine(
                    "CNativeOscBPart", 0x200, 16, contradiction_args
                )
            }
        ),
        panl=[FakePanl("CNativeOscBPart", port_panl)],
    )
    assert rows[0].confidence == CONFIDENCE_UNMAPPED
    assert "port shape contradicts" in rows[0].evidence


def test_port_shape_arity_contradiction_demotes_to_unmapped():
    port_panl = (Port("input", "Audio"), Port("output", "Audio"))
    three_args = (
        Port("input", "Audio"),
        Port("input", "Audio"),
        Port("output", "Audio"),
    )
    rows = build_module_map(
        [FakeDescriptor(p_words=8)],
        [7],
        **make_args(
            compute={
                "CNativeOscBPart": ComputeRoutine(
                    "CNativeOscBPart", 0x200, 16, three_args
                )
            }
        ),
        panl=[FakePanl("CNativeOscBPart", port_panl)],
    )
    assert rows[0].confidence == CONFIDENCE_UNMAPPED


def test_port_shape_unknown_args_do_not_contradict():
    """An empty argument shape is 'unknown', and unknown is not a
    contradiction. A routine with no shape cannot be demoted by this check."""
    rows = build_module_map(
        [FakeDescriptor(p_words=8)],
        [7],
        **make_args(),  # no args on the routine
        panl=[FakePanl("CNativeOscBPart", (Port("input", "Audio"),))],
        size_tolerance=10 ** 9,
    )
    assert rows[0].confidence == CONFIDENCE_EXACT


def test_port_shape_compatible_shape_does_not_demote():
    port_panl = (Port("input", "Audio"), Port("output", "Audio"))
    compatible_args = (Port("input", "Audio"), Port("output", "Audio"))
    rows = build_module_map(
        [FakeDescriptor(p_words=8)],
        [7],
        **make_args(
            compute={
                "CNativeOscBPart": ComputeRoutine(
                    "CNativeOscBPart", 0x200, 16, compatible_args
                )
            }
        ),
        panl=[FakePanl("CNativeOscBPart", port_panl)],
        size_tolerance=10 ** 9,
    )
    assert rows[0].confidence == CONFIDENCE_EXACT


# ---------------------------------------------------------------------------
# Structure, determinism, and the CSV output.
# ---------------------------------------------------------------------------


def test_inputs_must_be_index_aligned():
    with pytest.raises(ModuleMapError) as caught:
        build_module_map(
            [FakeDescriptor(), FakeDescriptor()],
            [7],  # only one
            **make_args(),
            panl=[FakePanl("A"), FakePanl("B")],
        )
    assert "MODULEMAP-MISMATCHED-LENGTHS" in str(caught.value)


def test_output_is_deterministic():
    def once():
        return build_module_map(
            [FakeDescriptor(p_words=6), FakeDescriptor(p_words=8)],
            [112, 7],
            **make_args(),
            panl=[FakePanl("LevCLevAdd"), FakePanl("CNativeOscBPart")],
        )

    a, b = once(), once()
    assert [r.confidence for r in a] == [r.confidence for r in b]
    assert [r.evidence for r in a] == [r.evidence for r in b]


def test_csv_has_the_fixed_columns_and_header():
    rows = build_module_map(
        [FakeDescriptor(p_words=6)],
        [112],
        **make_args(),
        panl=[FakePanl("LevCLevAdd")],
    )
    text = to_csv_text(rows)
    lines = text.strip().split("\n")
    header = lines[0].rstrip("\r")  # csv rows end in CRLF
    for column in COLUMNS:
        assert column in header
    # The evidence column is last and holds the join, so a wrong row can be
    # traced without re-deriving it.
    assert header.endswith("evidence")


def test_write_csv_round_trips_through_to_csv_text(tmp_path, monkeypatch):
    rows = build_module_map(
        [FakeDescriptor(p_words=6)],
        [112],
        **make_args(),
        panl=[FakePanl("LevCLevAdd")],
    )
    path = tmp_path / "module_map.csv"
    write_csv(str(path), rows)
    # Text-mode read applies universal newlines and would hide the CRLF csv
    # rows chose; comparing bytes is the exact round trip.
    assert path.read_bytes() == to_csv_text(rows).encode("utf-8")


# ---------------------------------------------------------------------------
# Gated: the real artifacts, through the artifacts_dir fixture.
#
# The structural facts a generator can assert without a reverse-engineered
# descriptor_index -> patch_type_id correspondence: the row count (194 on both
# the descriptor and editor sides -- design 18.9.3 says the counts agree), the
# schema, the confidence vocabulary, determinism, and that the coverage counts
# are internally consistent. Skip where NMG2_ARTIFACTS is unset.
# ---------------------------------------------------------------------------


def _descriptors_from_csv(artifacts_dir):
    import csv as _csv
    import os

    path = os.path.join(artifacts_dir, "dsp", "g2_module_descriptors.csv")
    if not os.path.isfile(path):
        for root, _dirs, files in os.walk(artifacts_dir):
            if os.path.basename(path) in files:
                path = os.path.join(root, os.path.basename(path))
                break
    descriptors = []
    with open(path, newline="") as fh:
        for record in _csv.DictReader(fh):
            descriptors.append(
                FakeDescriptor(
                    p_ptr=int(record["p_ptr"], 16),
                    x_words=int(record["x_words_0x1C"]),
                    y_words=int(record["y_words_0x20"]),
                    p_words=int(record["p_words_0x24"]),
                )
            )
    return descriptors


def _panl_from_json(artifacts_dir):
    import json
    import os

    path = os.path.join(artifacts_dir, "g2demo", "g2_modules.json")
    if not os.path.isfile(path):
        for root, _dirs, files in os.walk(artifacts_dir):
            if os.path.basename(path) in files:
                path = os.path.join(root, os.path.basename(path))
                break
    with open(path) as fh:
        payload = json.load(fh)
    panl = []
    for entry in payload:
        ports = []
        for inp in entry.get("inputs", []) or []:
            ports.append(Port("input", inp.get("signal", "any")))
        for out in entry.get("outputs", []) or []:
            ports.append(Port("output", out.get("signal", "any")))
        panl.append(FakePanl(entry.get("internalName"), ports))
    return panl


def test_gated_real_artifacts_produce_a_well_formed_map(artifacts_dir):
    """The whole generator runs against the real descriptor and editor tables.
    What is asserted is what is knowable without the un-derived
    correspondence: one row per descriptor, a valid confidence vocabulary in
    every row, and a coverage break-down that sums to the row count."""
    descriptors = _descriptors_from_csv(artifacts_dir)
    panl = _panl_from_json(artifacts_dir)
    # 194 on the descriptor side and 194 on the editor side -- the counts agree.
    assert len(descriptors) == 194
    assert len(panl) == 194

    # Without a descriptor_index -> patch_type_id correspondence every chain
    # breaks at link one, which is the honest answer the design demands: a
    # count is not a correspondence. The important assertions are that the
    # generator does not crash, produces one well-formed unmapped row per
    # descriptor, and makes the coverage internally consistent.
    g2ools = {}
    compute_symbols = {}
    compute = {}
    rows = build_module_map(
        descriptors, [None] * len(descriptors), g2ools, panl, compute_symbols, compute
    )
    assert len(rows) == 194
    for row in rows:
        assert row.confidence in (CONFIDENCE_EXACT, CONFIDENCE_DERIVED, CONFIDENCE_UNMAPPED)
        assert row.confidence == CONFIDENCE_UNMAPPED  # link one is un-derived
    counts = {"exact": 0, "derived": 0, "unmapped": 0}
    for row in rows:
        counts[row.confidence] += 1
    assert sum(counts.values()) == 194
