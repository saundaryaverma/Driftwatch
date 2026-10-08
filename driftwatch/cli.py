"""Command line: driftwatch run SUITE [options]"""
import argparse
import os
import sys
from pathlib import Path

from driftwatch import report
from driftwatch.baseline import compare, gate, load_baseline, save_baseline
from driftwatch.checks import CheckError
from driftwatch.runner import run_suite
from driftwatch.suite import SuiteError, load_suite
from driftwatch.targets import TargetError, build_target, openai_judge, parse_target_spec


def build_parser():
    parser = argparse.ArgumentParser(prog="driftwatch", description="Regression testing for LLM apps.")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run a suite")
    run.add_argument("suite", help="path to a suite YAML file")
    run.add_argument("--target", help="override the suite's target: python:module:func, openai:<model>, or a URL")
    run.add_argument("--baseline", help="baseline file (default: baseline.json next to the suite)")
    run.add_argument("--update-baseline", action="store_true", help="save this run as the new baseline")
    run.add_argument("--repeats", type=int, help="run every case this many times")
    run.add_argument("--tag", action="append", help="only run cases with this tag (repeatable)")
    run.add_argument("--judge", help="model for llm_judge checks, e.g. openai:gpt-4o-mini")
    run.add_argument("--report-md", help="write a Markdown report here")
    run.add_argument("--report-json", help="write a JSON report here")
    run.add_argument("--junit", help="write JUnit XML here")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        suite = load_suite(args.suite)
        target_config = parse_target_spec(args.target) if args.target else suite.target
        if not target_config:
            raise TargetError("no target: add 'target' to the suite or pass --target")
        target = build_target(target_config, base_dir=suite.path.parent)
        judge = None
        if args.judge:
            kind, _, model = args.judge.partition(":")
            if kind != "openai" or not model:
                raise TargetError("--judge must look like openai:<model>")
            judge = openai_judge(model)
        if args.repeats:
            for case in suite.cases:
                case.repeats = args.repeats
        results = run_suite(suite, target, judge, args.tag)
        if not results:
            raise SuiteError("no cases matched the given --tag")
    except (SuiteError, TargetError, CheckError) as exc:
        print(f"driftwatch: {exc}", file=sys.stderr)
        return 2

    baseline_path = Path(args.baseline) if args.baseline else suite.path.parent / "baseline.json"
    diff = compare(results, load_baseline(baseline_path))
    reasons = gate(results, diff, suite.gate)

    print(report.console(suite.name, results, diff, reasons))
    md = report.markdown(suite.name, results, diff, reasons)
    if args.report_md:
        Path(args.report_md).write_text(md)
    if args.report_json:
        Path(args.report_json).write_text(report.to_json(suite.name, results, diff, reasons))
    if args.junit:
        Path(args.junit).write_text(report.junit(suite.name, results, diff))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(md)

    if args.update_baseline:
        save_baseline(baseline_path, suite.name, results)
        print(f"\nSaved baseline: {baseline_path}")
        return 0
    return 1 if reasons else 0


if __name__ == "__main__":
    sys.exit(main())
