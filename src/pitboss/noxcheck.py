"""The local check of a worker: the nox sessions that stand for CI's (pitboss#210).

``pitboss nox`` runs the sessions of ``Session``, in that order (the rule that
states the order and the stop is the worker brief's ``Nox`` sentence,
``brieftextwork.NOX``), each with ``-r`` (reuse the environment). The other
sessions (docs, dry_release, the other Python versions) are CI's: its ``Run Nox``
step runs the whole suite. Running the sessions is a seam (keyword: nox-runner):
a test gives a runner and a clock, so no real nox runs.
"""

import dataclasses
import enum
from typing import Protocol, Sequence

from .expansion import Outcome

STOP_AFTER = "-x"
# The tests session ends with these lines (keyword: test-timing, pitboss#324):
# the total, then the slowest tests, each line starting with the prefix so that
# `rg test-timing` finds them in CI's log and `pitboss nox` can show them.
TIMING_PREFIX = "test-timing "
SLOWEST_COUNT = 30
PROOF = "CI's `Run Nox` step is the proof of the whole suite."


class Session(enum.Enum):
    """The sessions ``pitboss nox`` runs, in the order it runs them.

    Attributes:
        SKILLS: the skill and its references.
        LINT: black and stolid.
        MYPY: the type check.
        TESTS: the tests of one Python version, last (the longest).
    """

    SKILLS = "skills"
    LINT = "lint"
    MYPY = "mypy"
    TESTS = "tests-3.13"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Step:
    """A session that ran.

    Attributes:
        name: the session.
        outcome: what it gave back (its output has standard error joined to
            standard output).
        seconds: how long it took.
    """

    name: str
    outcome: Outcome
    seconds: float


class Runner(Protocol):
    """Runs a command line and gives back what it printed."""

    def __call__(self, command: Sequence[str], /) -> Outcome:
        """Run a command.

        Args:
            command: the command line.

        Returns:
            What it gave back.
        """


class Clock(Protocol):
    """Reads a clock that does not go back."""

    def __call__(self) -> float:
        """Read the clock.

        Returns:
            The seconds.
        """


def command_of(name: str, modules: Sequence[str]) -> Sequence[str]:
    """The command line of a session: always ``-r``.

    The tests session always gets ``-x`` (virtue stops after the first
    unsuccessful test), with the test modules after it when there are some.

    Args:
        name: the session.
        modules: the test modules, for the tests session only.

    Returns:
        The command line.
    """
    wanted = ["--", STOP_AFTER, *modules] if name == Session.TESTS.value else []
    return ["nox", "-r", "-s", name, *wanted]


def run_sessions(
    runner: Runner, clock: Clock, modules: Sequence[str]
) -> Sequence[Step]:
    """Run the sessions in order, up to the first that fails.

    Args:
        runner: runs a command line.
        clock: reads the time.
        modules: the test modules the tests session runs; all when empty.

    Returns:
        The sessions that ran; a failed one is the last.
    """
    steps: list[Step] = []
    for session in Session:
        name = session.value
        started = clock()
        outcome = runner(command_of(name, modules))
        steps.append(Step(name=name, outcome=outcome, seconds=clock() - started))
        if outcome.status:
            break
    return steps


def timing_of(step: Step) -> Sequence[str]:
    """The timing lines a session printed (the tests session's).

    Args:
        step: the session.

    Returns:
        Its lines that start with ``TIMING_PREFIX``; none for the others.
    """
    return [
        line
        for line in step.outcome.output.splitlines()
        if line.startswith(TIMING_PREFIX)
    ]


def line_of(step: Step) -> str:
    """The line that says how a session went.

    Args:
        step: the session.

    Returns:
        Its name, ``success`` or ``failed``, and its seconds.
    """
    shown = "failed" if step.outcome.status else "success"
    return f"{step.name} {shown} {step.seconds:.0f}s"
