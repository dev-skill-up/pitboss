"""What ``pitboss next TICKET`` prints for the Plan (keyword: next-guide)."""

import pathlib
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import nextguide, steptexts, ticketwhen
from . import world

TICKET = "owner/project#99"
ISSUE = f"{world.PROJECT}/issues/99"
FIRST = f"WORKER: {TICKET}: {steptexts.FIRST_STEP}\n"
WORKFLOW = """\
name: check
on: push
jobs:
  plan:
    runs-on: ubuntu-24.04
    steps:
      - name: Run Nox
        run: true
  fixtures:
    name: fixtures (shard ${{ matrix.shard }})
    strategy:
      matrix:
        shard: [1, 2]
    steps:
      - run: true
"""
STAR = (
    "Intro.\n\n## Done-when\n\n* The first thing.\n* The second\n  thing.\n\n## Notes\n"
)
DASH = STAR.replace("* ", "- ")
NUMBERED = "## Done-when\n\n1. One.\n2. Two.\n"
PARAGRAPH = "Done-when: `pitboss next` prints it.\n\nMore.\n"


def run_with(body: str, workflow: str | None) -> str:
    """Run ``pitboss next`` on ticket 99 in a checkout with a check workflow.

    Args:
        body: the ticket's body.
        workflow: the text of the checkout's ``check.yml``; None for none.

    Returns:
        What it printed, without the note of the library the world lacks.
    """
    here = world.make_world()
    here.bodies[ISSUE] = {"title": "A ticket", "state": "open", "body": body}
    if workflow is not None:
        path = pathlib.Path(here.workspace) / nextguide.CHECK_WORKFLOW
        path.parent.mkdir(parents=True)
        path.write_text(workflow, encoding="utf-8")
    found = world.invoke(here, "next", here.config, "#99", "--now", world.FUTURE)
    lines = [each for each in found.out.splitlines() if "owner/gone" not in each]
    return "".join(f"{each}\n" for each in lines)


class TestDoneWhenMarker(unittest.TestCase):
    """The bullets are printed with the marker the ticket gave them."""

    def test_star_bullets_keep_their_marker(self) -> None:
        """A ticket written with ``* `` is printed with ``* ``, not ``- ``."""
        printed = run_with(STAR, None)
        assert_that(printed, contains_string("\n* The first thing.\n"))
        assert_that(printed, contains_string("\n* The second thing.\n"))
        assert_that("- The first" in printed, equal_to(False))
        assert_that(printed.endswith(FIRST), equal_to(True))

    def test_dash_bullets_keep_theirs(self) -> None:
        """The nearest input the rule must still tell apart: ``- `` is ``- ``."""
        printed = run_with(DASH, None)
        assert_that(printed, contains_string("\n- The first thing.\n"))
        assert_that("* The first" in printed, equal_to(False))

    def test_numbered_bullets_keep_theirs(self) -> None:
        """A numbered Done-when is printed numbered."""
        printed = run_with(NUMBERED, None)
        assert_that(printed, contains_string("\n1. One.\n2. Two.\n"))

    def test_a_paragraph_done_when_prints_nothing_extra(self) -> None:
        """No bullet, no marker to copy, no line."""
        assert_that(run_with(PARAGRAPH, None), equal_to(FIRST))

    def test_bullets_of_the_ticket_are_listed_with_markers(self) -> None:
        """The function behind it lists marked items only."""
        assert_that(
            ticketwhen.bullets(STAR),
            equal_to(["* The first thing.", "* The second thing."]),
        )
        assert_that(ticketwhen.bullets(PARAGRAPH), equal_to([]))


class TestCiJobs(unittest.TestCase):
    """The job names of the check workflow, as written."""

    def test_a_matrix_job_is_named_with_its_expression(self) -> None:
        """A matrix job is ``name (key ${{ matrix.key }})``, a plain job its key."""
        printed = run_with(STAR, WORKFLOW)
        assert_that(
            printed,
            contains_string(
                "CI JOBS: owner/project#99: the jobs of"
                " `.github/workflows/check.yml`, as written (a CI pointer names one"
                " of them): plan; fixtures (shard ${{ matrix.shard }})\n"
            ),
        )

    def test_a_shard_number_is_no_job(self) -> None:
        """The nearest wrong form, ``fixtures (shard N)``, is not printed."""
        printed = run_with(STAR, WORKFLOW)
        assert_that("fixtures (shard N)" in printed, equal_to(False))

    def test_no_workflow_prints_no_line(self) -> None:
        """A checkout without ``check.yml`` gets no ``CI JOBS`` line."""
        assert_that("CI JOBS" in run_with(STAR, None), equal_to(False))

    def test_a_workflow_without_jobs_prints_no_line(self) -> None:
        """Nothing to name, nothing printed."""
        assert_that(nextguide.ci_jobs_line(TICKET, "name: check\n"), equal_to(""))
        assert_that(nextguide.ci_jobs_line(TICKET, None), equal_to(""))
