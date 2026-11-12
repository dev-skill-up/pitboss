"""Properties P1 to P5 of the review flow over a bounded alphabet (pitboss#444).

Every sequence of up to ``DEPTH`` events of the alphabet (plan and execution
reviews, the three ruling words, a Plan check at a new head, a push, a merge of
main, CI green or red, the pause label, a conflict) is walked from a PR that has
a Plan, an Execution and a clean Plan check. At each state the shipped
``flow.next_step`` is read and the properties are checked; a failure prints the
sequence of events that led to it (keyword: properties).
"""

import time
import unittest
from typing import Callable, Iterator, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import expansion, plandigest, steps
from . import model

DEPTH = 5
SECONDS = 60
Allowed = model.Allowed
Property = Callable[[model.Model, steps.Next, Allowed], str]


def walk(
    allowed: Allowed = model.allowed_once, depth: int = DEPTH
) -> Iterator[tuple[model.Model, Sequence[str]]]:
    """Every state reachable within a depth, with the events that reach it.

    A state reached by two sequences of events is read once, with the first.

    Args:
        allowed: the rule for a ruling.
        depth: the most events.

    Yields:
        Each model and its events.
    """
    seen = {model.key(model.Model())}
    layer = [(model.Model(), ())]
    yield model.Model(), ()
    for _ in range(depth):
        following = []
        for each, path in layer:
            for moved in model.moves(each, allowed):
                key = model.key(moved)
                if key not in seen:
                    seen.add(key)
                    following.append((moved, (*path, moved.last)))
        yield from following
        layer = following


def p1_a_step(at: model.Model, step: steps.Next, allowed: Allowed) -> str:
    """P1: the PR has a step that names an action or an owner.

    Args:
        at: the PR.
        step: its step.
        allowed: the rule for a ruling (unused).

    Returns:
        The finding, empty when the property holds.
    """
    waits = step.step is steps.Step.WAIT_FOR_CI and at.ci != "running"
    nothing = not steps.describe(step).strip() or step.step is steps.Step.WAIT_FOR_UNDRAFT
    return "P1: no step names an action or an owner" if waits or nothing else ""


def p2_ruling_steps(at: model.Model, step: steps.Next, allowed: Allowed) -> str:
    """P2: a ``do these steps`` ruling is the step within one call.

    Args:
        at: the PR, whose last event is considered.
        step: its step.
        allowed: the rule for a ruling (unused).

    Returns:
        The finding, empty when the property holds.
    """
    due = at.last == "ruling do these steps" and not at.paused
    due = due and at.ci == "green" and not at.conflict
    ruled = steps.Task.RULING_STEPS in (step.task,) or step.stage is steps.Stage.RULING_STEPS
    held = step.step in (steps.Step.PLAN_EDITED, steps.Step.WAIT_FOR_OWNER)
    return "P2: the ruling's steps are not the step" if due and not ruled and not held else ""


def p4_one_ruling(at: model.Model, step: steps.Next, allowed: Allowed) -> str:
    """P4: at most one ruling before a pause.

    Args:
        at: the PR.
        step: its step (unused).
        allowed: the rule for a ruling (unused).

    Returns:
        The finding, empty when the property holds.
    """
    return "P4: a second ruling before a pause" if at.since_pause > 1 else ""


def p5_moves(at: model.Model, step: steps.Next, allowed: Allowed) -> str:
    """P5: the printed step, simulated, moves the state to another step.

    Args:
        at: the PR.
        step: its step.
        allowed: the rule for a ruling.

    Returns:
        The finding, empty when the property holds.
    """
    after = model.simulated(at, step, allowed)
    if after is None:
        return ""
    return "P5: the step leaves the PR at the same step" if model.step_of(after) == step else ""


PROPERTIES: Sequence[Property] = (p1_a_step, p2_ruling_steps, p4_one_ruling, p5_moves)


def violations(
    checks: Sequence[Property],
    allowed: Allowed = model.allowed_once,
    depth: int = DEPTH,
) -> Sequence[str]:
    """The sequences that break a property, with the finding.

    Args:
        checks: the properties, all read at each state (its step is read once).
        allowed: the rule for a ruling.
        depth: the most events.

    Returns:
        A line for each, ``finding after: event, event``.
    """
    found = []
    for at, path in walk(allowed, depth):
        step = model.step_of(at)
        for check in checks:
            said = check(at, step, allowed)
            if said:
                found.append(f"{said} after: {', '.join(path) or 'no event'}")
    return found


def never(at: model.Model) -> bool:
    """A rule that lets every ruling through (the planted violation of P4).

    Args:
        at: the PR (unused).

    Returns:
        True.
    """
    return True


class TestProperties(unittest.TestCase):
    """The properties, and each one failing when its violation is planted."""

    def test_properties_hold_to_depth_5_in_under_a_minute(self) -> None:
        """P1, P2, P4 and P5 hold on every sequence, within the time."""
        started = time.monotonic()
        found = violations(PROPERTIES)
        elapsed = time.monotonic() - started
        for line in found[:20]:
            print(line)
        print(f"properties: {len(found)} violations, {elapsed:.1f}s")
        assert_that(found, equal_to([]))
        assert_that(elapsed < SECONDS, equal_to(True))

    def test_a4_p1_every_pr_has_a_step_to_depth_3(self) -> None:
        """A4: no state of the alphabet, to depth 3, is a PR with nothing to do."""
        assert_that(violations([p1_a_step], model.allowed_once, 3), equal_to([]))

    def test_a2_p2_ruling_steps_hold_to_depth_4(self) -> None:
        """A2: after a `do these steps` ruling the step is the ruling's, to depth 4."""
        assert_that(violations([p2_ruling_steps], model.allowed_once, 4), equal_to([]))

    def test_properties_p4_planted_second_ruling_fails_printing_the_sequence(
        self,
    ) -> None:
        """P4 planted: a rule that lets a second ruling through fails, with its events."""
        found = violations([p4_one_ruling], never, 3)
        assert_that(len(found) > 0, equal_to(True))
        assert_that(found[0], contains_string("P4: a second ruling before a pause after: ruling"))

    def test_properties_p4_the_shipped_rule_refuses_the_second(self) -> None:
        """The nearest input: with the rule, the same depth has no violation."""
        assert_that(violations([p4_one_ruling], model.allowed_once, 3), equal_to([]))

    def test_properties_p1_planted_a_pr_with_no_step_fails(self) -> None:
        """P1 planted: a step that waits for a CI that is not running fails."""
        waiting = steps.wait_for_ci()
        green = model.Model()
        assert_that(p1_a_step(green, waiting, model.allowed_once), contains_string("P1"))
        assert_that(p1_a_step(green, steps.merge(), model.allowed_once), equal_to(""))

    def test_properties_p2_planted_another_step_after_the_ruling_fails(self) -> None:
        """P2 planted: after a `do these steps` ruling a merge step fails."""
        ruled = model.ruled(model.Model(), model.Ruling.DO_THESE_STEPS, model.allowed_once)
        assert ruled is not None
        assert_that(p2_ruling_steps(ruled, steps.merge(), model.allowed_once), contains_string("P2"))
        assert_that(
            p2_ruling_steps(ruled, steps.worker(steps.Task.RULING_STEPS), model.allowed_once),
            equal_to(""),
        )

    def test_properties_p5_planted_a_step_that_changes_nothing_fails(self) -> None:
        """P5 planted: simulating a step that leaves the step the same fails."""
        start = model.Model()
        step = model.step_of(start)
        stuck = model.step_of(model.simulated(start, step, model.allowed_once) or start)
        assert_that(stuck == step, equal_to(False))
        same = steps.worker(steps.Task.RESOLVE_CONFLICT)
        conflicted = model.Model(conflict=True)
        assert_that(model.step_of(conflicted), equal_to(same))
        after = model.simulated(conflicted, same, model.allowed_once)
        assert after is not None
        assert_that(model.step_of(after) == same, equal_to(False))


URLS = "https://github.com/o/r/actions/runs/{run}/job/{job}"
PLAN = "1. `cmd` shows it. CI: workflow `w.yml`, job `tests`, step `Run`, see {url}\n"


def at_head(run: int) -> str:
    """A Plan section whose CI pointer names the run of a head.

    Args:
        run: the run's id.

    Returns:
        The section.
    """
    return "## Plan\n" + PLAN.format(url=URLS.format(run=run, job=run + 1))


class TestPlanDigest(unittest.TestCase):
    """P3: a Plan check at a later head leaves an approved Plan's digest unchanged."""

    def test_properties_p3_the_run_ids_of_a_later_head_keep_the_digest(self) -> None:
        """Each head's run and job ids give the digest the approval recorded."""
        approved = expansion.section_digest(plandigest.section(f"Fixes #1\n\n{at_head(10)}"))
        for run in (11, 12, 99999):
            body = f"Fixes #1\n\n{at_head(run)}"
            assert_that(expansion.section_digest(plandigest.section(body)), equal_to(approved))

    def test_properties_p3_planted_an_id_in_the_digest_fails(self) -> None:
        """P3 planted: a digest that reads the ids (main's) changes at a later head."""
        first = expansion.text_digest(plandigest.section(f"Fixes #1\n\n{at_head(10)}"))
        later = expansion.text_digest(plandigest.section(f"Fixes #1\n\n{at_head(11)}"))
        assert_that(first == later, equal_to(False))

    def test_properties_p3_another_word_in_the_plan_changes_the_digest(self) -> None:
        """The nearest input: a changed word is an edit, whatever the ids."""
        body = f"Fixes #1\n\n{at_head(10)}".replace("shows it", "shows that")
        approved = expansion.section_digest(plandigest.section(f"Fixes #1\n\n{at_head(10)}"))
        assert_that(
            expansion.section_digest(plandigest.section(body)) == approved, equal_to(False)
        )
