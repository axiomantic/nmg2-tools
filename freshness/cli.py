"""The command line for the findings freshness checker.

Exit codes:

  0  every note examined either declared at least one pin and had every pin
     re-derived and hold, or EARNED a SETTLED verdict — and at least one real
     pin was resolved.
  1  a pin MOVED, a pin could not be re-derived, a line was not a pin, a note
     declared no pins at all, a note declared itself settled without a pointer
     this run could re-derive, no note was examined, or no pin was resolved.
  2  the invocation itself is wrong: a path that is not there.

A SETTLED note does not fail the run and cannot on its own pass it. A settled
note is not counted as a resolved pin, so a corpus of nothing but settled
tombstones still exits 1 on "no pins resolved". The exemption removes a false
alarm; it never manufactures a clean run.

`ctest -R` exits 0 when its pattern matches no test, and that is the shape this
tool refuses. It therefore never exits 0 on "nothing to check": an empty corpus and a corpus of wholly unpinned notes are
both exit 1, and each prints which of the two it was.

Running a note's commands is OPT-IN via `--run-commands`. A note is data. Without
the flag a command pin reports UNRESOLVABLE, which fails the run — declining to
run a command is never mistaken for the command having held.

Querying a remote is OPT-IN via `--check-remotes`, and it is a SEPARATE flag.
`git ls-remote` leaves the machine, and the remote it queries is named by a note;
a git remote URL is not inert. The two opt-ins buy different things, so one is
never granted by asking for the other. Without the flag a `remote` pin reports
UNRESOLVABLE and the run fails.
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
    parser.add_argument(
        "--check-remotes",
        action="store_true",
        help="ask the remote a `remote` pin names, with `git ls-remote`, "
        "whether it has the commit. Without this those pins report "
        "UNRESOLVABLE and the run fails.",
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

    result = checker.check_corpus(
        roots,
        run_commands=args.run_commands,
        check_remotes=args.check_remotes,
    )
    stream.write(result.report())
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
