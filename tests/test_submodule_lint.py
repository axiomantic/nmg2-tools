from nmg2_tools.submodule_lint import lint_gitmodules_text, lint_repo_tree


def test_private_repo_named_fails():
    text = (
        '[submodule "artifacts"]\n'
        "\tpath = artifacts\n"
        "\turl = git@github.com:axiomantic/nmg2-artifacts.git\n"
    )
    failures = lint_gitmodules_text(text)
    assert any(f.startswith("SUBMODULE-PRIVATE") for f in failures)


def test_public_sibling_passes():
    text = (
        '[submodule "mcf5307"]\n'
        "\tpath = mcf5307\n"
        "\turl = https://github.com/axiomantic/mcf5307.git\n"
    )
    failures = lint_gitmodules_text(text)
    assert failures == []


def test_unknown_repo_fails_named():
    text = (
        '[submodule "weird"]\n'
        "\tpath = weird\n"
        "\turl = https://github.com/someoneelse/weird.git\n"
    )
    failures = lint_gitmodules_text(text)
    assert any(f.startswith("SUBMODULE-UNKNOWN") for f in failures)


def test_unlisted_axiomantic_repo_fails_named():
    text = (
        '[submodule "secret"]\n'
        "\tpath = secret\n"
        "\turl = git@github.com:axiomantic/secret-thing.git\n"
    )
    failures = lint_gitmodules_text(text)
    assert any(f.startswith("SUBMODULE-UNLISTED") for f in failures)


def test_no_gitmodules_file_passes(tmp_path):
    failures = lint_repo_tree(tmp_path)
    assert failures == []
