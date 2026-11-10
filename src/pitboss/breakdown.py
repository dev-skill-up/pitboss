"""The lines that end a command: the seconds and counts of each kind of work.

A command that waits for GitHub or git says, as its last lines on standard
error, where the time went before anything is fixed (keyword: timing-lines,
pitboss#443). The seconds of a kind are its commands' own, added up, so a kind
that ran at once adds up to more than the section took.
"""

import dataclasses
from typing import Sequence

from . import calllog

PREFIX = "pitboss timing: "
FAMILIES = (("GitHub API", "gh"), ("git", "git"))
OTHER = "other processes"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Section:
    """One section of a command, as the breakdown tells it.

    Attributes:
        name: its name.
        count: how many things it worked on (items ranked, briefs built), 0
            when it counts none.
        noun: what the count counts (``items``).
        phase: what it took and the commands it ran.
    """

    name: str
    count: int
    noun: str
    phase: calllog.Phase


def family_of(call: calllog.Call) -> str:
    """Say which kind of work a command is.

    Args:
        call: the command.

    Returns:
        ``GitHub API`` for ``gh``, ``git`` for ``git``, else ``other processes``.
    """
    program = call.name.split(" ", 1)[0]
    return next((word for word, each in FAMILIES if each == program), OTHER)


def work(calls: Sequence[calllog.Call]) -> str:
    """The count and the seconds waited of each kind of work.

    Args:
        calls: the commands that ran.

    Returns:
        For example ``GitHub API 3 calls 1.5s, git 0 calls 0.0s, other
        processes 1 calls 0.0s``.
    """
    names = [word for word, _ in FAMILIES] + [OTHER]
    parts = []
    for word in names:
        of_kind = [each for each in calls if family_of(each) == word]
        waited = sum(each.seconds for each in of_kind)
        parts.append(f"{word} {len(of_kind)} calls {waited:.1f}s")
    return ", ".join(parts)


def _section_line(each: Section) -> str:
    counted = f", {each.count} {each.noun}" if each.count else ""
    seconds = f"{each.phase.seconds:.1f}s"
    return f"{PREFIX}{each.name}: {seconds}{counted}; {work(each.phase.calls)}"


def lines(
    command: str, sections: Sequence[Section], total: float, startup: float | None
) -> Sequence[str]:
    """The lines of a command's breakdown.

    Args:
        command: the command, as typed.
        sections: its sections, in order.
        total: the seconds the command took.
        startup: the seconds from the start of the process (or of the ``uvx``
            that made it) to the start of the command, None when unknown.

    Returns:
        The command's total and its start-up, a line for each section and the
        totals of each kind of work.
    """
    boot = "unknown" if startup is None else f"{startup:.1f}s"
    calls = [call for each in sections for call in each.phase.calls]
    return [
        f"{PREFIX}{command}: {total:.1f}s in the command, startup before it {boot}",
        *(_section_line(each) for each in sections),
        f"{PREFIX}all: {work(calls)}",
    ]
