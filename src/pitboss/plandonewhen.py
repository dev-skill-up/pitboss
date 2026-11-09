"""The Plan's Done-when is the ticket body's, word for word (keyword: plan-done-when).

Seen on pitboss#378 (pitboss#317): an "Interpretation" paragraph in the Execution
narrowed Done-when items 5 to 7, and a review found it a round later. Rejections
of 2026-11-08 (pitboss#396): "Done-when not met as written" was 23 of 94
findings. ``pitboss plan-check`` reads the ticket's body, never its comments
(owner, 2026-11-08T23:06Z), and refuses a Plan that does not hold each bullet of
the Done-when, word for word, in a numbered Plan row of its own, naming the first
that does not (``plan-done-when``). Where a bullet names its measurement as
``measured by `COMMAND``` (``VERBS`` with ``PREPOSITIONS``), that command must be
a backticked span of the bullet's row outside the copy, never a substitute
(``plan-measurement``). It refuses a body with no ``Done-when digest:`` line, or
whose line is not the ticket's digest now: the Done-when was edited after a
worker started (``done-when-edited``). It also refuses a body whose Plan or
Execution has an "Interpretation" or "interpreted" paragraph about a Done-when
item (``plan-interpretation``): meet the Done-when as written, or prove it
impossible. The module reads nothing: the texts are given.
"""

import re
from typing import AbstractSet, Sequence

from . import bodytext, planrowtext, ticketwhen

CHECK = "plan-done-when"
MEASUREMENT = "plan-measurement"
EDITED = "done-when-edited"
INTERPRETATION = "plan-interpretation"
DIGEST_PREFIX = "Done-when digest: "
SHOWN = 100
RULE = "meet the Done-when as written, or prove it impossible"
VERBS = ("measured", "counted", "checked", "shown", "printed", "reported", "found")
PREPOSITIONS = ("by", "with", "using")
MEASURED = re.compile(
    r"\b(?:" + "|".join(VERBS) + r")\s+(?:" + "|".join(PREPOSITIONS) + r")\s+"
    r"`([^`\n]+)`",
    re.IGNORECASE,
)
DIGEST_LINE = re.compile(
    r"^" + re.escape(DIGEST_PREFIX) + r"([0-9a-f]{16})[ \t]*$", re.MULTILINE
)
UNMET = "{check}: the ticket's Done-when item {why}; the first one is: {item}; {rule}"
UNMEASURED = (
    "{check}: the Done-when item names the measurement `{each}` and its Plan row"
    " does not run it (the item: {item}); the Plan uses the measurement the"
    " Done-when names, never a substitute"
)
NO_LINE = (
    "{check}: the body has no `{prefix}{now}` line: the digest of the ticket's"
    " Done-when, as the brief printed it when the worker started, is the record"
    " that it was not edited after"
)
CHANGED = (
    "{check}: the ticket's Done-when was edited after a worker started (the body"
    " records {recorded}, the ticket's is now {now}); the Done-when is the body's"
    " at the start, and it is edited only before a worker starts"
)
INTERPRET = re.compile(r"\binterpret(?:ation|ations|ed|ing|s)?\b", re.IGNORECASE)
ABOUT = re.compile(r"\bdone[- ]when\b|\bitems?\s+\d", re.IGNORECASE)


def _squeezed(text: str) -> str:
    return " ".join(text.split())


def measurements(item: str) -> Sequence[str]:
    """The commands a Done-when item names as its measurement.

    Args:
        item: one item of a ticket's Done-when.

    Returns:
        The backticked command after each ``measured by``, ``counted with``,
        ``found using`` or the like, in order.
    """
    return [_squeezed(each) for each in MEASURED.findall(item)]


def _runs(command: str, remainder: str) -> bool:
    # the row's own backticked spans: the command itself, or piped into more
    return any(
        span == command or span.startswith(command + " |")
        for span in (_squeezed(each) for each in planrowtext.spans(remainder))
    )


def _why(item: str, section: str, rows: Sequence[str]) -> str:
    # why an item is in no free numbered row
    if any(item in row for row in rows):
        return "shares its numbered Plan row with another item"
    if item in _squeezed(section):
        return "is not in a numbered Plan row (`1. ...`)"
    return "is not in the Plan word for word"


def findings(section: str, ticket: str) -> Sequence[str]:
    """What the Plan lacks of the ticket's Done-when.

    Args:
        section: the Plan section.
        ticket: the ticket's text; its comments are never read.

    Returns:
        One finding naming the first item that is not in a numbered Plan row of
        its own, word for word (whitespace and line breaks aside); when every
        item is, one finding for each measurement a row does not run; none when
        the Plan holds them all.
    """
    rows = [_squeezed(each) for each in planrowtext.rows(section).values()]
    used: set[int] = set()
    paired: list[tuple[str, str]] = []
    for item in ticketwhen.items(ticket):
        at = _free(item, rows, used)
        if at is None:
            why = _why(item, section, rows)
            return [UNMET.format(check=CHECK, why=why, item=item[:SHOWN], rule=RULE)]
        used.add(at)
        paired.append((item, rows[at].replace(item, " ", 1)))
    return _unmeasured(paired)


def _free(item: str, rows: Sequence[str], used: AbstractSet[int]) -> int | None:
    # the first numbered row that holds the item and is no other item's
    free = [at for at, row in enumerate(rows) if item in row and at not in used]
    return free[0] if free else None


def _unmeasured(paired: Sequence[tuple[str, str]]) -> Sequence[str]:
    # the measurements an item names that its row (less the copy) does not run
    return [
        UNMEASURED.format(check=MEASUREMENT, each=each, item=item[:SHOWN])
        for item, remainder in paired
        for each in measurements(item)
        if not _runs(each, remainder)
    ]


def edited(body: str, ticket: str) -> Sequence[str]:
    """The finding for a Done-when edited after a worker started.

    Args:
        body: the PR's body, which keeps the ``Done-when digest:`` line the brief
            printed when the worker started.
        ticket: the ticket's text now.

    Returns:
        One finding when the ticket has a Done-when and the body's last digest
        line is missing or is not the ticket's digest now; none otherwise.
    """
    now = ticketwhen.digest(ticket)
    recorded = DIGEST_LINE.findall(body)[-1:]
    if not now or recorded == [now]:
        return []
    if not recorded:
        return [NO_LINE.format(check=EDITED, prefix=DIGEST_PREFIX, now=now)]
    return [CHANGED.format(check=EDITED, recorded=recorded[0], now=now)]


def interpretations(body: str) -> Sequence[str]:
    """The paragraphs of the Plan and the Execution that interpret a Done-when item.

    Args:
        body: the PR's body.

    Returns:
        A finding for each paragraph (outside a fenced block) that has the word
        "interpretation", "interpreted" or the like and names a Done-when or an
        item number.
    """
    return [
        f"{INTERPRETATION}: a paragraph interprets a Done-when item"
        f" ({_squeezed(each)[:SHOWN]}): {RULE}"
        for each in bodytext.paragraphs(body)
        if INTERPRET.search(each) and ABOUT.search(each)
    ]
