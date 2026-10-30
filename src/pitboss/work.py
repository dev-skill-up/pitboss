"""What to start next: one sorted list, and which empty slot takes what.

The order (work-order): the open PRs that need work come first, in one list,
oldest first, whatever each needs. What a PR needs is the step ``flow.next_step``
gives it (keyword: review-flow): a worker's round, whose kind is its task (a
revision of the plan and nothing else, a fix of the CI, the Plan and Execution
body, the resolution of a conflict, or any other fix of a review), or a review
by a new reviewer (a draft's plan-only review included). There is no update
kind. The kind is a label on the line, not a rank. A PR whose step is to wait
(for CI, an undraft or the owner), to ask Opus for a ruling, to pause for the
owner, to undraft or to merge is none of them: it is offered for no round.
After them come the
new PRs, one for each open ticket with a priority label that no open PR names,
by priority label, then oldest first. Nothing predicts which files a ticket
will touch: work is taken in this order, every PR starts from the base branch,
and a conflict is resolved by merging the base branch in.
"""

import dataclasses
import enum
import re
from typing import AbstractSet, Iterable, Mapping, Sequence

from . import config, ghapi, ledger, parsing, pulls, shapes, steps

_TRAILING_NUMBER = re.compile(r"[-/](\d+)$")
_ISSUE_URL = re.compile(r"github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)")


class Category(enum.IntEnum):
    """The kinds of work: a label on a line, never a rank among the open PRs.

    Attributes:
        FIX_REVIEW: an author fixes what a review asked for (a PR).
        REVISE_PLAN: an author revises the plan a review did not approve, and
            touches nothing else (a PR).
        REVIEW: a reviewer (never the author) reviews a green head, or a
            draft's plan alone (a PR).
        NEW_PR: a worker starts a ticket (after every PR).
        FIX_CI: an author fixes a red CI, which is no rejection (a PR).
        FIRST_ROUND: an author writes the Plan and Execution body of a PR that
            has none (a PR).
        RESOLVE_CONFLICT: an author resolves the conflict of an approved head
            (a PR).
    """

    FIX_REVIEW = 1
    REVISE_PLAN = 2
    REVIEW = 4
    NEW_PR = 5
    FIX_CI = 6
    FIRST_ROUND = 7
    RESOLVE_CONFLICT = 8


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Item:
    """One thing a worker could start.

    Attributes:
        category: its kind.
        reference: its ``owner/name#number``.
        created_at: when the PR or ticket was opened (ISO 8601).
        title: its title.
        priority: the index of its priority label (0 for PRs).
        labels: its labels.
    """

    category: Category
    reference: str
    created_at: str
    title: str
    priority: int = 0
    labels: AbstractSet[str] = frozenset()


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
        if (category := _category(pull)) is not None
    ]


CATEGORY_OF_TASK: Mapping[steps.Task | None, Category] = {
    steps.Task.REVISE_PLAN: Category.REVISE_PLAN,
    steps.Task.FIX_CI: Category.FIX_CI,
    steps.Task.FIRST_ROUND: Category.FIRST_ROUND,
    steps.Task.RESOLVE_CONFLICT: Category.RESOLVE_CONFLICT,
}


def _category(pull: pulls.PullFacts) -> Category | None:
    step = pull.step
    if step.step is steps.Step.WORKER:
        return CATEGORY_OF_TASK.get(step.task, Category.FIX_REVIEW)
    # review-flow: the step alone decides, so ``next`` and ``slots next`` agree
    return Category.REVIEW if step.step is steps.Step.REGULAR_REVIEW else None


def _references(pull: pulls.PullFacts) -> frozenset[str]:
    text = f"{pull.pull.title}\n{pull.pull.body}"
    found = {
        ledger.reference(match.group(0), pull.repo)
        for match in re.finditer(r"(?:[\w.-]+/)?[\w.-]*#\d+", text)
    }
    found.update(
        f"{match.group(1)}#{match.group(2)}" for match in _ISSUE_URL.finditer(text)
    )
    trailing = _TRAILING_NUMBER.search(pull.pull.head.branch)
    if trailing:
        found.add(f"{pull.repo.slug}#{trailing.group(1)}")
    return frozenset(found)


def taken(facts: Iterable[pulls.PullFacts]) -> AbstractSet[str]:
    """The tickets open PRs already work on.

    A PR names a ticket by ``#N``, ``name#N``, ``owner/name#N`` or the
    ticket's URL in its title or body, or by a branch ending in ``-N``.

    Args:
        facts: the open PRs.

    Returns:
        The tickets' references.
    """
    return frozenset().union(*(_references(pull) for pull in facts))


def ticket_items(
    github: ghapi.GitHub, settings: config.Config, in_progress: AbstractSet[str]
) -> Sequence[Item]:
    """The open tickets with a priority label that no open PR names.

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
    for repo in config.repositories(settings):
        for priority, label in ranked:
            path = f"repos/{repo.slug}/issues?state=open&labels={label}"
            for issue in ghapi.pages(github, path, parsing.issues):
                yield _ticket_item(f"{repo.slug}#{issue.number}", issue, priority)


def _ticket_item(reference: str, issue: shapes.Issue, priority: int) -> Item:
    return Item(
        category=Category.NEW_PR,
        reference=reference,
        created_at=issue.created_at,
        title=issue.title,
        priority=priority,
        labels=issue.labels,
    )


def ordered(items: Iterable[Item], held: Iterable[str]) -> Sequence[Item]:
    """Sort the items, leaving out what a slot already holds.

    Args:
        items: the items.
        held: the references slots hold.

    Returns:
        The items, first to take first: every open PR, oldest first, then
        the tickets by priority label, oldest first.
    """
    holding = frozenset(held)
    return sorted(
        (item for item in items if item.reference not in holding),
        key=lambda item: (
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


def queued(
    found: Sequence[pulls.Read],
    github: ghapi.GitHub,
    settings: config.Config,
    book: ledger.Ledger,
) -> Sequence[Item]:
    """The work that is queued: PRs and tickets, in the order to start them.

    A PR that could not be read may work on any ticket, so while one exists no
    ticket is offered as new work (keyword: unreadable-pull).

    Args:
        found: the open PRs, read or not.
        github: the API.
        settings: the configuration.
        book: the ledger.

    Returns:
        The ordered items.
    """
    facts = pulls.readable(found)
    tickets = ticket_items(github, settings, taken(facts))
    items = [
        *pull_items(facts),
        *(tickets if len(facts) == len(found) else ()),
    ]
    return ordered(items, [slot.task for slot in book.slots if slot.agent])


Assignment = tuple[ledger.Slot, Item | None]


def assign(
    items: Sequence[Item], book: ledger.Ledger, slots: config.Slots
) -> Sequence[Assignment]:
    """Give each empty slot, smallest model first, the first item it may take.

    Args:
        items: the ordered items.
        book: the ledger.
        slots: the slot configuration.

    Returns:
        Each empty slot with its item, or None when nothing fits.
    """
    rank = {model: index for index, model in enumerate(slots.models)}
    left = [
        (item, rank[model])
        for item in items
        if (model := smallest_model(item, slots, book.failed)) is not None
    ]
    found: list[Assignment] = []
    empty = [each for each in book.slots if not each.agent]
    for empty_slot in sorted(empty, key=lambda each: rank.get(each.model, len(rank))):
        size = rank.get(empty_slot.model, -1)
        index = next((at for at, pair in enumerate(left) if pair[1] <= size), None)
        found.append((empty_slot, None if index is None else left.pop(index)[0]))
    return found
