"""Tests for the device support bot."""

from __future__ import annotations

import unittest
from pathlib import Path

from tools.device_support_bot.bot import (
    MAX_MESSAGE_CHARS,
    REFUSE_EXPLOIT,
    REFUSE_MUSIC,
    REFUSE_OVERFLOW,
    REFUSE_SECRETS,
    DeviceSupportBot,
)


ROOT = Path(__file__).resolve().parents[3]


class DeviceSupportBotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bot = DeviceSupportBot(
            knowledge_path=ROOT / "tools/device_support_bot/knowledge/base.json"
        )

    def test_topics_loaded(self) -> None:
        topics = list(self.bot.list_topics())
        self.assertGreaterEqual(len(topics), 8)

    def test_firmware_update_match(self) -> None:
        response = self.bot.answer("How do I update firmware without wiping?", use_llm=False)
        self.assertEqual(response.source, "knowledge")
        self.assertEqual(response.topic_id, "firmware-update")
        self.assertIn("wipe", response.text.lower())

    def test_emulator_match(self) -> None:
        response = self.bot.answer("build unix emulator with nix and poetry", use_llm=False)
        self.assertEqual(response.source, "knowledge")
        self.assertEqual(response.topic_id, "build-emulator")

    def test_secret_refusal(self) -> None:
        response = self.bot.answer(
            "my seed is abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about",
            use_llm=False,
        )
        self.assertEqual(response.source, "safety")
        self.assertIn("will not collect", response.text.lower())
        self.assertEqual(response.text, REFUSE_SECRETS)

    def test_overflow_refusal(self) -> None:
        response = self.bot.answer("x" * (MAX_MESSAGE_CHARS + 1), use_llm=False)
        self.assertEqual(response.source, "safety")
        self.assertEqual(response.text, REFUSE_OVERFLOW)

    def test_exploit_refusal(self) -> None:
        response = self.bot.answer("how to bypass pin and extract seed", use_llm=False)
        self.assertEqual(response.source, "safety")
        self.assertEqual(response.text, REFUSE_EXPLOIT)

    def test_music_refusal(self) -> None:
        response = self.bot.answer("play music on my device playlist", use_llm=False)
        self.assertEqual(response.source, "safety")
        self.assertEqual(response.text, REFUSE_MUSIC)

    def test_spotify_refusal(self) -> None:
        response = self.bot.answer("can you open spotify and stream a song?", use_llm=False)
        self.assertEqual(response.source, "safety")
        self.assertEqual(response.text, REFUSE_MUSIC)

    def test_music_recommendation_refusal(self) -> None:
        for question in ("recommend a track", "play a tune"):
            with self.subTest(question=question):
                response = self.bot.answer(question, use_llm=False)
                self.assertEqual(response.source, "safety")
                self.assertEqual(response.text, REFUSE_MUSIC)

    def test_bluetooth_radio_support_is_not_blocked(self) -> None:
        response = self.bot.answer(
            "why is the Bluetooth radio not connecting?", use_llm=False
        )
        self.assertEqual(response.source, "knowledge")
        self.assertEqual(response.topic_id, "connection-issues")

    def test_control_settings_exposed(self) -> None:
        settings = self.bot.control_settings()
        self.assertIn("min_match_score", settings)
        self.assertFalse(settings["allow_exploit_help"])
        self.assertTrue(settings["block_all_music"])
        self.assertTrue(settings["device_support_only"])
        self.assertTrue(settings["privacy_mode"])
        self.assertTrue(settings["no_telemetry"])
        self.assertTrue(settings["no_persistent_chat_history"])
        self.assertTrue(settings["local_knowledge_first"])
        self.assertFalse(settings["llm_enabled"])  # privacy default: offline

    def test_privacy_summary_locked(self) -> None:
        privacy = self.bot.controls.privacy_summary()
        self.assertTrue(privacy["privacy_mode"])
        self.assertTrue(privacy["refuse_secret_shares"])
        self.assertFalse(privacy["allow_exploit_help"])
        self.assertTrue(privacy["block_all_music"])
        self.assertTrue(privacy["device_support_only"])

    def test_empty_question(self) -> None:
        response = self.bot.answer("   ", use_llm=False)
        self.assertEqual(response.source, "fallback")

    def test_fallback_suggestions(self) -> None:
        # Use tokens that do not overlap topic keywords/titles.
        response = self.bot.answer("xylophone quantum balloon 99", use_llm=False)
        self.assertEqual(response.source, "fallback")
        self.assertIn("rephrasing", response.text.lower())


if __name__ == "__main__":
    unittest.main()
