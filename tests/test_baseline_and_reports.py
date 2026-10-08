import json
import xml.etree.ElementTree as ET

from driftwatch import report
from driftwatch.baseline import compare, gate, load_baseline, save_baseline

RULES = {"min_pass_rate": 0.0, "fail_on_regression": True, "fail_on_critical": True}


def result(id, passed, critical=False, flaky=False, repeats=1):
    run = {"reply": "r", "error": None, "latency_ms": 12.0, "passed": passed,
           "checks": [{"check": "contains_any", "passed": passed, "reason": "ok" if passed else "none found"}]}
    return {"id": id, "tags": [], "critical": critical, "repeats": repeats,
            "pass_rate": 1.0 if passed else 0.0, "passed": passed, "flaky": flaky, "runs": [run] * repeats}


def test_baseline_round_trip(tmp_path):
    path = tmp_path / "baseline.json"
    save_baseline(path, "s", [result("a", True), result("b", False)])
    assert load_baseline(path)["results"]["b"]["passed"] is False
    assert load_baseline(tmp_path / "missing.json") is None


def test_compare_classifies_changes():
    baseline = {"results": {"a": {"passed": True}, "b": {"passed": False}, "gone": {"passed": True}}}
    diff = compare([result("a", False), result("b", True), result("c", True)], baseline)
    assert diff == {"regressions": ["a"], "fixed": ["b"], "new": ["c"], "removed": ["gone"]}


def test_compare_without_baseline_treats_everything_as_new():
    assert compare([result("a", False)], None)["regressions"] == []


def test_gate_rules():
    no_diff = {"regressions": []}
    assert gate([result("a", True)], no_diff, RULES) == []
    assert "critical" in gate([result("a", False, critical=True)], no_diff, RULES)[0]
    assert "regressed" in gate([result("a", True)], {"regressions": ["x"]}, RULES)[0]
    assert "pass rate" in gate([result("a", False)], no_diff, {**RULES, "min_pass_rate": 0.9})[0]


def test_gate_rules_can_be_turned_off():
    rules = {**RULES, "fail_on_regression": False, "fail_on_critical": False}
    assert gate([result("a", False, critical=True)], {"regressions": ["a"]}, rules) == []


def test_junit_is_valid_and_marks_regressions():
    results = [result("a", True), result("b", False), result("c", True, flaky=True, repeats=2)]
    root = ET.fromstring(report.junit("s", results, {"regressions": ["b"]}))
    assert root.attrib["tests"] == "3" and root.attrib["failures"] == "1"
    failure = root.find("testcase[@name='b']/failure")
    assert failure.attrib["type"] == "regression"
    assert "flaky" in root.find("testcase[@name='c']/system-out").text


def test_markdown_and_json_reports():
    results = [result("a", True), result("b", False, critical=True)]
    diff = {"regressions": [], "fixed": [], "new": [], "removed": []}
    md = report.markdown("s", results, diff, ["critical cases failed: b"])
    assert "**FAIL**" in md and "| b (critical) | FAIL |" in md
    data = json.loads(report.to_json("s", results, diff, []))
    assert data["passed"] is True and len(data["results"]) == 2
