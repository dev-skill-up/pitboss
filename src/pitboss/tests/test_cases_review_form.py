"""I38 of pitboss#444: a review does not start on a head with a CI run unfinished."""

import unittest

from hamcrest import assert_that, equal_to

from . import fakes, world
from .cleanworld import same
from .says import says
from .test_register_rules import shown

HEAD = "c" * 40


def _check(number: int, state: tuple[str, str, str]) -> dict[str, object]:
    name, status, conclusion = state
    url = f"https://github.com/owner/project/actions/runs/{number}/job/1"
    return {
        "id": number,
        "name": name,
        "status": status,
        "conclusion": conclusion or None,
        "head_sha": HEAD,
        "started_at": "2026-11-11T10:00:00Z",
        "completed_at": "2026-11-11T10:05:00Z" if conclusion else None,
        "check_suite": {"id": 1},
        "app": {"slug": "github-actions"},
        "details_url": url,
    }


def runs(*states: tuple[str, str, str]) -> world.World:
    """A world whose head HEAD has check runs.

    Args:
        *states: name, status and conclusion of each run.

    Returns:
        The world.
    """
    here = world.make_world()
    checks = [_check(number, each) for number, each in enumerate(states, 100)]
    here.bodies.update(
        fakes.bodies_under(
            "repos/owner/project",
            [(f"commits/{HEAD}/check-runs", {"check_runs": checks})],
        )
    )
    return here


def review_form(here: world.World) -> world.Result:
    """Run ``review-form --head`` on the world's project.

    Args:
        here: the world.

    Returns:
        The finished command.
    """
    return world.invoke(here, "review-form", here.config, "project", "--head", HEAD)


class TestReviewCi(unittest.TestCase):
    """``review-form --head`` refuses a head that is not green."""

    def test_i38_a_run_in_progress_refuses_and_is_named(self) -> None:
        """The run and its state are printed, the status is 1."""
        here = runs(("check", "completed", "success"), ("e2e", "in_progress", ""))
        done = review_form(here)
        said = "CI RUN e2e (101): not completed" in done.out
        assert_that((done.code, said), equal_to((1, True)))

    def test_i38_a_failed_run_is_named_as_failed(self) -> None:
        """A run that completed with a failure is not a success."""
        done = review_form(runs(("check", "completed", "failure")))
        said = "CI RUN check (100): failed" in done.out
        assert_that((done.code, said), equal_to((1, True)))

    def test_i38_a_head_with_every_run_green_prints_the_form(self) -> None:
        """The nearest input that must pass."""
        here = runs(("check", "completed", "success"))
        done = review_form(here)
        says(done.out, "Body: <digest>")
        same(done.code, 0)

    def test_i38_made_false_is_refused_in_a_review(self) -> None:
        """Holds on main too (A8): the review rule refuses the words with their line."""
        refused = "test_a8_makes_false_is_refused_with_its_line"
        assert_that(shown("test_review_rules", refused), equal_to(1))
