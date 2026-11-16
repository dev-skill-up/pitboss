"""The edits a ruling orders on the ticket or the PR body (keyword: ruling-lint).

A leaf module: the flow reads it, and it imports nothing of the gates.
"""

import dataclasses
import re
from typing import MutableMapping, Sequence

STEP = re.compile(
    r"^[ \t]*(?:(?:\d+[.)]|[-*])[ \t]+)?(ticket|body)[ \t]+(delete|replace)[ \t]*:"
    r"[ \t]*(.+?)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
ARROW = " => "
GATE = "ruling step {step} ({edit}): {why}"


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
    return bool(_edits(ruling))


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
        for each in _edits(ruling)
        if each.target == "body"
    )


def _edits(ruling: str) -> Sequence[Edit]:
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


def applied(ruling: str, texts: MutableMapping[str, str]) -> Sequence[str]:
    """Apply each edit a ruling orders to its text, in the order written.

    Args:
        ruling: the ruling's text.
        texts: the ticket's and the body's text by target; each edit is made in it.

    Returns:
        A finding for each edit whose text is not there, naming the step.
    """
    lost: list[str] = []
    for each in _edits(ruling):
        if each.old not in texts[each.target]:
            why = f"the text is not in the {each.target}: {each.old[:60]}"
            lost.append(GATE.format(step=each.step, edit=each.shown, why=why))
        else:
            texts[each.target] = texts[each.target].replace(each.old, each.new, 1)
    return lost
