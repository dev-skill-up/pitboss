"""The local check of a worker: the nox sessions that stand for CI's (pitboss#210).

``pitboss nox`` runs the tests of one Python version first (until the tests run
there is no reason to lint the code), then the ``skills`` session, ``lint`` and
``mypy``, each with ``-r`` (reuse the environment), and stops at
the first that fails. The other sessions (docs, dry_release, the other Python
versions) are CI's: its ``Run Nox`` step runs the whole suite. Running the sessions
is a seam (keyword: nox-runner): a test gives a runner and a clock, so no real nox
runs.
"""

import dataclasses
import enum
from typing import Protocol, Sequence

from .expansion import Outcome

PROOF = "CI's `Run Nox` step is the proof of the whole suite."


class Session(enum.Enum):
    """The sessions ``pitboss nox`` runs, in the order it runs them.

    Attributes:
        TESTS: the tests of one Python version.
        SKILLS: the skill and its references.
        LINT: black and stolid.
        MYPY: the type check.
    """

    TESTS = "tests-3.13"
    SKILLS = "skills"
    LINT = "lint"
    MYPY = "mypy"


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

    Args:
        name: the session.
        modules: the test modules, for the tests session only.

    Returns:
        The command line.
    """
    wanted = ["--", *modules] if modules and name == Session.TESTS.value else []
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


def line_of(step: Step) -> str:
    """The line that says how a session went.

    Args:
        step: the session.

    Returns:
        Its name, ``success`` or ``failed``, and its seconds.
    """
    shown = "failed" if step.outcome.status else "success"
    return f"{step.name} {shown} {step.seconds:.0f}s"
