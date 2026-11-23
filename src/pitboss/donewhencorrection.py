"""A started ticket's Done-when rows corrected, every other row as it was (pitboss#488).

The owner's standing approval (project instructions): a Done-when row the agent
wrote and no ruling backs is corrected even after a worker started, the other rows
kept verbatim. ``findings`` is that check on two ticket bodies: the corrected rows
are named (counted from 1), and nothing outside them changed. ``record`` is the
comment that keeps the old and the new text on the ticket. The bodies are given;
this module reads no ticket.
"""

from typing import Sequence

from . import ticketwhen


def _named(corrects: str) -> Sequence[int]:
    return [int(each) for each in corrects.split(",") if each.strip().isdigit()]


def _row_lines(body: str) -> Sequence[int]:
    # the lines of the body the Done-when section holds
    found = list(ticketwhen.SECTION.finditer(body))[:1]
    return [
        number
        for each in found
        for number in range(
            body.count("\n", 0, each.start(2)),
            body.count("\n", 0, each.end(2)) + 1,
        )
    ]


def _of_a_row(line: str, rows: Sequence[str]) -> bool:
    # whether a changed line is a part of a corrected row's text
    marked = ticketwhen.BULLET.match(line)
    words = (marked[3] if marked else line).strip()
    return any(words in each for each in rows)


def _outside(old: str, new: str, rows: Sequence[str]) -> Sequence[str]:
    # every line that is no part of a corrected row is as it was
    before = old.split("\n")
    after = new.split("\n")
    if before[len(after) :] or after[len(before) :]:
        return ["the body's line count changed: a row is corrected in place"]
    inside = _row_lines(old)
    moved = [
        number + 1
        for number, (was, now) in enumerate(zip(before, after))
        if was != now and not (number in inside and _of_a_row(now, rows))
    ]
    return [
        f"line {each} is no part of a corrected row, it changed" for each in moved[:1]
    ]


def _rows(old: str, new: str, named: Sequence[int]) -> Sequence[str]:
    # what is wrong with the rows the edit names, and with the rows it leaves
    before, after = ticketwhen.items(old), ticketwhen.items(new)
    if absent := [each for each in named if not 1 <= each <= len(before)]:
        return [f"the ticket has {len(before)} Done-when rows, not row {absent[0]}"]
    if len(after) != len(before):
        return [
            f"the ticket has {len(before)} Done-when rows, the body has {len(after)}"
        ]
    kept = [
        number
        for number, pair in enumerate(zip(before, after), 1)
        if number not in named and pair[0] != pair[1]
    ]
    return [f"row {each} is not named in corrects, it changed" for each in kept[:1]]


def findings(old: str, new: str, corrects: str) -> Sequence[str]:
    """What stops a correction of the rows named from being made.

    Args:
        old: the ticket's body now.
        new: the body it is to have.
        corrects: the rows corrected, counted from 1 and separated by commas.

    Returns:
        Each reason the correction is refused; none when it is allowed.
    """
    named = _named(corrects)
    if len(named) != len(corrects.split(",")):
        return ["corrects names the Done-when rows corrected, as 1,3"]
    found = _rows(old, new, named)
    after = ticketwhen.items(new)
    return found or _outside(old, new, [after[each - 1] for each in named])


def record(old: str, new: str, corrects: str) -> str:
    """The comment that keeps what each corrected row was and is.

    Args:
        old: the ticket's body before.
        new: the body after.
        corrects: the rows corrected, counted from 1 and separated by commas.

    Returns:
        The comment's text.
    """
    before = ticketwhen.items(old)
    after = ticketwhen.items(new)
    rows = [
        f"Row {each}:\n- was: {before[each - 1]}\n- now: {after[each - 1]}"
        for each in _named(corrects)
    ]
    return f"Done-when correction (corrects={corrects})\n\n" + "\n\n".join(rows)
