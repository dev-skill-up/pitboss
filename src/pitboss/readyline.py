"""The NEXT lines of a draft whose Plan is approved (keyword: mark-ready, pitboss#273).

Marking a PR ready is an action of the orchestrator, not a round for a worker or a
reviewer, so no item of the list is a PR to undraft. It was printed only as a
``PR STATE`` line, and a draft sat unmarked for an hour while the orchestrator read
the ``NEXT`` list. Each such draft is now a ``NEXT`` line of its own, above every
start and review line: the action when no hold shows, the hold and its end when one
does.
"""

import datetime
from typing import Iterable, Sequence

from . import config, pulls, record, steps

HOLD_WORDS = "HOLD on undrafts (the RUNNER PRESSURE line says why)"
UNKNOWN_END = "unknown (the runners' look could not be read)"


def hold_end(runners: config.Runners, now: datetime.datetime) -> str:
    """When the quiet period of the runners ends, as the record shows it.

    Args:
        runners: the runners' configuration.
        now: the time now.

    Returns:
        The time at the earliest, or ``unknown`` when the record owes no quiet
        minutes (a look that could not be read holds with none owed), is empty
        or cannot be read. It never raises.
    """
    try:
        entries = record.read_entries(record.read(runners.record), now)
    except SystemExit:
        return UNKNOWN_END
    if not entries:
        return UNKNOWN_END
    owed = record.minutes_remaining(entries, runners.quiet_minutes, now)
    if not owed:
        return UNKNOWN_END
    end = now + datetime.timedelta(minutes=owed)
    return f"{end.isoformat(timespec='seconds')} at the earliest"


def line(pull: pulls.PullFacts, runners: config.Runners, now: datetime.datetime) -> str:
    """The text of the NEXT line of one draft whose Plan is approved.

    Args:
        pull: the PR; its step is an undraft or the wait for one.
        runners: the runners' configuration.
        now: the time now.

    Returns:
        The text after the number: the action, or the hold and its end.
    """
    reference = pulls.reference(pull)
    if pull.step.step is steps.Step.UNDRAFT:
        return (
            f"{reference} (mark the PR ready: update_pull_request draft=false for"
            f" {reference}; the next step is the CI gate on the undrafted head)"
        )
    return f"{reference} ({HOLD_WORDS}: mark ready at {hold_end(runners, now)})"


def texts(
    settings: config.Config, facts: Sequence[pulls.PullFacts], now: datetime.datetime
) -> Iterable[str]:
    """The NEXT lines (after their numbers) of every such draft.

    Args:
        settings: the configuration.
        facts: the open PRs that were read.
        now: the time now.

    Yields:
        The texts, in the order of ``facts``.
    """
    wanted = (steps.Step.UNDRAFT, steps.Step.WAIT_FOR_UNDRAFT)
    for pull in facts:
        if pull.step.step in wanted:
            yield line(pull, settings.runners, now)
