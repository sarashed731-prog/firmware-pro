# Device support bot

Local, offline-first assistant for common **OneKey Pro** device and firmware questions.

It ships a curated knowledge base under `tools/device_support_bot/knowledge/base.json` and a small Python CLI. Matching is keyword-based and works without network access. If `OPENAI_API_KEY` is set, unmatched questions can optionally be sent to an OpenAI-compatible chat API.


## Privacy posture (always on for devices)

The bot runs in **privacy mode** by default:

- No telemetry and no persistent chat history
- Local knowledge base is tried first
- Seed/PIN/passphrase pastes are refused
- Exploit/bypass help is hard-denied
- Optional cloud LLM is **off** unless you explicitly set `DEVICE_SUPPORT_BOT_LLM=1`

Critical privacy guards cannot be turned off via environment variables.

## Safety

- The bot **never** asks for seed phrases, recovery words, PINs, passphrases, or private keys.
- Messages that look like recovery-phrase dumps are refused.
- Security vulnerabilities must go to **security@onekey.so**, not public issues.

## Run

From the repository root:

```bash
# Single question (offline)
python3 -m tools.device_support_bot --no-llm "How do I verify firmware?"

# List topics
python3 -m tools.device_support_bot --list-topics

# Show control settings
python3 -m tools.device_support_bot --show-controls

# Interactive mode
python3 -m tools.device_support_bot --interactive --no-llm
```

### Control settings

Runtime controls live in `tools/device_support_bot/settings.py` and can be tuned with env vars:

| Variable | Effect |
| --- | --- |
| `DEVICE_SUPPORT_BOT_MIN_SCORE` | Minimum match score (default `0.25`) |
| `DEVICE_SUPPORT_BOT_MAX_RELATED` | Related topics to append |
| `DEVICE_SUPPORT_BOT_REFUSE_SECRETS` | Refuse seed/PIN-like pastes (`true`/`false`) |
| `DEVICE_SUPPORT_BOT_SAFETY_FOOTER` | Append safety footer on answers |
| `DEVICE_SUPPORT_BOT_LLM` | Allow optional LLM fallback |
| `DEVICE_SUPPORT_BOT_LLM_TEMPERATURE` | LLM temperature |
| `DEVICE_SUPPORT_BOT_LLM_TIMEOUT` | LLM HTTP timeout seconds |
| `DEVICE_SUPPORT_BOT_BANNER` | Interactive banner on/off |
| `DEVICE_SUPPORT_BOT_JSON_COMPACT` | Compact `--json` output |

Messages longer than 4000 characters are rejected (overflow guard). Exploit/bypass requests are refused. `allow_exploit_help` is always false.

Optional LLM fallback:

```bash
export OPENAI_API_KEY=...          # optional
# export OPENAI_API_BASE=https://api.openai.com/v1
# export DEVICE_SUPPORT_BOT_MODEL=gpt-4o-mini
python3 -m tools.device_support_bot "Explain bootloader recovery"
```

## Tests

```bash
PYTHONPATH=. python3 -m unittest tools.device_support_bot.tests.test_bot -v
```

## Extending the knowledge base

Edit `tools/device_support_bot/knowledge/base.json`:

- Add a `topics[]` entry with `id`, `title`, `keywords`, and `answer`.
- Keep answers actionable and link to docs paths when possible.
- Do not store secrets or user-specific account data in the knowledge base.
