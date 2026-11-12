"""The hand-back form: one line for each Done-when item, nothing else (pitboss#444).

The keyword is handback-form. Work is done or not done, never "done except"
(2026-10-28); a hand-back finishes an item or shows it is impossible
(2026-11-10); an open item is never the conclusion (2026-11-12). A hand-back is
``## Items``, then exactly one line for each item::

    - [ID] done | evidence: <a GitHub run, job, PR, commit or issue URL, or a path>
    - [ID] impossible | command: `<the command>` | output: <what it printed>
    - [ID] owner | request: <a step only the owner can take> | recommended: <the
      answer> | until then: <what proceeds>

then, optionally, ``## Evidence`` with fenced blocks only. A sentence that
qualifies an item has no place to stand, so it refuses the hand-back.
"""

import dataclasses
import pathlib
import re
from typing import Callable, Sequence

DONE = re.compile(r"- \[([\w.-]+)\] done \| evidence: (\S+)")
IMPOSSIBLE = re.compile(
    r"- \[([\w.-]+)\] impossible \| command: `[^`]+` \| output: \S.*"
)
OWNER = re.compile(
    r"- \[([\w.-]+)\] owner \| request: \S[^|]* \| recommended: \S[^|]* \| until then:"
    r" \S[^|]*"
)
URL = re.compile(
    r"https://github\.com/[\w.-]+/[\w.-]+/(actions/runs/\d+(/job/\d+)?|pull/\d+(#\S+)?"
    r"|commit/[0-9a-f]{40}|issues/\d+(#\S+)?)"
)
Exists = Callable[[str], bool]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Form:
    """The rules of the form (each can be given, so a test can take one out).

    Attributes:
        done: a ``done`` line.
        url: a pointer that is a GitHub URL.
        others: the ``impossible`` and ``owner`` lines.
    """

    done: re.Pattern[str] = DONE
    url: re.Pattern[str] = URL
    others: Sequence[re.Pattern[str]] = (IMPOSSIBLE, OWNER)


def in_checkout(root: pathlib.Path | None) -> Exists:
    """Whether a pointer is a file of a checkout.

    Args:
        root: the checkout, or None when there is none.

    Returns:
        The test of a pointer: a relative path that exists under the root.
    """
    return (
        lambda pointer: root is not None
        and not pointer.startswith(("/", "~", ".."))
        and (root / pointer).exists()
    )


HEADINGS = ("## Items", "## Evidence")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Place:
    """Where a line of a hand-back stands.

    Attributes:
        section: the section it is in (``Items`` or ``Evidence``), empty before
            the first.
        fence: whether it is inside a fenced block of the Evidence.
    """

    section: str = ""
    fence: bool = False


def _evidence(place: Place, number: int, line: str) -> tuple[Place, Sequence[str]]:
    fence = line.startswith("```")
    said = (
        []
        if fence
        else [f"line {number}: Evidence holds fenced blocks only: {line[:50]!r}"]
    )
    return dataclasses.replace(place, fence=fence), said


def _heading(place: Place, number: int, line: str) -> tuple[Place, Sequence[str]]:
    late = line == HEADINGS[0] and place.section
    said = [f"line {number}: a second or late `## Items`"] if late else []
    return dataclasses.replace(place, section=line[3:]), said


def step(place: Place, number: int, line: str) -> tuple[Place, Sequence[str], bool]:
    """Read one line that is not blank.

    Args:
        place: where the line before left the reading.
        number: the line's number.
        line: the line.

    Returns:
        Where the reading is after it, what is wrong with it, and whether it is
        a line of the Items to read as an item.
    """
    if place.fence:
        return dataclasses.replace(place, fence=not line.startswith("```")), [], False
    if line in HEADINGS:
        return (*_heading(place, number, line), False)
    if not place.section:
        return place, [f"line {number}: text before `## Items`: {line[:50]!r}"], False
    if place.section == "Evidence":
        return (*_evidence(place, number, line), False)
    return place, [], True


def _item(
    form: Form, exists: Exists, number: int, line: str
) -> tuple[Sequence[str], str]:
    # what is wrong with an item line, and the item it names ("" for none)
    done = form.done.fullmatch(line)
    pointed = done and (form.url.fullmatch(done.group(2)) or exists(done.group(2)))
    said = (
        [
            f"line {number}: the evidence of {done.group(1)} is neither a GitHub run,"
            " job, PR, commit or issue URL nor a file of the checkout"
        ]
        if done and not pointed
        else []
    )
    match = done or next(
        (each.fullmatch(line) for each in form.others if each.fullmatch(line)), None
    )
    if match is None:
        return [
            *said,
            f"line {number}: not an item line of the form: {line[:50]!r}",
        ], ""
    return said, match.group(1)


def _read(
    text: str, form: Form, exists: Exists
) -> tuple[Place, Sequence[str], Sequence[str]]:
    # where the reading ends, what is wrong and the items named, in order
    place, found, seen = Place(), [], []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        place, said, is_item = step(place, number, line)
        found += said
        if is_item:
            wrong, named = _item(form, exists, number, line)
            found += wrong
            seen += [named] if named else []
    return place, found, seen


def findings(
    text: str, ids: Sequence[str], exists: Exists, form: Form | None = None
) -> Sequence[str]:
    """What is wrong with a hand-back.

    Args:
        text: the hand-back.
        ids: the ticket's Done-when item ids.
        exists: whether a pointer is a file of the checkout.
        form: the rules (the shipped ones when none).

    Returns:
        A line for each fault; none when it is in the form.
    """
    place, read, seen = _read(text, form or Form(), exists)
    found = list(read)
    if place.fence:
        found.append("an Evidence block is not closed")
    if not place.section:
        found.append("no `## Items` section")
    return [*found, *_counted(ids, seen)]


def _counted(ids: Sequence[str], seen: Sequence[str]) -> Sequence[str]:
    # each item has one line, and each line is of an item of the ticket
    found = [
        f"item {each} has {seen.count(each)} lines, not one"
        for each in ids
        if seen.count(each) != 1
    ]
    return found + [
        f"item {each} is not one of the ticket's Done-when items"
        for each in seen
        if each not in ids
    ]
