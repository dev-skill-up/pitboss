"""The standing rules of the coordinator are printed by the sweep (pitboss#444, item 2).

Each test is named for the id of its row in ``rules.tsv``: the sweep ends with the
rule's sentence, whatever the project's own reminders are.
"""

import unittest

from .. import brieftextrules
from . import world
from .says import says
from .test_commands import sweep
from .test_evidence_rules import words


def printed(rule: str) -> None:
    """Check that the sweep prints the rule's sentence as a reminder.

    Args:
        rule: the id of the rule.
    """
    done = sweep(world.make_world())
    says(words(done.out), "SWEEP REMINDER: " + brieftextrules.reminder(rule))


class TestTheSweepPrintsTheRule(unittest.TestCase):
    """One test for each rule the coordinator keeps outside the PRs."""

    def test_a32_no_attribution_and_no_owner_assignment(self) -> None:
        """Printed."""
        printed("A32")

    def test_a33_pins_never_move_by_a_model(self) -> None:
        """Printed."""
        printed("A33")

    def test_a34_no_shim_for_a_weak_engine(self) -> None:
        """Printed."""
        printed("A34")

    def test_b3_never_tell_the_owner_nothing_is_running(self) -> None:
        """Printed."""
        printed("B3")

    def test_b4_a_slot_idle_message_is_corrected(self) -> None:
        """Printed."""
        printed("B4")

    def test_b5_slots_next_is_read_again_before_a_dispatch(self) -> None:
        """Printed."""
        printed("B5")

    def test_d7_never_assume_the_owner_acted(self) -> None:
        """Printed."""
        printed("D7")

    def test_d8_ruling_comments_are_standing_approved(self) -> None:
        """Printed."""
        printed("D8")

    def test_d9_every_question_comes_with_an_artifact(self) -> None:
        """Printed."""
        printed("D9")

    def test_d10_ci_reads_go_through_the_new_environment_thread(self) -> None:
        """Printed."""
        printed("D10")

    def test_d15_never_resolve_a_human_decision_card(self) -> None:
        """Printed."""
        printed("D15")
