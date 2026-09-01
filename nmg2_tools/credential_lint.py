"""Check that workflow files reference only allowed secrets.

This check reads every workflow file under ``.github/workflows/`` of a
repository, including every reusable workflow file in that same directory.
It is a line-based scan of the raw text. It matches both the interpolated
form ``${{ secrets.NAME }}`` and the bare form ``secrets.NAME`` (the bare
form appears inside reusable-workflow ``secrets:`` blocks).

In a PUBLIC repository, only the three organisation momus secrets, plus the
ambient ``GITHUB_TOKEN`` (which GitHub injects at run time and is never
stored as an organisation or repository secret), are allowed. Any other
``secrets.NAME`` reference is a failure.

In a PRIVATE repository (``--visibility private``) this check passes
unconditionally: private repositories, such as ``nmg2-artifacts``, may
legitimately hold secrets that a public repository must not.

THIS IS AN ABSENCE TEST, SO IT CARRIES CONTROLS. "No disallowed secret was
found" and "no file was read" both used to print nothing and exit 0, which
made a scan that never ran indistinguishable from a clean tree. Two named
findings separate them, in the same shape ``payload_lint`` uses for a
register it cannot read:

  ``CRED-SCOPE-ABSENT``  there is no ``.github/workflows/`` directory
  ``CRED-SCOPE-EMPTY``   the directory holds no ``.yml`` or ``.yaml`` file

Neither is a credential finding. Both say the check did not run, which is
the one thing a clean exit must never be allowed to mean.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ALLOWED_SECRETS = {
    "LLM_API_KEY",
    "MOMUS_APP_ID",
    "MOMUS_APP_PRIVATE_KEY",
    # GITHUB_TOKEN is ambient: GitHub Actions injects it per-run. It is not a
    # stored organisation or repository secret, so referencing it carries no
    # credential-leak risk and it is allowed unconditionally.
    "GITHUB_TOKEN",
}

_SECRET_RE = re.compile(r"secrets\.([A-Za-z_][A-Za-z0-9_]*)")


def lint_workflow_text(text: str, path: str = "<text>") -> list[str]:
    """Return named failures for disallowed ``secrets.NAME`` references."""
    failures: list[str] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for m in _SECRET_RE.finditer(line):
            name = m.group(1)
            if name not in ALLOWED_SECRETS:
                failures.append(
                    f"CRED-FOREIGN-SECRET: {path}:{lineno}: "
                    f"secrets.{name} is not an allowed secret"
                )
    return failures


def lint_repo_tree(repo_path: Path) -> list[str]:
    """Lint every workflow file under ``.github/workflows/`` of a repository.

    FAIL CLOSED ON A DEGENERATE POPULATION. An absent directory and a
    directory with no workflow file in it are both refused by name rather
    than reported clean, because this function cannot tell a repository with
    nothing to check from a checkout that did not land.
    """
    workflows_dir = repo_path / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return [
            f"CRED-SCOPE-ABSENT: {workflows_dir}: not a directory, so no "
            f"workflow file was read and this check proved nothing"
        ]
    workflow_files = [
        candidate
        for candidate in sorted(workflows_dir.rglob("*"))
        if candidate.is_file() and candidate.suffix in (".yml", ".yaml")
    ]
    if not workflow_files:
        return [
            f"CRED-SCOPE-EMPTY: {workflows_dir}: holds no .yml or .yaml file, "
            f"so the scan examined nothing and a clean result says nothing"
        ]
    failures: list[str] = []
    for workflow_file in workflow_files:
        rel = workflow_file.relative_to(repo_path)
        failures.extend(lint_workflow_text(workflow_file.read_text(), str(rel)))
    return failures


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "repo_path", type=Path, help="path to the repository root to check"
    )
    parser.add_argument(
        "--visibility",
        choices=["public", "private"],
        default="public",
        help="repository visibility (default: public)",
    )
    args = parser.parse_args(argv)

    if args.visibility == "private":
        return 0

    failures = lint_repo_tree(args.repo_path)
    for failure in failures:
        print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
