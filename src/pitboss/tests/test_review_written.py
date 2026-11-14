"""The review ``act review`` writes is in the repository's form (pitboss#483)."""

import dataclasses
import pathlib
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import actcore, config, reviews, shapes
from ..totaljson import members
from . import gateworld, knownkit, linting, quietworld, test_plan_revision, world
from .actplay import GIVEN, refusal

QUIRE = "Independent review (a separate reviewer agent) of head {sha}: {verdict}"
FORMS = [
    config.DEFAULT_REVIEW_FORM,
    config.ReviewForm(lines=[QUIRE], approved="approved", changes_needed="needs work"),
    gateworld.FORM,
]
FINDINGS = "the Plan has a row for each bullet."
VERDICTS = dict(zip(("approved", "changes needed"), reviews.Verdict))
PLAN_ONLY = ["changes needed", "", "changes needed"]
PULL = "repos/owner/project/pulls/3"
ACT = ("act", "review", "owner/project#3", f"findings={FINDINGS}")


def acted(here: world.World, *grades: str) -> world.Result:
    """Run ``pitboss act review`` on PR 3 (a dry run) as the signed-in login.

    Args:
        here: the world.
        *grades: the grade options.

    Returns:
        What it did.
    """
    here.bodies["user"] = {"login": "pitboss-bot"}
    return world.invoke(here, *ACT, *grades, "--config", here.config)


def written(grades: Sequence[str], form: config.ReviewForm) -> str:
    """The review ``act review`` writes on the known world's PR.

    Args:
        grades: the Plan, Execution ("" for none) and verdict grades.
        form: the form of the PR's repository.

    Returns:
        The review.
    """
    found = dataclasses.replace(knownkit.made(GIVEN).act, form=lambda repo: form)
    named = zip(("plan", "execution", "verdict"), grades)
    options = {key: value for key, value in named if value}
    target = actcore.Target(repo=knownkit.REPO, number=knownkit.NUMBER)
    return GIVEN.verbs["review"](found, target, {**options, "findings": FINDINGS})


class TestTheForm(unittest.TestCase):
    """The first line, what the reader reads, and a review of the Plan alone."""

    def test_the_first_line_is_the_one_review_form_prints(self) -> None:
        """Through the command: review-form's form line, with the head and verdict."""
        here = world.make_world()
        with pathlib.Path(here.config).open("a", encoding="utf-8") as stream:
            stream.write(f"\n[review.form]\nlines = [{QUIRE!r}]\n")
        form = world.again(here, "review-form", "project").out.splitlines()
        line = next(each for each in form if not each.startswith("#"))
        grades = [f"{key}=approved" for key in ("plan", "execution", "verdict")]
        done = acted(here, *grades)
        sha = test_plan_revision.HEAD
        first = line.replace("{sha}", sha).replace("{verdict}", "approved")
        assert_that(done.out.splitlines()[0], equal_to(first))

    def test_the_reader_reads_the_verdict_it_was_given(self) -> None:
        """Every form, each verdict, with and without an Execution line."""
        for form in FORMS:
            for verdict, read in VERDICTS.items():
                for execution in (verdict, ""):
                    text = written([verdict, execution, verdict], form)
                    found = reviews.read_comment(text, form)
                    assert_that(found, equal_to((knownkit.HEAD, read)))

    def test_no_execution_option_writes_a_plan_only_review(self) -> None:
        """No Execution line, the form's own lines once; another grade is refused."""
        lines = written(PLAN_ONLY, FORMS[2]).splitlines()
        keys = ("Execution:", "Plan:", "Verdict:", "Reviewed:")
        counts = [sum(each.startswith(key) for each in lines) for key in keys]
        assert_that(counts, equal_to([0, 1, 1, 1]))
        hub = knownkit.made(GIVEN)
        words = {"plan": "approved", "verdict": "approved", "execution": "ok"}
        assert_that(
            refusal(hub, "review", findings="x", **words), contains_string("grade")
        )

    def test_a_plan_only_review_passes_lint_review_kind_plan(self) -> None:
        """``pitboss lint review --review-kind plan`` prints ok."""
        path = linting.write_text("review.md", written(PLAN_ONLY, FORMS[0]))
        done = linting.lint("review", path, "--review-kind", "plan")
        assert_that((done.code, linting.lines(done)), equal_to((0, ["ok"])))

    def test_slots_next_offers_a_draft_the_plan_revision(self) -> None:
        """A draft whose newest review asks for a new Plan is listed for it."""
        here = world.make_world()
        grades = [f"{key}=changes needed" for key in ("plan", "verdict")]
        posted = shapes.Comment(
            body=acted(here, *grades).out,
            author_association="MEMBER",
            created_at="2026-10-30T00:00:01Z",
        )
        here.bodies[test_plan_revision.COMMENTS] = [world.comment_json(posted)]
        here.bodies[PULL] = {**members(here.bodies[PULL]), "draft": True}
        calm = quietworld.calm(quietworld.at_rest(here))
        after = test_plan_revision.AFTER
        listed = world.invoke(calm, "slots", "next", calm.config, *after).out
        line = "".join(each for each in listed.splitlines() if "project#3 (" in each)
        assert_that(line, contains_string("(revise the plan,"))
