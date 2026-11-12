"""Tests for the rules a repository states for its reviews (keyword: repo-rules)."""

import base64
import json
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import reporules
from . import fakes, world
from .test_slot_commands import next_output

PWA = """# pwa

## We write bats, not shell

Our own code is bats; the only non-bats code is what is impossible in bats.

## Adversarial review before merge

A review knows three kinds:

* **A bug fix** (current functionality that misbehaves): confirm it is minimal.
* **Process, documentation or CI** changes: confirm they add no capability.

Whatever its kind, a pull request that adds non-bats code of ours gets
`Verdict: changes needed` unless it names the avenue in bats it exhausted.

## Other

Nothing.
"""
PLAIN = "# lib\n\nNo review rules here.\n"
NEW_SCRIPT = (
    "diff --git a/job-took.sh b/job-took.sh\n--- /dev/null\n+++ b/job-took.sh\n"
    "@@ -0,0 +1,2 @@\n+#!/bin/sh\n+echo took\n"
)
EDITED_SCRIPT = NEW_SCRIPT.replace("--- /dev/null", "--- a/job-took.sh")
LONG_STEP = (
    "--- a/.github/workflows/c.yml\n+++ b/.github/workflows/c.yml\n@@ -1 +1,4 @@\n"
    "+      - run: |\n+          make\n+          ./job-took.sh\n"
)
ONE_STEP = LONG_STEP.replace(
    "|\n+          make\n+          ./job-took.sh", "bats check"
)
AVENUE = "Avenue exhausted: bats has no clock, so date is the one call."


class TestFindings(unittest.TestCase):
    """The diff decides the rule; the body may name the avenue."""

    def test_c22_a_new_script_in_a_repository_that_writes_bats_is_flagged(self) -> None:
        """The finding quotes the repository's sentence."""
        found = reporules.findings("body", PWA, NEW_SCRIPT, "Fixes #1")
        assert_that(len(found), equal_to(1))
        assert_that(found[0], contains_string("job-took.sh"))
        assert_that(found[0], contains_string("Our own code is bats"))

    def test_c22_a_body_that_names_the_avenue_is_not_flagged(self) -> None:
        """The avenue exhausted is the exception the rule states."""
        assert_that(reporules.findings("body", PWA, NEW_SCRIPT, AVENUE), equal_to([]))

    def test_c22_a_repository_with_no_such_rule_is_not_flagged(self) -> None:
        """No rule, no finding, whatever the diff adds."""
        assert_that(reporules.findings("body", PLAIN, NEW_SCRIPT, ""), equal_to([]))

    def test_c22_a_workflow_step_of_many_commands_is_flagged_and_one_is_not(
        self,
    ) -> None:
        """Only a ``run:`` step beyond one command, or an edited file not new."""
        shown = [
            len(reporules.findings("body", PWA, diff, ""))
            for diff in (LONG_STEP, ONE_STEP, EDITED_SCRIPT)
        ]
        assert_that(shown, equal_to([1, 0, 0]))


class TestBrief(unittest.TestCase):
    """The review brief carries the repository's rules."""

    def test_c22_the_rules_are_the_verdict_paragraphs_and_the_kinds(self) -> None:
        """Each paragraph naming the verdict, each kind, nothing else."""
        found = reporules.rules(PWA)
        assert_that(len(found), equal_to(3))
        assert_that(reporules.rules(PLAIN), equal_to([]))
        assert_that(reporules.lines(PLAIN), equal_to([]))
        assert_that(reporules.lines(PWA)[0], contains_string("REPOSITORY RULES"))

    def test_c22_a_review_brief_prints_the_repository_rules(self) -> None:
        """The brief pitboss prints for the review has the section."""
        here = world.make_world()
        content = base64.b64encode(PWA.encode()).decode()
        here.bodies["repos/owner/project/contents/CLAUDE.md"] = json.loads(
            json.dumps({"content": content})
        )
        text = next_output(here)
        assert_that(text, contains_string("REPOSITORY RULES"))
        assert_that(text, contains_string("names the avenue in bats it exhausted"))

    def test_c22_a_repository_with_no_claude_md_has_no_section(self) -> None:
        """An unreadable file adds nothing."""
        assert_that(reporules.read(fakes.github({}), "owner/none"), equal_to(""))
