"""A Plan row that runs nox is refused (keyword: plan-nox, pitboss#251)."""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, empty, equal_to, has_length

from .. import brief, forms, noxrow, plancheck, plancommands
from .briefmake import pinned

SENTENCE = (
    "Nox rows: a Plan row never runs `nox`, `pitboss nox` or `uvx ... nox`; give"
    " the CI pointer instead: the workflow, the run of the head, the job, the step"
    " `Run Nox` and a greppable test name (pitboss#251)."
)
NOX_ROWS = (
    "timeout 598 nox -r -s tests-3.13 -- x",
    "timeout 598 uvx --from . pitboss nox",
    "pitboss nox",
    "nox",
    "uvx nox -s lint",
    "python -m nox -s mypy",
    "cd x && nox -r",
    "FOO=1 .venv/bin/nox",
    "uvx --python 3.13 nox -s tests-3.13",
    "uvx --with foo nox",
    "uvx nox@latest",
    "uv run --python 3.13 nox",
    "env FOO=1 nox",
    "time nox",
)
OTHER_ROWS = (
    "git rev-parse HEAD",
    "git grep nox",
    "cat noxfile.py",
    "echo nox",
    "timeout 598",
)
PLAN_WITH_NOX = (
    "## Plan\nRun the tests.\n\n$ timeout 598 nox -r -s tests-3.13\n$ git status\n\n"
    "## Execution\nx\n"
)
PLAN_WITH_POINTER = (
    "## Plan\nCI's `Run Nox` step of `pr-main.yml` prints the test name"
    " `test_nox_row`.\n\n$ git status\n$ git rev-parse HEAD\n\n## Execution\nx\n"
)


def ran_nothing(command: str) -> plancheck.Run:
    """A runner that exits 0.

    Args:
        command: the command.

    Returns:
        The run.
    """
    return plancheck.finished(0, 0.0)


def refused(section: str) -> Sequence[int]:
    """The rows plan-check refuses.

    Args:
        section: the Plan.

    Returns:
        The numbers of the rows that did not run.
    """
    return plancheck.report(section, ran_nothing)[1]


class TestNoxRow(unittest.TestCase):
    """The refusal in plan-check and lint pr-body, and the sentence of the briefs."""

    def test_a_nox_command_is_recognised(self) -> None:
        """Each spelling of a nox run."""
        for each in NOX_ROWS:
            assert_that(noxrow.runs_nox(each), equal_to(True), each)

    def test_other_commands_are_not(self) -> None:
        """A word that contains or mentions nox is no run of it."""
        for each in OTHER_ROWS:
            assert_that(noxrow.runs_nox(each), equal_to(False), each)

    def test_plan_check_accepts_the_ci_pointer_and_git_rows(self) -> None:
        """The same Plan with the pointer passes."""
        assert_that(refused(PLAN_WITH_POINTER), empty())

    def test_the_form_check_carries_it(self) -> None:
        """pr_body reports the nox row."""
        subject = forms.Subject(name="body", body=PLAN_WITH_NOX, head="")
        found = [each for each in forms.pr_body(subject) if "plan-nox" in each]
        assert_that(found, has_length(1))
