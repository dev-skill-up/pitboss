"""A ruling's word and its steps are one value (keyword: ruling-typed, #517).

quire#1125: a ruling that said ``revise the plan`` carried code steps, so the round
it sent (a worker that changes the Plan only) could never do them, and a hand-back
that left them undone counted as the ruling used. Two rules close the class:

* ``refusal``: at ``ruling post`` a ``revise the plan`` ruling holds only edit steps
  (``ticket delete``, ``body replace``, ...) of the form ``rulinglint`` reads; a step
  of any other kind needs ``do these steps``.
* ``carried``: a ruling is applied only by a hand-back whose PR body carries the
  ruling's typed body edits, not by any hand-back after it.
"""

import re
from typing import Sequence


def _line(source: str) -> re.Pattern[str]:
    return re.compile(source, re.IGNORECASE)


HEADING = _line(r"^[ \t]*(?:#+[ \t]*)?\**steps\b[^\n]{0,40}$")
NEXT_SECTION = _line(r"^[ \t]*(?:#+[ \t]|\*\*|how[ \t]+we[ \t]+got[ \t]+here)")
ITEM = re.compile(r"^(?:\d+[.)]|[-*])[ \t]+(.+?)[ \t]*$")
NOT_AN_EDIT = (
    "a `revise the plan` ruling orders only edits of the ticket or the body, each"
    " as `ticket|body delete|replace: text`; step {number} is not one: {text!r}"
    " (a step that changes code needs `do these steps`)"
)


STEP = re.compile(
    r"^[ \t]*(?:(?:\d+[.)]|[-*])[ \t]+)?(ticket|body)[ \t]+(delete|replace)[ \t]*:"
    r"[ \t]*(.+?)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
ARROW = " => "


def unquoted(text: str) -> str:
    """The text without its quotes.

    Args:
        text: the text.

    Returns:
        It, stripped, without a backtick or a quote at either end.
    """
    return text.strip().strip("`\"'").strip()


def parts(ruling: str) -> Sequence[tuple[str, str, str]]:
    """The edits a ruling orders, in the order written.

    Args:
        ruling: the ruling's text.

    Returns:
        ``(target, old, new)`` for each: the target is ``ticket`` or ``body``, old
        the text to find, new what takes its place (empty for a deletion).
    """
    found = []
    for each in STEP.finditer(ruling):
        target, operation, text = each.group(1).lower(), each.group(2), each.group(3)
        old, _, new = (
            text.partition(ARROW) if operation.lower() == "replace" else (text, "", "")
        )
        found.append((target, unquoted(old), unquoted(new)))
    return found


def steps_of(text: str) -> Sequence[str]:
    """The steps a ruling lists.

    Args:
        text: the ruling.

    Returns:
        The text of each numbered or bulleted line under its ``Steps`` heading,
        up to the next heading or the ``How we got here`` section.
    """
    found: list[str] = []
    inside = False
    for line in text.splitlines():
        if HEADING.match(line):
            inside = True
        elif inside and NEXT_SECTION.match(line):
            inside = False
        elif inside and (item := ITEM.match(line)):
            found.append(item.group(1))
    return found


def refusal(text: str) -> str:
    """Say why the steps of a ``revise the plan`` ruling are not all edits.

    Args:
        text: the ruling, whose word is ``revise the plan``.

    Returns:
        The reason when a step is not an edit; empty otherwise.
    """
    for number, each in enumerate(steps_of(text), 1):
        if not parts(each):
            return NOT_AN_EDIT.format(number=number, text=each[:60])
    return ""


def carried(text: str, body: str) -> bool:
    """Whether a PR body carries the body edits a ruling orders.

    Args:
        text: the ruling.
        body: the PR's body.

    Returns:
        True when each ``body`` edit shows: its new text is in the body, and a
        deletion's text is not. A ruling with no body edit is carried by any body.
    """
    edits = parts("\n".join(steps_of(text)))  # the steps only, not the analysis
    return all(
        (new in body) and (old in new or old not in body) if new else (old not in body)
        for target, old, new in edits
        if target == "body"
    )


def edits_body(text: str) -> bool:
    """Whether a ruling orders an edit of the PR body.

    Args:
        text: the ruling.

    Returns:
        True when one of its steps is a ``body`` edit, which the body alone shows
        was done (no push is needed to see it).
    """
    return any(target == "body" for target, _, _ in parts("\n".join(steps_of(text))))
