from nmg2_tools.submodule_lint import lint_gitmodules_text, lint_repo_tree


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

    The task's own check requires the step to PASS on the gearmulator fork, and
    six of that fork's eight submodules are third-party public repositories the
    plan's table does not list and never will.
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


def test_no_gitmodules_file_passes(tmp_path):
    failures, notes = lint_repo_tree(tmp_path)
    assert failures == []
    assert notes == []
