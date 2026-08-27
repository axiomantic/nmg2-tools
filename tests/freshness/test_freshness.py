"""Tests for the findings freshness checker.

A note in `nmg2-findings` records a measurement. Work lands that invalidates it
and the note keeps reading as current, because nothing connects the two. Six
notes went stale within a day of being written and none announced it; one stale
verdict reached the operator as an instruction that would have destroyed a sound
marker.

This suite holds the checker to the two properties that make it a mechanism
rather than a convention:

  * a pin is RE-DERIVED, so a moved fact is reported as MOVED;
  * the ABSENCE of a pin is itself a finding, and "nothing to check" is never
    exit 0.

The KNOWN POSITIVE and the KNOWN NEGATIVE are carried by
`test_two_count_pins_over_one_real_command_report_the_drifted_figure_and_only_it`:
two `count` pins in one note, running the SAME command over the SAME population
through the SAME resolver, one whose figure has moved and one whose figure has
not. Its subject is a plan fixture COMMITTED TO THIS REPOSITORY, so the pair
states a fact this repository controls.

The real-corpus tests at the bottom are informational and skip when the corpus
is absent. None of them asserts that a document outside this repository is in a
BROKEN state: such a test fails the moment somebody corrects the document, which
is the outcome this whole tool exists to produce.
"""

import hashlib
import pathlib
import shutil
import subprocess
import sys
import textwrap

import pytest

from freshness import checker, cli

ROOT = pathlib.Path(__file__).resolve().parents[2]
CORPUS = pathlib.Path("/Users/eek/Development/nmg2-findings")


def note(tmp_path, body, name="note.md"):
    path = tmp_path / name
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def pin_block(*lines):
    body = "\n".join(lines)
    return f"# A note\n\nSome prose.\n\n```pins\n{body}\n```\n"


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """A two-commit checkout plus one commit on a side branch.

    The side commit resolves and is NOT an ancestor of HEAD, which is the only
    way to tell a pin that still names a real commit from one that names a
    commit the branch has left behind.
    """
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH, so no commit can be resolved")
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.invalid")
    git(root, "config", "user.name", "T")
    (root / "a.txt").write_text("one\n", encoding="utf-8")
    git(root, "add", "a.txt")
    git(root, "commit", "-q", "-m", "one")
    first = git(root, "rev-parse", "HEAD")
    git(root, "checkout", "-q", "-b", "side")
    (root / "b.txt").write_text("side\n", encoding="utf-8")
    git(root, "add", "b.txt")
    git(root, "commit", "-q", "-m", "side")
    side = git(root, "rev-parse", "HEAD")
    git(root, "checkout", "-q", "main")
    (root / "a.txt").write_text("two\n", encoding="utf-8")
    git(root, "add", "a.txt")
    git(root, "commit", "-q", "-m", "two")
    head = git(root, "rev-parse", "HEAD")
    return {"path": root, "first": first, "side": side, "head": head}


# ---------------------------------------------------------------- parsing


def test_parse_reads_every_pin_kind_out_of_a_fenced_block():
    text = pin_block(
        "# a comment, and a blank line below",
        "",
        "repo /tmp/r 0123abc",
        "file /tmp/f sha256=" + "0" * 64,
        "file /tmp/f bytes=17",
        "count 40 -- echo 40",
        "exit 0 -- true",
        "output hello -- echo hello",
    )

    assert checker.parse_pins(text) == [
        checker.Pin(kind="repo", subject="/tmp/r", expected="0123abc", line=8),
        checker.Pin(kind="file", subject="/tmp/f", expected="sha256=" + "0" * 64, line=9),
        checker.Pin(kind="file", subject="/tmp/f", expected="bytes=17", line=10),
        checker.Pin(kind="count", subject="echo 40", expected="40", line=11),
        checker.Pin(kind="exit", subject="true", expected="0", line=12),
        checker.Pin(kind="output", subject="echo hello", expected="hello", line=13),
    ]


def test_parse_collects_pins_from_every_block_in_the_note():
    text = (
        "```pins\nexit 0 -- true\n```\n\nprose\n\n```pins\nexit 1 -- false\n```\n"
    )

    assert checker.parse_pins(text) == [
        checker.Pin(kind="exit", subject="true", expected="0", line=2),
        checker.Pin(kind="exit", subject="false", expected="1", line=8),
    ]


def test_a_fence_that_is_not_a_pins_fence_is_not_read():
    """A note is full of shell transcripts. Only a `pins` fence declares pins."""
    text = "```bash\nexit 0 -- true\n```\n"

    assert checker.parse_pins(text) == []


def test_an_unreadable_line_is_kept_as_a_malformed_pin_and_never_dropped():
    """Dropping it would make a typo read exactly like a note with fewer pins."""
    text = pin_block("nonsense here", "repo /tmp/r 0123abc")

    parsed = checker.parse_pins(text)

    assert parsed == [
        checker.Pin(kind="?", subject="", expected="", line=6, raw="nonsense here"),
        checker.Pin(kind="repo", subject="/tmp/r", expected="0123abc", line=7),
    ]
    assert checker.resolve(parsed[0], run_commands=True) == checker.PinResult(
        pin=parsed[0],
        verdict=checker.MALFORMED,
        detail="'nonsense here' is not a pin: the kind must be one of "
        "count, exit, file, output, remote, repo",
    )


def test_a_count_pin_whose_figure_is_not_an_integer_is_malformed():
    pin = checker.parse_pins(pin_block("count many -- echo 1"))[0]

    assert checker.resolve(pin, run_commands=True) == checker.PinResult(
        pin=pin,
        verdict=checker.MALFORMED,
        detail="a count pin's figure must be an integer, and 'many' is not",
    )


def test_a_file_pin_with_an_unknown_attribute_is_malformed():
    pin = checker.parse_pins(pin_block("file /tmp/f mtime=3"))[0]

    assert checker.resolve(pin, run_commands=True) == checker.PinResult(
        pin=pin,
        verdict=checker.MALFORMED,
        detail="a file pin must read `sha256=<64 hex>` or `bytes=<n>`, "
        "and 'mtime=3' reads neither",
    )


# ---------------------------------------------------------------- repo pins


def test_a_repo_pin_is_ok_when_the_commit_is_still_an_ancestor_of_head(repo):
    pin = checker.parse_pins(
        pin_block(f"repo {repo['path']} {repo['first'][:7]}")
    )[0]

    assert checker.resolve(pin) == checker.PinResult(
        pin=pin,
        verdict=checker.OK,
        detail=f"{repo['first'][:7]} is an ancestor of HEAD {repo['head']}",
    )


def test_a_repo_pin_has_moved_when_head_has_left_the_commit_behind(repo):
    pin = checker.parse_pins(pin_block(f"repo {repo['path']} {repo['side']}"))[0]

    assert checker.resolve(pin) == checker.PinResult(
        pin=pin,
        verdict=checker.MOVED,
        detail=f"{repo['side']} resolves but is not an ancestor of "
        f"HEAD {repo['head']}",
    )


def test_a_repo_pin_naming_a_commit_that_does_not_resolve_is_unresolvable(repo):
    pin = checker.parse_pins(pin_block(f"repo {repo['path']} {'d' * 40}"))[0]

    assert checker.resolve(pin) == checker.PinResult(
        pin=pin,
        verdict=checker.UNRESOLVABLE,
        detail=f"{'d' * 40} does not resolve to a commit in {repo['path']}",
    )


def test_a_repo_pin_naming_a_directory_that_is_not_a_checkout_is_unresolvable(
    tmp_path,
):
    pin = checker.parse_pins(pin_block(f"repo {tmp_path} 0123abc"))[0]

    assert checker.resolve(pin) == checker.PinResult(
        pin=pin,
        verdict=checker.UNRESOLVABLE,
        detail=f"{tmp_path} is not a git checkout",
    )


# -------------------------------------------------------------- remote pins
#
# A `repo` pin asks whether a commit is an ancestor of HEAD, which is a fact
# about THIS MACHINE. Two commits were found in this project that existed on no
# remote at all: one was the tip of a local branch in a submodule AND the commit
# the superproject pinned, so a fresh `git clone --recursive` could not check
# out its own submodule; the other was a detached-HEAD commit in a reference
# clone, and it passed every dirtiness check legitimately because the tree was
# clean. A planned restack that resets each fork's `main` to its upstream head
# would take anything reachable only locally with it.
#
# `refs/remotes/origin/*` cannot answer this. It is a CACHE written by the last
# fetch or push; it can predate the last push, and in a clone whose remote was
# re-pointed it describes a DIFFERENT repository. Every test below is decided by
# `git ls-remote`, and
# `test_the_refs_cache_is_not_evidence_a_re_pointed_remote_has_the_commit`
# arms exactly that trap.


@pytest.fixture
def pushed(tmp_path):
    """A clone with a real remote — a bare repository on disk is a remote.

    Three commits on `main`: `base` and `tip` reached the remote, `local` did
    not. The KNOWN POSITIVE and the KNOWN NEGATIVE therefore live in one
    checkout, are written the same way, and are decided by one resolver. The
    only difference between them is whether the commit was pushed.
    """
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH, so no commit can be resolved")
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "-b", "main", str(origin)],
        capture_output=True,
        text=True,
        check=True,
    )
    work = tmp_path / "work"
    subprocess.run(
        ["git", "clone", "-q", str(origin), str(work)],
        capture_output=True,
        text=True,
        check=True,
    )
    git(work, "config", "user.email", "t@example.invalid")
    git(work, "config", "user.name", "T")
    shas = {}
    for message in ("base", "tip"):
        (work / "a.txt").write_text(message + "\n", encoding="utf-8")
        git(work, "add", "a.txt")
        git(work, "commit", "-q", "-m", message)
        shas[message] = git(work, "rev-parse", "HEAD")
    git(work, "push", "-q", "origin", "main")
    (work / "a.txt").write_text("local\n", encoding="utf-8")
    git(work, "add", "a.txt")
    git(work, "commit", "-q", "-m", "local")
    shas["local"] = git(work, "rev-parse", "HEAD")
    shas["origin"] = origin
    shas["work"] = work
    return shas


def remote_pin(line):
    return checker.parse_pins(pin_block(line))[0]


def test_a_remote_pin_is_ok_when_the_commit_is_the_tip_of_a_remote_ref(pushed):
    """The KNOWN POSITIVE: this commit was pushed and is the branch tip."""
    pin = remote_pin(f"remote {pushed['work']} {pushed['tip']}")

    assert checker.resolve(pin, check_remotes=True) == checker.PinResult(
        pin=pin,
        verdict=checker.OK,
        detail=f"{pushed['tip']} is on origin: it is the tip of refs/heads/main",
    )


def test_a_remote_pin_is_ok_when_the_commit_is_an_ancestor_of_a_remote_ref(pushed):
    pin = remote_pin(f"remote {pushed['work']} {pushed['base']}")

    assert checker.resolve(pin, check_remotes=True) == checker.PinResult(
        pin=pin,
        verdict=checker.OK,
        detail=f"{pushed['base']} is on origin: it is an ancestor of "
        f"refs/heads/main at {pushed['tip']}",
    )


def test_a_remote_pin_has_moved_when_the_commit_reached_no_remote_ref(pushed):
    """The KNOWN NEGATIVE: the commit exists here and nowhere else.

    This is MOVED and not UNRESOLVABLE. The remote answered; the answer was no.
    Conflating the two would reintroduce the blindness this pin kind exists to
    remove — an unpushed commit would read like a check that could not run.
    """
    pin = remote_pin(f"remote {pushed['work']} {pushed['local']}")

    assert checker.resolve(pin, check_remotes=True) == checker.PinResult(
        pin=pin,
        verdict=checker.MOVED,
        detail=f"{pushed['local']} is on no ref of origin: it exists only in "
        "this clone (1 remote ref(s) examined)",
    )


def test_one_note_reports_the_pushed_commit_ok_and_the_unpushed_one_moved(pushed):
    """The discrimination pair for this pin kind: one note, one resolver, two
    commits from one checkout, differing only in whether they were pushed."""
    path = note(
        tmp_path=pushed["work"],
        body=pin_block(
            f"remote {pushed['work']} {pushed['tip']}",
            f"remote {pushed['work']} {pushed['local']}",
        ),
    )

    result = checker.check_note(path, check_remotes=True)

    assert result == checker.NoteResult(
        path=path,
        results=[
            checker.PinResult(
                pin=checker.Pin(
                    kind="remote",
                    subject=str(pushed["work"]),
                    expected=pushed["tip"],
                    line=6,
                ),
                verdict=checker.OK,
                detail=f"{pushed['tip']} is on origin: it is the tip of "
                "refs/heads/main",
            ),
            checker.PinResult(
                pin=checker.Pin(
                    kind="remote",
                    subject=str(pushed["work"]),
                    expected=pushed["local"],
                    line=7,
                ),
                verdict=checker.MOVED,
                detail=f"{pushed['local']} is on no ref of origin: it exists "
                "only in this clone (1 remote ref(s) examined)",
            ),
        ],
    )
    assert result.verdict == checker.MOVED


def test_a_remote_pin_names_the_remote_and_one_commit_can_differ_between_them(
    pushed,
):
    """The same commit, the same clone, two remotes, opposite verdicts.

    `origin` never received it; `backup` did. A resolver that ignored the named
    remote could not produce both of these.
    """
    backup = pushed["work"].parent / "backup.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "-b", "main", str(backup)],
        capture_output=True,
        text=True,
        check=True,
    )
    git(pushed["work"], "remote", "add", "backup", str(backup))
    git(pushed["work"], "push", "-q", "backup", "main")

    on_backup = remote_pin(f"remote {pushed['work']} backup={pushed['local']}")
    on_origin = remote_pin(f"remote {pushed['work']} {pushed['local']}")

    assert checker.resolve(on_backup, check_remotes=True) == checker.PinResult(
        pin=on_backup,
        verdict=checker.OK,
        detail=f"{pushed['local']} is on backup: it is the tip of refs/heads/main",
    )
    assert checker.resolve(on_origin, check_remotes=True) == checker.PinResult(
        pin=on_origin,
        verdict=checker.MOVED,
        detail=f"{pushed['local']} is on no ref of origin: it exists only in "
        "this clone (1 remote ref(s) examined)",
    )


def test_the_refs_cache_is_not_evidence_a_re_pointed_remote_has_the_commit(pushed):
    """The design constraint, armed.

    `refs/remotes/origin/main` still names the pushed commit, because a fetch
    or push wrote it and nothing invalidates it. The URL now points at a
    different repository that has never seen that commit. An implementation
    that read the cache reports OK here; `git ls-remote` reports the truth.
    """
    elsewhere = pushed["work"].parent / "elsewhere.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "-b", "main", str(elsewhere)],
        capture_output=True,
        text=True,
        check=True,
    )
    git(pushed["work"], "remote", "set-url", "origin", str(elsewhere))
    assert git(pushed["work"], "rev-parse", "refs/remotes/origin/main") == pushed["tip"]

    pin = remote_pin(f"remote {pushed['work']} {pushed['tip']}")

    assert checker.resolve(pin, check_remotes=True) == checker.PinResult(
        pin=pin,
        verdict=checker.MOVED,
        detail=f"{pushed['tip']} is on no ref of origin: it exists only in "
        "this clone (0 remote ref(s) examined)",
    )


def test_a_remote_pin_is_unresolvable_until_the_caller_opts_in(pushed):
    """`git ls-remote` is a network call, and the remote URL comes from a note.
    Querying it is a decision the invocation makes, and declining reports
    UNRESOLVABLE rather than passing the pin."""
    pin = remote_pin(f"remote {pushed['work']} {pushed['tip']}")

    assert checker.resolve(pin, check_remotes=False) == checker.PinResult(
        pin=pin,
        verdict=checker.UNRESOLVABLE,
        detail="the remote was not queried: --check-remotes was not given",
    )


def test_a_remote_pin_is_unresolvable_when_the_remote_cannot_be_reached(pushed):
    """Offline is not absent. A remote that cannot be queried says nothing
    about where the commit is, and reporting OK here would be the exact silent
    pass this pin kind exists to prevent."""
    git(
        pushed["work"],
        "remote",
        "set-url",
        "origin",
        str(pushed["work"].parent / "no-such-repository.git"),
    )
    pin = remote_pin(f"remote {pushed['work']} {pushed['tip']}")

    assert checker.resolve(pin, check_remotes=True) == checker.PinResult(
        pin=pin,
        verdict=checker.UNRESOLVABLE,
        detail=f"git ls-remote origin exited 128 in {pushed['work']}; the "
        "remote could not be queried",
    )


def test_a_remote_ref_this_clone_lacks_the_objects_for_is_unresolvable_not_moved(
    pushed,
):
    """A ref the clone never fetched could contain the commit. Answering MOVED
    would be a claim the run cannot support."""
    other = pushed["work"].parent / "other"
    subprocess.run(
        ["git", "clone", "-q", str(pushed["origin"]), str(other)],
        capture_output=True,
        text=True,
        check=True,
    )
    git(other, "config", "user.email", "t@example.invalid")
    git(other, "config", "user.name", "T")
    git(other, "checkout", "-q", "-b", "feature")
    (other / "c.txt").write_text("elsewhere\n", encoding="utf-8")
    git(other, "add", "c.txt")
    git(other, "commit", "-q", "-m", "feature")
    git(other, "push", "-q", "origin", "feature")

    pin = remote_pin(f"remote {pushed['work']} {pushed['local']}")

    assert checker.resolve(pin, check_remotes=True) == checker.PinResult(
        pin=pin,
        verdict=checker.UNRESOLVABLE,
        detail=f"{pushed['local']} is on none of the 1 remote ref(s) this "
        "clone can examine, and 1 more could not be examined because this "
        "clone does not have their objects; fetch origin and re-run",
    )


def test_a_remote_pin_naming_a_commit_that_does_not_resolve_is_unresolvable(pushed):
    pin = remote_pin(f"remote {pushed['work']} {'d' * 40}")

    assert checker.resolve(pin, check_remotes=True) == checker.PinResult(
        pin=pin,
        verdict=checker.UNRESOLVABLE,
        detail=f"{'d' * 40} does not resolve to a commit in {pushed['work']}",
    )


def test_a_remote_pin_naming_a_directory_that_is_not_a_checkout_is_unresolvable(
    tmp_path,
):
    pin = remote_pin(f"remote {tmp_path} 0123abc")

    assert checker.resolve(pin, check_remotes=True) == checker.PinResult(
        pin=pin,
        verdict=checker.UNRESOLVABLE,
        detail=f"{tmp_path} is not a git checkout",
    )


def test_a_remote_pin_whose_figure_is_not_a_sha_is_malformed():
    """The tool's first five catches were all defects in the PINS, not in the
    notes. A template that emits the kind and loses the sha must be reported."""
    pin = remote_pin("remote /tmp/r not-a-sha")

    assert checker.resolve(pin, check_remotes=True) == checker.PinResult(
        pin=pin,
        verdict=checker.MALFORMED,
        detail="a remote pin must read `<sha>` or `<remote>=<sha>` with at "
        "least 4 hex digits, and 'not-a-sha' reads neither",
    )


def test_a_remote_pin_with_an_empty_remote_name_is_malformed():
    pin = remote_pin("remote /tmp/r =0123abcd")

    assert checker.resolve(pin, check_remotes=True) == checker.PinResult(
        pin=pin,
        verdict=checker.MALFORMED,
        detail="a remote pin must read `<sha>` or `<remote>=<sha>` with at "
        "least 4 hex digits, and '=0123abcd' reads neither",
    )


# ---------------------------------------------------------------- file pins


def test_a_file_sha256_pin_is_ok_when_the_bytes_are_unchanged(tmp_path):
    target = tmp_path / "artifact.bin"
    target.write_bytes(b"stable")
    digest = hashlib.sha256(b"stable").hexdigest()
    pin = checker.parse_pins(pin_block(f"file {target} sha256={digest}"))[0]

    assert checker.resolve(pin) == checker.PinResult(
        pin=pin, verdict=checker.OK, detail=f"sha256 is still {digest}"
    )


def test_a_file_sha256_pin_has_moved_when_the_bytes_changed(tmp_path):
    target = tmp_path / "artifact.bin"
    target.write_bytes(b"moved")
    pinned = hashlib.sha256(b"stable").hexdigest()
    now = hashlib.sha256(b"moved").hexdigest()
    pin = checker.parse_pins(pin_block(f"file {target} sha256={pinned}"))[0]

    assert checker.resolve(pin) == checker.PinResult(
        pin=pin,
        verdict=checker.MOVED,
        detail=f"sha256 was {pinned}, is now {now}",
    )


def test_a_file_bytes_pin_has_moved_when_the_length_changed(tmp_path):
    target = tmp_path / "artifact.bin"
    target.write_bytes(b"1234567")
    pin = checker.parse_pins(pin_block(f"file {target} bytes=4"))[0]

    assert checker.resolve(pin) == checker.PinResult(
        pin=pin, verdict=checker.MOVED, detail="length was 4 bytes, is now 7 bytes"
    )


def test_a_file_bytes_pin_is_ok_when_the_length_is_unchanged(tmp_path):
    target = tmp_path / "artifact.bin"
    target.write_bytes(b"1234")
    pin = checker.parse_pins(pin_block(f"file {target} bytes=4"))[0]

    assert checker.resolve(pin) == checker.PinResult(
        pin=pin, verdict=checker.OK, detail="length is still 4 bytes"
    )


def test_a_file_pin_naming_a_file_that_is_gone_is_unresolvable(tmp_path):
    missing = tmp_path / "gone.bin"
    pin = checker.parse_pins(pin_block(f"file {missing} bytes=4"))[0]

    assert checker.resolve(pin) == checker.PinResult(
        pin=pin, verdict=checker.UNRESOLVABLE, detail=f"no such file: {missing}"
    )


# ------------------------------------------------------------ command pins


def test_a_command_pin_is_unresolvable_until_the_caller_opts_in():
    """A note is data. Running what it says is a decision the invocation makes,
    and declining it reports UNRESOLVABLE rather than passing the pin."""
    pin = checker.parse_pins(pin_block("count 1 -- echo 1"))[0]

    assert checker.resolve(pin, run_commands=False) == checker.PinResult(
        pin=pin,
        verdict=checker.UNRESOLVABLE,
        detail="the command was not run: --run-commands was not given",
    )


def test_a_count_pin_is_ok_when_the_command_still_prints_the_figure():
    pin = checker.parse_pins(pin_block("count 40 -- echo 40"))[0]

    assert checker.resolve(pin, run_commands=True) == checker.PinResult(
        pin=pin, verdict=checker.OK, detail="the count is still 40"
    )


def test_a_count_pin_has_moved_when_the_command_prints_a_different_figure():
    pin = checker.parse_pins(pin_block("count 40 -- echo 2"))[0]

    assert checker.resolve(pin, run_commands=True) == checker.PinResult(
        pin=pin, verdict=checker.MOVED, detail="the count was 40, is now 2"
    )


def test_a_count_pin_whose_command_fails_is_unresolvable_not_moved():
    """A broken pipeline is not evidence that the figure changed."""
    pin = checker.parse_pins(pin_block("count 40 -- echo 40; exit 3"))[0]

    assert checker.resolve(pin, run_commands=True) == checker.PinResult(
        pin=pin,
        verdict=checker.UNRESOLVABLE,
        detail="the command exited 3",
    )


def test_a_count_pin_whose_command_prints_no_figure_is_unresolvable():
    pin = checker.parse_pins(pin_block("count 40 -- echo not-a-number"))[0]

    assert checker.resolve(pin, run_commands=True) == checker.PinResult(
        pin=pin,
        verdict=checker.UNRESOLVABLE,
        detail="the command printed 'not-a-number', which is not an integer",
    )


def test_an_exit_pin_reports_the_code_it_got():
    ok = checker.parse_pins(pin_block("exit 0 -- true"))[0]
    moved = checker.parse_pins(pin_block("exit 0 -- exit 5"))[0]

    assert checker.resolve(ok, run_commands=True) == checker.PinResult(
        pin=ok, verdict=checker.OK, detail="the command still exits 0"
    )
    assert checker.resolve(moved, run_commands=True) == checker.PinResult(
        pin=moved,
        verdict=checker.MOVED,
        detail="the exit code was 0, is now 5",
    )


def test_an_output_pin_compares_the_whole_stripped_output():
    ok = checker.parse_pins(pin_block("output hello -- echo hello"))[0]
    moved = checker.parse_pins(pin_block("output hello -- echo goodbye"))[0]

    assert checker.resolve(ok, run_commands=True) == checker.PinResult(
        pin=ok, verdict=checker.OK, detail="the output is still 'hello'"
    )
    assert checker.resolve(moved, run_commands=True) == checker.PinResult(
        pin=moved,
        verdict=checker.MOVED,
        detail="the output was 'hello', is now 'goodbye'",
    )


# ------------------------------------------------------------- note level


def test_a_note_that_declares_no_pins_is_unpinned(tmp_path):
    """The whole point. A note with nothing to re-derive cannot be checked, and
    a checker that said nothing about it would read exactly like one that
    checked it and found it fresh."""
    path = note(tmp_path, "# A note\n\nA measurement with nothing behind it.\n")

    result = checker.check_note(path)

    assert result == checker.NoteResult(path=path, results=[])
    assert result.verdict == checker.UNPINNED


def test_a_note_verdict_is_the_worst_of_its_pins(tmp_path):
    path = note(
        tmp_path,
        pin_block("exit 0 -- true", "exit 0 -- exit 5"),
    )

    result = checker.check_note(path, run_commands=True)

    assert [r.verdict for r in result.results] == [checker.OK, checker.MOVED]
    assert result.verdict == checker.MOVED


def test_a_note_whose_pins_all_hold_is_ok(tmp_path):
    path = note(tmp_path, pin_block("exit 0 -- true"))

    result = checker.check_note(path, run_commands=True)

    assert [r.verdict for r in result.results] == [checker.OK]
    assert result.verdict == checker.OK


# ----------------------------------------------------------- corpus level


def test_a_corpus_in_which_every_pin_holds_reports_clean_and_exits_zero(tmp_path):
    note(tmp_path, pin_block("exit 0 -- true"), name="a.md")
    note(tmp_path, pin_block("exit 1 -- false"), name="b.md")

    result = checker.check_corpus([tmp_path], run_commands=True)

    assert [n.verdict for n in result.notes] == [checker.OK, checker.OK]
    assert result.exit_code == 0
    assert result.report() == (
        f"freshness: {tmp_path}\n"
        "           2 note(s) examined, 2 pin(s) resolved\n"
        "\n"
        "a.md: OK (1 pin)\n"
        "  [OK] exit line 6 — the command still exits 0\n"
        "b.md: OK (1 pin)\n"
        "  [OK] exit line 6 — the command still exits 1\n"
        "\n"
        "RESULT: 2 note(s) fresh, every pin re-derived.\n"
    )


def test_a_corpus_with_a_moved_pin_and_an_unpinned_note_exits_one(tmp_path):
    note(tmp_path, pin_block("count 40 -- echo 2"), name="moved.md")
    note(tmp_path, "# Nothing pinned\n\nProse only.\n", name="unpinned.md")

    result = checker.check_corpus([tmp_path], run_commands=True)

    assert [n.verdict for n in result.notes] == [checker.MOVED, checker.UNPINNED]
    assert result.exit_code == 1
    assert result.report() == (
        f"freshness: {tmp_path}\n"
        "           2 note(s) examined, 1 pin(s) resolved\n"
        "\n"
        "moved.md: MOVED (1 pin)\n"
        "  [MOVED] count line 6 — the count was 40, is now 2\n"
        "      command: echo 2\n"
        "unpinned.md: UNPINNED\n"
        "      the note declares no pins, so no claim in it can be re-derived. "
        "An unpinned note is not a checked note.\n"
        "\n"
        "RESULT: 1 MOVED, 1 UNPINNED. A stale note does not announce itself; "
        "this is the announcement.\n"
    )


def test_a_corpus_with_no_notes_never_exits_zero(tmp_path):
    """`ctest -R` exits 0 when its pattern matches no test. This does not."""
    empty = tmp_path / "empty"
    empty.mkdir()

    result = checker.check_corpus([empty])

    assert result.notes == []
    assert result.exit_code == 1
    assert result.report() == (
        f"freshness: {empty}\n"
        "           0 note(s) examined, 0 pin(s) resolved\n"
        "\n"
        "RESULT: NO NOTES EXAMINED. The checker found nothing to check, which "
        "is a hard error and never a pass.\n"
    )


def test_a_corpus_whose_notes_are_all_unpinned_never_exits_zero(tmp_path):
    """Zero pins resolved is its own guard. Every note being UNPINNED already
    fails the run, and this states the second reason separately so that
    weakening one cannot make 'nothing was checked' exit 0."""
    note(tmp_path, "# One\n\nProse.\n", name="a.md")

    result = checker.check_corpus([tmp_path])

    assert result.resolved == 0
    assert result.exit_code == 1
    assert "NO PINS RESOLVED" in result.report()


# -------------------------------------------------------------------- cli


def test_the_cli_exits_two_when_a_named_path_does_not_exist(tmp_path, capsys):
    missing = tmp_path / "nowhere"

    code = cli.main([str(missing)])

    assert code == 2
    assert capsys.readouterr().out == f"no such note or directory: {missing}\n"


def test_the_cli_requires_at_least_one_path(capsys):
    with pytest.raises(SystemExit) as raised:
        cli.main([])

    assert raised.value.code == 2


def test_the_cli_exits_one_on_a_moved_pin_and_prints_the_report(tmp_path, capsys):
    note(tmp_path, pin_block("count 40 -- echo 2"), name="moved.md")

    code = cli.main([str(tmp_path), "--run-commands"])

    assert code == 1
    assert capsys.readouterr().out == checker.check_corpus(
        [tmp_path], run_commands=True
    ).report()


def test_the_cli_queries_no_remote_until_check_remotes_is_given(pushed, capsys):
    """Without the flag the pin is loudly unchecked, never quietly passed."""
    path = note(pushed["work"], pin_block(f"remote {pushed['work']} {pushed['tip']}"))

    code = cli.main([str(path)])

    assert code == 1
    assert capsys.readouterr().out == (
        f"freshness: {path}\n"
        "           1 note(s) examined, 0 pin(s) resolved\n"
        "\n"
        f"{path}: UNRESOLVABLE (1 pin)\n"
        "  [UNRESOLVABLE] remote line 6 — the remote was not queried: "
        "--check-remotes was not given\n"
        "\n"
        "RESULT: NO PINS RESOLVED. Every note examined declared nothing this "
        "run could re-derive (1 note(s)). Nothing to check is never a pass.\n"
    )


def test_the_cli_exits_one_when_check_remotes_finds_a_commit_on_no_remote(
    pushed, capsys
):
    path = note(pushed["work"], pin_block(f"remote {pushed['work']} {pushed['local']}"))

    code = cli.main([str(path), "--check-remotes"])

    assert code == 1
    assert capsys.readouterr().out == (
        f"freshness: {path}\n"
        "           1 note(s) examined, 1 pin(s) resolved\n"
        "\n"
        f"{path}: MOVED (1 pin)\n"
        f"  [MOVED] remote line 6 — {pushed['local']} is on no ref of origin: "
        "it exists only in this clone (1 remote ref(s) examined)\n"
        "\n"
        "RESULT: 1 MOVED. A stale note does not announce itself; this is the "
        "announcement.\n"
    )


# ------------------------------------------------- the discrimination pair
#
# The control this tool exists to earn. Both pins below are `count` pins, both
# live in one note, both carry the SAME command over the SAME population, and
# both are resolved by `checker._resolve_command` — one code path. They differ
# in the figure they pin: one has drifted and one has not. A control that
# succeeded through a different path would prove nothing about the path that
# reported the failure.
#
# The subject is a plan fixture COMMITTED TO THIS REPOSITORY. An earlier version
# of this pair pinned a live note in `nmg2-findings` and asserted that the note
# was STALE, which made correcting the note a build failure — the suite paid
# whoever left a wrong document alone. A test may only assert a state its own
# repository controls.
#
# The command is a real `planlint` invocation with a `cd`, a module run, a pipe
# and a `sed`, not an `echo`: the resolver has to survive the shape a pin
# actually takes in a note.

FIXTURE_PLAN = (
    ROOT / "tests" / "planlint" / "fixtures"
    / "neg_structure_table_row_column_count.md"
)

# The figure the fixture plan yields, as a literal. Deriving it here by running
# the same command the pin runs would compare the tool against itself and assert
# nothing. The fixture is committed, so this figure moves only when somebody
# edits the fixture — and then this test is the thing that says so.
FIXTURE_STRUCTURE_FINDINGS = 2


def structure_count_command():
    return (
        f"cd {ROOT} && {sys.executable} -m planlint.cli --plan {FIXTURE_PLAN} "
        r"--only structure | sed -n 's/^structure: \([0-9][0-9]*\) "
        r"finding(s).*/\1/p'"
    )


def test_two_count_pins_over_one_real_command_report_the_drifted_figure_and_only_it(
    tmp_path,
):
    """The known positive and the known negative, one run, one resolver."""
    command = structure_count_command()
    path = note(
        tmp_path,
        pin_block(
            f"count {FIXTURE_STRUCTURE_FINDINGS} -- {command}",
            f"count 40 -- {command}",
        ),
    )

    result = checker.check_note(path, run_commands=True)

    assert result == checker.NoteResult(
        path=path,
        results=[
            checker.PinResult(
                pin=checker.Pin(
                    kind="count",
                    subject=command,
                    expected=str(FIXTURE_STRUCTURE_FINDINGS),
                    line=6,
                ),
                verdict=checker.OK,
                detail=f"the count is still {FIXTURE_STRUCTURE_FINDINGS}",
            ),
            checker.PinResult(
                pin=checker.Pin(
                    kind="count", subject=command, expected="40", line=7
                ),
                verdict=checker.MOVED,
                detail=f"the count was 40, is now {FIXTURE_STRUCTURE_FINDINGS}",
            ),
        ],
    )
    assert result.verdict == checker.MOVED


# ------------------------------------------------------------- real corpus
#
# Informational. These read the live findings corpus and skip when it is
# absent. Each asserts only that the corpus is CONSISTENT with itself, never
# that a document out there is broken.

REAL_NOTE = CORPUS / "2026-08-26-first-complete-lint-run.md"


def real_note_pins():
    if not REAL_NOTE.is_file():
        pytest.skip(f"the findings corpus is absent: {REAL_NOTE}")
    if not (ROOT / ".venv" / "bin" / "python").is_file():
        pytest.skip("the repository venv is absent, so no pin command can run")
    pins = checker.parse_pins(REAL_NOTE.read_text(encoding="utf-8"))
    if not pins:
        pytest.skip(f"{REAL_NOTE.name} carries no pins yet")
    # The KIND is part of the key. Without it a `repo` pin and a `remote` pin
    # naming the same commit in the same checkout collapse to one entry, the
    # second silently displaces the first, and a test goes on reporting a
    # verdict for a pin it is no longer looking at.
    return {
        pin.kind + "|" + pin.expected + "|" + pin.subject: pin for pin in pins
    }


def find_pin(pins, needle):
    matches = [pin for key, pin in pins.items() if needle in key]
    assert len(matches) == 1, f"{needle} matched {len(matches)} pins, expected 1"
    return matches[0]


def test_the_real_note_pins_a_count_that_has_not_moved():
    """Informational: the note's `structure` pin still re-derives. The
    discrimination this proves nothing about is proved above, on a fixture this
    repository owns."""
    pin = find_pin(real_note_pins(), "--only structure")

    result = checker.resolve(pin, run_commands=True)

    assert (result.verdict, result.detail) == (checker.OK, "the count is still 52")


def test_the_real_note_pins_the_artifacts_commit_it_was_measured_against():
    pins = real_note_pins()
    pin = find_pin(pins, "repo|8395bbf|")

    result = checker.resolve(pin, run_commands=True)

    assert result.verdict == checker.OK
    assert result.detail.startswith("8395bbf is an ancestor of HEAD ")


def test_the_real_note_pins_the_artifacts_commit_as_present_on_its_remote():
    """Informational, and it needs the network. The `repo` pin above is a fact
    about THIS MACHINE; this one is the fact that survives a restack."""
    pin = find_pin(real_note_pins(), "remote|8395bbf|")

    result = checker.resolve(pin, check_remotes=True)

    # An unreachable remote is an absent environment, like the absent corpus
    # above, and it skips. A remote that ANSWERED and does not have the commit
    # is MOVED and fails here — the two states are never conflated.
    if result.verdict == checker.UNRESOLVABLE and "could not be queried" in result.detail:
        pytest.skip(f"the artifacts remote is not reachable: {result.detail}")
    assert result.verdict == checker.OK
    assert result.detail.startswith("8395bbf is on origin: it is an ancestor of ")


def test_every_note_in_the_real_corpus_is_reported_and_none_is_silently_skipped():
    """The corpus holds notes with no pins. They are REPORTED as UNPINNED —
    the count of notes examined equals the count of `.md` files present."""
    if not CORPUS.is_dir():
        pytest.skip(f"the findings corpus is absent: {CORPUS}")
    present = sorted(p.name for p in CORPUS.glob("*.md"))

    result = checker.check_corpus([CORPUS], run_commands=False)

    assert [n.path.name for n in result.notes] == present
    assert result.exit_code == 1


def test_the_checker_is_imported_from_this_repository():
    """A stale copy on `sys.path` would let every assertion above pass while
    the committed tree stayed broken."""
    import freshness

    assert pathlib.Path(freshness.__file__).resolve().parent == ROOT / "freshness"
    assert sys.modules["freshness"].__name__ == "freshness"
