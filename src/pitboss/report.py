"""The sweep's lines: every line that calls for an action says the action."""

import dataclasses
import datetime
import sys
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
    found = newest.get(pulls.reference(pull))
    return queue.state(found) if found else "-"


def _unread_note(pull: pulls.PullFacts) -> str:
    if not pull.unread:
        return ""
    return f" (ignored: the comment of {pull.unread} is not in the review form)"


def pull_line(pull: pulls.PullFacts, newest: Mapping[str, queue.QueueRun]) -> str:
    """The summary line of one PR.

    Args:
        pull: the PR.
        newest: each PR reference's newest queue run.

    Returns:
        The line.
    """
    failed = ",".join(
        f"{check.name} (job {check.id})" for check in pulls.failed_checks(pull)
    )
    return (
        f"{pulls.reference(pull)} [{pull.pull.mergeable_state.name.lower()}]"
        f" auto-merge={'on' if pull.pull.auto_merge else 'off'}"
        f" pending={pulls.pending(pull)} failed=[{failed}]"
        f" queue={_queue_word(pull, newest)}"
        f" review={STANDING_WORDS[pull.standing]}{_unread_note(pull)}"
        f" {pull.pull.title[:55]} ({pull.pull.head.branch})"
    )


def _ready_line(pull: pulls.PullFacts, settings: config.Config) -> str | None:
    clean = pull.pull.mergeable_state is shapes.MergeState.CLEAN
    ready = pulls.green(pull) and clean and pulls.approved(pull)
    if not ready or pull.pull.auto_merge:
        return None
    name = pulls.reference(pull)
    if _by_hand(pull, settings):
        return f"{Marker.MERGE_BY_HAND.text} {name}: green, clean, approved"
    return f"{Marker.READY_TO_MERGE.text} {name}: arm auto-merge or merge"


def _by_hand(pull: pulls.PullFacts, settings: config.Config) -> bool:
    return pull.repo.slug in settings.no_auto_merge


def action_lines(
    pull: pulls.PullFacts,
    settings: config.Config,
    queued: bool,
    why: Mapping[int, str],
) -> Sequence[str]:
    """The actions one PR calls for.

    Args:
        pull: the PR.
        settings: the configuration.
        queued: whether the PR's newest queue run is unfinished.
        why: what was read of each failed check (by id), for its line.

    Returns:
        The lines.
    """
    merge = _ready_line(pull, settings)
    if merge is None and _auto_merge_off(pull, settings, queued):
        merge = f"{Marker.AUTO_MERGE_OFF.text} {pulls.reference(pull)}: arm it again"
    return [
        *_wait_lines(pull),
        *_conflict_lines(pull),
        *_failure_lines(pull, why),
        *([merge] if merge else []),
    ]


def _wait_lines(pull: pulls.PullFacts) -> Sequence[str]:
    if not pulls.waiting_for_ci(pull):
        return []
    return [
        f"{Marker.WAIT_FOR_CI.text} {pulls.reference(pull)}: no check run of the head"
        " has completed; not ready for review or to merge"
    ]


def _conflict_lines(pull: pulls.PullFacts) -> Sequence[str]:
    if not pulls.conflicted(pull):
        return []
    return [
        f"{Marker.CONFLICT.text} {pulls.reference(pull)}: merge {pull.pull.base} into"
        f" {pull.pull.head.branch} (never rewrite history)"
    ]


def _failure_lines(pull: pulls.PullFacts, why: Mapping[int, str]) -> Sequence[str]:
    return [
        f"{Marker.FAILED.text} {pulls.reference(pull)}: {check.name}"
        + (f": {why[check.id]}" if why.get(check.id) else "")
        for check in pulls.failed_checks(pull)
    ]


def _auto_merge_off(
    pull: pulls.PullFacts, settings: config.Config, queued: bool
) -> bool:
    manual = _by_hand(pull, settings)
    healthy = not (
        pulls.failed_checks(pull)
        or pulls.conflicted(pull)
        or pull.pull.draft
        or pulls.changes_needed(pull)
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
    stale_ids = {each.run.id for each in stale}
    live = [each for each in runs if not each.run.finished]
    limit = settings.timeout_minutes
    stale_lines = [
        f"{Marker.STALE_QUEUE_RUN.text} {_run_name(each)}: cancel-stale-runs cancels it"
        for each in stale
    ]
    live_lines = [
        f"{Marker.QUEUE_RUN.text} {_run_name(each)}:"
        f" {queue.age_minutes(each, now)} of {limit} minutes"
        for each in live
        if each.run.id not in stale_ids
    ]
    return [*stale_lines, *live_lines]


def _run_name(queue_run: queue.QueueRun) -> str:
    return (
        f"{queue_run.repo.slug} {queue_run.run.id}"
        f" (pr-{queue_run.number}, {queue_run.run.status})"
    )


def straggler_line(straggler: local.Straggler) -> str:
    """The line of one straggler.

    Args:
        straggler: the straggler.

    Returns:
        The line.
    """
    branch = straggler.branch or "detached"
    return (
        f"{Marker.STRAGGLER.text} {straggler.path} [{branch}]"
        f" uncommitted={straggler.uncommitted}"
        f" commits-not-on-origin={straggler.unpushed}"
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
    found = [_slot_line(slot) for slot in book.slots]
    if all(slot.agent for slot in book.slots):
        found.append("slots: the ledger says all full")
    return found


def _slot_line(slot: ledger.Slot) -> str:
    name = f"{slot.name} ({slot.model})"
    if slot.agent:
        state = ", waiting" if slot.waiting else ""
        return f"slot {name}: {slot.task} ({slot.agent}{state})"
    return (
        f"{Marker.EMPTY_SLOT.text}: {name}: run 'pitboss slots next' and start its line"
    )


def print_free_slots(book: ledger.Ledger, queued: int) -> None:
    """Print the line that says slots are free while work is queued.

    Args:
        book: the ledger.
        queued: how many items are queued.
    """
    free = sum(1 for slot in book.slots if not slot.agent)
    if free and queued:
        print(
            f"{Marker.SLOTS_FREE.text} {free}: {queued} queued; a wake-up"
            " (send_later) is required before this turn ends, or nothing starts them"
        )


def print_ledger(book: ledger.Ledger) -> None:
    """Print the ledger, and on stderr the reminder to check it.

    Args:
        book: the ledger.
    """
    for line in slot_lines(book):
        print(line)
    print(CHECK_LEDGER_LINE, file=sys.stderr)


CHECK_LEDGER_LINE = (
    f"{Marker.CHECK_BEFORE_YOU_ANSWER.text}: the ledger is kept by hand. List the"
    " agents the session runs, run 'pitboss slots check CONFIG --running NAME ...',"
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
    assignments: Sequence[work.Assignment]
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
