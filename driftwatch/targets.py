"""Targets are the AI apps under test. Every target is a function:
messages (list of {"role", "content"}) -> reply text."""
import importlib
import json
import sys
import urllib.request
from pathlib import Path


class TargetError(ValueError):
    pass


def python_target(callable_path):
    """'package.module:function'. The function receives the message list."""
    if ":" not in callable_path:
        raise TargetError(f"python target must look like 'module:function', got {callable_path!r}")
    module_name, func_name = callable_path.split(":", 1)
    if str(Path.cwd()) not in sys.path:
        sys.path.insert(0, str(Path.cwd()))
    try:
        func = getattr(importlib.import_module(module_name), func_name)
    except (ImportError, AttributeError) as exc:
        raise TargetError(f"can't load {callable_path!r}: {exc}") from exc
    return func


def fill_template(template, messages):
    """Fill {{prompt}} and {{messages}} placeholders in a request body template."""
    prompt = messages[-1]["content"]
    if template == "{{messages}}":
        return messages
    if isinstance(template, str):
        return template.replace("{{prompt}}", prompt)
    if isinstance(template, dict):
        return {k: fill_template(v, messages) for k, v in template.items()}
    if isinstance(template, list):
        return [fill_template(v, messages) for v in template]
    return template


def extract(data, path):
    """Follow a dotted path like 'choices.0.text' into parsed JSON."""
    for part in path.split("."):
        if isinstance(data, list):
            data = data[int(part)]
        elif isinstance(data, dict) and part in data:
            data = data[part]
        else:
            raise TargetError(f"reply_path {path!r} not found in response")
    return str(data)


def http_target(url, body=None, headers=None, reply_path=None, timeout=60):
    """POST a JSON body to any app. If reply_path is set the response is parsed as
    JSON and the reply is read from that path; otherwise the raw text is the reply."""
    body = body or {"messages": "{{messages}}"}

    def complete(messages):
        payload = json.dumps(fill_template(body, messages)).encode()
        req = urllib.request.Request(
            url, data=payload, method="POST",
            headers={"Content-Type": "application/json", **(headers or {})},
        )
        with urllib.request.urlopen(req, timeout=timeout) as res:
            text = res.read().decode()
        return extract(json.loads(text), reply_path) if reply_path else text

    return complete


def openai_target(model, system_prompt=None, temperature=0, client=None):
    if client is None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise TargetError("install the openai extra: pip install 'driftwatch[openai]'") from exc
        client = OpenAI()

    def complete(messages):
        full = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + messages
        res = client.chat.completions.create(model=model, messages=full, temperature=temperature)
        return res.choices[0].message.content or ""

    return complete


def openai_judge(model, client=None):
    """A grader for llm_judge checks. Returns {"pass": bool, "reason": str}."""
    if client is None:
        from openai import OpenAI
        client = OpenAI()

    def judge(rubric, prompt, reply):
        res = client.chat.completions.create(
            model=model, temperature=0, response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": (
                    "You grade an AI assistant's reply against a rubric. Respond with JSON: "
                    '{"pass": true or false, "reason": "one sentence"}.')},
                {"role": "user", "content": f"Rubric: {rubric}\n\nUser message: {prompt}\n\nReply: {reply}"},
            ],
        )
        verdict = json.loads(res.choices[0].message.content)
        return {"pass": bool(verdict.get("pass")), "reason": verdict.get("reason", "")}

    return judge


def build_target(config, base_dir=Path(".")):
    kind = config.get("type")
    if kind == "python":
        return python_target(config["callable"])
    if kind == "http":
        return http_target(config["url"], config.get("body"), config.get("headers"),
                           config.get("reply_path"), config.get("timeout", 60))
    if kind == "openai":
        system_prompt = config.get("system_prompt")
        if config.get("system_prompt_file"):
            system_prompt = (Path(base_dir) / config["system_prompt_file"]).read_text()
        return openai_target(config["model"], system_prompt, config.get("temperature", 0))
    raise TargetError(f"unknown target type {kind!r}; use python, http, or openai")


def parse_target_spec(spec):
    """Command-line shorthand: 'python:module:func' or 'openai:model'."""
    kind, _, rest = spec.partition(":")
    if kind == "python" and rest:
        return {"type": "python", "callable": rest}
    if kind == "openai" and rest:
        return {"type": "openai", "model": rest}
    if kind in ("http", "https"):
        return {"type": "http", "url": spec}
    raise TargetError(f"can't parse target {spec!r}; try python:module:func, openai:<model>, or a URL")
