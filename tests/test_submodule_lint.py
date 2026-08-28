import subprocess

from nmg2_tools.submodule_lint import (
    Section,
    declared_paths,
    lint_gitmodules_text,
    lint_repo_tree,
    lint_stale_declarations,
    lint_undeclared_gitlinks,
    parse_sections,
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


# ------------------------------------------- clause 3: the reverse direction


def test_a_gitmodules_section_with_no_gitlink_fails_and_names_the_section(
    tmp_path,
):
    """The reverse blind spot, and the mirror of SUBMODULE-UNDECLARED.

    A submodule removed by hand -- `git rm --cached` and a `rm -rf` -- drops
    the gitlink and leaves the section standing. The URL clause then goes on
    answering about a repository this tree no longer pulls in, and the answer
    reads exactly like a check that ran and found nothing wrong.
    """
    repo = _git_repo(tmp_path)
    (repo / ".gitmodules").write_text(
        '[submodule "vendor/removed"]\n'
        "\tpath = vendor/removed\n"
        "\turl = https://github.com/dsp56300/JUCE\n"
    )
    failures, _notes = lint_repo_tree(repo)
    stale = [f for f in failures if f.startswith("SUBMODULE-STALE-DECLARATION")]
    assert stale == [
        'SUBMODULE-STALE-DECLARATION: line 1: section [submodule '
        '"vendor/removed"] declares `path = vendor/removed`, but the index '
        "records no submodule gitlink there, so this declaration binds "
        "nothing and its URL names a repository this tree does not pull in. "
        "Remove the section, or restore the gitlink"
    ]


def test_restoring_the_gitlink_clears_the_stale_finding(tmp_path):
    """The known negative for the test above, in the SAME tree.

    A green run over a tree that never had the defect proves the clause is
    quiet, not that it discriminates. This is the same `.gitmodules`, with the
    one thing the finding named put back.
    """
    repo = _git_repo(tmp_path)
    (repo / ".gitmodules").write_text(
        '[submodule "vendor/removed"]\n'
        "\tpath = vendor/removed\n"
        "\turl = https://github.com/dsp56300/JUCE\n"
    )
    _add_gitlink(repo, "vendor/removed")
    failures, _notes = lint_repo_tree(repo)
    assert failures == []


def test_a_section_that_declares_no_path_is_named(tmp_path):
    """`declares nothing`, arriving one field over.

    git binds a section to a gitlink through `path =` alone. A section with a
    URL and no path is inert to git, so it is not merely cosmetic: it reads
    like a declaration and is not one.
    """
    repo = _git_repo(tmp_path)
    (repo / ".gitmodules").write_text(
        '[submodule "vendor/thing"]\n'
        "\turl = https://github.com/dsp56300/JUCE\n"
    )
    failures, _notes = lint_repo_tree(repo)
    assert [
        f for f in failures if f.startswith("SUBMODULE-DECLARATION-NO-PATH")
    ] == [
        'SUBMODULE-DECLARATION-NO-PATH: line 1: section [submodule '
        '"vendor/thing"] declares no `path = `, so git binds it to no gitlink '
        "and it declares nothing. The section name is a label, not a path"
    ]


def test_both_directions_fire_on_a_gitmodules_wrong_in_both(tmp_path):
    """One file can be wrong in both directions, and they are two defects.

    A gitlink at `vendor/thing` that no section declares, and a section
    declaring `somewhere/else` where no gitlink sits. Reporting only one of
    the two would leave the other silent behind a fixed finding.
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
    assert any(
        "SUBMODULE-STALE-DECLARATION" in f and "somewhere/else" in f
        for f in failures
    )


def test_the_stale_clause_is_a_pure_set_difference():
    assert lint_stale_declarations(
        ["a"], [Section("a", 1, "a"), Section("gone", 4, "b")]
    ) == [
        'SUBMODULE-STALE-DECLARATION: line 4: section [submodule "gone"] '
        "declares `path = b`, but the index records no submodule gitlink "
        "there, so this declaration binds nothing and its URL names a "
        "repository this tree does not pull in. Remove the section, or "
        "restore the gitlink"
    ]


def test_an_unreadable_index_does_not_report_every_section_as_stale(tmp_path):
    """The fail-closed path must not turn into a wall of false findings.

    With no gitlinks read, every section in the file would compare unequal
    against an empty set. One true finding -- the index could not be read --
    buried under a finding per section is a check that hides its own answer.
    """
    (tmp_path / ".gitmodules").write_text(
        '[submodule "a"]\n\tpath = a\n\turl = https://github.com/dsp56300/JUCE\n'
    )
    failures, _notes = lint_repo_tree(tmp_path)
    assert any(f.startswith("SUBMODULE-INDEX-UNREADABLE") for f in failures)
    assert not any(
        f.startswith("SUBMODULE-STALE-DECLARATION") for f in failures
    )


# ------------------------------------------------------- the section parser


def test_a_path_line_outside_any_section_declares_nothing(tmp_path):
    """It must not be able to silence SUBMODULE-UNDECLARED.

    git reads `path` only inside a `[submodule "..."]` section. A line-based
    scan treated a top-level `path =` as a declaration, so a line git ignores
    could answer the clause -- coverage asserted by a line with no effect.
    """
    repo = _git_repo(tmp_path)
    _add_gitlink(repo, "vendor/thing")
    (repo / ".gitmodules").write_text("path = vendor/thing\n")
    failures, _notes = lint_repo_tree(repo)
    assert any(
        f.startswith("SUBMODULE-UNDECLARED: vendor/thing") for f in failures
    )


def test_a_following_section_ends_the_submodule_section(tmp_path):
    """Keys under another section are not the submodule's."""
    text = (
        '[submodule "a"]\n'
        "\turl = https://github.com/dsp56300/JUCE\n"
        "[core]\n"
        "\tpath = not-a-declaration\n"
    )
    assert parse_sections(text) == [Section("a", 1, None)]
    assert declared_paths(text) == set()


def test_a_repeated_path_key_takes_the_last_value():
    """git's config parser does; so does this, or the two disagree."""
    text = '[submodule "a"]\n\tpath = first\n\tpath = second\n'
    assert declared_paths(text) == {"second"}
