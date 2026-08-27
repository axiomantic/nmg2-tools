"""The command line for the findings freshness checker.

Exit codes:

  0  every note examined declared at least one pin and every pin was
     re-derived and held.
  1  a pin MOVED, a pin could not be re-derived, a line was not a pin, a note
     declared no pins at all, no note was examined, or no pin was resolved.
  2  the invocation itself is wrong: a path that is not there.

`ctest -R` exits 0 when its pattern matches no test, and `planlint` states the
same reasoning for itself one repository over. This tool therefore never exits 0
on "nothing to check": an empty corpus and a corpus of wholly unpinned notes are
both exit 1, and each prints which of the two it was.

Running a note's commands is OPT-IN via `--run-commands`. A note is data. Without
the flag a command pin reports UNRESOLVABLE, which fails the run — declining to
run a command is never mistaken for the command having held.
"""

import argparse
import pathlib
import sys

from freshness import checker


def build_parser():
    parser = argparse.ArgumentParser(
        prog="freshness",
        description="Re-derive the facts a findings note pins, and report the "
        "ones that have moved.",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        metavar="PATH",
        help="a notes directory or a single note. Every `.md` file under a "
        "directory is examined, including one that declares no pins.",
    )
    parser.add_argument(
        "--run-commands",
        action="store_true",
        help="run the shell command a `count`, `exit` or `output` pin names. "
        "Without this those pins report UNRESOLVABLE and the run fails.",
    )
    return parser


def main(argv=None, stream=None):
    stream = stream or sys.stdout
    args = build_parser().parse_args(argv)

    roots = [pathlib.Path(p) for p in args.paths]
    for root in roots:
        if not root.exists():
            stream.write(f"no such note or directory: {root}\n")
            return 2

    result = checker.check_corpus(roots, run_commands=args.run_commands)
    stream.write(result.report())
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
