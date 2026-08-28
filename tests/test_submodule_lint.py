import subprocess

from nmg2_tools.submodule_lint import (
    declared_paths,
    lint_gitmodules_text,
    lint_repo_tree,
    lint_undeclared_gitlinks,
)


def _git_repo(path):
    """Initialise a real repository. The gitlink clause reads a real index."""
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def _add_gitlink(repo, rel_path):
    """Record a mode-160000 index entry at ``rel_path``.

    Written straight into the index with `update-index --cacheinfo` so the
    fixture needs no second repository and no network. The sha is arbitrary:
    nothing under test reads the commit it names, only the mode.
    """
    subprocess.run(
        [
            "git", "-C", str(repo), "update-index", "--add", "--cacheinfo",
            "160000," + "0" * 39 + "1," + rel_path,
        ],
        check=True,
    )


def test_private_repo_named_fails():
    text = (
        '[submodule "artifacts"]\n'
        "\tpath = artifacts\n"
        "\turl = git@github.com:axiomantic/nmg2-artifacts.git\n"
    )
    failures, _notes = lint_gitmodules_text(text)
    assert any(f.startswith("SUBMODULE-PRIVATE") for f in failures)


def test_public_sibling_passes():
    text = (
        '[submodule "mcf5307"]\n'
        "\tpath = mcf5307\n"
        "\turl = https://github.com/axiomantic/mcf5307.git\n"
    )
    failures, _notes = lint_gitmodules_text(text)
    assert failures == []


def test_third_party_repo_is_a_note_and_not_a_failure():
    """A repository outside the axiomantic organization does not fail the step.

    The task's own check requires the step to PASS on the gearmulator fork,
    whose submodules include third-party public repositories the plan's table
    does not list and never will.
    """
    text = (
        '[submodule "weird"]\n'
        "\tpath = weird\n"
        "\turl = https://github.com/someoneelse/weird.git\n"
    )
    failures, notes = lint_gitmodules_text(text)
    assert failures == []
    assert any(n.startswith("SUBMODULE-THIRD-PARTY") for n in notes)


def test_the_real_gearmulator_submodule_set_passes():
    """The measured content of the fork's own .gitmodules, held against the step.

    This is the case the two plan texts disagreed about. It is pinned here so
    that a later widening of the rule cannot silently make the fork unmergeable.
    """
    text = (
        '[submodule "source/dsp56300"]\n'
        "\turl = https://github.com/axiomantic/dsp56300\n"
        '[submodule "source/JUCE"]\n'
        "\turl = https://github.com/dsp56300/JUCE\n"
        '[submodule "source/cpp-terminal"]\n'
        "\turl = https://github.com/dsp56300/cpp-terminal\n"
        '[submodule "source/mc68k"]\n'
        "\turl = https://github.com/dsp56300/mc68k.git\n"
        '[submodule "source/clap-juce-extensions"]\n'
        "\turl = https://github.com/dsp56300/clap-juce-extensions.git\n"
        '[submodule "source/3rdparty/RmlUi"]\n'
        "\turl = https://github.com/dsp56300/RmlUi.git\n"
        '[submodule "source/3rdparty/freetype"]\n'
        "\turl = https://github.com/freetype/freetype.git\n"
        '[submodule "source/3rdparty/lunasvg"]\n'
        "\turl = https://github.com/sammycage/lunasvg.git\n"
    )
    failures, notes = lint_gitmodules_text(text)
    assert failures == []
    assert len(notes) == 6


def test_a_private_entry_added_to_that_set_still_fails():
    """The negative case. The flagship prohibition still fires on the fork."""
    text = (
        '[submodule "source/JUCE"]\n'
        "\turl = https://github.com/dsp56300/JUCE\n"
        '[submodule "artifacts"]\n'
        "\turl = https://github.com/axiomantic/nmg2-artifacts.git\n"
    )
    failures, _notes = lint_gitmodules_text(text)
    assert any(f.startswith("SUBMODULE-PRIVATE") for f in failures)


def test_unlisted_axiomantic_repo_fails_named():
    text = (
        '[submodule "secret"]\n'
        "\tpath = secret\n"
        "\turl = git@github.com:axiomantic/secret-thing.git\n"
    )
    failures, _notes = lint_gitmodules_text(text)
    assert any(f.startswith("SUBMODULE-UNLISTED") for f in failures)


def test_no_gitmodules_file_and_no_gitlink_passes(tmp_path):
    failures, notes = lint_repo_tree(_git_repo(tmp_path))
    assert failures == []
    assert notes == []


def test_a_directory_git_cannot_list_is_not_a_pass(tmp_path):
    """The fail-closed case, and the reason the test above uses a real repo.

    `tmp_path` is not a repository. Before the gitlink clause existed this
    function returned a clean pass for it, which is the same answer it gives
    for a repository with no submodules -- so "checked nothing" and "found
    nothing" were one result.
    """
    failures, _notes = lint_repo_tree(tmp_path)
    assert any(f.startswith("SUBMODULE-INDEX-UNREADABLE") for f in failures)


def test_a_gitlink_with_no_gitmodules_section_fails(tmp_path):
    """The blind spot this clause exists for.

    The payload lint used to report this path -- as PAYLOAD-UNREGISTERED, for
    the wrong reason, and it reported every DECLARED submodule the same way.
    Now that it reports none of them, this is the check that a gitlink nobody
    declared still reaches something.
    """
    repo = _git_repo(tmp_path)
    _add_gitlink(repo, "vendor/undeclared")
    failures, _notes = lint_repo_tree(repo)
    assert [f for f in failures if f.startswith("SUBMODULE-UNDECLARED")] == [
        "SUBMODULE-UNDECLARED: vendor/undeclared: the index records a "
        "submodule gitlink here, but no `.gitmodules` section declares this "
        "path, so no URL reached the authority table"
    ]


def test_a_declared_gitlink_passes(tmp_path):
    """The known negative. The clause must not fire on a normal submodule."""
    repo = _git_repo(tmp_path)
    _add_gitlink(repo, "SynthLib")
    (repo / ".gitmodules").write_text(
        '[submodule "SynthLib"]\n'
        "\tpath = SynthLib\n"
        "\turl = https://github.com/chrispurusha/SynthLib.git\n"
    )
    failures, _notes = lint_repo_tree(repo)
    assert failures == []


def test_the_section_name_is_not_the_declaration(tmp_path):
    """git matches a gitlink on `path =`, and so does this clause.

    A section whose label happens to equal the path is the common case, not
    the rule. Keying on the label would pass a `.gitmodules` that declares a
    different directory entirely.
    """
    repo = _git_repo(tmp_path)
    _add_gitlink(repo, "vendor/thing")
    (repo / ".gitmodules").write_text(
        '[submodule "vendor/thing"]\n'
        "\tpath = somewhere/else\n"
        "\turl = https://github.com/dsp56300/JUCE\n"
    )
    failures, _notes = lint_repo_tree(repo)
    assert any(
        f.startswith("SUBMODULE-UNDECLARED: vendor/thing") for f in failures
    )


def test_declared_paths_reads_path_lines_only():
    text = (
        '[submodule "label-not-a-path"]\n'
        "\tpath = source/JUCE\n"
        "\turl = https://github.com/dsp56300/JUCE\n"
    )
    assert declared_paths(text) == {"source/JUCE"}


def test_undeclared_clause_is_a_pure_set_difference():
    assert lint_undeclared_gitlinks(["a", "b"], {"a"}) == [
        "SUBMODULE-UNDECLARED: b: the index records a submodule gitlink "
        "here, but no `.gitmodules` section declares this path, so no URL "
        "reached the authority table"
    ]
