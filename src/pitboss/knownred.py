"""A step that spends runner time waits for a red that is known without it.

(keyword: known-red, quire#1120.) ``slots next`` offered to undraft quire#1120 although
its ``text-lint`` status was red (a missing run of the fixture repository): CI would
have run on a head that cannot pass. The plan and the audit of pitboss#444 asked of each
step whether the *hold* covers it (``actiongates.tsv``), never whether a cheap check
that is already known on the head says the spend is wasted. ``knownred.tsv`` lists those
checks; ``actiongates.tsv`` lists what spends (any row that is not ``free``). A spending
step that is not itself a push of a fix is *withheld* while a known red stands: the
sweep, ``slots next`` and ``pitboss act`` print one ``FIX FIRST`` line that names the
red and the step that fixes it, in place of the spending step.
"""

import dataclasses
from typing import Mapping, Protocol, Sequence

from . import (
    actiongates,
    actions,
    config,
    headchecks,
    phrases,
    pullref,
    shapes,
    steps,
    straycomments,
)
from .markers import Marker

FIELDS = 3
STATUS = "status:"
STEPS = "step:"
# the spending rows that are the fix itself: a worker's push
FIXES = ("Action.PUSH", "Step.WORKER")
FAILED = ("failure", "error")


class Headed(Protocol):
    """What the reds are read from (``pulls.PullFacts`` has it)."""

    @property
    def repo(self) -> config.Repo:
        """Return its repository."""

    @property
    def pull(self) -> shapes.Pull:
        """Return the PR."""

    @property
    def checks(self) -> Sequence[shapes.CheckRun]:
        """Return the check runs of its head."""

    @property
    def signals(self) -> headchecks.HeadSignals:
        """Return what may block it besides its checks."""

    @property
    def step(self) -> steps.Next:
        """Return the one step the PR is at."""

    @property
    def unreadable(self) -> straycomments.StrayComments:
        """Return its comments that try to be reviews and are not."""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Row:
    """One known-red check.

    Attributes:
        name: its id.
        source: where it is read from.
        fix: the step that clears it.
    """

    name: str
    source: str
    fix: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Red:
    """A known red on a head.

    Attributes:
        name: the check's id.
        why: what it says.
        fix: the step that clears it.
    """

    name: str
    why: str
    fix: str


def rows() -> Sequence[Row]:
    """The rows of ``knownred.tsv``.

    Returns:
        The known-red checks.
    """
    found = []
    for line in phrases.shipped_text("knownred.tsv").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != FIELDS:
            raise ValueError(f"knownred.tsv: {fields[0]} has {len(fields)} fields")
        found.append(Row(name=fields[0], source=fields[1], fix=fields[2]))
    return found


def spending() -> Mapping[str, str]:
    """What spends runner time, from the gate table, and what happens to each.

    Returns:
        By id, ``fix`` for a worker's push (it is the step that clears a red) and
        ``withheld`` for every other row whose gate is not ``free``.
    """
    table = actiongates.parse(phrases.shipped_text("actiongates.tsv"))
    return {
        name: "fix" if name in FIXES or name.startswith("Task.") else "withheld"
        for name, (gate, _where, _test) in table.items()
        if gate != "free"
    }


def _status(pull: Headed, context: str) -> str:
    for each in pull.signals.statuses:
        if each.context == context and each.state in FAILED:
            return each.description or each.state
    for check in pullref.failed_checks(pull):
        if check.name == context:
            return "a failed check"
    return ""


def _read(pull: Headed, row: Row) -> str:
    # what the row says of the head, empty when it is not red
    if row.source.startswith(STATUS):
        return _status(pull, row.source.removeprefix(STATUS))
    if row.source.startswith(STEPS):
        wanted = row.source.removeprefix(STEPS).split("+")
        return "no clean Plan check" if pull.step.step.name in wanted else ""
    if row.source == "unreadable":
        return (
            "a comment that tries to be a review is not in the form"
            if (pull.unreadable.newer or pull.unreadable.graded)
            else ""
        )
    if row.source == "pins":
        return pull.signals.pins.detail or "not OK" if _pins_red(pull) else ""
    return ""


def _pins_red(pull: Headed) -> bool:
    return pull.signals.pins.status.name == "NOT_OK"


def reds(pull: Headed) -> Sequence[Red]:
    """The known reds of a head.

    Args:
        pull: the PR.

    Returns:
        One entry for each row that is red on it.
    """
    found = []
    for row in rows():
        said = _read(pull, row)
        if said:
            found.append(Red(name=row.name, why=said, fix=row.fix))
    return found


def say(pull: Headed, withheld: str) -> str:
    """What a known red withholds, in words.

    Args:
        pull: the PR.
        withheld: what is not done now.

    Returns:
        The reds, the steps that clear them and what waits.
    """
    named = "; ".join(
        f"{each.name} is red ({each.why}): {each.fix}" for each in reds(pull)
    )
    return f"{named}; {withheld} waits (it would run CI on a head that cannot pass)"


def line(pull: Headed, withheld: str) -> str:
    """The FIX FIRST line.

    Args:
        pull: the PR.
        withheld: what is not done now.

    Returns:
        The line.
    """
    return f"{Marker.FIX_FIRST.text} {pullref.reference(pull)}: {say(pull, withheld)}"


def refusal(pull: Headed, action: actions.Action) -> str:
    """Why ``pitboss act`` refuses an action while a known red stands.

    Args:
        pull: the PR.
        action: the action.

    Returns:
        The FIX FIRST line, empty when the action is a push or nothing is red.
    """
    if spending().get(f"Action.{action.name}") != "withheld" or not reds(pull):
        return ""
    return line(pull, actions.word(action))


SPENT = {
    steps.Step.UNDRAFT: "the undraft",
    steps.Step.RUN_E2E: "the e2e dispatch",
    steps.Step.MERGE: "the merge",
}


def _spends(line: str, prefixes: Sequence[str]) -> bool:
    # a relock's re-dispatch is a workflow dispatch, whatever line carries it
    return line.startswith(tuple(prefixes)) or "re-dispatch" in line


def gate(pull: Headed, lines: Sequence[str], prefixes: Sequence[str]) -> Sequence[str]:
    """The lines of a PR with the spending ones replaced while a known red stands.

    Args:
        pull: the PR.
        lines: the lines it calls for.
        prefixes: the starts of the lines that ask for a spending action.

    Returns:
        The lines that spend nothing, then one ``FIX FIRST`` line; the lines
        unchanged when nothing is red or nothing spends.
    """
    spent = [each for each in lines if _spends(each, prefixes)]
    if not spent or not reds(pull):
        return lines
    kept = [each for each in lines if each not in spent]
    return [*kept, line(pull, "; ".join(each.split(":")[0] for each in spent))]
