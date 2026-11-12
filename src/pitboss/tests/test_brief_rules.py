"""No printed brief contradicts a standing rule, in any state it is printed in.

Quire#1120.
"""

import dataclasses
import unittest

from hamcrest import assert_that, contains_string, empty, equal_to

from .. import brief, briefrules, forms
from . import briefmake

STATES = [
    dataclasses.replace(briefmake.PROJECT, drafts=drafts, holds=holds)
    for drafts in (True, False)
    for holds in (True, False)
]


class TestBriefRules(unittest.TestCase):
    """The brief generator is run for every kind and every project state."""

    def test_c30_no_brief_tells_the_worker_to_do_a_forbidden_action(self) -> None:
        """Every kind, drafts and holds on and off, ready and not, with e2e."""
        found = [
            f"{kind.name}/{project.drafts}/{project.holds}: {each}"
            for kind in brief.Kind
            for project in STATES
            for ready in (True, False)
            for each in briefrules.findings(
                briefmake.text(kind, ready=ready, e2e=ready, project=project)
            )
        ]
        assert_that(sorted(set(found)), equal_to([]))

    def test_c30_a_planted_forbidden_step_is_found(self) -> None:
        """The checker finds an empty commit told, and passes it said as a ban."""
        told = "Push: end with an empty commit pushed to the branch."
        assert_that(briefrules.findings(told)[0], contains_string("no empty commit"))
        assert_that(briefrules.findings("Never push an empty commit."), empty())
        assert_that(briefrules.findings("Rerun the job.")[0], contains_string("C13"))

    def test_c30_the_body_only_revision_prints_no_push(self) -> None:
        """quire#1120: edit the body, the Head line names the pushed head, no push."""
        found = briefmake.text(brief.Kind.REVISE_PLAN)
        assert_that(found, contains_string("edit the PR body; the Head line names"))
        assert_that("Push: push with" in found, equal_to(False))
        assert_that("Push, then hand back" in found, equal_to(False))

    def test_c30_lint_accepts_the_unchanged_pushed_head_in_the_body(self) -> None:
        """A body-only revision: Head names the head that was pushed, no finding."""
        head = "a" * 40
        body = f"Fixes o/r#1\n\nHead: {head}\n\n## Evidence\n"
        subject = forms.Subject(name="b", body=body, head=head)
        found = [each for each in forms.pr_body(subject) if each.endswith("(head)")]
        assert_that(found, empty())
