"""A step that spends runner time waits for a red that is known (keyword: known-red).

quire#1120: ``slots next`` offered to undraft a PR whose ``text-lint`` status was red.
Every cell of the table below is one spending row of ``actiongates.tsv`` against one
known-red row of ``knownred.tsv``, played with a PR in that state; a row with no
applicator, or a cell that prints no FIX FIRST line, fails the test.
"""

import dataclasses
import datetime
import pathlib
import unittest
from typing import Callable, Mapping

from hamcrest import assert_that, contains_string, equal_to, has_item, not_

from .. import (
    actions,
    config,
    knownred,
    pinsreading,
    pulls,
    readyline,
    report,
    reviews,
    shapes,
    steps,
    straycomments,
)
from . import fakes, world
from .says import says
from .test_action_gates import act_arm, dropped
from .test_commands import sweep
from .test_report import facts, run

NOW = datetime.datetime(2026, 11, 12, tzinfo=datetime.timezone.utc)
RUNNERS = config.Runners(
    repositories=(), record=pathlib.Path("none"), quiet_minutes=15, held=False
)


def status(context: str) -> shapes.CommitStatus:
    """A failed commit status.

    Args:
        context: its context.

    Returns:
        The status.
    """
    return shapes.CommitStatus(
        context=context,
        succeeded=False,
        created_at="2026-11-12T10:00:00Z",
        state="failure",
        description="missing relock-scratch run",
    )


def red(pull: pulls.PullFacts, row: knownred.Row) -> pulls.PullFacts:
    """The PR with one known red on its head.

    Args:
        pull: the PR.
        row: the known-red row.

    Returns:
        The PR in that state.
    """
    signals = pull.signals
    if row.source.startswith(knownred.STATUS):
        context = row.source.removeprefix(knownred.STATUS)
        signals = dataclasses.replace(signals, statuses=(status(context),))
    elif row.source == "pins":
        reading = pinsreading.Reading(status=pinsreading.Status.NOT_OK, detail="no")
        signals = dataclasses.replace(signals, pins=reading)
    elif row.source == "unreadable":
        pull = dataclasses.replace(
            pull, unreadable=straycomments.StrayComments(newer="2026-11-12T10:00Z")
        )
    elif row.source.startswith(knownred.STEPS):
        step = row.source.removeprefix(knownred.STEPS).split("+")[0]
        pull = dataclasses.replace(pull, step=steps.Next(step=steps.Step[step]))
    return dataclasses.replace(pull, signals=signals)


def ready(step: steps.Next) -> pulls.PullFacts:
    """An approved, green PR at a step.

    Args:
        step: its step.

    Returns:
        The PR.
    """
    pull = facts(reviews.Standing.APPROVED, checks=[run(True)])
    return dataclasses.replace(pull, step=step)


def sweep_text(pull: pulls.PullFacts) -> str:
    """The action lines of a PR.

    Args:
        pull: the PR.

    Returns:
        The lines, joined.
    """
    settings = fakes.settings(fakes.directory())
    return "\n".join(report.action_lines(pull, settings, False, {}))


def act(action: actions.Action) -> Callable[[pulls.PullFacts], str]:
    """What ``pitboss act`` says of an action.

    Args:
        action: the action.

    Returns:
        A function from the PR to the refusal.
    """
    return lambda pull: knownred.refusal(pull, action)


def undraft(pull: pulls.PullFacts) -> str:
    """The NEXT text of a draft whose Plan is approved.

    Args:
        pull: the PR.

    Returns:
        The text.
    """
    return readyline.line(pull, RUNNERS, NOW)


# every withheld row of actiongates.tsv, and how its cell is played
APPLICATORS: Mapping[str, Callable[[pulls.PullFacts], str]] = {
    "Action.MERGE": act(actions.Action.MERGE),
    "Action.UNDRAFT": act(actions.Action.UNDRAFT),
    "Action.DISPATCH": act(actions.Action.DISPATCH),
    "Action.ARM": act(actions.Action.ARM),
    "Step.UNDRAFT": lambda pull: undraft(
        dataclasses.replace(pull, step=steps.undraft())
    ),
    "Step.RUN_E2E": lambda pull: sweep_text(
        dataclasses.replace(pull, step=steps.run_e2e("branch"))
    ),
    "Step.MERGE": lambda pull: sweep_text(
        dataclasses.replace(pull, step=steps.merge())
    ),
}
SHOULD_SHOW = {"Step.RUN_E2E": ""}
WITHHELD = [name for name, how in knownred.spending().items() if how == "withheld"]
ROWS = [each for each in knownred.rows() if each.source != "local"]


def unreachable(name: str, row: knownred.Row) -> bool:
    """Whether a PR can be in both states: at a step and at the step a red is.

    Args:
        name: the spending row.
        row: the known red.

    Returns:
        True for a spending step against a red that is a step: a PR is at one.
    """
    return name.startswith("Step.") and row.source.startswith(knownred.STEPS)


def played(name: str, row: knownred.Row | None) -> str:
    """What a spending row prints for a PR with a known red, or with none.

    Args:
        name: the spending row.
        row: the known red, or None for a clean head.

    Returns:
        What it printed.
    """
    pull = ready(steps.merge())
    pull = red(pull, row) if row else pull
    return APPLICATORS[name](pull)


def with_red_canonical_files(here: world.World) -> world.World:
    """Post a failed ``canonical-files`` status on the head of every PR.

    Args:
        here: the world.

    Returns:
        The world.
    """
    posted = {
        "statuses": [
            {
                "context": "canonical-files",
                "state": "failure",
                "description": "a pin is 107 commits old",
            }
        ]
    }
    here.bodies[fakes.page(f"{world.PROJECT}/commits/{fakes.HEAD}/status")] = posted
    return here


class TestThroughTheCommands(unittest.TestCase):
    """The sweep, ``slots next`` and ``act`` on a world (quire#1120)."""

    def test_c28_act_refuses_an_arm_while_a_known_red_stands(self) -> None:
        """The matrix allows the arm at the merge step; the known red does not."""
        here = with_red_canonical_files(dropped(False))
        done = act_arm(here, "--no-dry-run")
        says(done.err, "FIX FIRST", "canonical-files is red")
        assert_that(done.code, equal_to(2))
        assert_that([call for call in here.calls if "merge" in call], equal_to([]))

    def test_c28_the_sweep_prints_fix_first_for_the_merge_and_not_ready(self) -> None:
        """The READY TO MERGE line of the PR is replaced."""
        here = with_red_canonical_files(dropped(False))
        text = sweep(here).out
        assert_that(text, contains_string("FIX FIRST owner/project#2"))
        shown = [
            each for each in text.splitlines() if each.startswith("READY TO MERGE")
        ]
        assert_that(shown, equal_to([]))
        assert_that(text, not_(contains_string("re-arm")))


class TestEveryCell(unittest.TestCase):
    """Each spending row against each known red."""

    def test_c28_every_withheld_row_has_an_applicator(self) -> None:
        """A row added to actiongates.tsv with no cell here fails."""
        assert_that(sorted(APPLICATORS), equal_to(sorted(WITHHELD)))

    def test_c28_a_known_red_withholds_every_spending_row(self) -> None:
        """FIX FIRST names the red and its fix, in place of the spending step."""
        for name in WITHHELD:
            for row in ROWS:
                if unreachable(name, row):
                    continue
                with self.subTest(name=name, red=row.name):
                    said = played(name, row)
                    assert_that(said, contains_string("FIX FIRST"))
                    assert_that(said, contains_string(f"{row.name} is red"))
                    assert_that(said, contains_string(row.fix))

    def test_c28_a_cleared_red_offers_the_step(self) -> None:
        """A head with no known red gets the step, not FIX FIRST."""
        for name in WITHHELD:
            with self.subTest(name=name):
                assert_that(played(name, None), not_(contains_string("FIX FIRST")))

    def test_c28_the_step_is_offered_again_once_the_red_is_cleared(self) -> None:
        """The same PR before and after the status turns green."""
        row = ROWS[0]
        pull = ready(steps.undraft())
        assert_that(undraft(red(pull, row)), contains_string("FIX FIRST"))
        assert_that(undraft(pull), contains_string("mark the PR ready"))

    def test_c28_a_push_is_the_fix_and_is_never_withheld(self) -> None:
        """The workers' pushes and rounds are the fix steps."""
        fixes = [n for n, how in knownred.spending().items() if how == "fix"]
        assert_that(fixes, has_item("Action.PUSH"))
        pull = red(ready(steps.merge()), ROWS[0])
        assert_that(knownred.refusal(pull, actions.Action.PUSH), equal_to(""))

    def test_c28_a_local_row_names_the_command_that_runs_it(self) -> None:
        """base-check and hand-back-check are not on the head: the row says where."""
        local = [each for each in knownred.rows() if each.source == "local"]
        assert_that(
            [each.name for each in local], equal_to(["base-check", "hand-back-check"])
        )
        for each in local:
            assert_that(each.fix, contains_string("`pitboss "))

    def test_c28_the_relock_re_dispatch_waits_too(self) -> None:
        """A NEEDS line that asks for a re-dispatch is withheld by a known red."""
        pull = red(ready(steps.merge()), ROWS[0])
        line = "NEEDS o/r#7: the red check passed on main since: re-dispatch x"
        shown = knownred.gate(pull, [line, "UPDATE o/r#7: x"], ())
        assert_that(shown[-1], contains_string("FIX FIRST"))
        assert_that(shown, not_(has_item(line)))
