"""The module map generator.

WHAT THE MAP IS FOR.

Oracle Tier 1 diffs the emulated output of module ``N`` against the
``Compute()`` routine of module ``N``. Before that is possible, something must
say which ``Compute()`` belongs to which descriptor. This module builds that
binding: one row per module descriptor.

THE JOIN IS A CHAIN, AND THE ORDER IS LOAD-BEARING.

The chain is stated once, here, and the ``PANL`` ``FileName`` is never a link
in it:

    descriptor_index  ->  patch_type_id  ->  g2ools_name  ->  compute_symbol

``descriptor_index`` is the signature-scan order. ``patch_type_id`` is the
patch-file and wire module type identifier. ``g2ools_name`` is ``msg/g2ools``
``nord/g2/modules.py`` keyed by that identifier. ``compute_symbol`` is the
``Compute()`` routine in ``extracted/g2engine/p2_compute_index.txt``.

The ``PANL`` ``FileName`` is carried as a column so a human can read the table,
and it is used for exactly one thing: to RAISE a row's confidence. Many names
do not match exactly, and one worked example is a mismatch -- ``LevCLevAdd`` is the file name and
``LvlAdd`` is the engine class. A row whose chain produced a ``Compute()``
routine AND whose ``panl_filename`` equals a ``Compute()`` class name on its own
is ``exact`` (two agreeing routes). A row where only the chain agreed is
``derived``. A row where the chain broke is ``unmapped``.

A DEMOTION IS ALWAYS SAFE. A FALSE ``exact`` IS NOT.

A demotion removes a module from Tier 1 and leaves it to Tier 2. A false
``exact`` diffs a module against the wrong oracle: it fails confusingly or,
worse, passes. So both corroboration checks below only ever DEMOTE; they never
promote, and when either disagrees the row is recorded with the disagreement.

THE WORD-COUNT CHECK.

A module's ``Compute()`` code size correlates with its P word count. The G1
precedent is recorded: a Pearson correlation of 0.779 over 86 modules, with the
measured block always larger than the cost table's figure. When the two sizes
disagree beyond the tolerance that precedent allows, an ``exact`` row is
demoted to ``derived`` and the disagreement is
recorded in the evidence.

THE PORT-SHAPE CHECK.

A ``Compute()`` routine's argument shape must be consistent with its
descriptor's ports and signal types (``extracted/g2demo/g2_modules.json``). A
contradiction demotes the row to ``unmapped`` rather than leaving a wrong
binding in place.

WHAT THIS GENERATOR AUTHORS AND WHAT IT LIFTS.

This module contains NO Clavia byte. It is a pure function of its input tables,
and it is written so that a test can drive every decision it makes with
synthetic data. The one link that is not yet proved by any committed artifact --
``descriptor_index -> patch_type_id`` (the counts agree on each side, but a
count is not a correspondence) -- is supplied as an input table, not derived or
guessed here. Where that table is absent for a row, the
row is ``unmapped`` with the reason in its evidence.
"""

from __future__ import annotations

import csv
import dataclasses
import io
from collections.abc import Mapping, Sequence

# The confidence values, ordered.
CONFIDENCE_EXACT = "exact"
CONFIDENCE_DERIVED = "derived"
CONFIDENCE_UNMAPPED = "unmapped"

# The CSV column order. ``evidence`` is last so it never breaks a fixed-width
# read.
COLUMNS = (
    "descriptor_index",
    "p_ptr",
    "x_words",
    "y_words",
    "p_words",
    "patch_type_id",
    "g2ools_name",
    "panl_filename",
    "compute_symbol",
    "compute_addr",
    "confidence",
    "evidence",
)


class ModuleMapError(ValueError):
    """An input this generator refuses to read.

    The message starts with a name: ``MODULEMAP-MISMATCHED-LENGTHS``,
    ``MODULEMAP-BAD-CONFIDENCE`` or ``MODULEMAP-BAD-ARG-DIRECTION``.
    """


@dataclasses.dataclass(frozen=True)
class Port:
    """One port of a module descriptor or of a ``Compute()`` routine.

    ``direction`` is ``"input"`` or ``"output"``. ``signal`` is the signal type
    (Audio, Control, Logic, ...) as the source table spells it.
    """

    direction: str
    signal: str


@dataclasses.dataclass(frozen=True)
class ComputeRoutine:
    """One decompiled ``Compute()`` routine.

    ``symbol`` is the routine's class name. ``addr`` and ``size`` come from
    ``extracted/g2engine/p2_compute_index.txt`` and ``p4_all_compute.c``; a
    ``None`` size means no size is available for the word-count check. ``args``
    is the argument shape used by the port-shape check (empty when it is not
    known).
    """

    symbol: str
    addr: int | None = None
    size: int | None = None
    args: tuple[Port, ...] = ()


@dataclasses.dataclass(frozen=True)
class ModuleRow:
    """One output row of the module map.

    This is the shape of the CSV. ``confidence`` is one of ``exact``,
    ``derived`` or ``unmapped``. ``evidence`` carries the join that produced the
    row so a wrong row can be traced without re-deriving it.
    """

    descriptor_index: int
    p_ptr: int
    x_words: int
    y_words: int
    p_words: int
    patch_type_id: int | None
    g2ools_name: str | None
    panl_filename: str | None
    compute_symbol: str | None
    compute_addr: int | None
    confidence: str
    evidence: str

    def as_dict(self) -> dict[str, object]:
        return {
            "descriptor_index": self.descriptor_index,
            "p_ptr": self.p_ptr,
            "x_words": self.x_words,
            "y_words": self.y_words,
            "p_words": self.p_words,
            "patch_type_id": self.patch_type_id,
            "g2ools_name": self.g2ools_name,
            "panl_filename": self.panl_filename,
            "compute_symbol": self.compute_symbol,
            "compute_addr": self.compute_addr,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


def _signal_compatible(routine_signal: str, panl_signal: str) -> bool:
    """Whether a ``Compute()`` argument's signal and a descriptor port's signal
    are the same enough to be a real binding.

    ``any`` (and ``dynamic``, which is the editor's way of saying "it depends")
    is compatible with any concrete signal. Anything else must match exactly;
    an Audio port is not a Logic port.
    """
    if routine_signal in ("any", "dynamic") or panl_signal in ("any", "dynamic"):
        return True
    return routine_signal == panl_signal


def _port_shape_contradicts(compute_args: Sequence[Port], panl_ports: Sequence[Port]) -> bool:
    """Design 18.9.3 check 2.

    A ``Compute()`` routine with a known argument shape must agree with its
    descriptor's ports: the same number of inputs and outputs, and compatible
    signal types position by position. A contradiction means the chain bound a
    routine that this descriptor cannot actually drive, so the row must fall to
    ``unmapped`` rather than keep a wrong binding.

    An EMPTY argument shape (unknown) never contradicts -- "unknown" is not
    evidence of a contradiction, and demoting every unknown routine would
    empty the map. Only a shape that is KNOWN and WRONG demotes.
    """
    if not compute_args:
        return False

    compute_inputs = [p for p in compute_args if p.direction == "input"]
    compute_outputs = [p for p in compute_args if p.direction == "output"]
    panl_inputs = [p for p in panl_ports if p.direction == "input"]
    panl_outputs = [p for p in panl_ports if p.direction == "output"]

    if len(compute_inputs) != len(panl_inputs) or len(compute_outputs) != len(panl_outputs):
        return True

    for compute_port, panl_port in zip(compute_args, panl_ports):
        if not _signal_compatible(compute_port.signal, panl_port.signal):
            return True

    return False


def _word_count_disagrees(p_words: int | None, compute_size: int | None,
                          scale: float, tolerance: float) -> bool:
    """Design 18.9.3 check 1.

    A module's ``Compute()`` code size correlates with its P word count. The G1
    precedent is a Pearson correlation of 0.779 over 86 modules with the
    measured block always larger. ``scale`` carries the measured-block-to-words
    relationship and ``tolerance`` how far a row may differ before the
    precedent says the binding is suspect. When the sizes disagree beyond the
    tolerance, the check says so and the caller demotes the row.

    A row with no computed size (``None``) cannot be checked and never
    disagrees -- again, an unknown is not evidence of a disagreement.
    """
    if compute_size is None or p_words is None or p_words <= 0:
        return False
    expected = p_words * scale
    return abs(compute_size - expected) > tolerance


def _corroborated_by_name(panl_filename: str | None,
                          compute: Mapping[str, ComputeRoutine]) -> bool:
    """Design 18.9.3: a row is ``exact`` only when TWO routes agree.

    The chain produced the ``compute_symbol``. The independent route is the
    ``panl_filename``: when it equals a ``Compute()`` class name on its own, the
    name route and the chain say the same thing. ``LevCLevAdd`` is ``LvlAdd``'s
    file name and equals no ``Compute()`` class, so that row is ``derived``, not
    ``exact``.
    """
    if not panl_filename:
        return False
    return panl_filename in compute


def build_module_map(
    descriptors: Sequence,
    patch_types: Sequence[int | None],
    g2ools: Mapping[int, str],
    panl: Sequence,
    compute_symbols: Mapping[str, str],
    compute: Mapping[str, ComputeRoutine],
    *,
    size_scale: float = 1.0,
    size_tolerance: float = 0.0,
    word_count_check: bool = True,
    port_shape_check: bool = True,
) -> list[ModuleRow]:
    """Build the module map.

    Every argument is index-aligned over the descriptor set:

    ``descriptors`` -- per descriptor index, the signature-scan record; each
        object needs ``p_ptr``, ``x_words``, ``y_words``, ``p_words``.

    ``patch_types`` -- per descriptor index, the patch-file type identifier, or
        ``None`` when the correspondence is not established.

    ``g2ools`` -- ``patch_type_id -> g2ools_name`` (``msg/g2ools``).

    ``panl`` -- per descriptor index, the editor's descriptor; each object
        needs ``panl_filename`` (the ``PANL`` ``FileName``) and ``ports`` (a
        sequence of :class:`Port`).

    ``compute_symbols`` -- the chain link ``g2ools_name -> compute_symbol``.

    ``compute`` -- ``compute_symbol -> ComputeRoutine``.

    Returns the rows in descriptor-index order, one per descriptor. A row is
    ``exact`` when the chain resolved AND the ``panl_filename`` corroborates it;
    ``derived`` when the chain resolved but the name route did not (or the
    word-count check demoted it); ``unmapped`` when the chain broke or the
    port-shape check demoted it.
    """
    n = len(descriptors)
    if len(patch_types) != n or len(panl) != n:
        raise ModuleMapError(
            "MODULEMAP-MISMATCHED-LENGTHS: "
            f"descriptors={n} patch_types={len(patch_types)} panl={len(panl)}"
        )

    rows: list[ModuleRow] = []
    for index, descriptor in enumerate(descriptors):
        rows.append(
            _build_row(
                index,
                descriptor,
                patch_types[index],
                g2ools,
                panl[index],
                compute_symbols,
                compute,
                size_scale=size_scale,
                size_tolerance=size_tolerance,
                word_count_check=word_count_check,
                port_shape_check=port_shape_check,
            )
        )
    return rows


def _build_row(index, descriptor, patch_type_id, g2ools, panl_entry,
               compute_symbols, compute, *, size_scale, size_tolerance,
               word_count_check, port_shape_check) -> ModuleRow:
    p_ptr = descriptor.p_ptr
    x_words = descriptor.x_words
    y_words = descriptor.y_words
    p_words = descriptor.p_words
    panl_filename = getattr(panl_entry, "panl_filename", None)
    panl_ports = getattr(panl_entry, "ports", ())

    # Link 1: descriptor_index -> patch_type_id.
    if patch_type_id is None:
        return ModuleRow(
            index, p_ptr, x_words, y_words, p_words,
            None, None, panl_filename, None, None,
            CONFIDENCE_UNMAPPED,
            f"descriptor {index}: no patch_type_id established",
        )

    # Link 2: patch_type_id -> g2ools_name.
    g2ools_name = g2ools.get(patch_type_id)
    if g2ools_name is None:
        return ModuleRow(
            index, p_ptr, x_words, y_words, p_words,
            patch_type_id, None, panl_filename, None, None,
            CONFIDENCE_UNMAPPED,
            f"descriptor {index}: patch_type_id {patch_type_id} unknown to g2ools",
        )

    # Link 3: g2ools_name -> compute_symbol.
    compute_symbol = compute_symbols.get(g2ools_name)
    if compute_symbol is None:
        return ModuleRow(
            index, p_ptr, x_words, y_words, p_words,
            patch_type_id, g2ools_name, panl_filename, None, None,
            CONFIDENCE_UNMAPPED,
            f"descriptor {index}: g2ools_name {g2ools_name} matches no Compute() symbol",
        )

    routine = compute.get(compute_symbol)
    routine_args = routine.args if routine is not None else ()
    routine_size = routine.size if routine is not None else None
    compute_addr = routine.addr if routine is not None else None

    # The chain resolved. Establish the base confidence from the routes.
    if _corroborated_by_name(panl_filename, compute):
        confidence = CONFIDENCE_EXACT
        evidence = (
            f"descriptor {index}: chain patch_type_id {patch_type_id} -> "
            f"{g2ools_name} -> {compute_symbol}; panl_filename {panl_filename!r} "
            "corroborates the Compute() name"
        )
    else:
        confidence = CONFIDENCE_DERIVED
        evidence = (
            f"descriptor {index}: chain patch_type_id {patch_type_id} -> "
            f"{g2ools_name} -> {compute_symbol}; panl_filename {panl_filename!r} "
            "does not corroborate the Compute() name"
        )

    # Corroboration check 1: word count. Only ever demotes exact -> derived.
    if (
        word_count_check
        and confidence == CONFIDENCE_EXACT
        and _word_count_disagrees(p_words, routine_size, size_scale, size_tolerance)
    ):
        disagreement = abs((routine_size or 0) - (p_words or 0) * size_scale)
        confidence = CONFIDENCE_DERIVED
        evidence += (
            f"; word count disagrees with Compute() size by {disagreement:.0f}"
        )

    # Corroboration check 2: port shape. Only ever demotes to unmapped.
    if (
        port_shape_check
        and _port_shape_contradicts(routine_args, panl_ports)
    ):
        confidence = CONFIDENCE_UNMAPPED
        evidence += "; port shape contradicts the descriptor's ports"

    if confidence not in (CONFIDENCE_EXACT, CONFIDENCE_DERIVED, CONFIDENCE_UNMAPPED):
        raise ModuleMapError(f"MODULEMAP-BAD-CONFIDENCE: {confidence!r}")

    return ModuleRow(
        index, p_ptr, x_words, y_words, p_words,
        patch_type_id, g2ools_name, panl_filename, compute_symbol, compute_addr,
        confidence, evidence,
    )


def to_csv_text(rows: Sequence[ModuleRow]) -> str:
    """Render the rows as ``module_map.csv`` text, header included.

    The column order and the header are fixed by :data:`COLUMNS`.
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(COLUMNS))
    writer.writeheader()
    for row in rows:
        writer.writerow(row.as_dict())
    return buffer.getvalue()


def write_csv(path, rows: Sequence[ModuleRow]) -> None:
    """Write the map to ``path`` as ``module_map.csv``."""
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(to_csv_text(rows))
