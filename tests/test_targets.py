import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest

from driftwatch.targets import (TargetError, build_target, extract, fill_template, http_target,
                                openai_judge, openai_target, parse_target_spec)

MESSAGES = [{"role": "user", "content": "earlier"}, {"role": "user", "content": "Where is my order?"}]


def test_fill_template_inserts_prompt_and_messages():
    body = {"q": "Q: {{prompt}}", "history": "{{messages}}", "n": 3}
    assert fill_template(body, MESSAGES) == {"q": "Q: Where is my order?", "history": MESSAGES, "n": 3}


def test_extract_follows_dotted_paths():
    assert extract({"choices": [{"text": "hi"}]}, "choices.0.text") == "hi"
    with pytest.raises(TargetError):
        extract({"a": 1}, "b")


@pytest.fixture
def server():
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            received.append(body)
            out = json.dumps({"data": {"reply": f"echo: {body['message']}"}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *args):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}/chat", received
    httpd.shutdown()


def test_http_target_posts_template_and_reads_reply_path(server):
    url, received = server
    target = http_target(url, body={"message": "{{prompt}}"}, reply_path="data.reply")
    assert target(MESSAGES) == "echo: Where is my order?"
    assert received == [{"message": "Where is my order?"}]


def test_python_target_loads_a_function():
    target = build_target({"type": "python", "callable": "examples.support_bot.bot_v1:reply"})
    assert "30 days" in target([{"role": "user", "content": "returns?"}])


def test_python_target_reports_bad_paths():
    with pytest.raises(TargetError):
        build_target({"type": "python", "callable": "no_such_module:reply"})
    with pytest.raises(TargetError):
        build_target({"type": "python", "callable": "missing-colon"})


class FakeOpenAI:
    def __init__(self, content):
        self.sent = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.content = content

    def _create(self, **kwargs):
        self.sent.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))])


def test_openai_target_adds_system_prompt():
    client = FakeOpenAI("hi")
    assert openai_target("m", "Be brief.", client=client)(MESSAGES) == "hi"
    assert client.sent[0]["messages"][0] == {"role": "system", "content": "Be brief."}
    assert client.sent[0]["temperature"] == 0


def test_openai_judge_parses_verdict():
    client = FakeOpenAI('{"pass": false, "reason": "rude"}')
    assert openai_judge("m", client=client)(rubric="polite", prompt="q", reply="go away") == {
        "pass": False, "reason": "rude"}


@pytest.mark.parametrize("spec,expected", [
    ("python:pkg.mod:fn", {"type": "python", "callable": "pkg.mod:fn"}),
    ("openai:gpt-4o-mini", {"type": "openai", "model": "gpt-4o-mini"}),
    ("http://localhost:5000/chat", {"type": "http", "url": "http://localhost:5000/chat"}),
])
def test_parse_target_spec(spec, expected):
    assert parse_target_spec(spec) == expected


def test_unknown_target_type():
    with pytest.raises(TargetError):
        build_target({"type": "carrier-pigeon"})
    with pytest.raises(TargetError):
        parse_target_spec("ftp")
