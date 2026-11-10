"""The strict work order: unlabeled tickets first, then the order (pitboss#94)."""

import re
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import unlabeled
from . import fakes, quietworld, world
from .test_commands import sweep
from .test_slot_commands import next_output

OPEN = "issues?state=open"
OLDER_PULL = "2026-09-15T00:00:00+00:00"
RULE_LINE = unlabeled.RULE
NEXT_STEP = re.compile(r"^NEXT (\d+)\. (\S+) ")


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
BODIES = {
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
            ("issues/4/comments", []),  # no review yet: the library PR gets a round
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
    return here


def listed(output: str) -> Sequence[str]:
    """The work order of an output: unlabeled lines, the rule, then the steps.

    Args:
        output: what a command printed.

    Returns:
        The ``NO PRIORITY LABEL`` lines and the rule's line whole, and the
        reference of each ``NEXT`` step after the first.
    """
    found = []
    for line in output.splitlines():
        step = NEXT_STEP.match(line)
        if line.startswith(unlabeled.NO_LABEL) or line == RULE_LINE:
            found.append(line)
        elif step and step.group(1) != "1":
            found.append(step.group(2))
    return found


WHOLE_ORDER = [
    "NO PRIORITY LABEL owner/lib#14",
    "NO PRIORITY LABEL owner/project#11",
    "NO PRIORITY LABEL owner/project#13",
    RULE_LINE,
    "owner/lib#4",
    "owner/project#1",
    "owner/project#3",
    "owner/project#9",
    "owner/lib#16",
    "owner/project#10",
    "owner/project#12",
]


class TestTheWholeOrder(unittest.TestCase):
    """Unlabeled tickets first, the open PRs oldest first, then the priorities."""

    def test_slots_next_prints_the_whole_order(self) -> None:
        """The p3 ticket is labeled; the PRs come before every ticket."""
        assert_that(listed(next_output(ordered_world())), equal_to(WHOLE_ORDER))

    def test_the_unlabeled_lines_come_before_the_first_step(self) -> None:
        """After the slot header, only the unlabeled tickets and the rule."""
        shown = next_output(ordered_world()).splitlines()
        assert_that(shown[0].startswith("SLOTS "), equal_to(True))
        assert_that(shown[6], equal_to(RULE_LINE))
        assert_that(shown[7].startswith("NEXT 1. "), equal_to(True))

    def test_next_with_no_ticket_prints_it_too(self) -> None:
        """``next`` is what ``slots next`` prints."""
        shown = world.again(ordered_world(), "next", "--now", world.FUTURE)
        assert_that(listed(shown.out), equal_to(WHOLE_ORDER))

    def test_the_sweep_prints_the_unlabeled_ones_before_the_task_list(self) -> None:
        """The sweep names the same tickets and the rule, ahead of its list."""
        swept = sweep(ordered_world()).out.splitlines()
        marked = [at for at, line in enumerate(swept) if unlabeled.NO_LABEL in line]
        task = next(at for at, line in enumerate(swept) if line.startswith("TASK LIST"))
        assert_that(swept[marked[0] : marked[0] + 4], equal_to(WHOLE_ORDER[:4]))
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

    def test_a_label_that_is_no_priority_leaves_the_ticket_unlabeled(self) -> None:
        """``bug`` is no priority; ``p3`` and the configured ``low`` are."""
        shown = next_output(ordered_world())
        assert_that(shown, contains_string("NO PRIORITY LABEL owner/project#13"))
        assert_that("owner/lib#15" in shown, equal_to(False))
        assert_that("NO PRIORITY LABEL owner/project#12" in shown, equal_to(False))

    def test_a_full_first_page_with_a_pull_request_pages_on(self) -> None:
        """The issues list holds PRs: 99 tickets and a PR are a full page."""
        here = ordered_world()
        full = [
            _ticket(n, "2026-01-01T00:00:00+00:00", "urgent") for n in range(100, 199)
        ]
        full.append({**_ticket(199, "2026-01-01T00:00:00+00:00"), "pull_request": {}})
        path = f"{world.PROJECT}/{OPEN}"
        here.bodies[fakes.page(path)] = full
        here.bodies[fakes.page(path, 2)] = [_ticket(200, "2026-02-01T00:00:00+00:00")]
        found = [each for each in listed(next_output(here)) if "#200" in each]
        assert_that(found, equal_to(["NO PRIORITY LABEL owner/project#200"]))
