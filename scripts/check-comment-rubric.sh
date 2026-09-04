#!/bin/zsh
# Scans a checkout for comment-rubric violations, with a planted control per clause.
#
# WHY THIS EXISTS AS A SCRIPT. The same scan was run by hand a dozen times across
# seven repositories and produced a wrong answer nearly every time before a control
# caught it: the wrong population (default branches, in a project where nothing
# merges), a multi-word path list that zsh did not split, `--include` after the path
# under ugrep, a glob in a fetch refspec, a filename regex that excluded uppercase.
# Every one returned a confident zero.
#
# WHAT IT REPORTS. Raw hits per clause, and nothing else. **A raw match count is not
# a violation count.** Measured across seven repositories: 18 hits, 0 violations --
# every one was protected content. Read each hit before culling any.
#
# Usage:  ./check-comment-rubric.sh <path> [<path> ...]
# Exit:   0 no hits, 1 hits to adjudicate, 2 a control failed (results unusable).

emulate -L zsh
setopt no_unset
(( $# )) || { print -u2 "usage: $0 <path> ..."; exit 2 }

typeset -A PAT
PAT[taskid]='(SCH|PLG|BRD|CHN|CPU|INT|PROTO|DSP|USB|PERF|REPO|TOOL|ORC|SPK|W3)-[0-9]+'
# NOTE on what is NOT here, and why. A bare `rule [0-9]+` was tried and removed:
# on one repository it produced 18 hits and 0 violations, every one a reference to
# a five-rule structure DEFINED AND NUMBERED IN THE SAME FILE (`case_sites.cmake`).
# Local structure is not a foreign-ledger pointer. `rule N` now only fires when a
# design/plan citation qualifies it. A bare `§N.N` was likewise narrowed: it fired
# on a datasheet citation whose own line did not repeat the part number.
PAT[pointer]='[Dd]esign section|[Pp]lan section|[Dd]esign [0-9]+\.[0-9]|(design|plan) section [0-9.]+ rule [0-9]+|AGENTS\.md[^A-Za-z0-9]{0,4}[0-9]'
PAT[counts]='[Tt]here are [0-9]+ (cases|assertions|tests|mutations)|[0-9]+ (cases|assertions|tests) (below|here|in this)'
PAT[history]='[Tt]he previous version|[Ii]t used to be|\bformerly\b'
PAT[coverage]='\bcovers all|\btests all|\bchecks all|exhaustively (covers|tests)'
# `\b` ADDED 2026-09-03: unanchored, `covers all` fired inside `recovers all`
# and `tests all` inside `retests all`. Measured on a 57-head sweep.
PAT[resttree]='[Ee]very other (test|file) in|the rest of the tree|elsewhere in this tree'
PAT[roster]='(stubs|tasks|items|entries|cases|tests|files|branches|work|list|set|they) (are|is) not finished|not yet landed|still a stub'
# NARROWED 2026-09-03: a bare `is not finished` fired on protocol STATE text
# ("the body is not finished"), which is a domain fact, not a roster claim.

# Terms that MATCH a pattern and are NOT violations. Each was hit in this project.
EXEMPT='CRC-16|SHA-256|SHA-1|UTF-8|UTF-16|RFC-[0-9]|AN[0-9]+-[0-9]+|ISP-?118|ISP-?1362|MCF-?5307|DSP-?563|EP-[0-9]|IEEE-[0-9]|JP-8000|JE-8086|QU-24|PC-[0-9]|SP-[0-9]|A6-[0-9]|REG_PC-[0-9]|lint-current'

# EXTENDED 2026-09-03. The list below omitted `*.md`, `*.sh`, `*.json`, `*.toml`,
# `*.nims` and `Dockerfile`, so documentation and shell scripts were NEVER scanned
# in any of the seven repositories -- the cull was unverified for those file types
# while a 57-head sweep reported it clean. An include list is a POPULATION, and a
# population that silently omits a file type returns a confident partial answer.
INC=(--include='*.c' --include='*.h' --include='*.cpp' --include='*.hpp' --include='*.nim'
     --include='*.py' --include='*.cmake' --include='*.yml' --include='*.yaml' --include='*.txt'
     --include='*.md' --include='*.sh' --include='*.json' --include='*.toml'
     --include='*.nims' --include='Dockerfile')

# ---- CONTROL: every pattern must match a planted instance, and the exemption
# ---- list must NOT swallow it. A pattern that cannot fire proves nothing.
CD=$(mktemp -d) || exit 2
cat > "$CD/planted.c" <<'EOF'
// SCH-12 owns this. Design section 2.4 and rule 3 apply.
// There are 6 cases below. The previous version differed.
// This covers all the modes. Every other test in this tree checks it.
// The stubs are not finished.
EOF
cat > "$CD/exempt.c" <<'EOF'
// CRC-16 and SHA-256 and PC-4 and lint-current and ISP1362 and JP-8000.
EOF
fail=0
for k in ${(k)PAT}; do
  h=$(grep -cE -- "${PAT[$k]}" "$CD/planted.c" 2>/dev/null)
  (( h > 0 )) || { print "CONTROL FAILED: clause '$k' does not match its planted line."; fail=1 }
done
e=$(grep -hoE -- "${PAT[taskid]}" "$CD/exempt.c" 2>/dev/null | grep -vcE -- "$EXEMPT")
(( e == 0 )) || { print "CONTROL FAILED: the exemption list let $e technical term(s) through."; fail=1 }
rm -rf "$CD"
(( fail )) && exit 2
print "controls: all ${#PAT} clause patterns fire; exemption list holds"
print ""

# Per-clause counts are reported for triage, but the TOTAL is deduplicated by
# file:line -- one line matching two clauses is one thing to read, not two.
ALL=$(mktemp) || exit 2
for k in ${(k)PAT}; do
  out=$(grep -rnE ${INC} -- "${PAT[$k]}" "$@" 2>/dev/null | grep -vE -- "$EXEMPT")
  n=$(print -r -- "$out" | grep -c . )
  printf '%-10s %s\n' "$k" "$n"
  (( n )) && { print -r -- "$out" | cut -c1-150 | sed 's/^/    /'
               print -r -- "$out" | grep . | cut -d: -f1,2 >> "$ALL" }
done
total=$(sort -u "$ALL" 2>/dev/null | grep -c . )
rm -f "$ALL"

print ""
print "population: $(find "$@" -type f 2>/dev/null | grep -v '/\.git/' | wc -l | tr -d ' ') files under $*"
print "total hits: $total"
(( total )) && { print "Read every hit. A raw count is not a violation count -- across seven"
                 print "repositories this scan produced 18 hits and 0 violations."; exit 1 }
print "no hits"
exit 0
