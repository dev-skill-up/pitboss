"""The sweep's lines: every line that calls for an action says the action."""

import datetime
from typing import Mapping, Sequence

from . import (
    brieftextowner,
    causeline,
    config,
    configrepos,
    headchecks,
    holdgate,
    knownred,
    pinsline,
    pulls,
    queue,
    reviews,
    shapes,
    steps,
)
from .markers import Marker

STANDING_WORDS = {
    reviews.Standing.NONE: "none",
    reviews.Standing.APPROVED: "approved-this-head",
    reviews.Standing.APPROVED_BEFORE_MERGES: "approved-before-merges",
    reviews.Standing.CHANGES_NEEDED: "changes-needed",
    reviews.Standing.OLDER_HEAD: "older-head",
    reviews.Standing.OLDER_BODY: "older-body",
    reviews.Standing.PLAN_CHANGES_NEEDED: "plan-changes-needed",
    reviews.Standing.PLAN_APPROVED: "plan-approved",
}


def _queue_word(pull: pulls.PullFacts, newest: Mapping[str, queue.QueueRun]) -> str:
    found = newest.get(pulls.reference(pull))
    return queue.state(found) if found else "-"


def _unread_note(pull: pulls.PullFacts) -> str:
    if not pull.unreadable.newer:
        return ""
    return (
        f" (ignored: the comment of {pull.unreadable.newer} is not in the review form)"
    )


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


def _ruled(pull: pulls.PullFacts) -> bool:
    return pulls.at_merge(pull) and not pulls.approved(pull)


def _ready_line(pull: pulls.PullFacts, settings: config.Config) -> str | None:
    clean = pull.pull.mergeable_state is shapes.MergeState.CLEAN
    ruled = _ruled(pull)
    ready = pulls.green(pull) and clean and (pulls.approved(pull) or ruled)
    if not ready or pull.pull.auto_merge or pull.signals.gate:
        return None  # keyword: review-gate: a pending gate is no READY TO MERGE
    name = pulls.reference(pull)
    if configrepos.merges_by_hand(settings, pull.repo):
        why = "execution approved by the Opus ruling" if ruled else "approved"
        said = pinsline.why(pull.signals.pins, why)
        return f"{Marker.MERGE_BY_HAND.text} {name}: green, clean, {said}"
    return f"{Marker.READY_TO_MERGE.text} {name}: arm auto-merge or merge"


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
    behind = _behind_lines(pull, settings)
    merge = _merge_line(pull, settings, queued) if not behind else None
    found = [
        *_wait_lines(pull),
        *_conflict_lines(pull),
        *_failure_lines(pull, why),
        *pinsline.lines(pulls.reference(pull), pull.signals.pins, _posting(pull)),
        *behind,
        *([merge] if merge else []),
    ]
    # keywords: hold-gate (quire#1110), known-red (quire#1120): before the hold
    return holdgate.gate(pull, knownred.gate(pull, found, holdgate.PREFIXES))


def _merge_line(
    pull: pulls.PullFacts, settings: config.Config, queued: bool
) -> str | None:
    # the merge line of a PR that is not behind: ready, by hand, or auto-merge off
    merge = _ready_line(pull, settings)
    if merge is None and _auto_merge_off(pull, settings, queued):
        return f"{Marker.AUTO_MERGE_OFF.text} {pulls.reference(pull)}: arm it again"
    return merge


# keyword: behind-approved (pitboss#369): the strict up-to-date rule held pwa#293
# behind main after its review and checks; the merge of main is reviewed by the proof
BEHIND_STATES = frozenset({shapes.MergeState.BEHIND})
BEHIND_WORDS = (
    "update the branch, then the merge-main proof (bats merge-proof) is the review"
)


def _behind_lines(pull: pulls.PullFacts, settings: config.Config) -> Sequence[str]:
    # a merge-queue repository builds each entry on the current base: behind is no work
    queued = pull.repo.slug in settings.merge_queue.repositories
    said = [f"{Marker.BEHIND.text}: {BEHIND_WORDS}"]
    return (
        said
        if pull.pull.mergeable_state in BEHIND_STATES
        and _approved_green(pull)
        and not queued
        else []
    )


def _approved_green(pull: pulls.PullFacts) -> bool:
    return (pulls.approved(pull) or _ruled(pull)) and pulls.green(pull)


def _posting(pull: pulls.PullFacts) -> str:
    # keyword: pins-review (pitboss#350): only a relock PR can have the comment posted
    if pull.relock and pull.signals.gate:
        return pinsline.posting_words(pulls.reference(pull))
    return ""


def _conflict_lines(pull: pulls.PullFacts) -> Sequence[str]:
    if not pulls.conflicted(pull):
        return []
    return [
        f"{Marker.CONFLICT.text} {pulls.reference(pull)}: merge {pull.pull.base} into"
        f" {pull.pull.head.branch} (never rewrite history)"
    ]


def _wait_lines(pull: pulls.PullFacts) -> Sequence[str]:
    # keyword: draft-review (pitboss#156): a draft at a round has its own line
    # (draftline), not a wait for a CI it never runs
    # the RUN E2E step has its own line too (keyword: run-e2e, pitboss#199)
    at_round = pull.step.step in (
        steps.Step.REGULAR_REVIEW,
        steps.Step.WORKER,
        steps.Step.RUN_E2E,
    )
    if (pull.pull.draft and at_round) or not pulls.waiting_for_ci(pull):
        return []
    return [
        f"{Marker.WAIT_FOR_CI.text} {pulls.reference(pull)}: no check run of the head"
        " has completed; not ready for review or to merge"
    ]


def _failure_lines(pull: pulls.PullFacts, why: Mapping[int, str]) -> Sequence[str]:
    ref = pulls.reference(pull)  # keyword: red-cause (pitboss#420)
    return [
        said
        for check in headchecks.unanswered(pull.checks, pull.signals)
        for said in causeline.failed(ref, pull.repo.slug, check, why.get(check.id, ""))
    ]


def _auto_merge_off(
    pull: pulls.PullFacts, settings: config.Config, queued: bool
) -> bool:
    manual = configrepos.merges_by_hand(settings, pull.repo)
    # keyword: auto-merge-approved (pitboss#85): AUTO MERGE OFF is printed only for
    # a head a review approved; a head the Opus ruling approved gets READY TO MERGE
    # while auto-merge is off.
    healthy = pull.standing is reviews.Standing.APPROVED and pulls.approved(pull)
    healthy = healthy and not pulls.unhealthy(pull)
    return healthy and not manual and not queued and not pull.pull.auto_merge


HOLD_ACTIONS = holdgate.HOLD_ACTIONS  # keyword: hold-actions (pitboss#200)


def pressure_line(waiting: int) -> str:
    """The runner-pressure line of what waits now.

    Args:
        waiting: queue-run jobs waiting for a runner.

    Returns:
        The line.
    """
    if not waiting:
        return f"{Marker.NO_RUNNER_PRESSURE.text}: push and merge as usual"
    return (
        f"{Marker.RUNNER_PRESSURE.text}: {waiting} queue-run jobs waiting for a"
        f" runner: {HOLD_ACTIONS}"
    )


def queued_line(now: datetime.datetime, quiet_minutes: int) -> str:
    """The line that says a queued job was recorded.

    Args:
        now: when.
        quiet_minutes: the length of the quiet period that restarts.

    Returns:
        The line.
    """
    return (
        f"recorded a queued job at {now.isoformat(timespec='seconds')}: the quiet"
        f" period of {quiet_minutes} minutes restarts"
    )


def unreadable_record_line(reason: object) -> str:
    """The pressure line when the record cannot be read, so the quiet is unknown.

    Args:
        reason: why it cannot be read.

    Returns:
        The line.
    """
    head = f"{Marker.RUNNER_PRESSURE.text}: the quiet period cannot be told"
    return "; ".join([f"{head} ({reason})", HOLD_ACTIONS])


def no_hold_line() -> str:
    """The pressure line of a configuration with no ``[runners]`` table.

    Returns:
        The line: nothing is held and nothing is recorded.
    """
    return (
        f"{Marker.NO_RUNNER_PRESSURE.text}: no hold, the configuration has no"
        " [runners] table (its own runner budget); push and merge as usual"
    )


def seen_line(found: queue.Seen) -> str:
    """The runner-pressure line of a look, the first of a record included.

    Args:
        found: what the look showed.

    Returns:
        The line; where the record had no earlier look and nothing waits, it
        says the quiet period starts now (pitboss#215), not that a job waited.
    """
    if found.starts and found.owed and not found.waiting:
        return (
            f"{Marker.RUNNER_PRESSURE.text}: nothing waits now and the pressure"
            f" record has no earlier look; quiet period starts now; {found.owed}"
            f" quiet minutes remain: {HOLD_ACTIONS}"
        )
    return quiet_line(found.waiting, found.owed)


def quiet_line(waiting: int, owed: int) -> str:
    """The runner-pressure line of a look that counts the quiet period.

    Args:
        waiting: queue-run jobs waiting for a runner.
        owed: the quiet minutes still owed; 0 when the quiet period is over.

    Returns:
        The line.
    """
    if waiting:
        return f"{pressure_line(waiting)}; {owed} quiet minutes remain"
    if owed:
        return (
            f"{Marker.RUNNER_PRESSURE.text}: nothing waits now, but a job waited or"
            f" was put on the queue within the quiet period; {owed} quiet minutes"
            f" remain: {HOLD_ACTIONS}"
        )
    return pressure_line(0)


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
    limit = settings.merge_queue.timeout_minutes
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


def print_reminders(settings: config.Config) -> None:
    """Print the reminders each sweep ends with.

    Args:
        settings: the configuration.
    """
    for line in reminder_lines(settings):
        print(line)


def reminder_lines(settings: config.Config) -> Sequence[str]:
    """The sentences about the owner and the workers, then the project's questions.

    Args:
        settings: the configuration.

    Returns:
        The lines.
    """
    kept = [*brieftextowner.REMINDERS, *settings.reminders]
    return [f"{Marker.SWEEP_REMINDER.text}: {text}" for text in kept]


def print_queue(
    pressure: str,
    runs: Sequence[queue.QueueRun],
    settings: config.Config,
    now: datetime.datetime,
) -> None:
    """Print the runner pressure and the merge queue lines.

    Args:
        pressure: the runner-pressure line.
        runs: the merge queue's runs.
        settings: the configuration.
        now: the time now.
    """
    print(pressure)
    for line in queue_lines(runs, settings, now):
        print(line)
