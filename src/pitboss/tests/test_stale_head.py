"""A body that names an older head than the PR's has a step that fixes it.

The keyword is stale-head (quire#1115, quire#1110): after a push the body's
``Head:`` line was stale, ``text-lint`` was red, and pitboss offered no step. The
fields of a body that go stale after a push are the ones ``forms`` checks against
the head (the ``Head:`` line, the Evidence blocks, the ``Reviewed:`` line of a
review); each has a step that fixes it, and the test plants each.
"""

import dataclasses
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import expansion, flow, forms, headline, steps
from . import test_flow, test_flow_sweep
from .itemworld import one
from .linting import OK
from .says import says

HEAD = test_flow.HEAD
OLDER = "b" * 40
CURRENT = f"{test_flow.BODY}\nHead: {HEAD}\n"
STALE = f"{test_flow.BODY}\nHead: {OLDER}\n"
BLOCK = expansion.block("nox -s tests", OK, OLDER)
SUBJECT = forms.Subject(name="b", body="", head=HEAD)
EVIDENCE = f"{test_flow.BODY}\n## Evidence\n\n{BLOCK}\nHead: {HEAD}\n"


def step_of(body: str) -> steps.Next:
    """The step of a PR with a body.

    Args:
        body: the PR body.

    Returns:
        What ``flow.next_step`` gives.
    """
    return flow.next_step(test_flow.state(body=body))


class TestRow(unittest.TestCase):
    """The flow row."""

    def test_c18_a_body_with_an_older_head_line_gets_the_refresh_step(self) -> None:
        """Stale head line, stale Evidence, current and absent ``Head:`` lines."""
        bodies = [STALE, EVIDENCE, CURRENT, test_flow.BODY]
        refresh = steps.worker(steps.Task.REFRESH_BODY)
        got = [step_of(each) == refresh for each in bodies]
        assert_that(got, equal_to([True, True, False, False]))

    def test_c18_the_head_line_is_read_as_text_lint_reads_it(self) -> None:
        """The last ``Head:`` line decides; none is not stale."""
        texts = [
            f"Head: {OLDER}\nHead: {HEAD}\n",
            f"Head: {HEAD}\nHead: {OLDER}\n",
            "-",
        ]
        got = [headline.is_stale(each, HEAD) for each in texts]
        assert_that(got, equal_to([False, True, False]))


class TestPrinted(unittest.TestCase):
    """The step is printed, with the commands that fix and validate it."""

    def test_c18_slots_next_names_the_commands_that_rewrite_and_validate(self) -> None:
        """The brief says ``body-head``, ``expand`` and ``lint pr-body``."""
        here = test_flow_sweep.world_with([], body=STALE)
        says(one(here, "owner/project#3").out, "body-head", "pitboss expand", "lint pr")

    def test_c18_the_step_text_names_the_command_that_validates_it(self) -> None:
        """The step's own text, shown by the sweep, names ``lint pr-body``."""
        assert_that(steps.Task.REFRESH_BODY.value, contains_string("lint pr-body"))


class TestSiblings(unittest.TestCase):
    """Every field ``forms`` judges against the head has a step."""

    def test_c18_each_stale_field_is_found_by_the_form_check_and_has_a_step(
        self,
    ) -> None:
        """The Head line and an Evidence block: both are findings and both refresh."""
        bodies = [STALE, EVIDENCE]
        subjects = [dataclasses.replace(SUBJECT, body=each) for each in bodies]
        said = ["\n".join(forms.pr_body(each, [])) for each in subjects]
        assert_that(all("head" in each for each in said), equal_to(True))
        wanted = [steps.worker(steps.Task.REFRESH_BODY)] * 2
        assert_that([step_of(each) for each in bodies], equal_to(wanted))
