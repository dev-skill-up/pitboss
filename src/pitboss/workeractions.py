"""What a worker's whole output file holds (keyword: worker-actions, pitboss#352).

A statement about what a worker did is made from this scan: the tool calls with
their inputs, and the final report, which is the worker's hand-back. A pattern
found in a call's input or in the final report is a match; a scan that finds
none says how many calls and the final report it read.
"""

import json
import re
from typing import Mapping, Sequence

from . import toolcalls

FINAL_REPORT = "final report"


def _text_of(content: object) -> str:
    if isinstance(content, str):
        return content
    items = content if isinstance(content, list) else []
    return "\n".join(
        str(item["text"])
        for item in items
        if isinstance(item, dict) and item.get("type") == "text" and "text" in item
    )


def _said(entry: str) -> str:
    try:
        message = json.loads(entry)["message"]
        return _text_of(message["content"]) if message["role"] == "assistant" else ""
    except (ValueError, KeyError, TypeError):
        return ""


def _is_message(entry: str) -> bool:
    try:
        return "message" in json.loads(entry)
    except (ValueError, TypeError):
        return False


def final_report(entries: Sequence[str]) -> tuple[int, str] | None:
    """The final report of an output file.

    It is the text of the last assistant message that has any. A file with no
    message entry in it (plain text) is its own final report.

    Args:
        entries: the lines of the file.

    Returns:
        The line number (from 1; 1 for a plain text) and the text, or None for
        an empty file.
    """
    said = [(number, _said(entry)) for number, entry in enumerate(entries, 1)]
    spoken = [(number, text) for number, text in said if text]
    if any(map(_is_message, entries)):
        return spoken[-1] if spoken else None
    whole = "\n".join(entries).strip()
    return (1, whole) if whole else None


def _input(given: Mapping[str, object]) -> str:
    return json.dumps(given, ensure_ascii=False, sort_keys=True)


def scan(entries: Sequence[str], patterns: Sequence[str]) -> Sequence[str]:
    """The calls and the final report of an output file that match a pattern.

    Args:
        entries: the lines of the file.
        patterns: regular expressions, searched without regard to case; a text
            matches when one of them is found in it.

    Returns:
        A line for each match, ``<line>: <tool> <input>`` for a call and
        ``<line>: final report: <text>`` for the report, or the one line
        ``no match in N calls and the final report``.
    """
    found = [re.compile(each, re.IGNORECASE) for each in patterns]
    calls = list(toolcalls.uses(entries))
    shown = [(index + 1, name, _input(given)) for index, name, given in calls]
    report = final_report(entries)
    if report:
        shown.append((report[0], FINAL_REPORT + ":", report[1]))
    matches = [
        f"{number}: {name} {text}"
        for number, name, text in shown
        if any(each.search(text) for each in found)
    ]
    return matches or [f"no match in {len(calls)} calls and the {FINAL_REPORT}"]
