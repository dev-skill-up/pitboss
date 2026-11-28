"""A red check an open p0 ticket names is that ticket's (keyword: owned-red, #531).

quire#1128 was given "fix the CI" for ``e2e (extras)``, a flaky test its diff does
not touch, while the open p0 ticket quire#1137 named the run and job.
"""

import dataclasses
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to, has_item

from .. import ownedred, pulls
from . import blank, fakes, rankworld, test_work, world
from .rankworld import mentioning, next_output, starts

JOB = 21
RUN = 4567
CHECK = {"id": JOB, "name": "test", "status": "completed", "conclusion": "failure"}
FIXES = "Fixes #9"


def p0(number: int, body: str) -> Mapping[str, object]:
    """A p0 ticket as the issues list gives it.

    Args:
        number: its number.
        body: its text.

    Returns:
        The JSON.
    """
    return {
        "number": number,
        "title": "e2e flake",
        "created_at": "2026-10-05T00:00:00Z",
        "labels": [{"name": "p0"}],
        "body": body,
        "comments": 0,
    }


def owned_world(body: str, fixes: str = FIXES) -> world.World:
    """A world where PR 3 is red from job 21 and a p0 ticket has a text.

    Args:
        body: the p0 ticket's text.
        fixes: what PR 3's body says it fixes.

    Returns:
        The world.
    """
    served = {
        "commits/" + "3" * 40 + "/check-runs": {"check_runs": [CHECK]},
        "issues?state=open&labels=p0": [p0(20, body)],
        "issues/20/comments": [],
    }
    here = world.make_world()
    rankworld.fixing(here, 3, fixes)
    here.bodies["repos/owner/project/issues/9"] = rankworld.ticket()
    flake = rankworld.ticket(body, number=20, labels=[{"name": "p0"}])
    rankworld.serve(here, "owner/project", 20, flake)
    for path, found in served.items():
        here.bodies[fakes.page(f"{world.PROJECT}/{path}")] = found
    return here


def red_pull(run: int = 0) -> pulls.PullFacts:
    """PR 3 of the project with the failed check of job 21.

    Args:
        run: the check's workflow run.

    Returns:
        The PR.
    """
    failed = dataclasses.replace(
        blank.CHECK_RUN, id=JOB, name="test", failed=True, finished=True, run=run
    )
    found = test_work.facts(3, test_work.NONE)
    return dataclasses.replace(found, checks=[failed])


def owners_in(here: world.World, run: int = 0) -> Sequence[str]:
    """The tickets that own the red of PR 3 in a world.

    Args:
        here: the world.
        run: the failed check's workflow run.

    Returns:
        Their references.
    """
    return ownedred.owners(fakes.github(here.bodies), red_pull(run))


class TestOwners(unittest.TestCase):
    """``ownedred.owners``."""

    def test_a_ticket_that_names_the_job_or_the_run_owns_the_red(self) -> None:
        """Job 21 or run 4567 in its text; another number or none is no owner."""
        found = [
            owners_in(owned_world(f"failed in job {JOB}")),
            owners_in(owned_world(f"failed in run {RUN}"), RUN),
            owners_in(owned_world(f"failed in run {RUN}"), 0),
            owners_in(owned_world(f"failed in job {JOB}0")),
        ]
        wanted: list[Sequence[str]] = [
            ["owner/project#20"],
            ["owner/project#20"],
            [],
            [],
        ]
        assert_that(found, equal_to(wanted))

    def test_a_ticket_the_pull_request_fixes_never_blocks_it(self) -> None:
        """The PR that fixes the flake is red from the flake: it is its own work."""
        here = owned_world(f"failed in job {JOB}", "Fixes #20")
        assert_that(owners_in(here), equal_to(["owner/project#20"]))
        mine = dataclasses.replace(
            red_pull(),
            pull=dataclasses.replace(red_pull().pull, body="Fixes #20"),
        )
        found = ownedred.owners(fakes.github(here.bodies), mine)
        assert_that(found, equal_to([]))

    def test_no_failed_check_reads_no_ticket(self) -> None:
        """A green head names no run: nothing is read."""
        green = dataclasses.replace(red_pull(), checks=[])
        found = ownedred.ids(green)
        assert_that(found, equal_to([]))
        assert_that(ownedred.owners(fakes.github({}), green), equal_to([]))


class TestRanking(unittest.TestCase):
    """``slots next`` for a PR whose red an open ticket owns."""

    def test_the_pull_request_has_no_fix_the_ci_line(self) -> None:
        """Owned: no worker line for PR 3; a ticket that names nothing: its line."""
        here = owned_world(f"failed in job {JOB}")
        owned = next_output(here)
        other = next_output(owned_world("failed in another run"))
        found = [
            mentioning(owned, "WORKER: owner/project#3: fix CI"),
            bool(mentioning(other, "WORKER: owner/project#3: fix CI")),
        ]
        assert_that(found, equal_to([[], True]))
        # quire#1128: the ticket that names the red is offered in the PR's place
        assert_that(starts(here), has_item("owner/project#20"))
