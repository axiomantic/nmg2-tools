"""The command line.

Exit codes:

  0  every selected lint ran and reported nothing.
  1  a lint reported a finding, or a lint found no input to examine.
  2  the invocation itself is wrong: an unknown lint, a missing plan document,
     or a repository lint with no repository.

`ctest -R` exiting 0 on no match cost this project about a hundred meaningless
checks. This tool therefore never exits 0 on "nothing to check".
"""

import argparse
import pathlib
import sys

from planlint import (
    checks,
    closure,
    counts,
    graph,
    implicit,
    payload,
    registrar,
    structure,
    tiers,
    waves,
)
from planlint.document import PlanDocument

# The order is the order the report prints. It runs from the structural lints to
# the two that catch the classes careful reading kept missing.
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
    "implicit": implicit.run,
    "registrar": registrar.run,
    "closure": closure.run,
}
REPOSITORY_LINTS = ("payload",)
ALL_LINTS = list(DOCUMENT_LINTS) + list(REPOSITORY_LINTS)


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

    # The payload lint reads a repository tree, so it joins the default run only
    # when a tree is given. Naming it explicitly with no `--repo` is an error and
    # never a quiet skip.
    selected = args.only or (
        list(DOCUMENT_LINTS) + (list(REPOSITORY_LINTS) if args.repo else [])
    )
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

    doc = PlanDocument.from_path(plan_path)
    stream.write(f"planlint: {plan_path}\n")
    stream.write(f"          {len(doc.tasks)} task blocks parsed\n\n")

    failed = False
    for name in ALL_LINTS:
        if name not in selected:
            continue
        if name in DOCUMENT_LINTS:
            if name == "checks":
                result = checks.run(
                    doc,
                    check_targets_path=args.check_targets,
                    build_dirs=args.build_dir,
                )
            else:
                result = DOCUMENT_LINTS[name](doc)
        else:
            result = payload.run(
                args.repo, public=not args.private, register=doc.fixture_register
            )
        stream.write(result.report())
        stream.write("\n")
        failed = failed or result.failed

    if failed:
        stream.write("RESULT: findings reported. See each rule above.\n")
        return 1
    stream.write("RESULT: ALL LINTS CLEAN\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
