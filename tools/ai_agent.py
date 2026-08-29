#!/usr/bin/env python3
"""Small, opt-in AI chat and safe repository check runner for iSH."""

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_ENDPOINT = "https://api.openai.com/v1/chat/completions"
COMMANDS = {
    "gen_check": ("make", "gen_check"),
    "rust_test": ("make", "-C", "core", "test_rust"),
    "emulator_test": ("make", "-C", "core", "test_emu"),
}
SENSITIVE_NAMES = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASS", "CREDENTIAL")


class AgentError(Exception):
    """An expected, user-facing agent error."""


def redact(value):
    """Remove likely secrets from output before displaying or sending it."""
    lines = []
    for line in str(value).splitlines():
        lower = line.lower()
        if any(name.lower() in lower for name in SENSITIVE_NAMES):
            lines.append("[redacted sensitive output]")
        else:
            lines.append(line)
    return "\n".join(lines)


class CommandRunner:
    def __init__(self, repository, timeout=300):
        self.repository = Path(repository).resolve()
        self.timeout = timeout
        self.process = None
        self.cancelled = threading.Event()

    def cancel(self):
        self.cancelled.set()
        if self.process and self.process.poll() is None:
            if hasattr(os, "killpg"):
                os.killpg(self.process.pid, signal.SIGTERM)
            else:
                self.process.terminate()

    def run(self, name, approve):
        if name not in COMMANDS:
            raise AgentError("Command is not allowlisted.")
        if not approve:
            raise AgentError("Command requires explicit approval.")
        self.cancelled.clear()
        env = {
            key: value
            for key, value in os.environ.items()
            if not any(secret in key.upper() for secret in SENSITIVE_NAMES)
        }
        returncode = None
        try:
            self.process = subprocess.Popen(
                COMMANDS[name],
                cwd=str(self.repository),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
            output, _ = self.process.communicate(timeout=self.timeout)
            returncode = self.process.returncode
        except subprocess.TimeoutExpired:
            self.cancel()
            try:
                output, _ = self.process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                if hasattr(os, "killpg"):
                    os.killpg(self.process.pid, signal.SIGKILL)
                else:
                    self.process.kill()
                output, _ = self.process.communicate()
            raise AgentError("Command timed out after {} seconds.\n{}".format(
                self.timeout, redact(output)
            ))
        finally:
            self.process = None
        output = redact(output)
        if self.cancelled.is_set():
            raise AgentError("Command cancelled.\n{}".format(output))
        if returncode:
            raise AgentError("Command failed with exit code {}.\n{}".format(
                returncode, output
            ))
        return output


class AIClient:
    def __init__(self, endpoint, api_key, model, timeout=60):
        if not api_key:
            raise AgentError("Set AI_AGENT_API_KEY before starting chat.")
        self.endpoint = endpoint
        self._api_key = api_key
        self.model = model
        self.timeout = timeout
        self.history = []

    def ask(self, prompt):
        self.history.append({"role": "user", "content": redact(prompt)})
        body = json.dumps({
            "model": self.model,
            "messages": self.history,
        }).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={
                "Authorization": "Bearer " + self._api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            answer = payload["choices"][0]["message"]["content"]
        except (urllib.error.URLError, TimeoutError) as exc:
            raise AgentError("AI service request failed: {}".format(exc))
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AgentError("AI service returned an invalid response: {}".format(exc))
        answer = redact(answer)
        self.history.append({"role": "assistant", "content": answer})
        return answer


def interactive(repository, endpoint):
    client = None
    runner = CommandRunner(repository)
    model = os.environ.get("AI_AGENT_MODEL", "gpt-4o-mini")
    try:
        client = AIClient(endpoint, os.environ.get("AI_AGENT_API_KEY"), model)
    except AgentError as exc:
        print("{} Chat is unavailable.".format(exc), file=sys.stderr)
    print("Commands: /run gen_check|rust_test|emulator_test, /cancel, /quit")
    while True:
        try:
            prompt = input("agent> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not prompt:
            continue
        if prompt == "/quit":
            break
        if prompt == "/cancel":
            runner.cancel()
            print("Cancellation requested.")
            continue
        if prompt.startswith("/run "):
            name = prompt[5:].strip()
            approved = input("Run {}? [y/N] ".format(name)).lower() == "y"
            try:
                print(runner.run(name, approved))
            except AgentError as exc:
                print("error: {}".format(exc), file=sys.stderr)
            continue
        if client is None:
            print("Chat unavailable until AI_AGENT_API_KEY is configured.", file=sys.stderr)
            continue
        try:
            print(client.ask(prompt))
        except AgentError as exc:
            print("error: {}".format(exc), file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("AI_AGENT_ENDPOINT", DEFAULT_ENDPOINT),
        help="OpenAI-compatible endpoint, e.g. http://127.0.0.1:8000/v1/chat/completions",
    )
    args = parser.parse_args()
    interactive(args.repository, args.endpoint)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    main()
