"""Tests for a PR that waits for another PR or a ticket (keyword: blocked-by)."""

import re
import unittest
from typing import Mapping

from hamcrest import assert_that, contains_string, equal_to

from .. import blockedform
from . import fakes, world
from .test_shared_red import PROJECT, offers, put_pull, shared_world
from .test_slot_commands import next_output

BEFORE = "2026-10-01T09:00:00Z"
AFTER = "2026-10-01T11:00:00Z"
FIX = "WORKER: owner/project#3: fix CI on the head"
CORRECT = "WORKER: owner/project#{n}: correct the Blocked-by lines"
MERGE_BASE = "WORKER: owner/project#3: the blockers merged"
NAMED = re.compile(r"^NEXT \d+ of \d+\. [A-Z]+: (\S+):", re.MULTILINE)


def issue(state: str, body: str = "", merged: str = "") -> Mapping[str, object]:
    """A blocker as ``issues/N`` gives it.

    Args:
        state: ``open`` or ``closed``.
        body: its text.
        merged: when it merged, else empty.

    Returns:
        The JSON.
    """
    pull = {"merged_at": merged} if merged else {}
    return {"state": state, "title": "blocker", "body": body, "pull_request": pull}


def declare(here: world.World, number: int, line: str) -> None:
    """Give a red PR a body with a Plan, an Execution and a dependency line.

    Args:
        here: the world.
        number: the PR.
        line: the lines to add to the body.
    """
    head = {"sha": str(number) * 40, "ref": f"branch-{number}"}
    body = f"{fakes.PLAN_AND_EXECUTION}\n{line}"
    here.bodies[f"{PROJECT}/pulls/{number}"] = fakes.pull_body(
        number, body=body, head=head, mergeable_state="behind"
    )


def blocked_world(body: str, others: Mapping[int, Mapping[str, object]]) -> world.World:
    """A world whose red PR 3 has a body, and the issues the blockers are.

    Args:
        body: PR 3's body.
        others: the issue JSON of each blocker by number.

    Returns:
        The world.
    """
    here = shared_world({3: "boom"})
    declare(here, 3, body)
    for number, found in others.items():
        here.bodies[f"{PROJECT}/issues/{number}"] = found
    return here


def in_no_answer(
    body: str,
    others: Mapping[int, Mapping[str, object]],
    extra: Mapping[str, object] | None = None,
) -> bool:
    """Whether ``slots next`` gives PR 3 no decision.

    Args:
        body: PR 3's body.
        others: the issue JSON of each blocker by number.
        extra: more bodies of the world.

    Returns:
        True when no ``NEXT`` line names it.
    """
    here = blocked_world(body, others)
    here.bodies.update(extra or {})
    return "owner/project#3" not in NAMED.findall(next_output(here))


class TestShapes(unittest.TestCase):
    """What a PR does for each state of its blocker."""

    def test_c21_an_open_blocker_is_in_no_answer_and_the_fix_is_not_offered(
        self,
    ) -> None:
        """quire#1116: the CI fix is not offered while quire#1110 is open."""
        here = blocked_world("Blocked-by: #110", {110: issue("open")})
        text = next_output(here)
        assert_that(
            [FIX in text, "UNKNOWN" in text, offers(text, FIX)],
            equal_to([False, False, []]),
        )
        assert_that(
            in_no_answer("Blocked-by: #110", {110: issue("open")}), equal_to(True)
        )

    def test_c21_a_blocker_of_another_repository_is_waited_for_too(self) -> None:
        """A relock waiting for a package publish is in no answer (one-path)."""
        lib = {"repos/owner/lib/issues/4": issue("open")}
        assert_that(in_no_answer("Blocked-by: owner/lib#4", {}, lib), equal_to(True))

    def test_c21_a_blocker_that_merged_after_the_red_check_calls_for_the_merge(
        self,
    ) -> None:
        """The decision is to merge the base and push, so CI runs again."""
        here = blocked_world("Blocked-by: #110", {110: issue("closed", "", AFTER)})
        text = next_output(here)
        assert_that([MERGE_BASE in text, FIX in text], equal_to([True, False]))

    def test_c21_a_blocker_that_merged_before_the_red_check_changes_nothing(
        self,
    ) -> None:
        """The red is not the blocker's: the CI fix stays."""
        here = blocked_world("Blocked-by: #110", {110: issue("closed", "", BEFORE)})
        text = next_output(here)
        assert_that([FIX in text, MERGE_BASE in text], equal_to([True, False]))

    def test_c21_a_blocker_closed_unmerged_or_unreadable_is_corrected(
        self,
    ) -> None:
        """The author corrects the line; nothing waits for a blocker that is gone."""
        for label, others in (("closed", {110: issue("closed")}), ("unread", {})):
            with self.subTest(label):
                here = blocked_world("Blocked-by: #110", others)
                assert_that(next_output(here), contains_string(CORRECT.format(n=3)))

    def test_c21_a_loop_is_refused_by_name_and_does_not_hang(self) -> None:
        """A blocked by B blocked by A: both are told to correct the lines."""
        mutual = {
            5: issue("open", "Blocked-by: #3"),
            3: issue("open", "Blocked-by: #5"),
        }
        here = blocked_world("Blocked-by: #5", mutual)
        put_pull(here, 5, "boom")
        declare(here, 5, "Blocked-by: #3")
        text = next_output(here)
        assert_that(
            [CORRECT.format(n=n) in text for n in (3, 5)], equal_to([True, True])
        )

    def test_c21_a_chain_with_no_way_back_and_a_self_reference_are_no_loop(
        self,
    ) -> None:
        """A blocker that waits for a third, and a PR that names itself."""
        chain = {110: issue("open", "Blocked-by: #111"), 111: issue("open")}
        body = "Blocked-by: #110\nBlocked-by: #3"
        assert_that(in_no_answer(body, chain), equal_to(True))

    def test_c21_two_blockers_that_share_a_third_are_no_loop(self) -> None:
        """A diamond reads the shared blocker once and finds no way back."""
        diamond = {
            110: issue("open", "Blocked-by: #111\nBlocked-by: #112"),
            111: issue("open", "Blocked-by: #113"),
            112: issue("open", "Blocked-by: #113"),
            113: issue("open"),
        }
        assert_that(in_no_answer("Blocked-by: #110", diamond), equal_to(True))

    def test_c21_a_chain_longer_than_the_limit_ends(self) -> None:
        """No more than LIMIT blockers are read looking for a loop."""
        long = {n: issue("open", f"Blocked-by: #{n + 1}") for n in range(110, 190)}
        assert_that(in_no_answer("Blocked-by: #110", long), equal_to(True))


class TestForm(unittest.TestCase):
    """The one form of the line."""

    def test_c21_only_the_form_is_a_dependency_line(self) -> None:
        """A line that starts like a dependency and is not the form is a finding."""
        good = ["Blocked-by: #12", "Blocked-by: o/r#12", "prose, blocked by #3"]
        bad = [
            "Blocked by #12",
            "blocked-by: #12",
            "Blocked-by: 12",
            "Blocked-by: #1, #2",
        ]
        found = [bool(blockedform.findings("body", row)) for row in (*good, *bad)]
        assert_that(found, equal_to([False] * len(good) + [True] * len(bad)))
        assert_that(
            blockedform.findings("body", "Blocked by #12")[0].endswith("(blocked-by)"),
            equal_to(True),
        )
