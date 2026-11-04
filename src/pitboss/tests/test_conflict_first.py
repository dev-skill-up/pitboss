"""A conflicted PR is the worker's, whatever its stage (pitboss#148).

The cause, found with data: ``flow.next_step`` returned ``RESOLVE_CONFLICT``
only once the execution was approved. A dirty head runs no CI (its checks are
empty or red) and a draft waits for its Plan review, so the draft gate and the
CI gate answered first: ``slots next`` read the PR as waiting for CI, as a
draft's review or as a red CI's fix, never as a conflict, while the sweep
printed ``CONFLICT`` for it from the merge state alone (the merge state read
was right; the flow step was wrong).
"""

import re
import unittest
from typing import AbstractSet, Sequence

from hamcrest import assert_that, contains_string, equal_to

from . import fakes, world
from .test_commands import sweep
from .test_slot_commands import next_output

PROJECT = world.PROJECT
SLUG = "owner/project"
CONFLICT_LINE = re.compile(r"^CONFLICT (\S+#\d+):", re.MULTILINE)
RESOLVE_LINE = re.compile(
    r"^NEXT \d+\. (\S+#\d+) \(resolve the conflict,", re.MULTILINE
)
NEXT_LINE = re.compile(r"^NEXT \d+\. (\S+#\d+) \((.*?),", re.MULTILINE)


def make_dirty(
    here: world.World,
    number: int,
    created_at: str,
    checks: Sequence[object],
    **changes: object,
) -> None:
    """Make a PR of ``owner/project`` conflicted, with the checks of its head.

    Args:
        here: the world.
        number: the PR.
        created_at: when it was opened.
        checks: the check runs of its head.
        **changes: other changes to its JSON.
    """
    head = str(number) * 40
    branch = {"sha": head, "ref": f"branch-{number}"}
    here.bodies[f"{PROJECT}/pulls/{number}"] = fakes.pull_body(
        number,
        head=branch,
        mergeable_state="dirty",
        created_at=created_at,
        **changes,
    )
    answers = {
        f"commits/{head}/check-runs": {"check_runs": list(checks)},
        f"commits/{head}/status": fakes.NO_STATUS,
        f"issues/{number}/comments": [],
        f"pulls/{number}/reviews": [],
    }
    for each, body in answers.items():
        here.bodies[fakes.page(f"{PROJECT}/{each}")] = body


def both_sets(here: world.World) -> tuple[AbstractSet[str], AbstractSet[str]]:
    """The PRs the sweep prints CONFLICT for, and ``slots next`` resolves.

    Args:
        here: the world.

    Returns:
        The two sets of references.
    """
    swept = set(CONFLICT_LINE.findall(sweep(here).out))
    return swept, set(RESOLVE_LINE.findall(next_output(here)))


def assert_sets(
    here: world.World, swept: AbstractSet[str], resolved: AbstractSet[str]
) -> None:
    """Assert the PRs the sweep prints CONFLICT for, and ``slots next`` resolves.

    Args:
        here: the world.
        swept: the references the sweep prints CONFLICT for.
        resolved: the references ``slots next`` lists as resolve the conflict.
    """
    found = both_sets(here)
    assert_that(found, equal_to((swept, resolved)))


def conflicted_world() -> world.World:
    """Open PRs that are all dirty and have no review, and others that are not.

    PR 1 has a red check, PR 2 is a draft with no check, PR 3 has no check
    run (a dirty head runs no CI) and a green PR 4 of the library is clean.

    Returns:
        The world.
    """
    here = world.make_world()
    make_dirty(here, 1, "2026-10-01T00:00:00+00:00", [world.RED])
    make_dirty(here, 2, "2026-09-01T00:00:00+00:00", [], draft=True)
    make_dirty(here, 3, "2026-08-01T00:00:00+00:00", [])
    return here


class TestConflictFirst(unittest.TestCase):
    """The sweep and ``slots next`` agree on the PRs with a conflict."""

    def test_a_dirty_pr_with_no_review_is_a_resolve_the_conflict_line(self) -> None:
        """Whatever its checks and draft state say, each gets its own line."""
        listed = next_output(conflicted_world())
        for number in (1, 2, 3):
            assert_that(
                listed,
                contains_string(f"owner/project#{number} (resolve the conflict,"),
            )

    def test_the_sweep_and_slots_next_agree_on_the_conflicted_pull_requests(
        self,
    ) -> None:
        """One fixture of PRs: the CONFLICT set is the resolve-the-conflict set."""
        every = {f"{SLUG}#{number}" for number in (1, 2, 3)}
        assert_sets(conflicted_world(), every, every)

    def test_they_come_before_any_ticket_and_the_oldest_first(self) -> None:
        """Every conflicted PR precedes every other line, by when it was opened."""
        found = NEXT_LINE.findall(next_output(conflicted_world()))
        kinds = [(reference, kind) for reference, kind in found]
        assert_that(
            kinds[:3],
            equal_to(
                [
                    ("owner/project#3", "resolve the conflict"),
                    ("owner/project#2", "resolve the conflict"),
                    ("owner/project#1", "resolve the conflict"),
                ]
            ),
        )
        later = [kind for _, kind in kinds[3:]]
        assert_that("resolve the conflict" in later, equal_to(False))

    def test_a_clean_pr_is_not_listed_for_a_conflict(self) -> None:
        """Only the default world's dirty PR 1 is in both sets."""
        assert_sets(world.make_world(), {f"{SLUG}#1"}, {f"{SLUG}#1"})
