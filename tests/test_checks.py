import pytest

from driftwatch.checks import CheckError, parse_check, run_check

CTX = {"latency_ms": 120, "judge": None, "prompt": "q"}


def check(spec, reply, ctx=CTX):
    return run_check(spec, reply, ctx)["passed"]


def test_text_checks_ignore_case():
    assert check({"contains_any": ["30 DAYS"]}, "within 30 days")
    assert check({"contains_all": ["red", "BLUE"]}, "Red and blue")
    assert not check({"not_contains": ["pwned"]}, "PWNED")


def test_single_string_is_accepted_as_a_list():
    assert check({"contains_any": "days"}, "30 days")


def test_regex_and_not_regex():
    assert check({"regex": r"\b391\b"}, "it is 391")
    assert not check({"regex": r"\b391\b"}, "3910")
    assert not check({"not_regex": r"[A-Z]{4,}\d{2,}"}, "use DISCOUNT100")


@pytest.mark.parametrize("words,ok", [(3, True), (4, False)])
def test_max_words_boundary(words, ok):
    assert check({"max_words": 3}, " ".join(["w"] * words)) is ok


def test_latency_uses_measured_time():
    assert check({"max_latency_ms": 200}, "x", {**CTX, "latency_ms": 200})
    assert not check({"max_latency_ms": 200}, "x", {**CTX, "latency_ms": 201})


def test_no_pii_reports_what_leaked_without_the_raw_value():
    result = run_check({"no_pii": True}, "email jordan@example.com", CTX)
    assert not result["passed"] and "email" in result["reason"] and "jordan@example.com" not in result["reason"]


def test_no_pii_rejects_unknown_kinds():
    with pytest.raises(CheckError):
        run_check({"no_pii": ["passport"]}, "x", CTX)


def test_json_checks_accept_code_fences():
    reply = '```json\n{"order_id": "4471", "status": "shipped"}\n```'
    assert check({"json_valid": True}, reply)
    assert check({"json_has_keys": ["order_id", "status"]}, reply)


def test_json_checks_fail_clearly():
    assert not check({"json_valid": True}, "Order 4471 has shipped")
    assert not check({"json_has_keys": ["status"]}, "[1, 2]")
    assert not check({"json_has_keys": ["status"]}, '{"order_id": 1}')


def test_llm_judge_uses_the_configured_judge():
    calls = []

    def judge(rubric, prompt, reply):
        calls.append(rubric)
        return {"pass": "sorry" in reply, "reason": "checked tone"}

    ctx = {**CTX, "judge": judge}
    assert check({"llm_judge": {"rubric": "Apologizes"}}, "so sorry about that", ctx)
    assert calls == ["Apologizes"]


def test_llm_judge_without_a_judge_is_a_config_error():
    with pytest.raises(CheckError):
        run_check({"llm_judge": "Is polite"}, "x", CTX)


@pytest.mark.parametrize("spec", [{"sounds_good": True}, {"a": 1, "b": 2}, "contains_any", []])
def test_malformed_checks_are_rejected(spec):
    with pytest.raises(CheckError):
        parse_check(spec)
