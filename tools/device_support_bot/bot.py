"""Offline-first support engine for OneKey Pro device questions."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .settings import ControlSettings, DEFAULT_CONTROLS

DEFAULT_KNOWLEDGE = Path(__file__).resolve().parent / "knowledge" / "base.json"

# Hard cap on inbound message size to avoid pathological overflow in matching/LLM.
MAX_MESSAGE_CHARS = 4000

REFUSE_SECRETS = (
    "I will not collect or handle seed phrases, PINs, passphrases, or private keys. "
    "If you were about to share a secret, stop and store it offline only. "
    "Official support will never ask you to paste those values into chat."
)

REFUSE_OVERFLOW = (
    "That message is too long for the support bot. "
    "Please ask a shorter question (a few sentences) without pasting logs or secrets."
)

REFUSE_EXPLOIT = (
    "I cannot help with exploits, attacks, or bypassing device security. "
    "To report a vulnerability responsibly, email security@onekey.so."
)

EXPLOIT_PATTERNS = (
    re.compile(r"\b(exploit|payload|0day|jailbreak)\b", re.I),
    re.compile(r"\b(bypass|break)\b.*\b(pin|seed|secure element|securelement)\b", re.I),
    re.compile(r"\bextract\b.*\b(seed|private key|mnemonic)\b", re.I),
)


@dataclass(frozen=True)
class SupportResponse:
    """A single bot reply with optional matched topic metadata."""

    text: str
    topic_id: Optional[str] = None
    topic_title: Optional[str] = None
    score: float = 0.0
    source: str = "knowledge"  # knowledge | safety | llm | fallback


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _score_topic(query_tokens: Sequence[str], topic: Dict[str, Any]) -> float:
    if not query_tokens:
        return 0.0

    keywords = [k.lower() for k in topic.get("keywords", [])]
    # Ignore tiny title words ("a", "to", "on") that create false positives.
    title_tokens = [t for t in _tokenize(topic.get("title", "")) if len(t) >= 3]
    haystack = keywords + title_tokens
    if not haystack:
        return 0.0

    query_set = set(query_tokens)
    hits = 0.0
    for token in query_set:
        if len(token) < 3:
            continue
        for item in haystack:
            item_tokens = {t for t in _tokenize(item) if len(t) >= 3}
            item_tokens.add(item.replace(" ", ""))
            if token == item or token in item_tokens:
                hits += 1.0
                break
            # Substring only for longer tokens to avoid "a" in "balloon" style hits.
            if len(token) >= 4 and len(item) >= 4 and (token in item or item in token):
                hits += 0.8
                break
            if len(token) >= 4 and len(item) >= 4 and (
                item.startswith(token) or token.startswith(item)
            ):
                hits += 0.6
                break

    joined = " ".join(query_tokens)
    for kw in keywords:
        if " " in kw and kw in joined:
            hits += 1.5

    return hits / max(len(query_set), 1)


class DeviceSupportBot:
    """Answer common OneKey Pro support questions from a local knowledge base.

    Optionally calls an OpenAI-compatible chat API when ``OPENAI_API_KEY`` (or a
    caller-supplied key) is available. The local matcher always runs first for
    safety filtering and FAQ hits.
    """

    def __init__(
        self,
        knowledge_path: Optional[Path] = None,
        *,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        min_score: Optional[float] = None,
        controls: Optional[ControlSettings] = None,
    ) -> None:
        path = Path(knowledge_path) if knowledge_path else DEFAULT_KNOWLEDGE
        with path.open(encoding="utf-8") as fh:
            self.knowledge: Dict[str, Any] = json.load(fh)
        self.topics: List[Dict[str, Any]] = list(self.knowledge.get("topics", []))
        self.safety_rules: List[str] = list(self.knowledge.get("safety_rules", []))
        self.controls = controls or DEFAULT_CONTROLS
        self.min_score = (
            float(min_score)
            if min_score is not None
            else float(self.controls.min_match_score)
        )
        self.api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
        self.api_base = (
            api_base
            or os.environ.get("OPENAI_API_BASE")
            or "https://api.openai.com/v1"
        ).rstrip("/")
        self.model = model or os.environ.get("DEVICE_SUPPORT_BOT_MODEL") or "gpt-4o-mini"

    def looks_like_secret_share(self, message: str) -> bool:
        """Return True when the user message appears to include wallet secrets."""
        stripped = message.strip()
        if not stripped:
            return False
        if re.search(
            r"\b(my|here'?s|here is)\b.*\b(seed|mnemonic|recovery)\b", stripped, re.I
        ):
            return True
        if re.search(r"\b(seed|mnemonic|recovery phrase)\b\s*[:=]", stripped, re.I):
            return True
        words = re.findall(r"[a-zA-Z]+", stripped)
        if len(words) >= 12 and len(words) <= 24 and len(set(w.lower() for w in words)) >= 10:
            if sum(1 for w in words if 3 <= len(w) <= 8) >= len(words) * 0.8:
                return True
        return False

    def looks_like_exploit_request(self, message: str) -> bool:
        return any(p.search(message) for p in EXPLOIT_PATTERNS)

    def rank_topics(
        self, message: str, *, limit: int = 5
    ) -> List[Tuple[float, Dict[str, Any]]]:
        tokens = _tokenize(message)
        ranked: List[Tuple[float, Dict[str, Any]]] = []
        for topic in self.topics:
            score = _score_topic(tokens, topic)
            if score > 0:
                ranked.append((score, topic))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return ranked[:limit]

    def answer(self, message: str, *, use_llm: bool = True) -> SupportResponse:
        """Return the best support response for ``message``."""
        text = (message or "").strip()
        if not text:
            return SupportResponse(
                text=(
                    "Ask a question about your OneKey Pro device, firmware, "
                    "or developer setup."
                ),
                source="fallback",
            )

        if len(text) > MAX_MESSAGE_CHARS:
            return SupportResponse(text=REFUSE_OVERFLOW, source="safety")

        if self.controls.refuse_secret_shares and self.looks_like_secret_share(text):
            return SupportResponse(text=REFUSE_SECRETS, source="safety")

        if not self.controls.allow_exploit_help and self.looks_like_exploit_request(text):
            return SupportResponse(text=REFUSE_EXPLOIT, source="safety")

        ranked = self.rank_topics(text)
        if ranked and ranked[0][0] >= self.min_score:
            score, topic = ranked[0]
            body = topic.get("answer", "").strip()
            tips = ""
            related_n = max(0, int(self.controls.max_related_topics))
            related_titles: List[str] = []
            for rel_score, rel_topic in ranked[1 : related_n + 1]:
                if rel_score >= self.min_score:
                    related_titles.append(str(rel_topic.get("title")))
            if related_titles:
                tips = "\n\nRelated topics: " + ", ".join(related_titles) + "."

            safety = ""
            if self.controls.append_safety_footer:
                safety = (
                    "\n\nSafety: never share seed phrases, PINs, or private keys "
                    "with anyone or any bot."
                )
            return SupportResponse(
                text=f"**{topic.get('title', 'Help')}**\n\n{body}{tips}{safety}",
                topic_id=topic.get("id"),
                topic_title=topic.get("title"),
                score=score,
                source="knowledge",
            )

        llm_allowed = use_llm and self.controls.llm_enabled and bool(self.api_key)
        if llm_allowed:
            llm_text = self._llm_answer(text, ranked)
            if llm_text:
                return SupportResponse(text=llm_text, source="llm")

        return SupportResponse(
            text=self._fallback(text, ranked),
            source="fallback",
            score=ranked[0][0] if ranked else 0.0,
            topic_id=ranked[0][1].get("id") if ranked else None,
            topic_title=ranked[0][1].get("title") if ranked else None,
        )

    def _system_prompt(self) -> str:
        rules = "\n".join(f"- {r}" for r in self.safety_rules)
        catalog = "\n".join(f"- {t.get('id')}: {t.get('title')}" for t in self.topics)
        device = self.knowledge.get("device", "OneKey Pro")
        return (
            f"You are a concise support assistant for the {device} hardware wallet firmware. "
            "Help with device setup, firmware, emulator, and safe usage. "
            "If unsure, say so and point to official docs. "
            "Refuse requests for exploits or secret handling.\n"
            f"Safety rules:\n{rules}\n"
            f"Known topics:\n{catalog}"
        )

    def _llm_answer(
        self, message: str, ranked: Sequence[Tuple[float, Dict[str, Any]]]
    ) -> Optional[str]:
        context_bits: List[str] = []
        for score, topic in ranked[:3]:
            context_bits.append(
                f"[{topic.get('id')} score={score:.2f}] {topic.get('title')}: "
                f"{topic.get('answer')}"
            )
        user_content = message
        if context_bits:
            user_content += "\n\nLocal knowledge candidates:\n" + "\n".join(context_bits)

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": user_content},
            ],
            "temperature": float(self.controls.llm_temperature),
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.api_base}/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + str(self.api_key),
            },
            method="POST",
        )
        timeout = float(self.controls.llm_timeout_sec)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"].strip()
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            KeyError,
            IndexError,
            TimeoutError,
            json.JSONDecodeError,
        ):
            return None

    def _fallback(
        self, message: str, ranked: Sequence[Tuple[float, Dict[str, Any]]]
    ) -> str:
        del message  # reserved for future context
        lines = [
            "I could not find a strong local match for that question.",
            "Try rephrasing, or ask about: setup, firmware update, verify firmware, "
            "emulator build, connection issues, FIDO2, security reporting, or contributing.",
            "Human help: OneKey community discussions / GitHub issues (non-security). "
            "Security: security@onekey.so.",
        ]
        if ranked:
            suggestions = ", ".join(
                f"{t.get('title')} ({s:.2f})" for s, t in ranked[:3]
            )
            lines.insert(1, f"Closest topics: {suggestions}.")
        return "\n".join(lines)

    def list_topics(self) -> Iterable[str]:
        for topic in self.topics:
            yield f"{topic.get('id')}: {topic.get('title')}"

    def control_settings(self) -> Dict[str, Any]:
        return self.controls.to_dict()
