"""GitHub as a dictionary of what it holds, for the read-back tests (landed)."""

import dataclasses
import json
import subprocess
from typing import Mapping, NoReturn, MutableMapping, MutableSequence, Sequence

from ..retrying import Read

NOT_FOUND = "gh: Not Found (HTTP 404)"
BAD_GATEWAY = "gh: Bad Gateway (HTTP 502)"
TIMEOUT = "gh: Gateway Timeout (HTTP 504)"
GONE = "(not there)"
LAGGING = "(its reading fails)"


def fail(status: str) -> NoReturn:
    """What ``gh api`` does when it fails.

    Args:
        status: the line it printed.

    Returns:
        Nothing: it raises.

    Raises:
        subprocess.CalledProcessError: always.
    """
    raise subprocess.CalledProcessError(1, ["gh"], output="", stderr=status)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Hub:
    """What GitHub holds at each path, changed by the writes made.

    Attributes:
        state: the JSON each path holds (a path not held is a 404; ``LAGGING`` is a
            path whose reading fails with a 502).
        after: what each write changes it to (``GONE`` removes the path).
        lands: whether a write that returns changes GitHub.
        fails: the statuses the first writes raise with, first first.
        kept: whether a write that raises changes GitHub (a 5xx after it landed).
        writes: every write made, in order.
    """

    state: MutableMapping[str, object]
    after: Mapping[str, object]
    lands: bool = True
    fails: Sequence[str] = ()
    kept: bool = False
    writes: MutableSequence[Sequence[str]] = dataclasses.field(default_factory=list)

    def run(self, cmdargs: Sequence[str], /) -> Read:
        """A read.

        Args:
            cmdargs: the ``gh api`` line.

        Returns:
            The path's JSON.

        """
        path = cmdargs[-1] if cmdargs[2] != "graphql" else "graphql"
        held = self.state.get(path, GONE)
        if held == LAGGING:
            fail(BAD_GATEWAY)
        if held == GONE:
            fail(NOT_FOUND)
        return Read(stdout=json.dumps(held))

    def mutate(self, cmdargs: Sequence[str], /) -> Read:
        """A write: it raises as told, and changes GitHub or does not.

        Args:
            cmdargs: the line.

        Returns:
            What it printed.

        """
        turn = len(self.writes)
        self.writes.append(list(cmdargs))
        failing = turn < len(self.fails)
        if self.lands and (self.kept or not failing):
            apply(self.state, self.after)
        if failing:
            fail(self.fails[turn])
        return Read(stdout="7")


def apply(state: MutableMapping[str, object], after: Mapping[str, object]) -> None:
    """Change what GitHub holds as a write says.

    Args:
        state: what each path holds.
        after: what each path holds once the write landed.
    """
    for path, value in after.items():
        if value == GONE:
            state.pop(path, None)
        else:
            state[path] = value
