"""Compare a run with a saved baseline, and decide whether the run passes."""
import json
from pathlib import Path


def save_baseline(path, suite_name, results):
    data = {
        "suite": suite_name,
        "results": {r["id"]: {"passed": r["passed"], "pass_rate": r["pass_rate"]} for r in results},
    }
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def load_baseline(path):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else None


def compare(results, baseline):
    before = (baseline or {}).get("results", {})
    now = {r["id"]: r for r in results}
    return {
        "regressions": [i for i, r in now.items() if before.get(i, {}).get("passed") is True and not r["passed"]],
        "fixed": [i for i, r in now.items() if before.get(i, {}).get("passed") is False and r["passed"]],
        "new": [i for i in now if i not in before],
        "removed": [i for i in before if i not in now],
    }


def gate(results, diff, rules):
    """Reasons the run fails. An empty list means it passes."""
    reasons = []
    if rules["fail_on_critical"]:
        critical = [r["id"] for r in results if r["critical"] and not r["passed"]]
        if critical:
            reasons.append(f"critical cases failed: {', '.join(critical)}")
    if rules["fail_on_regression"] and diff["regressions"]:
        reasons.append(f"regressed since baseline: {', '.join(diff['regressions'])}")
    rate = sum(r["passed"] for r in results) / len(results) if results else 0
    if rate < rules["min_pass_rate"]:
        reasons.append(f"pass rate {rate:.0%} is below the required {rules['min_pass_rate']:.0%}")
    return reasons
