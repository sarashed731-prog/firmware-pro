# Local AI agent

`tools/ai_agent.py` provides an opt-in, iSH-compatible chat client and a
restricted repository check runner. It does not access devices, drives, Gmail,
or network services unless the user starts it and configures an AI endpoint.

## Setup

From the repository root:

```sh
export AI_AGENT_API_KEY='your-provider-key'
export AI_AGENT_MODEL='gpt-4o-mini'
python3 tools/ai_agent.py
```

`AI_AGENT_ENDPOINT` may point to an OpenAI-compatible chat-completions endpoint.
For a service running inside iSH, use the loopback address explicitly:

```sh
python3 tools/ai_agent.py \
  --endpoint http://127.0.0.1:8000/v1/chat/completions
```

If the service runs on the iOS host rather than inside iSH, use the host and
port exposed by that service; `127.0.0.1` refers to iSH's own network
namespace.
The key is read from the environment only; never put it in the repository,
shell history, prompts, or bug reports.

## Supported operations

The `/run` command accepts only `gen_check`, `rust_test`, and `emulator_test`.
Each operation requires a separate `y` confirmation. Arguments, shell syntax,
redirections, pipelines, and arbitrary subprocesses are rejected. Commands run
from the repository root with a five-minute timeout. `/cancel` requests
cancellation of a running command; `Ctrl-C` exits the client.

Only the current conversation is retained in memory. Prompts and displayed
command output are redacted when lines appear to contain keys, tokens,
passwords, secrets, or credentials. Do not send firmware signing material,
device secrets, personal files, or account data to the AI service.

## Emergency shutdown

Press `Ctrl-C`, terminate the Python process, and unset `AI_AGENT_API_KEY`.
Review and revoke the provider key from its account dashboard if it may have
been exposed.
