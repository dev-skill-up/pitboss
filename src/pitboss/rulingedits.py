"""The edits a ruling orders on the ticket or the PR body (keyword: ruling-lint).

A leaf module: the flow reads it, and it imports nothing of the gates.
"""

import dataclasses
import re
from typing import Sequence

STEP = re.compile(
    r"^[ \t]*(?:(?:\d+[.)]|[-*])[ \t]+)?(ticket|body)[ \t]+(delete|replace)[ \t]*:"
    r"[ \t]*(.+?)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
ARROW = " => "


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Edit:
    """One edit a ruling orders.

    Attributes:
        step: its number, from 1, in the order written.
        target: ``ticket`` or ``body``.
        old: the text to find, whole.
        new: what takes its place; empty for a deletion.
    """

    step: int
    target: str
    old: str
    new: str

    @property
    def shown(self) -> str:
        """The step as written.

        Returns:
            The target, the operation and the text, cut short.
        """
        verb = "replace" if self.new else "delete"
        return f"{self.target} {verb}: {self.old[:60]}"


def _unquoted(text: str) -> str:
    return text.strip().strip("`\"'").strip()


def orders_edits(ruling: str) -> bool:
    """Whether a ruling orders an edit of the ticket or the body.

    Args:
        ruling: the ruling's text.

    Returns:
        True when one of its steps is an edit.
    """
    return bool(edits(ruling))


def body_edits_done(ruling: str, body: str) -> bool:
    """Whether the body already shows every edit the ruling orders on it.

    Args:
        ruling: the ruling's text.
        body: the PR's body.

    Returns:
        True when each ``body replace`` has its new text in the body and each
        ``body delete`` has its old text gone (keyword: body-edits-done).
    """
    return all(
        (each.new in body) if each.new else (each.old not in body)
        for each in edits(ruling)
        if each.target == "body"
    )


def edits(ruling: str) -> Sequence[Edit]:
    # the edits a ruling orders, in the order written
    found: list[Edit] = []
    for number, each in enumerate(STEP.finditer(ruling), 1):
        target, operation, text = (
            each.group(1).lower(),
            each.group(2).lower(),
            each.group(3),
        )
        old, _, new = (
            text.partition(ARROW) if operation == "replace" else (text, "", "")
        )
        found.append(
            Edit(step=number, target=target, old=_unquoted(old), new=_unquoted(new))
        )
    return found


