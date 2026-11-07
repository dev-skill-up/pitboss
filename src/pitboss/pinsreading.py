"""What the pins-check command said of a PR, and what the sweep does with it.

pitboss#34 (keyword: pins-only): the review of a relock or pins-only PR is no
agent review at all. When CI is green and the project's command prints ``OK``,
the sweep marks the PR ``PINS-ONLY OK`` and offers the merge; any other output
is offered for a review as before. ``pinsonly`` runs the command.
"""

import dataclasses
import enum
import re
from typing import Sequence

OK_LINE = re.compile(r"OK(?:[: ]|$)")


class Status(enum.Enum):
    """What the pins-check says about a PR.

    Attributes:
        NOT_PINS_ONLY: the PR is not pins-only, or no command is configured, or
            it is not at a review: nothing was asked.
        OK: the command printed ``OK``.
        NOT_OK: the PR is pins-only and the command did not print ``OK``, or
            could not be run.
    """

    NOT_PINS_ONLY = enum.auto()
    OK = enum.auto()
    NOT_OK = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Reading:
    """The answer for one PR.

    Attributes:
        status: what the command said.
        detail: the line of its output that says so, or why it could not run.
    """

    status: Status
    detail: str = ""


NOTHING = Reading(status=Status.NOT_PINS_ONLY)


def cleared(found: Reading) -> bool:
    """Whether the pins-check printed OK.

    Args:
        found: what the pins-check said.

    Returns:
        True for OK.
    """
    return found.status is Status.OK


def printed_lines(stdout: str) -> Sequence[str]:
    """The lines a command printed, without the blank ones.

    Args:
        stdout: its output.

    Returns:
        The stripped lines.
    """
    return [line.strip() for line in stdout.splitlines() if line.strip()]


def printed_ok(stdout: str) -> bool:
    """Whether the last line a command printed starts with ``OK``.

    Args:
        stdout: its output.

    Returns:
        True when the last non-blank line is ``OK`` or begins ``OK:`` or ``OK ``
        (``NOT OK: ...`` is not).
    """
    last = printed_lines(stdout)[-1:]
    return bool(last) and OK_LINE.match(last[0]) is not None


def read(stdout: str) -> Reading:
    """What a command that exited 0 said.

    Args:
        stdout: its output.

    Returns:
        OK when its last line says so, else NOT_OK; the detail is the last line.
    """
    status = Status.OK if printed_ok(stdout) else Status.NOT_OK
    return Reading(status=status, detail=(printed_lines(stdout) or ["no output"])[-1])
