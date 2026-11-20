"""C14 and C15: rules of the register that contradict (keyword: rule-conflicts).

quire#1115: ``test.fixme`` for a known flaky test against never quarantining a test
to get green. The register's words show the pair, ``ruleconflicts.tsv`` declares how
it is settled, and a PR that hits a ``ruling`` pair gets the Opus ruling brief.
"""

import dataclasses
import unittest

from hamcrest import (
    assert_that,
    contains_string,
    empty,
    equal_to,
    has_item,
    has_length,
    is_,
)

from .. import flow, rules, ruleconflicts, steps
from . import test_flow, test_flow_sweep, test_rules
from .itemworld import one
from .says import says

REGISTER = test_rules.shipped_rows()
DECLARED = ruleconflicts.shipped()
FIXME_BODY = test_flow.BODY + "\nThe flaky test is marked test.fixme('#9 flake').\n"
SETTLED = test_flow.ruling(4, line="Ruling: do these steps\nConflict: C14 T53")


def row(ident: str, words: str) -> rules.Row:
    """A rule of the register.

    Args:
        ident: its id.
        words: its words.

    Returns:
        The row.
    """
    return rules.Row(
        id=ident, date="", kind="output", words=words, function="-", tests=()
    )


def resolved(resolution: str) -> ruleconflicts.Declared:
    """The first declared pair with another resolution.

    Args:
        resolution: the resolution.

    Returns:
        The pair.
    """
    return dataclasses.replace(DECLARED[0], resolution=resolution)


class TestPairs(unittest.TestCase):
    """The register against the declared pairs."""

    def test_c15_the_shipped_pairs_match_the_register(self) -> None:
        """No finding, and the quarantine pair is a ruling."""
        assert_that(ruleconflicts.findings(REGISTER, DECLARED), empty())
        assert_that(
            [(each.first, each.second, each.resolution) for each in DECLARED],
            has_item(("C14", "T53", "ruling")),
        )
        assert_that(("C14", "T53") in ruleconflicts.detected(REGISTER), is_(True))

    def test_c15_an_undeclared_pair_is_found(self) -> None:
        """Planted: a rule that forbids what another does, with no declaration."""
        planted = [
            row("Z1", "Never delete a branch with an open pull request"),
            row("Z2", "Delete a branch after its pull request merges"),
        ]
        found = ruleconflicts.findings(planted, [])
        assert_that(found[0], contains_string("Z1 forbids what Z2 does"))
        agreed = [planted[0], row("Z3", "Never delete a branch, refuse it")]
        assert_that(ruleconflicts.findings(agreed, []), empty())

    def test_c15_a_declared_pair_must_be_in_the_register_and_settled(self) -> None:
        """Planted: a gone rule, and a resolution that is neither."""
        gone = ruleconflicts.Declared(
            first="C14", second="Q9", resolution="ruling", trigger="x", question="q"
        )
        odd = resolved("wins:A1")
        wins = resolved("wins:C14")
        found = ruleconflicts.findings(REGISTER, [gone, odd, wins])
        says("\n".join(found), "C14 Q9 names a rule not in", "the resolution 'wins:A1'")
        assert_that(found, has_length(2))

    def test_c15_a_short_line_is_read_as_unsettled(self) -> None:
        """A line of the wrong width has no resolution, so it is a finding."""
        short = ruleconflicts.parse("# a\n\nC14\tT53\n")
        found = ruleconflicts.findings(REGISTER, [*DECLARED, *short])
        assert_that(found, has_item("conflict: C14  has the resolution ''"))


def conflict_of(step: steps.Move) -> str:
    """The pair a step names.

    Args:
        step: the step.

    Returns:
        Its ``conflict``; empty for an idle PR.
    """
    return step.conflict if isinstance(step, steps.Next) else ""


class TestHit(unittest.TestCase):
    """A PR that hits a ruling pair."""

    def test_c15_a_pair_that_is_hit_gets_the_ruling_step(self) -> None:
        """The body names test.fixme: the Opus ruling, with the pair; a control."""
        hit = flow.next_step(test_flow.state(body=FIXME_BODY))
        plain = flow.next_step(test_flow.state())
        assert_that(
            (steps.step_of(hit), conflict_of(hit), conflict_of(plain)),
            equal_to((steps.Step.OPUS_RULING, "C14 T53", "")),
        )

    def test_c15_a_ruling_that_names_the_pair_settles_it(self) -> None:
        """After the ruling with the Conflict line the PR is at its usual step."""
        settled = flow.next_step(test_flow.state(comments=[SETTLED], body=FIXME_BODY))
        again = flow.next_step(
            test_flow.state(comments=[test_flow.ruling(4)], body=FIXME_BODY)
        )
        assert_that(
            (conflict_of(settled), conflict_of(again)), equal_to(("", "C14 T53"))
        )

    def test_c15_a_win_is_not_a_ruling(self) -> None:
        """A pair settled by a winning rule makes no step."""
        wins = resolved("wins:C14")
        assert_that(ruleconflicts.pending([wins], [FIXME_BODY], []), equal_to(None))

    def test_c14_the_ruling_brief_states_both_rules_and_the_question(self) -> None:
        """``slots next`` for the PR prints both rules, the question and the line."""
        here = test_flow_sweep.world_with([], body=FIXME_BODY)
        found = one(here, "owner/project#3")
        says(
            found.out,
            "Rule conflict C14 and T53",
            "Never quarantine or skip a test to get green",
            "quarantine a failing test at its p0 ticket",
            "Question: Quire e2e rules require test.fixme",
            "Conflict: C14 T53",
        )
        assert_that(found.code == 0, is_(True))
