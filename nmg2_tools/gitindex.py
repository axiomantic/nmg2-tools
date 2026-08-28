"""Read a repository's git index with the entry MODE still attached.

Both repository lints walk the same list of tracked paths and ask different
questions about it, and both were reading it with plain ``git ls-files``,
which prints a submodule gitlink on a line of its own spelled exactly like a
file. The mode is the only thing that tells the two apart, so it is read here
once and neither caller has to know how.

This module is the home for that because neither lint owns the other:
``payload_lint`` needs gitlinks REMOVED from its population, and
``submodule_lint`` needs the same gitlinks as its population. A helper in
either one would have made the other import a check it has nothing to do
with.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# The index mode of a submodule gitlink: a tree entry recording a commit sha
# in another repository. It is not a file mode and there are no bytes behind
# it in this repository.
GITLINK_MODE = "160000"


def index_entries(repo_path: Path) -> list[tuple[str, str]]:
    """Return ``(mode, path)`` for every entry in the repository's index.

    ``-s`` is what makes the mode visible at all; without it a gitlink and a
    file are the same line.

    ``-z`` is what makes the split safe. Without it git QUOTES a path holding
    a tab or a newline, and the parse below would read the quoting as data.
    With it the only tab in a record is the field separator.

    The INDEX is the source, not the last commit. ``git ls-tree -r HEAD``
    exposes the same mode over a DIFFERENT population -- a staged file is in
    one and not the other -- so the two are not interchangeable and the lints
    that documented themselves as reading the index keep reading it.
    """
    result = subprocess.run(
        ["git", "-C", str(repo_path), "ls-files", "-s", "-z"],
        capture_output=True,
        text=True,
        check=True,
    )
    entries: list[tuple[str, str]] = []
    for record in result.stdout.split("\0"):
        if not record:
            continue
        meta, tab, path = record.partition("\t")
        if not tab or not path:
            continue
        entries.append((meta.split(" ", 1)[0], path))
    return entries


def gitlink_paths(repo_path: Path) -> list[str]:
    """Return the paths of the index entries that are submodule gitlinks."""
    return [
        path for mode, path in index_entries(repo_path) if mode == GITLINK_MODE
    ]


def blob_paths(repo_path: Path) -> list[str]:
    """Return the tracked paths that HAVE CONTENT in this repository."""
    return [
        path for mode, path in index_entries(repo_path) if mode != GITLINK_MODE
    ]
