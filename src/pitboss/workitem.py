"""One thing a worker could start, and the kinds of work (keyword: work-order).

Kept apart from ``work``, which orders items, so that the modules that only build
an item from a ticket need not depend on the reading of every PR (pitboss#443).
"""

import dataclasses
import enum
from typing import AbstractSet, Protocol, Sequence


class Category(enum.IntEnum):
    """The kinds of work: a label on a line, never a rank among the open PRs.

    Attributes:
        FIX_REVIEW: an author fixes what a review asked for (a PR).
        REVISE_PLAN: an author revises a Plan no review approved, nothing else (a PR).
        REVIEW: a reviewer (never the author) reviews a green head, or a
            Plan alone (a draft's, or revised after its rejection) (a PR).
        NEW_PR: a worker starts a ticket (after every PR).
        FIX_CI: an author fixes a red CI, which is no rejection (a PR).
        FIRST_ROUND: an author writes the Plan and Execution body of a PR (a PR).
        RESOLVE_CONFLICT: an author resolves the conflict of a head, at any
            stage except while it waits for a ruling, the owner or the restoring
            of an edited approved Plan (a PR).
        RULING_STEPS: an author does exactly the steps of an Opus ruling (a PR).
        RULING_AS_GIVEN: an author carries out an Opus ruling that splits,
            reshapes or abandons (a PR).
        REVIEW_FIX_ROUND: a reviewer checks the findings of a review that
            asked for changes at an older head, which differs from the current
            one (a PR; keyword: fix-round).
        RUN_PLAN: an author runs the commands of a Plan that was approved alone
            after a ruling and fills the Execution (a PR; keyword: plan-alone).
        ADD_CI_QUOTES: an author adds the CI quotes the Plan names to the body of
            a ready PR whose checks passed (a PR; keyword: ci-quotes).
        WAITING: a PR that is offered for no round (it waits, or its step is a
            ruling, a merge or an undraft) and whose ticket is blocked by an open
            ticket: it is only listed as blocked (keyword: blocked-pull,
            pitboss#388).
    """

    FIX_REVIEW = 1
    REVISE_PLAN = 2
    REVIEW = 4
    NEW_PR = 5
    FIX_CI = 6
    FIRST_ROUND = 7
    RESOLVE_CONFLICT = 8
    RULING_STEPS = 9
    RULING_AS_GIVEN = 10
    REVIEW_FIX_ROUND = 11
    RUN_PLAN = 12
    ADD_CI_QUOTES = 13
    WAITING = 14


CATEGORY_WORDS = {
    Category.WAITING: "wait for the ticket it depends on",
    Category.FIX_REVIEW: "fix the review",
    Category.REVISE_PLAN: "revise the plan",
    Category.REVIEW: "review it (a reviewer that is not its author)",
    Category.REVIEW_FIX_ROUND: "review the fix round's findings only",
    Category.NEW_PR: "start a PR",
    Category.FIX_CI: "fix the CI (a red CI is no rejection)",
    Category.FIRST_ROUND: "write the Plan and Execution body",
    Category.RESOLVE_CONFLICT: "resolve the conflict",
    Category.RULING_STEPS: "do the ruling's steps",
    Category.RULING_AS_GIVEN: "carry out the ruling",
    Category.RUN_PLAN: "run the Plan's commands and fill the Execution",
    Category.ADD_CI_QUOTES: "add the CI quotes to the body",
}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Item:
    """One thing a worker could start.

    Attributes:
        category: its kind.
        reference: its ``owner/name#number``.
        created_at: when the PR or ticket was opened (ISO 8601).
        title: its title.
        priority: the index of its priority label, the owner's if stated (0 for PRs).
        labels: its labels.
        body: a ticket's text, to look for a blocker in; for a PR at ``FIX_CI``
            whose red ``canonical-files`` asks for a line of the allowlist, that
            line (keyword: allowlist-miss, pitboss#448).
        comments: how many comments a ticket has.
        blockers: the open tickets and PRs a ticket says it cannot be worked on
            until (keyword: ticket-blocked), also for a PR whose ticket says it
            (keyword: blocked-pull, pitboss#388).
        ticket: the ticket a PR fixes, or "".
    """

    category: Category
    reference: str
    created_at: str
    title: str
    priority: int = 0
    labels: AbstractSet[str] = frozenset()
    body: str = ""
    comments: int = 0
    blockers: Sequence[str] = ()
    ticket: str = ""


class Described(Protocol):
    """What a ticket says about itself, as ``shapes.Issue`` and ``Ticket`` do."""

    @property
    def created_at(self) -> str:
        """When it was opened (ISO 8601).

        Returns:
            The time.
        """

    @property
    def title(self) -> str:
        """Its title.

        Returns:
            The title.
        """

    @property
    def labels(self) -> AbstractSet[str]:
        """Its labels.

        Returns:
            The names.
        """

    @property
    def body(self) -> str:
        """Its text.

        Returns:
            The text.
        """

    @property
    def comments(self) -> int:
        """How many comments it has.

        Returns:
            The count.
        """


def of_ticket(reference: str, issue: Described, priority: int = 0) -> Item:
    """An open ticket, as the item it is queued as.

    Args:
        reference: its ``owner/name#number``.
        issue: the ticket.
        priority: the index of its priority label.

    Returns:
        The item.
    """
    return Item(
        category=Category.NEW_PR,
        reference=reference,
        created_at=issue.created_at,
        title=issue.title,
        priority=priority,
        labels=issue.labels,
        body=issue.body,
        comments=issue.comments,
    )
