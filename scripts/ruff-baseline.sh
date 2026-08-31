#!/usr/bin/env bash
# Print the ruff baseline for this tree on stdout.
#
# CI regenerates with this script and diffs the result against
# `.ruff-baseline.txt`. Run it the same way to refresh that file:
#
#     scripts/ruff-baseline.sh > .ruff-baseline.txt
#
# The script, not the workflow, owns the format, so a human and CI cannot
# produce two different answers from the same tree.
set -euo pipefail

# `.ruff-version` is the ONE place the version is pinned. The workflow reads the
# same file to decide what to install, so CI and a local run cannot disagree
# about which tool produced a baseline.
#
# It is pinned because the rule set ruff applies by default moves between
# releases: this unmodified tree reports 1 finding under 0.6.9 and 0.12.0 and
# 275 under 0.16.5. `pyproject.toml` pins the rules; this pins the tool.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUFF_VERSION="$(tr -d "[:space:]" < "${here}/.ruff-version")"
if [ -z "${RUFF_VERSION}" ]; then
  echo "no version in ${here}/.ruff-version" >&2
  exit 1
fi

# `RUFF_BIN` lets CI point at a ruff it already installed. Unset, the script
# fetches the pinned version itself, which is what a fresh clone wants.
if [ -n "${RUFF_BIN:-}" ]; then
  ruff_cmd=("${RUFF_BIN}")
else
  ruff_cmd=(uvx "ruff@${RUFF_VERSION}")
fi

cat <<'HDR'
# Every ruff finding this tree currently reports, as `count<TAB>code<TAB>path`.
# Regenerate with `scripts/ruff-baseline.sh > .ruff-baseline.txt`.
#
# THIS FILE IS A RATCHET, NOT A RECORD. CI regenerates it and diffs. A new
# finding makes the diff non-empty and the job fails; so does FIXING one without
# updating this file. Both directions are loud, which is the point: a lint whose
# silence is indistinguishable from a lint that never ran is the defect this
# whole mechanism exists to answer.
#
# Line numbers are deliberately absent. They would churn on every unrelated edit
# and turn the ratchet into noise.
HDR

# ruff exits 1 when it has findings, which is the normal case here, and 2 when
# it could not run at all. Only the second is an error. Without this the `set
# -e` above would treat a tree with findings as a broken run.
set +e
report=$("${ruff_cmd[@]}" check . --output-format json)
status=$?
set -e
if [ "${status}" -ge 2 ]; then
  echo "ruff ${RUFF_VERSION} failed to run (exit ${status})" >&2
  exit 1
fi

printf '%s' "${report}" | python3 -c '
import collections, json, os, sys

findings = json.load(sys.stdin)
counts = collections.Counter(
    (f["code"], os.path.relpath(f["filename"])) for f in findings
)
for (code, path), n in sorted(counts.items(), key=lambda kv: (kv[0][1], kv[0][0])):
    print(f"{n}\t{code}\t{path}")
'
