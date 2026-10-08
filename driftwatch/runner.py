"""Run every case against a target, repeating cases to measure consistency."""
import time

from driftwatch.checks import run_check


def run_case(case, target, judge=None, clock=time.perf_counter):
    messages = case.history + [{"role": "user", "content": case.prompt}]
    runs = []
    for _ in range(case.repeats):
        start = clock()
        try:
            reply, error = target(list(messages)), None
        except Exception as exc:  # a crashed call fails this run, not the whole suite
            reply, error = "", f"{type(exc).__name__}: {exc}"
        latency_ms = (clock() - start) * 1000
        ctx = {"latency_ms": latency_ms, "judge": judge, "prompt": case.prompt}
        checks = [] if error else [run_check(spec, reply, ctx) for spec in case.checks]
        runs.append({
            "reply": reply,
            "error": error,
            "latency_ms": round(latency_ms, 1),
            "passed": error is None and all(c["passed"] for c in checks),
            "checks": checks,
        })

    passes = sum(r["passed"] for r in runs)
    pass_rate = passes / len(runs)
    return {
        "id": case.id,
        "tags": case.tags,
        "critical": case.critical,
        "repeats": case.repeats,
        "pass_rate": pass_rate,
        "passed": pass_rate >= case.min_pass_rate,
        "flaky": 0 < passes < len(runs),
        "runs": runs,
    }


def run_suite(suite, target, judge=None, tags=None):
    cases = [c for c in suite.cases if not tags or set(tags) & set(c.tags)]
    return [run_case(c, target, judge) for c in cases]
