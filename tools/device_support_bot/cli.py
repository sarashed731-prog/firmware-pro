"""CLI for the OneKey Pro device support bot."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .bot import DeviceSupportBot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="device-support-bot",
        description="Local AI-style support assistant for OneKey Pro digital devices.",
    )
    parser.add_argument(
        "question",
        nargs="*",
        help="Question to ask (omit for interactive mode)",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Start an interactive REPL",
    )
    parser.add_argument(
        "--list-topics",
        action="store_true",
        help="List knowledge-base topics and exit",
    )
    parser.add_argument(
        "--knowledge",
        type=Path,
        default=None,
        help="Path to knowledge base JSON (default: bundled base.json)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable optional OpenAI-compatible API even if OPENAI_API_KEY is set",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON for a single answer",
    )
    parser.add_argument(
        "--show-controls",
        action="store_true",
        help="Print active control settings and exit",
    )
    return parser


def _print_response(bot: DeviceSupportBot, question: str, *, use_llm: bool, as_json: bool) -> int:
    response = bot.answer(question, use_llm=use_llm)
    if as_json:
        import json

        indent = None if bot.controls.json_compact else 2
        print(
            json.dumps(
                {
                    "text": response.text,
                    "topic_id": response.topic_id,
                    "topic_title": response.topic_title,
                    "score": response.score,
                    "source": response.source,
                },
                ensure_ascii=True,
                indent=indent,
            )
        )
    else:
        print(response.text)
    return 0


def interactive_loop(bot: DeviceSupportBot, *, use_llm: bool) -> int:
    if bot.controls.interactive_banner:
        print("OneKey Pro device support bot (offline knowledge base).")
        print("Type a question, 'topics' for the catalog, or 'quit' to exit.")
        print("Never paste seed phrases, PINs, or private keys.\n")
    while True:
        try:
            line = input("support> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        lower = line.lower()
        if lower in {"q", "quit", "exit"}:
            return 0
        if lower in {"topics", "list"}:
            for item in bot.list_topics():
                print(f"  - {item}")
            continue
        if lower in {"controls", "settings"}:
            import json

            print(json.dumps(bot.control_settings(), indent=2, sort_keys=True))
            continue
        response = bot.answer(line, use_llm=use_llm)
        print(response.text)
        print()


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    bot = DeviceSupportBot(knowledge_path=args.knowledge)
    use_llm = (not args.no_llm) and bot.controls.llm_enabled

    if args.show_controls:
        import json

        payload = bot.control_settings()
        payload["privacy"] = bot.controls.privacy_summary()
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    if args.list_topics:
        for item in bot.list_topics():
            print(item)
        return 0

    question = " ".join(args.question).strip()
    if args.interactive or not question:
        if question:
            _print_response(bot, question, use_llm=use_llm, as_json=False)
            print()
        return interactive_loop(bot, use_llm=use_llm)

    return _print_response(bot, question, use_llm=use_llm, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
