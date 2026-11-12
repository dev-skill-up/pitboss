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


@dataclasses.dataclass(slots=True, kw_only=True)
class _Reading:
    form: Form
    exists: Exists
    found: list[str] = dataclasses.field(default_factory=list)
    seen: list[str] = dataclasses.field(default_factory=list)
    section: str = ""
    fence: bool = False


def _item(reading: _Reading, number: int, line: str) -> None:
    done = reading.form.done.fullmatch(line)
    if done and not (
        reading.form.url.fullmatch(done.group(2)) or reading.exists(done.group(2))
    ):
        reading.found.append(
            f"line {number}: the evidence of {done.group(1)} is neither a GitHub run,"
            " job, PR, commit or issue URL nor a file of the checkout"
        )
    match = done or next(
        (each.fullmatch(line) for each in reading.form.others if each.fullmatch(line)),
        None,
    )
    if match is None:
        reading.found.append(
            f"line {number}: not an item line of the form: {line[:50]!r}"
        )
    else:
        reading.seen.append(match.group(1))


def _line(reading: _Reading, number: int, line: str) -> None:
    if reading.fence:
        reading.fence = not line.startswith("```")
    elif line in ("## Items", "## Evidence"):
        if line == "## Items" and reading.section:
            reading.found.append(f"line {number}: a second or late `## Items`")
        reading.section = line[3:]
    elif not reading.section:
        reading.found.append(f"line {number}: text before `## Items`: {line[:50]!r}")
    elif reading.section == "Evidence":
        reading.fence = line.startswith("```")
        if not reading.fence:
            reading.found.append(
                f"line {number}: Evidence holds fenced blocks only: {line[:50]!r}"
            )
    else:
        _item(reading, number, line)


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
    reading = _Reading(form=form or Form(), exists=exists)
    for number, line in enumerate(text.splitlines(), 1):
        if line.strip():
            _line(reading, number, line)
    found = reading.found
    if reading.fence:
        found.append("an Evidence block is not closed")
    if not reading.section:
        found.append("no `## Items` section")
    found += [
        f"item {each} has {reading.seen.count(each)} lines, not one"
        for each in ids
        if reading.seen.count(each) != 1
    ]
    found += [
        f"item {each} is not one of the ticket's Done-when items"
        for each in reading.seen
        if each not in ids
    ]
    return found
