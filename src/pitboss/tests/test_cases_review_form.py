"""I38 of pitboss#444: a review does not start on a head with a CI run unfinished."""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from . import fakes, world
from .test_register_rules import shown

HEAD = "c" * 40


def runs(*states: tuple[str, str, str]) -> world.World:
    """A world whose head HEAD has check runs.

    Args:
        *states: name, status and conclusion of each run.

    Returns:
        The world.
    """
    here = world.make_world()
    checks = [
        {
            "id": number,
            "name": name,
            "status": status,
            "conclusion": conclusion or None,
            "head_sha": HEAD,
            "started_at": "2026-11-11T10:00:00Z",
            "completed_at": "2026-11-11T10:05:00Z" if conclusion else None,
            "check_suite": {"id": 1},
            "app": {"slug": "github-actions"},
            "details_url": f"https://github.com/owner/project/actions/runs/{number}/job/1",
        }
        for number, (name, status, conclusion) in enumerate(states, 100)
    ]
    here.bodies.update(
        fakes.bodies_under(
            "repos/owner/project",
            [(f"commits/{HEAD}/check-runs", {"check_runs": checks})],
        )
    )
    return here


class TestReviewCi(unittest.TestCase):
    """``review-form --head`` refuses a head that is not green."""

    def test_i38_a_run_in_progress_refuses_and_is_named(self) -> None:
        """The run and its state are printed, the status is 1."""
        here = runs(("check", "completed", "success"), ("e2e", "in_progress", ""))
        done = world.invoke(here, "review-form", here.config, "project", "--head", HEAD)
        assert_that(done.code, equal_to(1))
        assert_that(done.out, contains_string("CI RUN e2e (101): not completed"))

    def test_i38_a_head_with_every_run_green_prints_the_form(self) -> None:
        """The nearest input that must pass."""
        here = runs(("check", "completed", "success"))
        done = world.invoke(here, "review-form", here.config, "project", "--head", HEAD)
        assert_that(done.code, equal_to(0))
        assert_that(done.out, contains_string("Body: <digest>"))

    def test_i38_made_false_is_refused_in_a_review(self) -> None:
        """Holds on main too (A8): the review rule refuses the words with their line."""
        ran = shown("test_review_rules", "test_a8_makes_false_is_refused_with_its_line")
        assert_that(ran, equal_to(1))
