from itertools import cycle

from driftwatch.runner import run_case
from tests.conftest import FakeClock


def test_passing_case(case):
    result = run_case(case(), lambda m: "hello there")
    assert result["passed"] and result["pass_rate"] == 1 and not result["flaky"]


def test_target_receives_history_then_prompt(case):
    seen = []
    c = case(history=[{"role": "user", "content": "I'm Priya"}], prompt="My name?")
    run_case(c, lambda m: seen.append(m) or "hello")
    assert [m["content"] for m in seen[0]] == ["I'm Priya", "My name?"]


def test_inconsistent_answers_are_flaky_and_fail_a_strict_case(case):
    answers = cycle(["hello", "goodbye"])
    result = run_case(case(repeats=4), lambda m: next(answers))
    assert result["flaky"] and result["pass_rate"] == 0.5 and not result["passed"]


def test_min_pass_rate_allows_some_variance(case):
    answers = cycle(["hello", "hello", "hello", "goodbye"])
    result = run_case(case(repeats=4, min_pass_rate=0.75), lambda m: next(answers))
    assert result["passed"] and result["flaky"]


def test_a_crashing_target_fails_the_run_with_the_error(case):
    def broken(messages):
        raise TimeoutError("model took too long")

    result = run_case(case(repeats=2), broken)
    assert not result["passed"]
    assert all("TimeoutError" in r["error"] for r in result["runs"])


def test_latency_is_measured_per_run(case):
    c = case(checks=[{"max_latency_ms": 400}])
    assert run_case(c, lambda m: "x", clock=FakeClock(0.25))["passed"]
    assert not run_case(c, lambda m: "x", clock=FakeClock(0.5))["passed"]
