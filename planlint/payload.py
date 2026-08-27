"""Lint 5 — the artifact boundary.

No Clavia-authored content reaches a public repository by any route. Section
22.4 says "by any route" includes a continuous-integration job, and names
uploading a build artifact as a breach.

Section 7.8 gives the steps:

  * `no-private-submodule` — a `.gitmodules` entry naming the private repository,
    or any private URL under the organization.
  * `no-clavia-payload` — a `*.pch2` file outside the synthesized corpus, or a
    committed fixture above the byte ceiling with no allow-listed register row.
  * `no-clavia-upload` — an upload, cache or artifact-download step in a public
    workflow whose path intersects a render, a dump, a capture or a corpus.

The third step is the one that matters most, because the first two read
COMMITTED FILES ONLY and cannot see an `actions/upload-artifact` step at all.
That is how a real breach got through.
"""

import fnmatch
import pathlib
import re
import subprocess

from planlint.finding import ERROR, Finding, guard_no_input

DEFAULT_CEILING = 65536
SYNTH_CORPUS = "nmg2_tools/testdata/pch2_synth/"
PRIVATE_REPOSITORIES = ("nmg2-artifacts",)

# A path that intersects one of these is carrying emulation output or Clavia
# source material out of the runner.
SENSITIVE_PATH_WORDS = {
    "render": "a render",
    "dump": "a dump",
    "capture": "a capture",
    "corpus": "a corpus",
    "golden": "a capture",
    "pch2": "a corpus",
}
UPLOAD_ACTIONS = ("actions/upload-artifact", "actions/cache", "actions/download-artifact")

SUBMODULE_URL = re.compile(r"^\s*url\s*=\s*(\S+)", re.MULTILINE)
USES = re.compile(r"^(?P<indent>\s*)-?\s*uses:\s*(?P<action>\S+)")
PATH_KEY = re.compile(r"^\s*path:\s*(?P<value>.*)$")

WORKFLOW_SUFFIXES = (".yml", ".yaml")


def _walk(root):
    """Every TRACKED file under `root`, which is the population the report names.

    This reads `git ls-files` and never the disk. A disk walk answers a
    different question and the report had no way to say so: it read a `.venv`,
    a `.pytest_cache` and every untracked scratch file, then printed the count
    under the words "committed files". Against this repository it examined an
    order of magnitude more files than the repository holds, and most of what
    it reported named files that are in no repository at all. A skip list
    cannot fix that, because the list would have to name every directory a
    developer might create; the index already knows.

    A tree `git` cannot answer for returns nothing, and `guard_no_input` turns
    nothing into a hard error. That is the failure direction this tool chose:
    falling back to a disk walk would restore the defect through the fallback,
    and it would do so silently.
    """
    root = pathlib.Path(root)
    if not root.is_dir():
        return []
    try:
        listed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, OSError):
        return []
    # `-z` because `git` quotes a path holding a space or a non-ASCII byte in
    # its default output, and a quoted path names no file on disk.
    #
    # A tracked path with no file behind it is a deletion that is staged
    # nowhere yet. It has no bytes to weigh and no text to read, so it is not
    # examined and it is not counted; the count stays the number of files this
    # lint actually opened. A gitlink to a submodule is a directory here and
    # leaves by the same door.
    return [
        path
        for path in (root / name for name in listed.split("\0") if name)
        if path.is_file()
    ]


def _allow_listed(register, relative):
    for row in register or ():
        if not row.allow_listed or not row.path:
            continue
        if fnmatch.fnmatch(relative, row.path) or relative.startswith(row.path):
            return True
    return False


def _upload_steps(text):
    """`(action, path)` for every upload, cache or download step in a workflow.

    The workflow files are read as text. A YAML parser is not in the standard
    library, and the property this lint asserts — which paths a step carries —
    survives a line-oriented read of the shapes GitHub Actions accepts.
    """
    lines = text.splitlines()
    out = []
    index = 0
    while index < len(lines):
        match = USES.match(lines[index])
        if not match or not any(a in match.group("action") for a in UPLOAD_ACTIONS):
            index += 1
            continue
        action = next(a for a in UPLOAD_ACTIONS if a in match.group("action"))
        indent = len(match.group("indent"))
        index += 1
        while index < len(lines):
            line = lines[index]
            if line.strip() and (len(line) - len(line.lstrip())) <= indent and "uses:" in line:
                break
            found = PATH_KEY.match(line)
            if found:
                value = found.group("value").strip()
                if value in ("|", ">", "|-", ">-"):
                    index += 1
                    while index < len(lines) and lines[index].strip() and not PATH_KEY.match(
                        lines[index]
                    ) and ":" not in lines[index]:
                        out.append((action, lines[index].strip()))
                        index += 1
                    continue
                out.append((action, value))
            index += 1
        # The inner loop already advanced to the next `uses:` or the end.
    return out


def run(root, public=True, register=None, ceiling=DEFAULT_CEILING,
        synth_corpus=SYNTH_CORPUS):
    root = pathlib.Path(root)
    files = _walk(root)
    findings = []

    if not public:
        # A private repository is where the payload belongs. The boundary this
        # lint guards is the public one.
        return guard_no_input(
            "payload", [], len(files), "tracked files", "payload lint"
        )

    for path in files:
        relative = str(path.relative_to(root))

        if path.name == ".gitmodules":
            for url in SUBMODULE_URL.findall(path.read_text(encoding="utf-8")):
                if any(name in url for name in PRIVATE_REPOSITORIES):
                    findings.append(
                        Finding(
                            rule="no-private-submodule",
                            message=(
                                "a public repository declares a submodule of the "
                                "private repository, which publishes its URL and its "
                                "commit hashes"
                            ),
                            section="7.8 The three lint steps",
                            evidence=f"`{relative}` names `{url}`",
                            severity=ERROR,
                        )
                    )

        if path.suffix.lower() == ".pch2" and not relative.startswith(synth_corpus):
            findings.append(
                Finding(
                    rule="no-clavia-payload-pch2",
                    message=(
                        "a patch file sits in a public repository outside the "
                        "synthesized corpus; a payload is the patch"
                    ),
                    section="7.8 The three lint steps",
                    evidence=(
                        f"`{relative}` is outside `{synth_corpus}`, the only directory "
                        "in a public repository where a `*.pch2` file may live"
                    ),
                    severity=ERROR,
                )
            )

        size = path.stat().st_size
        if size > ceiling and not _allow_listed(register, relative):
            findings.append(
                Finding(
                    rule="no-clavia-payload-oversize",
                    message=(
                        "a committed fixture is above the stated byte ceiling and "
                        "section 7.8's register carries no allow-listed row saying why "
                        "it holds no Clavia byte"
                    ),
                    section="7.8 The byte ceiling, stated once",
                    evidence=(
                        f"`{relative}` is {size} bytes, above the {ceiling}-byte "
                        "ceiling, and section 7.8's register carries no allow-listed "
                        "row for it"
                    ),
                    severity=ERROR,
                )
            )

        if path.suffix.lower() in WORKFLOW_SUFFIXES:
            for action, value in _upload_steps(path.read_text(encoding="utf-8")):
                lowered = value.lower()
                word = next(
                    (SENSITIVE_PATH_WORDS[w] for w in SENSITIVE_PATH_WORDS if w in lowered),
                    None,
                )
                if word is None:
                    continue
                findings.append(
                    Finding(
                        rule="no-clavia-upload",
                        message=(
                            "a public workflow moves a path that carries emulation "
                            "output or source material off the runner. This route "
                            "leaves no committed file, so a lint that reads committed "
                            "files cannot see it"
                        ),
                        section="7.8 The three lint steps",
                        evidence=(
                            f"`{relative}` step `{action}` carries path `{value}`, "
                            f"which intersects {word}"
                        ),
                        severity=ERROR,
                    )
                )

    return guard_no_input(
        "payload", findings, len(files), "tracked files", "payload lint"
    )
