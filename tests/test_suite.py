import pytest

from driftwatch.suite import SuiteError, load_suite

VALID = """
name: demo
target: {type: python, callable: m:f}
defaults: {repeats: 3}
gate: {min_pass_rate: 0.5}
cases:
  - id: a
    prompt: hi
    checks: [{contains_any: [hello]}]
  - id: b
    prompt: hi
    repeats: 1
    critical: true
    history: [{role: user, content: earlier}]
    checks: [{max_words: 5}]
"""


def write(tmp_path, text):
    path = tmp_path / "suite.yaml"
    path.write_text(text)
    return path


def test_loads_cases_defaults_and_gate(tmp_path):
    suite = load_suite(write(tmp_path, VALID))
    a, b = suite.cases
    assert (a.repeats, b.repeats) == (3, 1)
    assert b.critical and b.history[0]["content"] == "earlier"
    assert suite.gate["min_pass_rate"] == 0.5 and suite.gate["fail_on_regression"] is True


def test_shipped_example_suite_is_valid():
    suite = load_suite("examples/support_bot/suite.yaml")
    assert len(suite.cases) >= 8


@pytest.mark.parametrize("text,message", [
    ("cases: []", "at least one case"),
    ("cases:\n  - id: a\n    prompt: hi", "missing 'checks'"),
    ("cases:\n  - {id: a, prompt: x, checks: [{max_words: 1}]}\n  - {id: a, prompt: y, checks: [{max_words: 1}]}", "duplicate id"),
    ("cases:\n  - {id: a, prompt: x, checks: [{nope: 1}]}", "unknown check"),
    ("cases:\n  - {id: a, prompt: x, repeats: 0, checks: [{max_words: 1}]}", "repeats"),
    ("cases:\n  - {id: a, prompt: x, history: [{role: system, content: y}], checks: [{max_words: 1}]}", "history"),
    ("cases: [unclosed", "not valid YAML"),
])
def test_invalid_suites_explain_the_problem(tmp_path, text, message):
    with pytest.raises(SuiteError, match=message):
        load_suite(write(tmp_path, text))
