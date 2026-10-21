"""The sweep's lines: every line that calls for an action says the action."""

import dataclasses
import datetime
from typing import Iterable, Mapping, Sequence

from . import config, ledger, local, pulls, queue, reviews, shapes, work
from .markers import Marker

STANDING_WORDS = {
    reviews.Standing.NONE: "none",
    reviews.Standing.APPROVED: "approved-this-head",
    reviews.Standing.APPROVED_BEFORE_MERGES: "approved-before-merges",
    reviews.Standing.CHANGES_NEEDED: "changes-needed",
    reviews.Standing.OLDER_HEAD: "older-head",
}
CATEGORY_WORDS = {
    work.Category.FIX_REVIEW: "fix the review",
    work.Category.REVIEW: "review it (a reviewer that is not its author)",
    work.Category.NEW_PR: "start a PR",
}


def _queue_word(pull: pulls.PullFacts, newest: Mapping[str, queue.QueueRun]) -> str:
    found = newest.get(pull.reference)
    return found.state if found else "-"


def pull_line(pull: pulls.PullFacts, newest: Mapping[str, queue.QueueRun]) -> str:
    """The summary line of one PR.

    Args:
        pull: the PR.
        newest: each PR reference's newest queue run.

    Returns:
        The line.
    """
    failed = ",".join(f"{check.name} (job {check.id})" for check in pull.failed)
    return (
        f"{pull.reference} [{pull.pull.mergeable_state.name.lower()}]"
        f" auto-merge={'on' if pull.pull.auto_merge else 'off'}"
        f" pending={pull.pending} failed=[{failed}]"
        f" queue={_queue_word(pull, newest)}"
        f" review={STANDING_WORDS[pull.standing]}"
        f" {pull.pull.title[:55]} ({pull.pull.head.branch})"
    )


def _ready_line(pull: pulls.PullFacts, settings: config.Config) -> str | None:
    clean = pull.pull.mergeable_state is shapes.MergeState.CLEAN
    if not (pull.green and clean and pull.approved and not pull.pull.auto_merge):
        return None
    if pull.repo.slug in settings.no_auto_merge:
        return f"{Marker.MERGE_BY_HAND.text} {pull.reference}: green, clean, approved"
    return f"{Marker.READY_TO_MERGE.text} {pull.reference}: arm auto-merge or merge"


def action_lines(
    pull: pulls.PullFacts, settings: config.Config, queued: bool
) -> Sequence[str]:
    """The actions one PR calls for.

    Args:
        pull: the PR.
        settings: the configuration.
        queued: whether the PR's newest queue run is unfinished.

    Returns:
        The lines.
    """
    found = []
    base = pull.pull.base
    if pull.conflicted:
        found.append(
            f"{Marker.CONFLICT.text} {pull.reference}: merge {base} into"
            f" {pull.pull.head.branch} (never rewrite history)"
        )
    slug = pull.repo.slug
    for check in pull.failed:
        found.append(
            f"{Marker.FAILED.text} {pull.reference}: {check.name}: read"
            f" gh api repos/{slug}/actions/jobs/{check.id}/logs"
        )
    ready = _ready_line(pull, settings)
    if ready is not None:
        found.append(ready)
    elif _auto_merge_off(pull, settings, queued):
        found.append(f"{Marker.AUTO_MERGE_OFF.text} {pull.reference}: arm it again")
    return found


def _auto_merge_off(
    pull: pulls.PullFacts, settings: config.Config, queued: bool
) -> bool:
    manual = pull.repo.slug in settings.no_auto_merge
    healthy = not (
        pull.failed
        or pull.conflicted
        or pull.pull.draft
        or pull.standing is reviews.Standing.CHANGES_NEEDED
    )
    return healthy and not manual and not queued and not pull.pull.auto_merge


def pressure_line(waiting: int) -> str:
    """The runner-pressure line.

    Args:
        waiting: queue-run jobs waiting for a runner.

    Returns:
        The line.
    """
    if not waiting:
        return f"{Marker.NO_RUNNER_PRESSURE.text}: push and merge as usual"
    return (
        f"{Marker.RUNNER_PRESSURE.text}: {waiting} queue-run jobs waiting for a"
        " runner: HOLD pushes, PRs, merges and re-runs (all repositories)"
    )


def queue_lines(
    runs: Sequence[queue.QueueRun], settings: config.Config, now: datetime.datetime
) -> Sequence[str]:
    """The unfinished queue runs: stale ones, and the newest with their age.

    Args:
        runs: the runs of every repository read.
        settings: the configuration.
        now: the time now.

    Returns:
        The lines.
    """
    stale = queue.stale_runs(runs)
    found = [
        f"{Marker.STALE_QUEUE_RUN.text} {run.repo.slug} {run.run.id}"
        f" (pr-{run.number}, {run.run.status}): cancel-stale-runs cancels it"
        for run in stale
    ]
    stale_ids = {run.run.id for run in stale}
    limit = settings.timeout_minutes
    for run in runs:
        if not run.finished and run.run.id not in stale_ids:
            found.append(
                f"{Marker.QUEUE_RUN.text} {run.repo.slug} {run.run.id}"
                f" (pr-{run.number}, {run.run.status},"
                f" {queue.age_minutes(run, now)} of {limit} minutes)"
            )
    return found


def straggler_line(straggler: local.Straggler) -> str:
    """The line of one straggler.

    Args:
        straggler: the straggler.

    Returns:
        The line.
    """
    return (
        f"{Marker.STRAGGLER.text} {straggler.path} [{straggler.branch or 'detached'}]"
        f" uncommitted={straggler.uncommitted} commits-not-on-origin={straggler.unpushed}"
        f" branch-on-origin={'yes' if straggler.on_origin else 'no'}"
        f" last={straggler.last}"
    )


def reminder_lines(settings: config.Config) -> Sequence[str]:
    """The questions each sweep ends with.

    Args:
        settings: the configuration.

    Returns:
        The lines.
    """
    return [f"{Marker.SWEEP_REMINDER.text}: {text}" for text in settings.reminders]


def slot_lines(book: ledger.Ledger) -> Sequence[str]:
    """The ledger, with a loud line for each empty slot.

    Args:
        book: the ledger.

    Returns:
        The lines.
    """
    found = []
    for slot in book.slots:
        if slot.agent:
            found.append(f"slot {slot.name} ({slot.model}): {slot.task} ({slot.agent})")
        else:
            found.append(
                f"{Marker.EMPTY_SLOT.text}: {slot.name} ({slot.model}):"
                " run 'pitboss slots next' and start its line"
            )
    if all(slot.agent for slot in book.slots):
        found.append("slots: the ledger says all full")
    return found


CHECK_LEDGER_LINE = (
    f"{Marker.CHECK_BEFORE_YOU_ANSWER.text}: the ledger is kept by hand. List the agents"
    " the session runs, run 'pitboss slots check CONFIG --running NAME ...',"
    " fix the ledger with 'slots free' and 'slots set', then act or answer."
)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class NextView:
    """What ``slots next`` prints from.

    Attributes:
        items: the ordered items.
        assignments: each empty slot and its item.
        slots: the slot configuration.
        failed: each reference's failed models.
        now: the time now.
    """

    items: Sequence[work.Item]
    assignments: Sequence[tuple[ledger.Slot, work.Item | None]]
    slots: config.Slots
    failed: Mapping[str, Sequence[str]]
    now: datetime.datetime


def _age_days(created_at: str, now: datetime.datetime) -> int:
    return (now - datetime.datetime.fromisoformat(created_at)).days


def _item_text(item: work.Item, view: NextView) -> str:
    model = work.smallest_model(item, view.slots, view.failed) or "none left"
    priority = (
        f" {view.slots.priority_labels[item.priority]}"
        if item.category is work.Category.NEW_PR
        else ""
    )
    return (
        f"{item.reference} ({CATEGORY_WORDS[item.category]}{priority},"
        f" opened {item.created_at[:10]}, {_age_days(item.created_at, view.now)}"
        f" days, smallest model {model}): {item.title[:60]}"
    )


def next_lines(view: NextView) -> Iterable[str]:
    """The sorted list, then what each empty slot takes.

    Args:
        view: what to print from.

    Yields:
        The lines.
    """
    for index, item in enumerate(view.items, start=1):
        yield f"{Marker.NEXT.text} {index}. {_item_text(item, view)}"
    if not view.assignments:
        yield "slots: the ledger says all full: start nothing"
    for slot, chosen in view.assignments:
        target = "nothing fits it: leave it empty"
        if chosen is not None:
            target = "start " + _item_text(chosen, view)
        yield f"{Marker.EMPTY_SLOT.text}: {slot.name} ({slot.model}): {target}"
