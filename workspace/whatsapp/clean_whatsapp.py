#!/usr/bin/env python3
"""Remove timestamps and sender names from a WhatsApp text export."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


MESSAGE_PATTERNS = (
    # iOS-style export:
    # [24/07/2026, 14:03:12] Person: Message
    re.compile(
        r"^\[\d{1,2}/\d{1,2}/\d{2,4}, .+?\]\s+[^:]+:\s?(.*)$"
    ),
    # Android-style export:
    # 24/07/2026, 14:03 - Person: Message
    re.compile(
        r"^\d{1,2}/\d{1,2}/\d{2,4}, .+?\s+-\s+[^:]+:\s?(.*)$"
    ),
)


def message_body(line: str) -> str | None:
    """Return the body when a line starts a user message."""
    normalized = line.lstrip("\u200e\u200f")
    for pattern in MESSAGE_PATTERNS:
        match = pattern.match(normalized)
        if match:
            return match.group(1)
    return None


def clean_export(text: str) -> list[str]:
    """Extract message bodies while preserving multiline messages."""
    messages: list[str] = []
    current_message: list[str] | None = None

    for line in text.splitlines(keepends=True):
        body = message_body(line.rstrip("\r\n"))
        if body is not None:
            if current_message is not None:
                messages.append("".join(current_message).strip())
            current_message = [body]
            if line.endswith(("\n", "\r")):
                current_message.append("\n")
        elif current_message is not None:
            current_message.append(line)

    if current_message is not None:
        messages.append("".join(current_message).strip())

    return messages


def process_messages(input_file: Path, output_file: Path) -> int:
    """Clean one WhatsApp export and return the number of messages."""
    text = input_file.read_text(encoding="utf-8")
    messages = clean_export(text)
    output_file.write_text("\n\n----\n\n".join(messages) + "\n", encoding="utf-8")
    return len(messages)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove timestamps and sender names from a WhatsApp text export."
    )
    parser.add_argument("input", nargs="?", type=Path, default=Path("msgs.txt"))
    parser.add_argument("output", nargs="?", type=Path, default=Path("cleaned_msgs.txt"))
    args = parser.parse_args()

    try:
        count = process_messages(args.input, args.output)
    except FileNotFoundError:
        parser.error(f"input file not found: {args.input}")

    print(f"Processed {count} messages.")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
