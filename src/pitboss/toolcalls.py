"""The tool calls in the entries of a worker's transcript (JSON lines)."""

import json
from typing import Iterable, Mapping, Sequence


def uses(entries: Sequence[str]) -> Iterable[tuple[int, str, Mapping[str, object]]]:
    """The tool calls of a transcript, in order.

    Args:
        entries: the lines of the transcript; a line that is not JSON or holds
            no tool call is passed over.

    Yields:
        Each call's index (of its line), tool name and input.
    """
    for index, entry in enumerate(entries):
        try:
            content = json.loads(entry)["message"]["content"]
        except (ValueError, KeyError, TypeError):
            continue
        for item in content if isinstance(content, list) else []:
            if isinstance(item, dict) and "name" in item:
                yield index, str(item["name"]), dict(item.get("input", {}))
