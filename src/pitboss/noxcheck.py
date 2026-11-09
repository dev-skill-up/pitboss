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
# The tests session reports the missing lines and branches of these changed files
# when it runs some modules only (keyword: changed-coverage, pitboss#364).
COVER_PREFIX = "--cover="
# A lint failure names the command to repeat alone (pitboss#364): the one session
# that failed, once; a session that passed on the head is not run again.
LINT_RERUN = (
    "lint-rerun the lint command line that ran: `{command}`; after the fix repeat"
    " only that session with `nox -s lint -r` (allowed because lint failed first;"
    " a session that passed on this head is not run again)"
)
# The tests session ends with these lines (keyword: test-timing, pitboss#324):
# the total, then the slowest tests, each line starting with the prefix so that
# `rg test-timing` finds them in CI's log and `pitboss nox` can show them.
TIMING_PREFIX = "test-timing "
SLOWEST_COUNT = 30
# A passing tests run that left a name in its TMPDIR fails after the suite with a
# line for each name (keyword: test-leak, pitboss#346): the prefix, the test that
# left it (or OUTSIDE_TESTS) and the name.
LEAK_PREFIX = "test-leak "
OUTSIDE_TESTS = "(outside any test)"
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


WITHOUT_TESTS = (Session.SKILLS, Session.LINT, Session.MYPY)


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


def covers_of(judged: Sequence[str]) -> Sequence[str]:
    """The words that name the changed files whose coverage is reported.

    Args:
        judged: the changed files.

    Returns:
        A ``--cover=`` word for each; ``noxfile.py`` reads them.
    """
    return [f"{COVER_PREFIX}{each}" for each in judged]


def command_of(name: str, modules: Sequence[str]) -> Sequence[str]:
    """The command line of a session: always ``-r``.

    The tests session always gets ``-x`` (virtue stops after the first
    unsuccessful test), with the words it is given after it: the covers
    (``covers_of``, keyword: changed-coverage) and the test modules, when there
    are some.

    Args:
        name: the session.
        modules: the words for the tests session only.

    Returns:
        The command line.
    """
    wanted = ["--", STOP_AFTER, *modules] if name == Session.TESTS.value else []
    return ["nox", "-r", "-s", name, *wanted]


def run_sessions(
    runner: Runner,
    clock: Clock,
    modules: Sequence[str],
    sessions: Sequence[Session] = tuple(Session),
) -> Sequence[Step]:
    """Run the sessions in order, up to the first that fails.

    Args:
        runner: runs a command line.
        clock: reads the time.
        modules: the words the tests session runs with: its covers and test
            modules; all the tests when empty.
        sessions: the sessions to run, in order (all of them; without the tests
            session when the diff reaches no test, pitboss#331).

    Returns:
        The sessions that ran; a failed one is the last.
    """
    steps: list[Step] = []
    for each in sessions:
        name = each.value
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


def summary_of(ran: Sequence[Step]) -> Sequence[str]:
    """One line for each session, the ones that did not run included.

    Args:
        ran: the sessions that ran, in order; a failed one is the last.

    Returns:
        ``line_of`` for each session that ran and ``NAME not run`` for each
        that did not (after a failure, or the tests when the diff reaches none),
        in the order the sessions run.
    """
    done = {each.name: line_of(each) for each in ran}
    return [done.get(each.value, f"{each.value} not run") for each in Session]


def rerun_of(failed: Step) -> Sequence[str]:
    """The line that names the command to repeat after a lint failure.

    Args:
        failed: the session that failed.

    Returns:
        The line with the exact command line that ran; none unless it is lint.
    """
    if failed.name != Session.LINT.value:
        return []
    command = " ".join(command_of(failed.name, []))
    return [LINT_RERUN.format(command=command)]
