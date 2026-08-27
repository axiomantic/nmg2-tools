"""Lint 13 — the repository half of section 24.6's citation form.

`planlint.markers` asks whether every declared path is NAMED by some entry.
This asks the other question, and section 24.6 states that the two are not one
finding: whether the commit an entry names ever touched the path that entry
claims.

The check is one command per cited commit — `git show --format= --name-only
<sha>`, in the repository the ENTRY names — so it needs no build tree and no
network. It needs a CLONE, and the CLI declares that requirement so that a run
without one announces the lint as SKIPPED rather than reporting it clean.

**This is the first rule in the package that runs a program.** Every other lint
reads files. The constraint is relaxed HERE and nowhere else, and only for a
read-only command: `git show` and `git rev-list` write nothing, `git -C` leaves
the working tree alone, and neither reaches the network. The sha reaching the
command line is matched by `document.SHA` before an entry exists at all, so an
argument shaped like an option cannot become one.

THE AMBIGUITY THE FORM ALREADY REMOVED. A scan that hunted a bare sha across
several clones has two ways to pass for the wrong reason: a sha that resolves
in NONE, and a short sha that resolves in TWO and is compared against a
stranger's history. The citation form names the repository on EVERY entry, so
this lint never hunts — it reads the one clone the entry names, or it reports
that it read nothing.

THE TWO SPELLINGS OF A DECLARED PATH. Section 1.1.1 rule B says a path is
repository-relative, and the plan writes some declared paths that way and some
as a BARE basename — §7.4.2's DSP-21 row records `jitops.cpp`, `jitops.h` and
`dsp_ops.inl` bare and calls that the owning spelling. `--name-only` prints
full paths either way, so comparing the two spellings as strings refutes a
citation the repository confirms. `tree_paths` and `resolve_bare` close that
gap, and the resolution belongs HERE rather than in `planlint.document`: rules
B and C are the DOCUMENT's own abbreviations and `expand_files_items` already
applies both to every entry's paths, but a bare name can only be resolved
against a REPOSITORY, and the document model has none.

RESOLUTION, NOT MATCHING. A bare name is admitted only where the commit's own
tree holds exactly ONE file by that name, and the resolved path is then
compared EXACTLY. A suffix test is the obvious shortcut and it makes this rule
VACUOUS: it admits any path ending in the name, so a citation naming a file in
the wrong directory passes and the rule can no longer fail.

FIVE STATES ARE NOT A VERDICT, and each is REPORTED under
`done-marker-citation-undecided` rather than admitted:

  * no clone was supplied for the repository the entry names;
  * the clone that was supplied does not resolve the sha. A clone may be behind
    or on another remote, so this is a fact about this machine and never a
    refutation of the document;
  * the sha is a MERGE commit. `--name-only` prints nothing for one, so
    "touched nothing" and "is a merge" are the same output, and reading the
    silence as an empty path set would build a false ERROR out of it;
  * no `git` ran at all — absent from the machine, or a clone that did not
    answer inside the timeout;
  * a BARE name that SEVERAL files in the commit's tree answer to. Picking one
    would be the vacuity above arriving one layer down, and reporting an ERROR
    would refute a citation that may well be true. A bare name NO file carries
    is not this state: it is a claim the repository refutes, and it is an ERROR.

The identity says one thing — this pair was not decided — and the EVIDENCE names
which of the four it was. That split is deliberate: a rule whose one message
covered a refutation and a non-reading would be the defect section 24.6 struck
as IM-4, one message for two distinct resolver failures.
"""

import fnmatch
import subprocess

from planlint.finding import ERROR, WARNING, Finding, LintResult, guard_no_input

# A `git` invocation that cannot outlive a lint run. A clone on a stalled
# network mount would otherwise hang the whole report with nothing printed.
TIMEOUT = 60

NO_CLONE = "no clone was supplied for that repository, so nothing was read"
NO_SHA = "the clone supplied for that repository does not resolve the sha"
NO_GIT = "no `git` could be run on this machine, so no repository was read"
MERGE = (
    "the sha is a MERGE commit, and `--name-only` prints no path for one, so "
    "touching nothing and being a merge are indistinguishable here"
)


def ambiguous(path, count):
    """The reason a BARE name that several files answer to decides nothing."""
    return (
        "the entry names a bare file name and the commit's tree holds "
        f"{count} files called `{path}`, so which one it claims is not "
        "decidable"
    )


def _git(root, *args):
    """`(exit status, stdout)` for one read-only git command in `root`.

    A machine with no `git`, and a clone that will not answer inside the
    timeout, are the two ways the command yields no reading at all. Both become
    a status this function's caller turns into an UNDECIDED finding: a
    traceback out of one lint takes the whole report's verdict line with it, so
    "this machine cannot read a repository" has to arrive as a finding and not
    as a crash.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None, ""
    return result.returncode, result.stdout


def changed_paths(root, sha):
    """`(the paths a commit touched, why it could not be read)`.

    A MERGE is distinguished from a commit that touched nothing by asking for
    the parents, because `--name-only` alone cannot tell the two apart.
    """
    status, out = _git(root, "rev-list", "--parents", "-n", "1", sha, "--")
    if status is None:
        return None, NO_GIT
    if status != 0:
        return None, NO_SHA
    if len(out.split()) > 2:
        return None, MERGE
    status, out = _git(root, "show", "--format=", "--name-only", sha, "--")
    if status is None:
        return None, NO_GIT
    if status != 0:
        return None, NO_SHA
    return [line for line in out.splitlines() if line.strip()], None


def tree_paths(root, sha):
    """`(every file the commit's tree holds, why it could not be read)`.

    `git ls-tree -r --name-only` is the second read-only command this rule
    runs, and it exists for ONE reading: the repository half of section
    1.1.1 rule B. `--name-only` on a commit prints repository-relative
    paths; the plan writes some declared paths that way and some as a bare
    basename, and §7.4.2's DSP-21 row records `jitops.cpp`, `jitops.h` and
    `dsp_ops.inl` bare as the OWNING spelling. Comparing the two spellings
    as strings refutes a citation the repository confirms.

    The tree is the commit's own, not HEAD's. A file that moved after the
    commit would otherwise resolve against a directory that did not hold it
    when the commit was made.
    """
    status, out = _git(root, "ls-tree", "-r", "--name-only", sha, "--")
    if status is None:
        return None, NO_GIT
    if status != 0:
        return None, NO_SHA
    return [line for line in out.splitlines() if line.strip()], None


def is_bare(path):
    """Whether an entry names a file WITHOUT saying where it lives.

    A path that carries a directory, a directory itself, and a glob all say
    where they look, and each is compared as written. Only a lone basename
    makes no claim about a location, and only that spelling is resolved.
    """
    return (
        "/" not in path
        and "*" not in path
        and "?" not in path
        and "[" not in path
    )


def resolve_bare(tree, path):
    """`(the one path the tree calls `path`, how many it calls that)`.

    The resolution is the REPOSITORY's, and it is a resolution rather than a
    match: a bare name is admitted only where the tree holds exactly ONE
    file by that name, and the resolved path is then compared EXACTLY. A
    suffix test would instead admit any path ending in the name, which
    passes a citation naming a file in the wrong directory and leaves the
    rule unable to fail.

    Zero matches is NOT ambiguity and is not returned as one. A name no file
    in the tree carries is a claim the repository refutes, and the caller
    reports it as the ERROR it is.
    """
    matches = [found for found in tree if found.rsplit("/", 1)[-1] == path]
    if len(matches) == 1:
        return matches[0], 1
    return None, len(matches)


def covers(touched, path):
    """Whether a commit's changed paths cover a path an entry claims.

    An entry may name a SET rather than one file, in two spellings, and
    `--name-only` prints the literal files either way:

      * a DIRECTORY. REPO-14's citation names `planlint/`, and no commit ever
        touches a directory by name.
      * a GLOB. CPU-7, CPU-8 and CPU-9 each declare a
        `conformance/corpus/*_*.json` corpus and cite it, because the `Files:`
        line declares it that way.

    A set is covered when the commit touched at least one MEMBER of it, which
    is the same reading in both spellings. Comparing either as a literal string
    refutes a true citation, which is what the first run of this rule against
    the plan did to every corpus declaration it read.
    """
    if path.endswith("/"):
        return any(found.startswith(path) for found in touched)
    if "*" in path or "?" in path or "[" in path:
        return any(fnmatch.fnmatchcase(found, path) for found in touched)
    return path in touched


def run(doc, clones=None):
    clones = clones or {}
    findings = []
    examined = 0
    read = {}
    trees = {}

    for marker in doc.done_markers:
        task = doc.task(marker.task)
        section = task.section if task else ""
        for entry in marker.entries:
            root = clones.get(entry.repository)
            key = (entry.repository, entry.sha)
            if key not in read:
                read[key] = (
                    (None, NO_CLONE) if root is None else changed_paths(root, entry.sha)
                )
            touched, undecided = read[key]

            for path in entry.paths:
                examined += 1
                cited = f"`{entry.repository}` `{entry.sha}`"
                reason = undecided
                # What the entry claims, and how it was arrived at. A path
                # written with a directory is its own resolution, so both
                # stay equal to the entry's own text and the clause below is
                # empty. Only a bare name moves, and the evidence says so.
                claimed = path
                resolution = ""
                if reason is None and is_bare(path):
                    if key not in trees:
                        trees[key] = tree_paths(root, entry.sha)
                    tree, tree_undecided = trees[key]
                    if tree_undecided is not None:
                        reason = tree_undecided
                    else:
                        resolved, count = resolve_bare(tree, path)
                        if count > 1:
                            reason = ambiguous(path, count)
                        elif resolved is not None:
                            claimed = resolved
                            resolution = (
                                " — a bare name the commit's tree resolves "
                                f"to `{resolved}`"
                            )
                if reason is not None:
                    findings.append(
                        Finding(
                            rule="done-marker-citation-undecided",
                            message=(
                                "a cited commit and a claimed path were NOT "
                                "decided. The pair is reported rather than "
                                "passed: a scan that reads nothing and a scan "
                                "that passes everything print the same result, "
                                "and this rule refuses to print the second when "
                                "it did the first"
                            ),
                            task=marker.task,
                            section=section,
                            line=marker.line,
                            evidence=(
                                f"{cited} cited for `{path}`: {reason}"
                            ),
                            severity=WARNING,
                        )
                    )
                    continue
                if covers(touched, claimed):
                    continue
                findings.append(
                    Finding(
                        rule="done-marker-commit-not-in-path-history",
                        message=(
                            "a completion marker's citation names a commit for "
                            "a path that commit never touched. An entry states "
                            "which commit covered which path, so an entry "
                            "naming a path outside its own commit is a claim "
                            "the repository refutes"
                        ),
                        task=marker.task,
                        section=section,
                        line=marker.line,
                        evidence=(
                            f"{cited} is cited for `{path}`{resolution}; "
                            f"`git show --format= --name-only {entry.sha}` in "
                            f"that clone lists {len(touched)} path"
                            f"{'' if len(touched) == 1 else 's'} and "
                            f"`{claimed}` is not one of them"
                        ),
                        severity=ERROR,
                    )
                )

    # The guard fires on a document with no TASK BODY, which is the state that
    # means the lint was pointed at something that is not a plan. It does NOT
    # fire on a plan whose markers cite no entry: that state is a real one, it
    # is what 88 of this plan's markers are in, and `planlint.markers` already
    # reports every one of them as `done-marker-citation-not-in-form`. A second
    # alarm on the same fact would say nothing new and would drown the first.
    #
    # The examined COUNT stays the pair, because the pair is what this lint
    # decides and the report has to carry the coverage figure. A run that reads
    # nothing then prints `0 cited (commit, path) pairs examined` beside its
    # clean verdict, rather than printing a clean verdict alone.
    if not doc.tasks:
        return guard_no_input(
            "citations", findings, 0, "task bodies", "citation lint"
        )
    return LintResult(
        name="citations",
        findings=findings,
        examined=examined,
        examined_label="cited (commit, path) pairs",
    )
