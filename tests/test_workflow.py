from pathlib import Path


def test_update_workflow_runs_on_push_to_main():
    workflow = Path(".github/workflows/update.yml").read_text(encoding="utf-8")

    assert "push:" in workflow
    assert "branches:" in workflow
    assert "- main" in workflow
