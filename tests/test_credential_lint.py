from nmg2_tools.credential_lint import lint_repo_tree, lint_workflow_text, main


def test_personal_access_token_reference_fails():
    text = (
        "jobs:\n"
        "  call:\n"
        "    steps:\n"
        "      - run: echo hi\n"
        "        env:\n"
        "          PAT: ${{ secrets.PERSONAL_ACCESS_TOKEN }}\n"
    )
    failures = lint_workflow_text(text, "w.yml")
    assert any(f.startswith("CRED-FOREIGN-SECRET") for f in failures)


def test_only_momus_secrets_passes():
    text = (
        "jobs:\n"
        "  call:\n"
        "    secrets:\n"
        "      LLM_API_KEY: ${{ secrets.LLM_API_KEY }}\n"
        "      MOMUS_APP_ID: ${{ secrets.MOMUS_APP_ID }}\n"
        "      MOMUS_APP_PRIVATE_KEY: ${{ secrets.MOMUS_APP_PRIVATE_KEY }}\n"
        "      token: ${{ secrets.GITHUB_TOKEN }}\n"
    )
    failures = lint_workflow_text(text, "w.yml")
    assert failures == []


def test_no_secrets_reference_passes():
    text = "jobs:\n  call:\n    steps:\n      - run: echo hi\n"
    failures = lint_workflow_text(text, "w.yml")
    assert failures == []


def _repo_with_workflows(tmp_path, files):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    for name, text in files.items():
        (workflows / name).write_text(text)
    return tmp_path


CLEAN_WORKFLOW = "jobs:\n  call:\n    steps:\n      - run: echo hi\n"
DIRTY_WORKFLOW = (
    "jobs:\n"
    "  call:\n"
    "    steps:\n"
    "      - run: echo hi\n"
    "        env:\n"
    "          PAT: ${{ secrets.PERSONAL_ACCESS_TOKEN }}\n"
)


def test_absent_workflow_directory_is_refused(tmp_path):
    failures = lint_repo_tree(tmp_path)
    assert [f.split(":")[0] for f in failures] == ["CRED-SCOPE-ABSENT"]


def test_empty_workflow_directory_is_refused(tmp_path):
    repo = _repo_with_workflows(tmp_path, {})
    failures = lint_repo_tree(repo)
    assert [f.split(":")[0] for f in failures] == ["CRED-SCOPE-EMPTY"]


def test_directory_of_non_workflow_files_is_refused(tmp_path):
    repo = _repo_with_workflows(tmp_path, {"README.md": "not a workflow\n"})
    failures = lint_repo_tree(repo)
    assert [f.split(":")[0] for f in failures] == ["CRED-SCOPE-EMPTY"]


def test_populated_clean_directory_still_passes(tmp_path):
    repo = _repo_with_workflows(tmp_path, {"ci.yml": CLEAN_WORKFLOW})
    assert lint_repo_tree(repo) == []


def test_populated_dirty_directory_still_fails(tmp_path):
    repo = _repo_with_workflows(tmp_path, {"ci.yml": DIRTY_WORKFLOW})
    failures = lint_repo_tree(repo)
    assert [f.split(":")[0] for f in failures] == ["CRED-FOREIGN-SECRET"]


def test_main_exits_non_zero_on_a_degenerate_population(tmp_path):
    assert main([str(tmp_path)]) == 1


def test_main_exits_zero_on_a_populated_clean_tree(tmp_path):
    repo = _repo_with_workflows(tmp_path, {"ci.yml": CLEAN_WORKFLOW})
    assert main([str(repo)]) == 0
