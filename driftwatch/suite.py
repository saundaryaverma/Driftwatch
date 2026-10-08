"""Load and validate a suite file."""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from driftwatch.checks import parse_check


class SuiteError(ValueError):
    """The suite file is invalid. The message says where and why."""


@dataclass
class Case:
    id: str
    prompt: str
    checks: list
    history: list = field(default_factory=list)
    tags: list = field(default_factory=list)
    critical: bool = False
    repeats: int = 1
    min_pass_rate: float = 1.0


@dataclass
class Suite:
    name: str
    target: dict
    cases: list
    gate: dict
    path: Path


GATE_DEFAULTS = {"min_pass_rate": 1.0, "fail_on_regression": True, "fail_on_critical": True}


def load_suite(path):
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise SuiteError(f"{path}: not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise SuiteError(f"{path}: expected a mapping at the top level")
    if not raw.get("cases"):
        raise SuiteError(f"{path}: needs at least one case under 'cases'")

    defaults = raw.get("defaults", {})
    cases, seen = [], set()
    for i, item in enumerate(raw["cases"]):
        where = f"{path}: case #{i + 1}"
        if not isinstance(item, dict):
            raise SuiteError(f"{where}: must be a mapping")
        for key in ("id", "prompt", "checks"):
            if not item.get(key):
                raise SuiteError(f"{where}: missing '{key}'")
        if item["id"] in seen:
            raise SuiteError(f"{where}: duplicate id {item['id']!r}")
        seen.add(item["id"])
        for spec in item["checks"]:
            try:
                parse_check(spec)
            except ValueError as exc:
                raise SuiteError(f"{where} ({item['id']}): {exc}") from exc
        for turn in item.get("history", []):
            if turn.get("role") not in ("user", "assistant") or "content" not in turn:
                raise SuiteError(f"{where} ({item['id']}): history turns need role user/assistant and content")
        repeats = int(item.get("repeats", defaults.get("repeats", 1)))
        rate = float(item.get("min_pass_rate", defaults.get("min_pass_rate", 1.0)))
        if repeats < 1 or not 0 <= rate <= 1:
            raise SuiteError(f"{where} ({item['id']}): repeats must be >= 1 and min_pass_rate between 0 and 1")
        cases.append(Case(
            id=item["id"], prompt=item["prompt"], checks=item["checks"],
            history=item.get("history", []), tags=item.get("tags", []),
            critical=bool(item.get("critical", False)), repeats=repeats, min_pass_rate=rate,
        ))

    return Suite(
        name=raw.get("name", path.stem),
        target=raw.get("target", {}),
        cases=cases,
        gate={**GATE_DEFAULTS, **raw.get("gate", {})},
        path=path,
    )
