"""What to start next: one sorted list, and which empty slot takes what.

The order (work-order): (1) the author's fix for a review that asked for
changes on the PR's current head; (2) a review of a PR that is green on
its head and has no review of it; (3) a new PR for an open ticket with a
priority label. Within a category, by priority label, then oldest first.
"""

import concurrent.futures
import dataclasses
import enum
import re
from typing import Iterable, Mapping, Sequence

from . import config, ghapi, ledger, pulls, reviews, shapes

_BACKTICKED_PATH = re.compile(r"`([^`\s]+/[^`\s]+)`")
_TRAILING_NUMBER = re.compile(r"[-/](\d+)$")
_ISSUE_URL = re.compile(r"github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)")


class Category(enum.IntEnum):
    """The kinds of work, in the order they are taken.

    Attributes:
        FIX_REVIEW: an author fixes what a review asked for.
        REVIEW: a reviewer (never the author) reviews a green head.
        NEW_PR: a worker starts a ticket.
    """

    FIX_REVIEW = 1
    REVIEW = 2
    NEW_PR = 3


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
    labels: frozenset[str] = frozenset()


def pull_items(facts: Iterable[pulls.PullFacts]) -> Sequence[Item]:
    """The fixes and reviews the open PRs need.

    Args:
        facts: the open PRs.

    Returns:
        The items.
    """
    found = []
    for pull in facts:
        category = None
        if pull.standing is reviews.Standing.CHANGES_NEEDED:
            category = Category.FIX_REVIEW
        elif _awaits_review(pull):
            category = Category.REVIEW
        if category is not None:
            found.append(
                Item(
                    category=category,
                    reference=pull.reference,
                    created_at=pull.pull.created_at,
                    title=pull.pull.title,
                )
            )
    return found


def _awaits_review(pull: pulls.PullFacts) -> bool:
    unreviewed = pull.standing in (reviews.Standing.NONE, reviews.Standing.OLDER_HEAD)
    return unreviewed and pull.green and not pull.conflicted and not pull.pull.draft


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


def _touches(paths: Iterable[str], changed: Iterable[str]) -> bool:
    for path in paths:
        directory = path.removeprefix("./").split(":")[0].rstrip("/")
        if any(
            name == directory or name.startswith(directory + "/") for name in changed
        ):
            return True
    return False


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Taken:
    """What open PRs already cover.

    Attributes:
        references: every ticket an open PR names.
        changed: each repository's files that open PRs change.
    """

    references: frozenset[str]
    changed: Mapping[str, frozenset[str]]


def read_taken(github: ghapi.GitHub, facts: Sequence[pulls.PullFacts]) -> Taken:
    """Read what the open PRs name and change.

    Args:
        github: the API.
        facts: the open PRs.

    Returns:
        What they cover.
    """

    def files(pull: pulls.PullFacts) -> Sequence[str]:
        path = f"repos/{pull.repo.slug}/pulls/{pull.pull.number}/files"
        return ghapi.pages(github, path, shapes.filenames)

    with concurrent.futures.ThreadPoolExecutor() as pool:
        changed_lists = list(pool.map(files, facts))
    changed: dict[str, frozenset[str]] = {}
    for pull, names in zip(facts, changed_lists):
        changed[pull.repo.slug] = changed.get(pull.repo.slug, frozenset()) | set(names)
    references = frozenset().union(*(_references(pull) for pull in facts))
    return Taken(references=references, changed=changed)


def ticket_items(
    github: ghapi.GitHub, settings: config.Config, taken: Taken
) -> Sequence[Item]:
    """The open tickets with a priority label that no open PR covers.

    Args:
        github: the API.
        settings: the configuration.
        taken: what open PRs cover.

    Returns:
        The items.
    """
    found: dict[str, Item] = {}
    for repo in settings.repositories:
        for priority, label in enumerate(settings.slots.priority_labels):
            path = f"repos/{repo.slug}/issues?state=open&labels={label}"
            for issue in ghapi.pages(github, path, shapes.issues):
                item = _ticket_item(repo, issue, priority, taken)
                if item is not None:
                    found.setdefault(item.reference, item)
    return list(found.values())


def _ticket_item(
    repo: config.Repo, issue: shapes.Issue, priority: int, taken: Taken
) -> Item | None:
    item_reference = f"{repo.slug}#{issue.number}"
    paths = _BACKTICKED_PATH.findall(issue.body)
    changed = taken.changed.get(repo.slug, frozenset())
    if item_reference in taken.references or _touches(paths, changed):
        return None
    return Item(
        category=Category.NEW_PR,
        reference=item_reference,
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
        The items, first to take first.
    """
    holding = frozenset(held)
    return sorted(
        (item for item in items if item.reference not in holding),
        key=lambda item: (item.category, item.priority, item.created_at),
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


def assign(
    items: Sequence[Item], book: ledger.Ledger, slots: config.Slots
) -> Sequence[tuple[ledger.Slot, Item | None]]:
    """Give each empty slot, smallest model first, the first item it may take.

    Args:
        items: the ordered items.
        book: the ledger.
        slots: the slot configuration.

    Returns:
        Each empty slot with its item, or None when nothing fits.
    """
    rank = {model: index for index, model in enumerate(slots.models)}
    left = list(items)
    found: list[tuple[ledger.Slot, Item | None]] = []
    empty = [slot for slot in book.slots if not slot.agent]
    for slot in sorted(empty, key=lambda slot: rank.get(slot.model, len(rank))):
        fits = [
            item
            for item in left
            if (model := smallest_model(item, slots, book.failed)) is not None
            and rank[model] <= rank.get(slot.model, -1)
        ]
        chosen = fits[0] if fits else None
        if chosen is not None:
            left.remove(chosen)
        found.append((slot, chosen))
    return found
