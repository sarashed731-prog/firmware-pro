import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from tools import ai_agent
from tools.ai_agent import AIClient, AgentError, CommandRunner, redact


def test_redact_sensitive_lines():
    assert redact("normal\nAPI_KEY=secret") == "normal\n[redacted sensitive output]"


def test_command_injection_is_not_allowlisted(tmp_path):
    runner = CommandRunner(tmp_path)
    with pytest.raises(AgentError, match="allowlisted"):
        runner.run("gen_check; touch hacked", True)


def test_command_requires_approval(tmp_path):
    runner = CommandRunner(tmp_path)
    with pytest.raises(AgentError, match="approval"):
        runner.run("gen_check", False)


def test_successful_check(tmp_path, monkeypatch):
    monkeypatch.setitem(ai_agent.COMMANDS, "gen_check", ("echo", "ok"))
    runner = CommandRunner(tmp_path)
    runner.timeout = 10
    assert runner.run("gen_check", True) == "ok"


def test_timeout(tmp_path, monkeypatch):
    monkeypatch.setitem(ai_agent.COMMANDS, "gen_check", ("sleep", "1"))
    runner = CommandRunner(tmp_path, timeout=0.01)
    with pytest.raises(AgentError, match="timed out"):
        runner.run("gen_check", True)


def test_localhost_endpoint_is_accepted():
    client = AIClient("http://127.0.0.1:8000/v1/chat/completions", "test", "test")
    assert client.endpoint.startswith("http://127.0.0.1:")


def test_missing_api_key():
    with pytest.raises(AgentError, match="AI_AGENT_API_KEY"):
        AIClient("http://127.0.0.1", None, "test")


def test_malformed_response():
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *_args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        client = AIClient(
            "http://127.0.0.1:{}/".format(server.server_port), "test", "test"
        )
        with pytest.raises(AgentError, match="invalid response"):
            client.ask("hello")
    finally:
        server.shutdown()
        thread.join()
