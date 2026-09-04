"""Control settings for the device support bot.

Privacy and safety controls default to ON for device users. Critical privacy
guards cannot be disabled through environment variables.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any, Dict


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class ControlSettings:
    """Runtime controls for matching, privacy, safety, and optional LLM use."""

    # Knowledge matching
    min_match_score: float = 0.25
    max_related_topics: int = 3

    # Privacy controls (always enforced for device support)
    privacy_mode: bool = True
    refuse_secret_shares: bool = True
    redact_secrets_in_logs: bool = True
    no_telemetry: bool = True
    no_persistent_chat_history: bool = True
    local_knowledge_first: bool = True
    append_safety_footer: bool = True
    allow_exploit_help: bool = False  # hard-deny

    # LLM controls (off by default for privacy on devices)
    llm_enabled: bool = False
    llm_temperature: float = 0.2
    llm_timeout_sec: float = 30.0
    llm_requires_explicit_opt_in: bool = True

    # Output controls
    interactive_banner: bool = True
    json_compact: bool = False

    @classmethod
    def from_env(cls) -> "ControlSettings":
        """Load tunable settings while keeping critical privacy guards locked on."""
        base = cls()
        # LLM stays off unless explicitly enabled AND privacy mode allows opt-in.
        llm_env = _env_bool("DEVICE_SUPPORT_BOT_LLM", False)
        privacy_mode = True  # locked on for device deployments
        llm_enabled = bool(llm_env) and not base.llm_requires_explicit_opt_in
        # Explicit opt-in path: DEVICE_SUPPORT_BOT_LLM=1 is the opt-in signal.
        if llm_env and base.llm_requires_explicit_opt_in:
            llm_enabled = True  # user explicitly opted in via env

        return cls(
            min_match_score=_env_float(
                "DEVICE_SUPPORT_BOT_MIN_SCORE", base.min_match_score
            ),
            max_related_topics=int(
                _env_float(
                    "DEVICE_SUPPORT_BOT_MAX_RELATED", float(base.max_related_topics)
                )
            ),
            privacy_mode=privacy_mode,
            refuse_secret_shares=True,
            redact_secrets_in_logs=True,
            no_telemetry=True,
            no_persistent_chat_history=True,
            local_knowledge_first=True,
            append_safety_footer=_env_bool(
                "DEVICE_SUPPORT_BOT_SAFETY_FOOTER", base.append_safety_footer
            ),
            allow_exploit_help=False,
            llm_enabled=llm_enabled,
            llm_temperature=_env_float(
                "DEVICE_SUPPORT_BOT_LLM_TEMPERATURE", base.llm_temperature
            ),
            llm_timeout_sec=_env_float(
                "DEVICE_SUPPORT_BOT_LLM_TIMEOUT", base.llm_timeout_sec
            ),
            llm_requires_explicit_opt_in=True,
            interactive_banner=_env_bool(
                "DEVICE_SUPPORT_BOT_BANNER", base.interactive_banner
            ),
            json_compact=_env_bool(
                "DEVICE_SUPPORT_BOT_JSON_COMPACT", base.json_compact
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def privacy_summary(self) -> Dict[str, Any]:
        """Return the locked privacy posture for device deployments."""
        return {
            "privacy_mode": self.privacy_mode,
            "refuse_secret_shares": self.refuse_secret_shares,
            "redact_secrets_in_logs": self.redact_secrets_in_logs,
            "no_telemetry": self.no_telemetry,
            "no_persistent_chat_history": self.no_persistent_chat_history,
            "local_knowledge_first": self.local_knowledge_first,
            "allow_exploit_help": self.allow_exploit_help,
            "llm_enabled": self.llm_enabled,
            "llm_requires_explicit_opt_in": self.llm_requires_explicit_opt_in,
        }


DEFAULT_CONTROLS = ControlSettings.from_env()
