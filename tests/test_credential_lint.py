from nmg2_tools.credential_lint import lint_workflow_text


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
