"""Checks score one reply. Each returns (passed, reason).

In a suite file a check is a one-key mapping, for example:
    - contains_any: ["30 days", "thirty days"]
    - max_latency_ms: 1500
    - no_pii: true
"""
import json
import re

from driftwatch.pii import PATTERNS, find_pii


class CheckError(ValueError):
    """A check is misconfigured in the suite file."""


def _as_list(arg, name):
    if isinstance(arg, str):
        return [arg]
    if not isinstance(arg, list) or not arg:
        raise CheckError(f"{name} needs a string or a non-empty list")
    return arg


def contains_any(reply, arg, ctx):
    values = _as_list(arg, "contains_any")
    ok = any(v.lower() in reply.lower() for v in values)
    return ok, "ok" if ok else f"none of {values} found"


def contains_all(reply, arg, ctx):
    missing = [v for v in _as_list(arg, "contains_all") if v.lower() not in reply.lower()]
    return not missing, f"missing {missing}" if missing else "ok"


def not_contains(reply, arg, ctx):
    found = [v for v in _as_list(arg, "not_contains") if v.lower() in reply.lower()]
    return not found, f"must not contain {found}" if found else "ok"


def regex(reply, arg, ctx):
    ok = re.search(arg, reply, re.IGNORECASE | re.MULTILINE) is not None
    return ok, "ok" if ok else f"no match for /{arg}/"


def not_regex(reply, arg, ctx):
    match = re.search(arg, reply, re.IGNORECASE | re.MULTILINE)
    return match is None, "ok" if match is None else f"matched forbidden /{arg}/: {match.group(0)!r}"


def max_words(reply, arg, ctx):
    count = len(reply.split())
    return count <= arg, "ok" if count <= arg else f"{count} words, limit {arg}"


def max_latency_ms(reply, arg, ctx):
    ms = ctx["latency_ms"]
    return ms <= arg, "ok" if ms <= arg else f"took {ms:.0f} ms, limit {arg} ms"


def no_pii(reply, arg, ctx):
    kinds = None if arg is True else _as_list(arg, "no_pii")
    if kinds:
        unknown = set(kinds) - set(PATTERNS)
        if unknown:
            raise CheckError(f"no_pii: unknown kinds {sorted(unknown)}; use {sorted(PATTERNS)}")
    found = find_pii(reply, kinds)
    return not found, "ok" if not found else f"leaked {found}"


def _parse_json(reply):
    text = reply.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    return json.loads(text)


def json_valid(reply, arg, ctx):
    try:
        _parse_json(reply)
        return True, "ok"
    except ValueError as exc:
        return False, f"not valid JSON: {exc}"


def json_has_keys(reply, arg, ctx):
    try:
        data = _parse_json(reply)
    except ValueError:
        return False, "not valid JSON"
    if not isinstance(data, dict):
        return False, "JSON is not an object"
    missing = [k for k in _as_list(arg, "json_has_keys") if k not in data]
    return not missing, f"missing keys {missing}" if missing else "ok"


def llm_judge(reply, arg, ctx):
    """Ask a model whether the reply meets a rubric. Needs a judge to be configured."""
    judge = ctx.get("judge")
    if judge is None:
        raise CheckError("llm_judge needs a judge model: run with --judge openai:<model>")
    rubric = arg["rubric"] if isinstance(arg, dict) else arg
    verdict = judge(rubric=rubric, prompt=ctx["prompt"], reply=reply)
    return verdict["pass"], verdict.get("reason", "")


CHECKS = {
    "contains_any": contains_any,
    "contains_all": contains_all,
    "not_contains": not_contains,
    "regex": regex,
    "not_regex": not_regex,
    "max_words": max_words,
    "max_latency_ms": max_latency_ms,
    "no_pii": no_pii,
    "json_valid": json_valid,
    "json_has_keys": json_has_keys,
    "llm_judge": llm_judge,
}


def parse_check(spec):
    if not isinstance(spec, dict) or len(spec) != 1:
        raise CheckError(f"each check must be a single 'name: value' entry, got {spec!r}")
    (name, arg), = spec.items()
    if name not in CHECKS:
        raise CheckError(f"unknown check {name!r}; available: {sorted(CHECKS)}")
    return name, arg


def run_check(spec, reply, ctx):
    name, arg = parse_check(spec)
    passed, reason = CHECKS[name](reply, arg, ctx)
    return {"check": name, "passed": bool(passed), "reason": reason}
