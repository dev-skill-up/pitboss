"""The review ``act review`` writes is in the repository's form (pitboss#483)."""

import pathlib
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import actwrite, config, reviews, shapes
from ..totaljson import members
from . import fakes, linting, quietworld, test_plan_revision, world
from .test_act_command import PULL, _act, _here

QUIRE = "Independent review (a separate reviewer agent) of head {sha}: {verdict}"
FORMS = [
    config.DEFAULT_REVIEW_FORM,
    config.ReviewForm(lines=[QUIRE], approved="approved", changes_needed="needs work"),
    config.ReviewForm(
        lines=["## Adversarial review", "Reviewed: {sha}", "Verdict: {verdict}"],
        approved="approved",
        changes_needed="changes needed",
    ),
]
FINDINGS = "findings=the Plan has a row for each bullet."
PLAN_ONLY = ["changes needed", "", "changes needed"]
PULL_3 = "repos/owner/project/pulls/3"


def written(grades: list[str], form: config.ReviewForm) -> str:
    """The review ``act review`` writes on PR 3 of the fake GitHub.

    Args:
        grades: the Plan, Execution ("" for none) and verdict grades.
        form: the repository's form.

    Returns:
        The review.
    """
    return actwrite.review_text(fakes.pull_body(3), grades, FINDINGS, {}, form)


class TestTheForm(unittest.TestCase):
    """The first line, what the reader reads, and a review of the Plan alone."""

    def test_the_first_line_is_the_one_review_form_prints(self) -> None:
        """Through the command: review-form's form line, with the head and verdict."""
        here = _here()
        with pathlib.Path(here.config).open("a", encoding="utf-8") as stream:
            stream.write(f"\n[review.form]\nlines = [{QUIRE!r}]\n")
        form = world.again(here, "review-form", "project").out.splitlines()
        line = next(each for each in form if not each.startswith("#"))
        grades = [f"{key}=approved" for key in ("plan", "execution", "verdict")]
        done = _act(here, "review", PULL, *grades, FINDINGS)
        sha = str(members(members(here.bodies[PULL_3]).get("head")).get("sha"))
        first = line.replace("{sha}", sha).replace("{verdict}", "approved")
        assert_that(done.out.splitlines()[0], equal_to(first))

    def test_the_reader_reads_the_verdict_it_was_given(self) -> None:
        """Every form, each verdict, with and without an Execution line."""
        for form in FORMS:
            for verdict, read in (
                ("approved", reviews.Verdict.APPROVED),
                ("changes needed", reviews.Verdict.CHANGES_NEEDED),
            ):
                for execution in (verdict, ""):
                    text = written([verdict, execution, verdict], form)
                    found = reviews.read_comment(text, form)
                    assert_that(found, equal_to((fakes.HEAD, read)))

    def test_no_execution_option_writes_a_plan_only_review(self) -> None:
        """No Execution line, the form's own lines once; another grade is refused."""
        lines = written(PLAN_ONLY, FORMS[2]).splitlines()
        keys = ("Execution:", "Plan:", "Verdict:", "Reviewed:")
        counts = [sum(each.startswith(key) for each in lines) for key in keys]
        assert_that(counts, equal_to([0, 1, 1, 1]))
        words = ("plan=approved", "verdict=approved", FINDINGS, "execution=ok")
        assert_that(_act(_here(), "review", PULL, *words).err, contains_string("grade"))

    def test_a_plan_only_review_passes_lint_review_kind_plan(self) -> None:
        """``pitboss lint review --review-kind plan`` prints ok."""
        path = linting.write_text("review.md", written(PLAN_ONLY, FORMS[0]))
        done = linting.lint("review", path, "--review-kind", "plan")
        assert_that((done.code, linting.lines(done)), equal_to((0, ["ok"])))

    def test_slots_next_offers_a_draft_the_plan_revision(self) -> None:
        """A draft whose newest review asks for a new Plan is listed for it."""
        here = world.make_world()
        pull = members(here.bodies[PULL_3])
        posted = shapes.Comment(
            body=actwrite.review_text(pull, PLAN_ONLY, FINDINGS, {}),
            author_association="MEMBER",
            created_at="2026-10-30T00:00:01Z",
        )
        here.bodies[test_plan_revision.COMMENTS] = [world.comment_json(posted)]
        here.bodies[PULL_3] = {**pull, "draft": True}
        calm = quietworld.calm(quietworld.at_rest(here))
        after = test_plan_revision.AFTER
        listed = world.invoke(calm, "slots", "next", calm.config, *after).out
        line = "".join(each for each in listed.splitlines() if "project#3 (" in each)
        assert_that(line, contains_string("(revise the plan,"))
