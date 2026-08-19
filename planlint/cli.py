"""The command line.

Exit codes:

  0  every selected lint ran and reported nothing.
  1  a lint reported a finding, or a lint found no input to examine.
  2  the invocation itself is wrong: an unknown lint, a missing plan document,
     or a repository lint with no repository.

`ctest -R` exits 0 when its pattern matches no test. This tool therefore never
exits 0 on "nothing to check".

A lint the default run leaves out is announced and not scored: the exit code is
what the lints that RAN reported, and the verdict line names the ones that did
not, because a report silent about a lint reads exactly like one in which that
lint passed.
"""

import argparse
import dataclasses
import pathlib
import sys
import typing

from planlint import (
    anchors,
    checks,
    closure,
    counts,
    graph,
    implicit,
    payload,
    registrar,
    rule9,
    structure,
    tiers,
    waves,
)
from planlint.document import PlanDocument

# The order is the order the report prints. It runs from the structural lints to
# the ones that catch the classes careful reading kept missing.
#
# `structure` is FIRST because every lint below it reads a parsed document. When
# the markup is broken, the reader below it is reading the wrong text, and a
# report that named the consequence before the cause would send a reader to the
# wrong repair.
DOCUMENT_LINTS = {
    "structure": structure.run,
    "graph": graph.run,
    "waves": waves.run,
    "tiers": tiers.run,
    "checks": checks.run,
    "counts": counts.run,
    "anchors": anchors.run,
    "implicit": implicit.run,
    "registrar": registrar.run,
    "rule9": rule9.run,
    "closure": closure.run,
}
REPOSITORY_LINTS = ("payload",)
ALL_LINTS = list(DOCUMENT_LINTS) + list(REPOSITORY_LINTS)


@dataclasses.dataclass(frozen=True)
class Requirement:
    """What an invocation must supply before a lint has anything to read."""

    flag: str
    satisfied: typing.Callable

    def unmet_because(self):
        return f"no {self.flag} given"


# A lint the default run may leave out declares here what it needs. This table
# is the ONLY route out of the default set, and it is also where the report gets
# the reason it prints, so the two cannot drift: a lint that skips silently
# would have to skip through a route that does not exist.
LINT_REQUIREMENTS = {
    "payload": Requirement("--repo", lambda args: bool(args.repo)),
}


class LintRegistryError(Exception):
    """The registry cannot account for a lint. Raised at import, never caught."""


def validate_lint_registry(all_lints=None, always_run=None, requirements=None):
    """Every lint either always runs or declares what it requires.

    A lint that does neither is the defect one level up: it would leave the
    default run whenever its input was absent, with nothing to print as the
    reason. This raises rather than reports, because a caller cannot repair it
    and a report on stdout would be one more line to skim past.
    """
    all_lints = ALL_LINTS if all_lints is None else all_lints
    always_run = DOCUMENT_LINTS if always_run is None else always_run
    requirements = LINT_REQUIREMENTS if requirements is None else requirements

    for name in all_lints:
        if name not in always_run and name not in requirements:
            raise LintRegistryError(
                f"lint '{name}' neither runs unconditionally nor declares what "
                "it requires, so a run that omits it could not name the reason"
            )
    for name in requirements:
        if name not in all_lints:
            raise LintRegistryError(
                f"a requirement is registered for '{name}', which is not a lint"
            )


validate_lint_registry()


def default_selection(args, all_lints=None, requirements=None):
    """`(selected, skipped)` for a run that named no `--only`.

    `skipped` maps a lint to why it did not run. The reason is a byproduct of
    the decision and not a second list written beside it.
    """
    all_lints = ALL_LINTS if all_lints is None else all_lints
    requirements = LINT_REQUIREMENTS if requirements is None else requirements

    selected = []
    skipped = {}
    for name in all_lints:
        requirement = requirements.get(name)
        if requirement is None or requirement.satisfied(args):
            selected.append(name)
        else:
            skipped[name] = requirement.unmet_because()
    return selected, skipped


def build_parser():
    parser = argparse.ArgumentParser(
        prog="planlint",
        description="Executable lints for the NMG2 implementation plan.",
    )
    parser.add_argument("--plan", required=True, help="path to the plan document")
    parser.add_argument("--repo", help="path to a repository tree, for the payload lint")
    parser.add_argument(
        "--private",
        action="store_true",
        help="the repository given by --repo is PRIVATE; the payload boundary does "
        "not apply to it",
    )
    parser.add_argument(
        "--check-targets",
        metavar="PATH",
        help="path to docs/check-targets.txt to verify set equality with plan Check: targets",
    )
    parser.add_argument(
        "--build-dir",
        action="append",
        default=None,
        metavar="REPO=PATH",
        help="path to a repository build directory for live test registration verification (can be specified multiple times)",
    )
    parser.add_argument(
        "--source-repo",
        action="append",
        default=None,
        metavar="LABEL=PATH",
        help="path to a repository SOURCE tree, for the rule 9 lint's half B. It "
        "reads the CMake files as written and needs no build directory (can be "
        "specified multiple times)",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=None,
        metavar="LINT",
        help=f"run one lint. One of: {', '.join(ALL_LINTS)}",
    )
    return parser


def main(argv=None, stream=None):
    stream = stream or sys.stdout
    args = build_parser().parse_args(argv)

    # A lint the default run leaves out is ANNOUNCED, because a report that says
    # nothing about it reads exactly like one in which it passed. `--only` is
    # the caller's own record of what they asked for, so what it leaves out is
    # not a silent narrowing and carries no notice. Naming a lint explicitly
    # with its requirement unmet stays an error and never becomes a skip.
    if args.only:
        selected, skipped = args.only, {}
    else:
        selected, skipped = default_selection(args)
    unknown = [name for name in selected if name not in ALL_LINTS]
    if unknown:
        stream.write(
            f"unknown lint '{unknown[0]}'. Choose from: {', '.join(ALL_LINTS)}\n"
        )
        return 2

    plan_path = pathlib.Path(args.plan)
    if not plan_path.is_file():
        stream.write(f"no such plan document: {plan_path}\n")
        return 2

    if "payload" in selected and not args.repo:
        stream.write("--repo is required to run the payload lint\n")
        return 2

    source_repos = {}
    for entry in args.source_repo or ():
        if "=" not in entry:
            stream.write(
                f"invalid --source-repo '{entry}', expected LABEL=PATH\n"
            )
            return 2
        label, _, value = entry.partition("=")
        root = pathlib.Path(value.strip())
        if not root.is_dir():
            stream.write(f"no such repository tree: {root}\n")
            return 2
        source_repos[label.strip()] = root

    doc = PlanDocument.from_path(plan_path)
    stream.write(f"planlint: {plan_path}\n")
    stream.write(f"          {len(doc.tasks)} task blocks parsed\n\n")

    failed = False
    for name in ALL_LINTS:
        if name in skipped:
            stream.write(
                f"{name}: SKIPPED — {skipped[name]}; the lint did not run and "
                "its result is unknown\n\n"
            )
            continue
        if name not in selected:
            continue
        if name in DOCUMENT_LINTS:
            if name == "checks":
                result = checks.run(
                    doc,
                    check_targets_path=args.check_targets,
                    build_dirs=args.build_dir,
                )
            elif name == "rule9":
                result = rule9.run(doc, source_repos=source_repos)
            else:
                result = DOCUMENT_LINTS[name](doc)
        else:
            result = payload.run(
                args.repo, public=not args.private, register=doc.fixture_register
            )
        stream.write(result.report())
        stream.write("\n")
        failed = failed or result.failed

    # A skip changes the verdict's WORDING and never its exit code. Scoring it
    # would change what `if planlint; then` means for every existing caller,
    # which is a separate decision from making the skip visible.
    notice = ""
    if skipped:
        noun = "lint" if len(skipped) == 1 else "lints"
        notice = (
            f" {len(skipped)} {noun} SKIPPED ({', '.join(skipped)}). "
            "A skipped lint is not a clean lint."
        )

    if failed:
        stream.write(f"RESULT: findings reported. See each rule above.{notice}\n")
        return 1
    stream.write(
        f"RESULT: {'SELECTED LINTS CLEAN.' if skipped else 'ALL LINTS CLEAN'}"
        f"{notice}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
