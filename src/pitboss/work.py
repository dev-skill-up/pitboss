"""What to start next: one sorted list, and which empty slot takes what.

The order (work-order): the open PRs that need work come first, in one list,
oldest first, whatever each needs. What a PR needs is the step ``flow.next_step``
gives it (keyword: review-flow): a worker's round, whose kind is its task (a
revision of the plan and nothing else, a fix of the CI, the Plan and Execution
body, the resolution of a conflict, a fix of a review, or CI quotes), or a review
by a new reviewer (a draft's plan-only review included). The kind is a label on
the line, not a rank. A PR whose step is to wait (for CI, an undraft or the
owner), to ask Opus for a ruling, to pause for the owner, to undraft or to merge
is none of them: it is offered for no round. After them come the new PRs, one for
each open ticket with a priority label that no open PR fixes, by priority label
(the owner's if stated), then oldest first. Nothing predicts which files a ticket
will touch: work is taken in this order, every PR starts from the base branch, and
a conflict is resolved by merging the base branch in.
"""

import dataclasses
from typing import AbstractSet, Iterable, Mapping, Sequence

from . import (
    concurrently,
    config,
    ghapi,
    issuelist,
    ledger,
    pullnames,
    pulls,
    reviews,
    shapes,
    slotheld,
    steps,
    workitem,
)

Category = workitem.Category
CATEGORY_WORDS = workitem.CATEGORY_WORDS
Item = workitem.Item


def pull_items(facts: Iterable[pulls.PullFacts]) -> Sequence[Item]:
    """The fixes and reviews the open PRs need, as their steps say.

    Args:
        facts: the open PRs.

    Returns:
        The items.
    """
    return [
        Item(
            category=category,
            reference=pulls.reference(pull),
            created_at=pull.pull.created_at,
            title=pull.pull.title,
        )
        for pull in facts
        if (category := category_of(pull)) is not None
    ]


REVIEWS = frozenset({Category.REVIEW, Category.RELOCK_REVIEW})
CATEGORY_OF_TASK: Mapping[steps.Task | None, Category] = {
    steps.Task.REVISE_PLAN: Category.REVISE_PLAN,
    steps.Task.FIX_CI: Category.FIX_CI,
    steps.Task.FIRST_ROUND: Category.FIRST_ROUND,
    steps.Task.RESOLVE_CONFLICT: Category.RESOLVE_CONFLICT,
    steps.Task.RULING_STEPS: Category.RULING_STEPS,
    steps.Task.RULING_AS_GIVEN: Category.RULING_AS_GIVEN,
    steps.Task.RUN_PLAN: Category.RUN_PLAN,
    steps.Task.ADD_CI_QUOTES: Category.ADD_CI_QUOTES,
}


def category_of(pull: pulls.PullFacts) -> Category | None:
    """The kind of round a PR is offered for, from its step alone.

    Args:
        pull: the PR.

    Returns:
        The category, or None when its step is offered for no round.
    """
    step = pull.step
    if step.step is steps.Step.WORKER:
        return CATEGORY_OF_TASK.get(step.task, Category.FIX_REVIEW)
    # review-flow: the step alone decides, so ``next`` and ``slots next`` agree
    if step.step is not steps.Step.REGULAR_REVIEW:
        return None
    alone = step.stage is steps.Stage.PLAN_ONLY  # keyword: plan-review-listed
    fixing = fix_round(pull) and not alone
    if pull.relock:
        return Category.RELOCK_REVIEW  # keyword: relock-last (B9)
    return Category.REVIEW_FIX_ROUND if fixing else Category.REVIEW


def fix_round(pull: pulls.PullFacts) -> bool:
    """Whether the newest review asked for changes and the head moved since.

    Only then the review has two different heads to diff (keyword: fix-round,
    pitboss#294): a body edited at one head, or an approval, is no fix round.

    Args:
        pull: the PR.

    Returns:
        True when the newest review says changes needed and names an older head.
    """
    found = pull.review
    asked = found is not None and found.verdict is reviews.Verdict.CHANGES_NEEDED
    return asked and pull.standing is reviews.Standing.OLDER_HEAD


def taken(facts: Iterable[pulls.PullFacts]) -> AbstractSet[str]:
    """The tickets open PRs already work on.

    A PR works on a ticket (keyword: taken) only when its title or body fixes
    it with a ``Fixes`` or ``Closes`` form, or its branch ends in the ticket's
    number (``pullnames.names``); a mention elsewhere, in a Plan or an
    Evidence block, names none.

    Args:
        facts: the open PRs.

    Returns:
        The tickets' references.
    """
    return frozenset().union(
        *(
            pullnames.names(
                each.pull.title, each.pull.body, each.pull.head.branch, each.repo
            )
            for each in facts
        )
    )


def ticket_items(
    github: ghapi.GitHub, settings: config.Config, in_progress: AbstractSet[str]
) -> Sequence[Item]:
    """The open tickets with a priority label that no open PR fixes.

    Args:
        github: the API.
        settings: the configuration.
        in_progress: the tickets open PRs already work on.

    Returns:
        The items.
    """
    found: dict[str, Item] = {}
    for item in _labelled(github, settings):
        if item.reference not in in_progress:
            found.setdefault(item.reference, item)
    return list(found.values())


def _labelled(github: ghapi.GitHub, settings: config.Config) -> Iterable[Item]:
    ranked = list(enumerate(settings.slots.priority_labels))
    asked = [
        (repo, priority, label)
        for repo in config.repositories(settings)
        for priority, label in ranked
    ]

    def read(look: tuple[config.Repo, int, str]) -> Sequence[shapes.Issue]:
        repo, _, label = look
        path = f"repos/{repo.slug}/issues?state=open&labels={label}"
        return list(filter(None, ghapi.pages(github, path, issuelist.listed)))

    for (repo, priority, _), found in zip(asked, concurrently.each(read, asked)):
        for issue in found:
            yield workitem.of_ticket(f"{repo.slug}#{issue.number}", issue, priority)


def ordered(items: Iterable[Item], held: Iterable[str]) -> Sequence[Item]:
    """Sort the items, leaving out what a slot already holds.

    Args:
        items: the items.
        held: the references slots hold.

    Returns:
        The items, first to take first: every open PR, oldest first, then
        the tickets by priority label (the owner's if stated), oldest first,
        then the reviews of relock PRs (B9, keyword: relock-last).
    """
    holding = frozenset(held)
    return sorted(
        (item for item in items if item.reference not in holding),
        key=lambda item: (
            item.category is Category.RELOCK_REVIEW,
            item.category is Category.NEW_PR,
            item.priority,
            item.created_at,
        ),
    )


def smallest_model(
    item: Item, slots: config.Slots, failed: Mapping[str, Sequence[str]]
) -> str | None:
    """The smallest model the item may go to.

    Args:
        item: the item.
        slots: the slot configuration.
        failed: each reference's failed models.

    Returns:
        The model, or None when every model has failed it.
    """
    floors = [
        slots.models.index(model)
        for label, model in slots.model_labels.items()
        if label in item.labels and model in slots.models
    ]
    tried = frozenset(failed.get(item.reference, ()))
    for model in slots.models[max(floors, default=0) :]:
        if model not in tried:
            return model
    return None


Assignment = tuple[ledger.Slot, Item | None]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Offered:
    """The work that is queued, and the tickets that are kept back.

    Attributes:
        items: the ordered items to start.
        held: the tickets of held repositories, in the same order.
        standing: each held repository and its open count.
        blocked: the tickets that say they cannot be worked on until a ticket
            or PR that is open, in the same order (keyword: ticket-blocked).
        occupancy: what holds the slots (keyword: slot-held, pitboss#291).
        superseded: the tickets marked as superseded, which are not offered
            (keyword: superseded-ticket, pitboss#388).
        promoted: the ``PROMOTE`` lines (keyword: promote).
        blocks: the references that wait for each dependency that was offered
            ahead of them (keyword: blocks-line).
        labels: the ``priority_labels``, for the lines about the rank.
        unread: whether tickets beyond the window that was read are queued, so
            that the order ends where the window does (keyword: ticket-window,
            pitboss#443).
    """

    items: Sequence[Item]
    held: Sequence[Item]
    standing: Mapping[str, int]
    blocked: Sequence[Item]
    occupancy: slotheld.Occupancy = slotheld.UNLIMITED
    superseded: Sequence[Item] = ()
    promoted: Sequence[str] = ()
    blocks: Mapping[str, Sequence[str]] = dataclasses.field(default_factory=dict)
    labels: Sequence[str] = ()
    unread: bool = False


def queued(
    found: Sequence[pulls.Read],
    github: ghapi.GitHub,
    settings: config.Config,
    book: ledger.Ledger,
) -> Sequence[Item]:
    """The work that is queued: PRs and tickets, in the order to start them.

    A PR that could not be read may work on any ticket, so while one exists no
    ticket is offered as new work (keyword: unreadable-pull). The owner's hold
    is applied after it (``apart``).

    Args:
        found: the open PRs, read or not.
        github: the API.
        settings: the configuration.
        book: the ledger.

    Returns:
        The ordered items.
    """
    tickets = ticket_items(github, settings, taken(pulls.readable(found)))
    return assemble(found, tickets, book)


def assemble(
    found: Sequence[pulls.Read], tickets: Sequence[Item], book: ledger.Ledger
) -> Sequence[Item]:
    """The PRs' items and the tickets that were read, in the order to start them.

    Args:
        found: the open PRs, read or not.
        tickets: the tickets that no open PR fixes (``ticket_items``).
        book: the ledger.

    Returns:
        The ordered items; no ticket while a PR cannot be read.
    """
    facts = pulls.readable(found)
    items = [
        *pull_items(facts),
        *(tickets if len(facts) == len(found) else ()),
    ]
    return ordered(items, [slot.task for slot in book.slots if slot.agent])
