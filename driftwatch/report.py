"""Turn results into a console summary, Markdown, JSON, and JUnit XML."""
import json
import xml.etree.ElementTree as ET


def _failure_detail(result):
    for run in result["runs"]:
        if run["error"]:
            return run["error"]
        failed = [c["reason"] for c in run["checks"] if not c["passed"]]
        if failed:
            return "; ".join(failed)
    return ""


def _status(result, diff):
    if result["id"] in diff["regressions"]:
        return "REGRESSED"
    if not result["passed"]:
        return "FAIL"
    return "flaky" if result["flaky"] else "pass"


def _rate(result):
    if result["repeats"] == 1:
        return ""
    passes = round(result["pass_rate"] * result["repeats"])
    return f" ({passes}/{result['repeats']} runs)"


def console(suite_name, results, diff, reasons):
    passed = sum(r["passed"] for r in results)
    lines = [f"Driftwatch: {suite_name}", ""]
    width = max(len(r["id"]) for r in results)
    for r in results:
        status = _status(r, diff)
        line = f"  {status:<9} {r['id']:<{width}}{_rate(r)}".rstrip()
        if status in ("FAIL", "REGRESSED", "flaky"):
            line += f"\n            {_failure_detail(r)}"
        lines.append(line)
    lines += ["", f"{passed}/{len(results)} cases passed"]
    flaky = [r["id"] for r in results if r["flaky"]]
    if flaky:
        lines.append(f"Flaky (gave different results across runs): {', '.join(flaky)}")
    if diff["fixed"]:
        lines.append(f"Fixed since baseline: {', '.join(diff['fixed'])}")
    lines.append("")
    lines.append("RESULT: FAIL" if reasons else "RESULT: PASS")
    lines += [f"  - {reason}" for reason in reasons]
    return "\n".join(lines)


def markdown(suite_name, results, diff, reasons):
    passed = sum(r["passed"] for r in results)
    out = [f"## Driftwatch: {suite_name}", "",
           f"**{'FAIL' if reasons else 'PASS'}**: {passed}/{len(results)} cases passed", ""]
    out += [f"- {reason}" for reason in reasons]
    out += ["", "| Case | Result | Runs passed | p50 latency | Detail |", "| --- | --- | --- | --- | --- |"]
    for r in results:
        latencies = sorted(run["latency_ms"] for run in r["runs"])
        p50 = latencies[len(latencies) // 2]
        passes = round(r["pass_rate"] * r["repeats"])
        out.append(f"| {r['id']}{' (critical)' if r['critical'] else ''} | {_status(r, diff)} | "
                   f"{passes}/{r['repeats']} | {p50:.0f} ms | {_failure_detail(r) or 'ok'} |")
    return "\n".join(out) + "\n"


def to_json(suite_name, results, diff, reasons):
    return json.dumps({"suite": suite_name, "passed": not reasons, "gate_reasons": reasons,
                       "diff": diff, "results": results}, indent=2)


def junit(suite_name, results, diff):
    """JUnit XML, the format Jenkins, GitLab, and most CI dashboards read."""
    failures = sum(not r["passed"] for r in results)
    total_s = sum(run["latency_ms"] for r in results for run in r["runs"]) / 1000
    suite = ET.Element("testsuite", name=suite_name, tests=str(len(results)),
                       failures=str(failures), time=f"{total_s:.3f}")
    for r in results:
        case_s = sum(run["latency_ms"] for run in r["runs"]) / 1000
        tc = ET.SubElement(suite, "testcase", classname=suite_name, name=r["id"], time=f"{case_s:.3f}")
        if not r["passed"]:
            kind = "regression" if r["id"] in diff["regressions"] else "failure"
            failure = ET.SubElement(tc, "failure", type=kind, message=_failure_detail(r)[:500])
            failure.text = json.dumps(r["runs"], indent=2)
        elif r["flaky"]:
            ET.SubElement(tc, "system-out").text = f"flaky: passed {r['pass_rate']:.0%} of {r['repeats']} runs"
    return ET.tostring(suite, encoding="unicode", xml_declaration=True)
