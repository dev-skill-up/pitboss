"""A red that costs one cheap push to fix is classified.

The keyword is mechanical-fix, pitboss#32.

A failure of the plan job, or failures whose text is only a fixture expectation
mismatch, is fixed by one push and should not wait behind a runner-pressure hold. The
sweep prints ``MECHANICAL-FIX`` in place of the plain fix line with the matching text,
``SLOW-MECHANICAL-FIX`` when the fix push has not happened in the configured minutes
of the red, and ``pitboss push --mechanical`` is exempt from the hold only for such a
PR. Every other red stays a plain fix.
"""

import datetime
import re
from typing import Mapping, Sequence

from . import config, pulls, shapes
from .markers import Marker

SHOWN = 120


def _text(failure: shapes.Failure | None) -> str:
    if failure is None:
        return ""
    return "\n".join(
        [*failure.steps, failure.title, failure.summary, *failure.annotations]
    )


def _says(
    check: shapes.CheckRun, failure: shapes.Failure | None, rule: config.Mechanical
) -> str:
    # what makes this failed check mechanical, empty when nothing does
    if check.name in rule.checks:
        return f"the {check.name} job failed"
    for pattern in rule.patterns:
        found = re.search(pattern, _text(failure))
        if found:
            return found.group(0)[:SHOWN]
    return ""


def matching(
    pull: pulls.PullFacts,
    failures: Mapping[int, shapes.Failure],
    rule: config.Mechanical,
) -> str:
    """The text that makes a PR's red mechanical.

    Args:
        pull: the PR.
        failures: what is known of each failed check, by id.
        rule: what a mechanical red is.

    Returns:
        The matching text of each failed check, joined; empty when no check
        failed or one failed for another reason.
    """
    failed = pulls.failed_checks(pull)
    said = [_says(each, failures.get(each.id), rule) for each in failed]
    if not failed or not all(said):
        return ""
    return "; ".join(dict.fromkeys(said))


def _minutes(pull: pulls.PullFacts, now: datetime.datetime) -> float:
    done = [
        each.completed_at for each in pulls.failed_checks(pull) if each.completed_at
    ]
    if not done:
        return 0.0
    red = max(datetime.datetime.fromisoformat(each) for each in done)
    return (now - red).total_seconds() / 60


def lines(
    pull: pulls.PullFacts,
    now: datetime.datetime,
    settings: config.Config,
    failures: Mapping[int, shapes.Failure],
) -> Sequence[str]:
    """The MECHANICAL-FIX line of a PR, and SLOW-MECHANICAL-FIX when it waits.

    Args:
        pull: the PR.
        now: the time now.
        settings: the configuration.
        failures: what is known of each failed check, by id.

    Returns:
        Nothing for a red that is not mechanical.
    """
    rule = settings.runners.mechanical
    found = matching(pull, failures, rule)
    if not found:
        return []
    ref = pulls.reference(pull)
    said = [
        f"{Marker.MECHANICAL_FIX.text} {ref}: {found}; one push fixes it, and"
        " `pitboss push --mechanical` is exempt from the runner hold"
    ]
    waited = _minutes(pull, now)
    if waited >= rule.slow_minutes:
        said.append(
            f"{Marker.SLOW_MECHANICAL_FIX.text} {ref}: red for {int(waited)} minutes"
            f" (limit {rule.slow_minutes}), and no fix was pushed: push it now"
        )
    return said
