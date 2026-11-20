"""A red that costs one cheap push to fix is classified.

The keyword is mechanical-fix, pitboss#32.

A failure of the plan job, or failures whose text is only a fixture expectation
mismatch, is fixed by one push and should not wait behind a runner-pressure hold. The
sweep prints ``MECHANICAL-FIX`` in place of the plain fix line with the matching text,
``SLOW-MECHANICAL-FIX`` when the fix push has not happened in the configured minutes
of the red, and ``pitboss push --mechanical`` is exempt from the hold only for such a
PR. Every other red stays a plain fix.
"""

import re
from typing import Mapping

from . import config, pulls, shapes

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
