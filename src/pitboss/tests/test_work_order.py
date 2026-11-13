"""The strict work order: unlabeled tickets first, then the order (pitboss#94)."""

import re
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to, starts_with

from .. import unlabeled
from . import fakes, quietworld, world, worldcomments
from .test_commands import sweep
from .test_slot_commands import next_output

OPEN = "issues?state=open"
OLDER_PULL = "2026-09-15T00:00:00+00:00"
RULE_LINE = unlabeled.RULE
NEXT_STEP = re.compile(r"^NEXT \d+ of \d+\. [A-Z]+: (\S+): ", re.MULTILINE)


def _ticket(number: int, created: str, *labels: str) -> Mapping[str, object]:
    return {
        "number": number,
        "title": f"Ticket {number}",
        "created_at": created,
        "labels": [{"name": label} for label in labels],
    }


URGENT = [_ticket(10, "2026-09-02T00:00:00+00:00", "urgent"), world.TICKET]
LOW = [_ticket(12, "2026-08-01T00:00:00+00:00", "low")]
UNLABELED = [
    _ticket(13, "2026-09-05T00:00:00+00:00", "bug"),
    _ticket(11, "2026-09-03T00:00:00+00:00"),
]
LIBRARY_URGENT = [_ticket(16, "2026-09-01T12:00:00+00:00", "urgent")]
LIBRARY_OPEN = [
    _ticket(14, "2026-07-01T00:00:00+00:00", "enhancement"),
    _ticket(15, "2026-06-01T00:00:00+00:00", "p3"),
    *LIBRARY_URGENT,
]
SEARCH = "search/issues?q=user:owner+is:issue+is:open+-label:urgent+-label:low"
API = "https://api.github.com/repos/owner"


def _found(
    repository: str, tickets: Sequence[Mapping[str, object]]
) -> Sequence[object]:
    # what the search answers for the tickets of one repository
    return [{**each, "repository_url": f"{API}/{repository}"} for each in tickets]


BODIES = {
    fakes.page(SEARCH): {
        "items": [*_found("project", UNLABELED), *_found("lib", LIBRARY_OPEN[:2])]
    },
    **fakes.bodies_under(
        world.PROJECT,
        [
            (f"{OPEN}&labels=urgent", URGENT),
            (f"{OPEN}&labels=low", LOW),
            (OPEN, [*URGENT, *LOW, *UNLABELED]),
        ],
    ),
    **fakes.bodies_under(
        world.LIBRARY,
        [
            (f"{OPEN}&labels=urgent", LIBRARY_URGENT),
            (f"{OPEN}&labels=low", []),
            (OPEN, LIBRARY_OPEN),
            ("issues/4/comments", [worldcomments.CLEAN_CHECK]),  # no review yet
        ],
    ),
}


def ordered_world() -> world.World:
    """A world with unlabeled tickets in both repositories and two priorities.

    Returns:
        The world: urgent has 9 and 10 and low has 12; tickets 11 and 13 of
        the project and 14 of the library have no priority label, 15 of the
        library has ``p3`` (a priority that is never offered).
    """
    here = world.make_world()
    quietworld.edit_config(
        here, 'priority_labels = ["urgent"', 'priority_labels = ["urgent", "low"'
    )
    here.bodies.update(BODIES)
    # the library's PR is older than the project's: the order is across repositories
    head = {"sha": fakes.HEAD, "ref": "branch-4"}
    older = fakes.pull_body(4, head=head, created_at=OLDER_PULL)
    here.bodies[f"{world.LIBRARY}/pulls/4"] = older
    fakes.listed_row(here.bodies, world.LIBRARY, 4, created_at=OLDER_PULL)
    return here


def listed(output: str) -> Sequence[str]:
    """The item of each ``NEXT`` line of an output, in order.

    Args:
        output: what a command printed.

    Returns:
        The references.
    """
    return [step.group(1) for step in NEXT_STEP.finditer(output)]


def unlabeled_lines(output: str) -> Sequence[str]:
    """The ``NO PRIORITY LABEL`` lines of an output and the rule's line, whole.

    Args:
        output: what a command printed.

    Returns:
        The lines, in order.
    """
    lines = output.splitlines()
    return [x for x in lines if x.startswith(unlabeled.NO_LABEL) or x == RULE_LINE]


# keyword: one-path: the decisions, the open PRs oldest first across repositories,
# then the labelled tickets by priority and age (ticket 9 is PR 1's)
WHOLE_ORDER = [
    "owner/lib#4",
    "owner/project#1",
    "owner/project#3",
    "owner/lib#16",
    "owner/project#10",
]
UNLABELED_LINES = [
    "NO PRIORITY LABEL owner/lib#14",
    "NO PRIORITY LABEL owner/project#11",
    "NO PRIORITY LABEL owner/project#13",
    RULE_LINE,
]


class TestTheWholeOrder(unittest.TestCase):
    """Unlabeled tickets first, the open PRs oldest first, then the priorities."""

    def test_slots_next_prints_the_whole_order(self) -> None:
        """The p3 ticket is labeled; the PRs come before every ticket."""
        assert_that(listed(next_output(ordered_world())), equal_to(WHOLE_ORDER))

    def test_the_list_says_no_unlabeled_ticket(self) -> None:
        """The list is the decisions: no unlabeled line and no rule (one-path)."""
        shown = next_output(ordered_world())
        assert_that(shown, starts_with("NEXT 1 of 5. "))
        assert_that(unlabeled_lines(shown), equal_to([]))

    def test_next_with_no_ticket_prints_it_too(self) -> None:
        """``next`` is what ``slots next`` prints."""
        shown = world.again(ordered_world(), "next", "--now", world.FUTURE)
        assert_that(listed(shown.out), equal_to(WHOLE_ORDER))

    def test_the_sweep_prints_the_unlabeled_ones_before_the_task_list(self) -> None:
        """The sweep names the same tickets and the rule, ahead of its list."""
        swept = sweep(ordered_world()).out.splitlines()
        marked = [at for at, line in enumerate(swept) if unlabeled.NO_LABEL in line]
        task = next(at for at, line in enumerate(swept) if line.startswith("TASK LIST"))
        assert_that(swept[marked[0] : marked[0] + 4], equal_to(UNLABELED_LINES))
        assert_that(marked[-1] < task, equal_to(True))

    def test_no_unlabeled_ticket_prints_neither_line_nor_rule(self) -> None:
        """The default world has every ticket labeled."""
        shown = next_output(world.make_world())
        assert_that(unlabeled.NO_LABEL in shown, equal_to(False))
        assert_that(RULE_LINE in shown, equal_to(False))

    def test_with_no_priority_labels_configured_nothing_is_unlabeled(self) -> None:
        """There is no scheme to label by, so no ticket is called unlabeled."""
        here = ordered_world()
        quietworld.edit_config(
            here, 'priority_labels = ["urgent", "low"', "priority_labels = ["
        )
        assert_that(unlabeled.NO_LABEL in next_output(here), equal_to(False))
        assert_that(unlabeled.NO_LABEL in sweep(here).out, equal_to(False))

    def test_a_label_that_is_no_priority_leaves_the_ticket_unlabeled(self) -> None:
        """``bug`` is no priority; ``p3`` and the configured ``low`` are."""
        shown = sweep(ordered_world()).out
        assert_that(shown, contains_string("NO PRIORITY LABEL owner/project#13"))
        assert_that("owner/lib#15" in shown, equal_to(False))
        assert_that("NO PRIORITY LABEL owner/project#12" in shown, equal_to(False))

    def test_a_full_first_page_with_a_pull_request_pages_on(self) -> None:
        """The issues list holds PRs: 99 tickets and a PR are a full page."""
        here = ordered_world()
        full = [
            _ticket(n, "2026-02-01T00:00:00+00:00", "urgent") for n in range(100, 199)
        ]
        request = {**_ticket(199, "2026-02-01T00:00:00+00:00"), "pull_request": {}}
        here.bodies[fakes.page(f"{world.PROJECT}/{OPEN}")] = [*full, request]
        later = [_ticket(200, "2026-02-01T00:00:00+00:00")]
        here.bodies[fakes.page(f"{world.PROJECT}/{OPEN}", 2)] = later
        found = [each for each in unlabeled_lines(sweep(here).out) if "#200" in each]
        assert_that(found, equal_to(["NO PRIORITY LABEL owner/project#200"]))
