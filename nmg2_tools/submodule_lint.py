"""Check that every submodule URL names an authorised public repository.

This check is static. It reads no network. It parses the content of a
``.gitmodules`` file and holds each URL against a fixed authority table.

The authority table below is the same table the plan document states. Keep
it in sync with the plan by hand; this module does not read the plan.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PUBLIC = {
    "axiomantic/mcf5307",
    "axiomantic/nmg2-tools",
    "axiomantic/gearmulator",
    "axiomantic/dsp56300",
    "axiomantic/mc68k",
    "axiomantic/G2-Edit",
    "dsp56300/gearmulator",
    "dsp56300/dsp56300",
    "dsp56300/mc68k",
    "chrispurusha/G2-Edit",
}

PRIVATE = {
    "axiomantic/nmg2-artifacts",
}

# Matches both URL forms:
#   https://github.com/<owner>/<repo>.git
#   git@github.com:<owner>/<repo>.git
_URL_RE = re.compile(
    r"^\s*url\s*=\s*(?:https://github\.com/|git@github\.com:)"
    r"(?P<owner>[^/]+)/(?P<repo>[^/\s]+?)(?:\.git)?\s*$"
)


def _repo_name(url_line: str) -> str | None:
    """Return ``owner/repo`` for a ``.gitmodules`` ``url = ...`` line, or None."""
    m = _URL_RE.match(url_line)
    if not m:
        return None
    return f"{m.group('owner')}/{m.group('repo')}"


def lint_gitmodules_text(text: str) -> list[str]:
    """Return a list of named failures for the given ``.gitmodules`` text."""
    failures: list[str] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        repo = _repo_name(line)
        if repo is None:
            continue
        if repo in PRIVATE:
            failures.append(
                f"SUBMODULE-PRIVATE: line {lineno}: {repo} is a private repository"
            )
        elif repo in PUBLIC:
            continue
        elif repo.startswith("axiomantic/"):
            failures.append(
                f"SUBMODULE-UNLISTED: line {lineno}: {repo} is not on the "
                "public authority list"
            )
        else:
            failures.append(
                f"SUBMODULE-UNKNOWN: line {lineno}: {repo} names a repository "
                "outside both the public and private authority lists"
            )
    return failures


def lint_repo_tree(repo_path: Path) -> list[str]:
    """Lint the ``.gitmodules`` file at the root of ``repo_path``, if any."""
    gitmodules = repo_path / ".gitmodules"
    if not gitmodules.is_file():
        return []
    return lint_gitmodules_text(gitmodules.read_text())


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "repo_path", type=Path, help="path to the repository root to check"
    )
    args = parser.parse_args(argv)

    failures = lint_repo_tree(args.repo_path)
    for failure in failures:
        print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
