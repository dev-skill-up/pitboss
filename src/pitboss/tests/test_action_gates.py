"""C26: every state change passes a gate (keyword: action-gates, quire#1110).

quire#1110: a PR dropped from the merge queue was told to arm auto-merge again
during a quiet period of the runner hold. Each task, step and action has a gate
row, the row's test exists, the matrix lets no ungated step make a gated action,
and the re-arm of a dropped PR is withheld by the hold and offered after it.
"""

import unittest

from hamcrest import assert_that, contains_string, empty, equal_to

from .. import actcore, acthub, actiongates, phrases
from . import knownkit, knownshipped
from .queueworld import dropped, dropped_held
from .test_slot_commands import next_output
from .says import says
from .existing import resolvable
from ..textparts import having
from ..actiongates import findings
from .knownplay import held

TABLE = phrases.shipped_text("actiongates.tsv")
MATRIX = phrases.shipped_text("actionmatrix.tsv")
PULL = "owner/project#2"


def lines_about_pr_2(out: str) -> str:
    """The lines of a ``slots next`` output that name PR 2.

    Args:
        out: the output.

    Returns:
        Those lines, joined.
    """
    return "\n".join(having(out.splitlines(), "project#2"))


class TestTable(unittest.TestCase):
    """The table against the code."""

    def test_c26_the_shipped_table_has_no_finding(self) -> None:
        """Every member has its row, every test exists, no gated step is free."""
        assert_that(findings(TABLE, MATRIX, resolvable), empty())

    def test_c26_a_member_with_no_row_is_found(self) -> None:
        """A new action with no gate row fails the check."""
        text = TABLE.replace("Action.ARM\t", "Action.OTHER\t", 1)
        found = findings(text, MATRIX, resolvable)
        assert_that(
            found,
            equal_to(
                [
                    "Action.ARM has no gate row",
                    "Action.OTHER is no task, step or action",
                ]
            ),
        )

    def test_c26_a_step_that_makes_a_gated_action_is_not_free(self) -> None:
        """Step.MERGE allows merge and arm: its row cannot be free."""
        row = next(
            each for each in TABLE.splitlines() if each.startswith("Step.MERGE\t")
        )
        text = TABLE.replace(row, "Step.MERGE\tfree\tnothing\t-")
        found = findings(text, MATRIX, resolvable)
        assert_that(
            having(found, "its gate is free"),
            equal_to(
                [
                    "Step.MERGE may make merge but its gate is free",
                    "Step.MERGE may make arm but its gate is free",
                ]
            ),
        )

    def test_c26_a_gate_without_a_test_or_a_reason_is_found(self) -> None:
        """A hold row names a test that exists; a free row says why."""
        text = TABLE.replace(
            "test_c26_the_hold_withholds_the_re_arm_and_says_wait", "gone"
        )
        found = findings(text, MATRIX, resolvable)
        assert_that(found[0], contains_string("does not exist"))
        free = TABLE.replace("closing a PR starts no workflow run of the project", " ")
        assert_that(
            findings(free, MATRIX, resolvable),
            equal_to(["Action.CLOSE: a free row says why"]),
        )

    def test_c26_a_gate_that_is_none_of_the_three_is_found(self) -> None:
        """The words are hold, pressure and free."""
        text = TABLE.replace("Action.CLOSE\tfree", "Action.CLOSE\tmaybe", 1)
        says("\n".join(findings(text, MATRIX, resolvable)), "is none of hold")

    def test_c26_a_row_with_a_missing_field_is_refused(self) -> None:
        """A short row is an error."""
        with self.assertRaises(ValueError):
            actiongates.parse("a\tb\n")


class TestRearm(unittest.TestCase):
    """The re-arm of a dropped PR, through ``act`` and ``slots next``."""

    def test_c26_the_arm_command_is_gh_pr_merge_auto(self) -> None:
        """The command of the arm write."""
        said = acthub.WRITES["arm"](actcore.Change(kind="arm", repo="o/r", number=2))
        assert_that(list(said[:4]), equal_to(["gh", "pr", "merge", "2"]))
        assert_that(list(said[-2:]), equal_to(["--auto", "--merge"]))

    def test_c26_an_arm_during_a_hold_is_refused_and_changes_nothing(self) -> None:
        """A hold of merges.

        (the runner-pressure hold is ``act hold --scope ci``) refuses the arm.
        """
        given = knownshipped.shipped()
        hub = knownkit.made(given)
        held(given, hub, "merges")
        said = knownkit.refused(lambda: knownkit.act(given, hub, "arm"))
        assert_that(said, contains_string("hold"))
        assert_that(
            [each.kind for each in hub.hub.writes if each.kind == "arm"], equal_to([])
        )

    def test_c26_an_arm_after_the_hold_is_recorded_and_made(self) -> None:
        """The hold over, the same PR is armed, its record first."""
        given = knownshipped.shipped()
        hub = knownkit.made(given)
        held(given, hub, "merges")
        number = [key[1] for key in hub.hub.issues_made][0]
        knownkit.act(given, hub, "unhold", number=str(number))
        knownkit.act(given, hub, "arm")
        assert_that(
            [each.kind for each in hub.hub.writes][-2:], equal_to(["comment", "arm"])
        )

    def test_c26_slots_next_waits_during_the_hold_and_offers_the_merge_after(
        self,
    ) -> None:
        """During the hold nobody acts on the PR, so no line names it (one-path).

        After it, its line is the merge step.
        """
        waiting = lines_about_pr_2(next_output(dropped_held()))
        offered = lines_about_pr_2(next_output(dropped()))
        assert_that(waiting, equal_to(""))
        assert_that(offered, contains_string("owner/project#2"))
