"""End-to-end: run the real CLI on the shipped demo."""
import json
import shutil
import xml.etree.ElementTree as ET

import pytest

from driftwatch.cli import main

V1 = "python:examples.support_bot.bot_v1:reply"


@pytest.fixture
def suite(tmp_path):
    """A copy of the demo suite, so tests never touch the committed baseline."""
    path = tmp_path / "suite.yaml"
    shutil.copy("examples/support_bot/suite.yaml", path)
    return path


def test_v1_passes(suite, capsys):
    assert main(["run", str(suite), "--target", V1]) == 0
    assert "RESULT: PASS" in capsys.readouterr().out


def test_v2_regressions_are_caught_against_a_v1_baseline(suite, tmp_path, capsys):
    assert main(["run", str(suite), "--target", V1, "--update-baseline"]) == 0
    capsys.readouterr()
    code = main(["run", str(suite), "--junit", str(tmp_path / "j.xml"), "--report-json", str(tmp_path / "r.json")])
    out = capsys.readouterr().out
    assert code == 1
    for case in ("refuses-other-customers-data", "injection-discount-code",
                 "shipping-time-consistent", "greeting-is-fast"):
        assert f"REGRESSED {case}" in out
    assert "Flaky" in out
    data = json.loads((tmp_path / "r.json").read_text())
    assert len(data["diff"]["regressions"]) == 4
    assert ET.parse(tmp_path / "j.xml").getroot().attrib["failures"] == "4"


def test_tag_filter_runs_a_subset(suite, capsys):
    assert main(["run", str(suite), "--target", V1, "--tag", "safety"]) == 0
    out = capsys.readouterr().out
    assert "injection-discount-code" in out and "return-policy" not in out


def test_markdown_goes_to_github_summary(suite, tmp_path, monkeypatch):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    main(["run", str(suite), "--target", V1])
    assert "## Driftwatch" in summary.read_text()


def test_config_errors_exit_2(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text("cases: []")
    assert main(["run", str(bad)]) == 2
    assert "at least one case" in capsys.readouterr().err


def test_unmatched_tag_exits_2(suite, capsys):
    assert main(["run", str(suite), "--target", V1, "--tag", "nonexistent"]) == 2
