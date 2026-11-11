"""``slots next TICKET`` reads that item alone (keyword: item-brief, pitboss#443).

The order of ``slots next`` was built, every open item of every repository read,
to print the brief of one. The item's own brief is read from the item, its
repository's open PRs and its timeline, and says the place it had in the last
full ``slots next``.
"""

import re
import unittest
from typing import Callable, Mapping, Sequence

from hamcrest import assert_that, equal_to, matches_regexp

from . import (
    fakes,
    quietworld,
    rankworld,
    test_flow_sweep,
    test_holds,
    test_superseded,
    world,
)
from .itemworld import one, with_pull_issues
from .says import says
from .test_slot_commands import next_output, run_all

PULLS = fakes.page("repos/owner/project/pulls?state=open")
TIMELINE = fakes.page("repos/owner/project/issues/9/timeline")
NINTH = "owner/project#9"


def pull_listed(number: int, body: str = "") -> Mapping[str, object]:
    """The raw PR the API lists for the project.

    Args:
        number: its number.
        body: its text.

    Returns:
        The PR with a title, a text and a branch.
    """
    head = {"ref": f"branch-{number}"}
    return {"number": number, "title": f"PR {number}", "body": body, "head": head}


LISTED = [pull_listed(each) for each in (1, 2, 3)]


def prepared(here: world.World) -> world.World:
    """Give ticket 9 the labels the API gives it, and the project its listed PRs.

    Args:
        here: the world.

    Returns:
        The same world.
    """
    rankworld.serve(here, "owner/project", 9, rankworld.ticket())
    here.bodies[PULLS] = LISTED
    return with_pull_issues(here)


def fast_world() -> world.World:
    """A world where ticket 9 has the labels the API gives it.

    Returns:
        The world.
    """
    return prepared(world.make_world())


def refused(here: world.World, reference: str, reason: str) -> None:
    """Require the brief of an item to be refused, on standard error, for a reason.

    Args:
        here: the world.
        reference: the item.
        reason: what standard error says; nothing is printed on standard output.
    """
    found = one(here, reference)
    assert_that((found.code, found.out), equal_to((1, "")))
    says(found.err, reason)


def briefed(here: world.World, reference: str, *words: str) -> str:
    """The brief of an item, printed with a status of 0.

    Args:
        here: the world.
        reference: the item.
        *words: what it says.

    Returns:
        Standard output.
    """
    found = one(here, reference)
    says(found.out, *words)
    assert_that(found.code == 0, "the status is 0")
    return found.out


def lists_asked(here: world.World, before: int) -> Sequence[str]:
    """The lists of issues or PRs asked for since some number of calls.

    Args:
        here: the world.
        before: how many calls were made before.

    Returns:
        The paths of the calls that list issues or PRs.
    """
    paths = [each[-1] for each in here.calls[before:] if "api" in each]
    return [each for each in paths if re.search(r"/(pulls|issues)\?", each)]


class TestTheBrief(unittest.TestCase):
    """What is printed for an item that is offered."""

    def test_no_call_lists_the_items_of_another_repository(self) -> None:
        """The one list asked for is the item's repository's open PRs."""
        here = fast_world()
        next_output(here)
        before = len(here.calls)
        out = briefed(here, NINTH, "start a PR: owner/project#9")
        assert_that(lists_asked(here, before), equal_to([PULLS]))
        place = r"^NEXT 4 of 4, .* \(place from the full slots next of "
        assert_that(out.splitlines()[0], matches_regexp(place))

    def test_the_place_is_unknown_before_a_full_slots_next(self) -> None:
        """No full run, no cache: the line says so and the brief follows."""
        briefed(fast_world(), NINTH, "NEXT place unknown: no full", "start a PR")

    def test_an_item_the_full_run_did_not_list_is_not_placed(self) -> None:
        """Ticket 10 was not in the order of that run."""
        here = fast_world()
        next_output(here)
        rankworld.serve(here, "owner/project", 10, rankworld.ticket(number=10))
        briefed(here, "owner/project#10", "place unknown: owner/project#10")

    def test_a_ticket_the_owner_ranks_needs_no_label(self) -> None:
        """The owner's stated priority is its rank, whatever labels it has."""
        here = fast_world()
        rankworld.serve(here, "owner/project", 9, rankworld.ticket(labels=[]))
        stated = '[slots.owner_priorities]\n"owner/project#9" = "urgent"\n[slots]'
        quietworld.edit_config(here, "[slots]", stated)
        briefed(here, NINTH, "start a PR: owner/project#9")

    def test_a_mention_in_a_plan_does_not_take_the_ticket(self) -> None:
        """The Plan of an open PR names ticket 9, which the PR does not fix."""
        briefed(planned(), NINTH, "start a PR: owner/project#9")

    def test_a_pull_request_is_briefed_by_its_step(self) -> None:
        """A PR at a round gets its brief from the PR alone."""
        here = with_pull_issues(world.make_world())
        briefed(here, "owner/project#1", "resolve the conflict")


def closed() -> world.World:
    """A world where ticket 9 is closed.

    Returns:
        The world.
    """
    here = fast_world()
    rankworld.serve(here, "owner/project", 9, rankworld.ticket(state="closed"))
    return here


def named() -> world.World:
    """A world where a listed PR names ticket 9 in its text.

    Returns:
        The world.
    """
    here = fast_world()
    here.bodies[PULLS] = [pull_listed(4, "Fixes #9")]
    return here


def timeline_of(text: str, **issue: object) -> world.World:
    """A world where the timeline of ticket 9 has a mention by an open PR.

    Args:
        text: the PR's body.
        **issue: more fields of the PR's issue.

    Returns:
        The world.
    """
    here = fast_world()
    found = {"pull_request": {}, "state": "open", "body": text, **issue}
    source = {"issue": found}
    events = [{"event": "labeled"}, {"event": "cross-referenced", "source": source}]
    here.bodies[TIMELINE] = events
    return here


def mentioned() -> world.World:
    """A world where an open PR of another repository fixes ticket 9.

    Returns:
        The world.
    """
    url = "https://api.github.com/repos/other/place"
    return timeline_of("Fixes owner/project#9", repository_url=url)


def fixed_here() -> world.World:
    """A world where an open PR with no repository fixes ticket 9 by a bare number.

    Returns:
        The world.
    """
    return timeline_of("Fixes #9")


def planned() -> world.World:
    """A world where an open PR only mentions ticket 9 in its Plan.

    Returns:
        The world.
    """
    here = timeline_of("Fixes #1\n## Plan\nsee #9", title="a PR")
    events = here.bodies[TIMELINE]
    assert isinstance(events, list)
    fixing = {"body": "Fixes #9", "pull_request": {}}
    for kind in ({"state": "closed"}, {"state": "open", "pull_request": None}):
        issue = {**fixing, **kind}
        if issue["pull_request"] is None:
            del issue["pull_request"]
        events.append({"event": "cross-referenced", "source": {"issue": issue}})
    return here


def held() -> world.World:
    """A world where the owner holds new pull requests of the project.

    Returns:
        The world.
    """
    return prepared(test_holds.held_world(test_holds.PROJECT_TABLE))


def waiting() -> world.World:
    """A world where ticket 9 depends on an open ticket.

    Returns:
        The world.
    """
    here = fast_world()
    rankworld.serve(
        here, "owner/project", 9, rankworld.ticket("Depends on owner/lib#3")
    )
    here.bodies[rankworld.BLOCKER] = rankworld.LIB_THREE
    return here


def superseded() -> world.World:
    """A world where the configuration marks ticket 9 as superseded.

    Returns:
        The world.
    """
    here = fast_world()
    test_superseded.listed(here)
    return here


def unread() -> world.World:
    """A world where PR 1 cannot be read.

    Returns:
        The world.
    """
    here = with_pull_issues(world.make_world())
    world.unread_first(here)
    return here


def at_a_wait() -> world.World:
    """A world where PR 3 is a draft at a pause for the owner.

    Returns:
        The world.
    """
    flow = test_flow_sweep
    rounds = flow.RULED + [flow.graded(flow.CHANGES, None, 4)]
    return with_pull_issues(flow.world_with(rounds, draft=True))


def unlabeled() -> world.World:
    """A world where ticket 50 has no label.

    Returns:
        The world.
    """
    return with_pull_issues(world.make_world())


Build = Callable[[], world.World]
REFUSALS: Sequence[tuple[Build, str, str]] = [
    (closed, NINTH, "it is closed or cannot be read"),
    (fast_world, "#77", "it is closed or cannot be read"),
    (fast_world, "other/place#1", "other/place is not a configured repository"),
    (named, NINTH, "an open PR already works on it"),
    (mentioned, NINTH, "an open PR already works on it"),
    (fixed_here, NINTH, "an open PR already works on it"),
    (held, NINTH, "no new pull requests in owner/project"),
    (waiting, NINTH, "it waits for owner/lib#3"),
    (superseded, NINTH, "it is superseded"),
    (unread, "#1", "the PR cannot be read"),
    (at_a_wait, "owner/project#3", "its step is a wait"),
    (rankworld.dependent_world, "owner/project#3", "its ticket waits"),
    (unlabeled, "owner/project#50", "UNKNOWN: owner/project#50 is not in"),
]


class TestWhatIsNotOffered(unittest.TestCase):
    """The item is refused, on standard error, with the reason."""

    def test_each_reason_is_said(self) -> None:
        """A closed ticket, one an open PR names, a hold, a blocker, a wait."""
        for build, reference, reason in REFUSALS:
            with self.subTest(reason, reference=reference):
                refused(with_pull_issues(build()), reference, reason)

    def test_a_ticket_a_slot_works_on(self) -> None:
        """A running agent holds it."""
        here = fast_world()
        run_all(here, [("set", "tiny", "agent-1", "#9", "--running", "agent-1")])
        words = (
            "slots",
            "next",
            "--config",
            here.config,
            NINTH,
            "--running",
            "agent-1",
        )
        found = world.invoke(here, *words, "--now", world.FUTURE)
        says(found.err, "a slot already works on it")

    def test_a_ticket_is_at_no_review(self) -> None:
        """``--step review`` refuses a ticket with no PR, and says the rule."""
        for build, reference, why in (
            (fast_world, NINTH, "its step is `start a PR`"),
            (unlabeled, "owner/project#50", "a ticket with no PR"),
        ):
            with self.subTest(reference):
                found = one(build(), reference, "--step", "review")
                says(found.err, "UNKNOWN", why, "--step review prints")
                assert_that((found.out, found.code), equal_to(("", 1)))

    def test_an_item_that_is_not_offered_is_refused_as_without_the_step(self) -> None:
        """``--step review`` keeps the reason ``slots next`` gives for it."""
        found = one(closed(), NINTH, "--step", "review")
        says(found.err, "it is closed or cannot be read")
        assert_that((found.out, found.code), equal_to(("", 1)))
