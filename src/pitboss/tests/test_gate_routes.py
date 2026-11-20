"""Each stop's route is a constructor that carries its actor (P8, keyword: gate)."""

import unittest

from hamcrest import assert_that, equal_to

from .. import answer, gatepolicy, gateverbs
from ..gatestop import Route
from .hubwork import worker


def stopped(lifts: str, carried: answer.Carried) -> answer.Decision:
    """A decision on ``o/r#1`` that lifts a stop or carries a verb.

    Args:
        lifts: the stop line it lifts.
        carried: the verb that carries it out.

    Returns:
        The decision.
    """
    return answer.Decision(
        actor=answer.Actor.ORCHESTRATOR,
        verb="v",
        item="o/r#1",
        title="",
        carried=carried,
        lifts=lifts,
    )


class TestRoutes(unittest.TestCase):
    """P8: who acts on a stop, and whether an override lifts it, is its route's."""

    def test_p8_no_route_without_an_actor_is_lifted(self) -> None:
        """A route no actor takes is kept, so the gate never lifts it."""
        untaken = {each for each in Route if each.value.actor is None}
        assert_that(untaken <= gatepolicy.KEPT, equal_to(True))

    def test_p8_an_override_lifts_only_the_decision_s_own_stop(self) -> None:
        """``overridable`` reads the decision's ``lifts``, not its words."""
        found = stopped("a stop", answer.Carried.NOTHING)
        said = [
            gateverbs.overridable(found, "o/r#1", "a stop"),
            gateverbs.overridable(found, "o/r#1", "another"),
            gateverbs.overridable(stopped("", answer.Carried.NOTHING), "o/r#1", ""),
            gateverbs.overridable(found, "o/r#2", "a stop"),
        ]
        assert_that(said, equal_to([True, False, False, False]))

    def test_p8_a_verb_runs_only_on_the_step_it_carries(self) -> None:
        """``allows`` reads the decision's ``carried``, not its words."""
        merging = stopped("", answer.Carried.MERGE)
        said = [
            gateverbs.allows(gateverbs.ItemVerb.MERGE, merging, "o/r#1"),
            gateverbs.allows(gateverbs.ItemVerb.ARM, merging, "o/r#1"),
            gateverbs.allows(gateverbs.ItemVerb.UNDRAFT, merging, "o/r#1"),
            gateverbs.allows(gateverbs.ItemVerb.MERGE, worker("o/r#1"), "o/r#1"),
            gateverbs.allows(gateverbs.ItemVerb.OVERRIDE, merging, "o/r#1"),
        ]
        assert_that(said, equal_to([True, True, False, False, False]))
