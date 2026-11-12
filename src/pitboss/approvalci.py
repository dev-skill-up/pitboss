"""An approval of a head waits for its completed green check run (keyword: approval-ci).

Ported from bats-lang/quire#1038 (``lint_review_checks``, commit 61f995d): a review
that approves a head is refused when the newest run of the required check on that
head is missing, not completed or not green, and the finding says to write
"waiting for CI". The required check's name is the configuration's
``[review] required_check``. The runs are the ``--check-runs`` file, the JSON GitHub
gives for ``repos/OWNER/NAME/commits/SHA/check-runs``; the module reads nothing else.
"""

import argparse
import json
import pathlib
from typing import Sequence

from gather.commands import add_argument

from . import config, forms

ARGUMENT = add_argument(
    "--check-runs",
    default=None,
    help="review: the check runs of the reviewed head (the JSON of `gh api"
    " repos/OWNER/NAME/commits/SHA/check-runs`); a review that approves is refused"
    " unless the newest run of the required check is completed and green, and the"
    " finding says to write `waiting for CI` (approval-ci)",
)
REQUIRED_ARGUMENT = add_argument(
    "--required-check",
    default=None,
    help="review: the check an approval waits for (default: the configuration's"
    " `[review] required_check`, else `check`)",
)
ARGUMENTS = (ARGUMENT, REQUIRED_ARGUMENT)
MISSING = (
    "{name}: the review approves, but the head has no run of the check `{check}`;"
    " write `waiting for CI` and no verdict until it is completed and green"
    " (approval-ci)"
)
PENDING = (
    "{name}: the review approves, but the newest run of `{check}` is {state}, not"
    " completed; write `waiting for CI` and no verdict (approval-ci)"
)
RED = (
    "{name}: the review approves, but the newest run of `{check}` concluded"
    " {conclusion}, not success; write `waiting for CI` and no verdict, or"
    " `changes needed` if the failure is the change's (approval-ci)"
)


def approves(body: str, form: config.ReviewForm) -> bool:
    """Whether a review comment approves.

    Args:
        body: the comment.
        form: the form the review takes.

    Returns:
        True when a line of the body is a line of the form that carries the
        verdict, with the approving word.
    """
    wanted = [
        each.replace("{verdict}", form.approved)
        for each in form.lines
        if "{verdict}" in each
    ]
    return any(line.strip() in wanted for line in body.splitlines())


def _newest(runs: Sequence[object], check: str) -> dict[str, object] | None:
    named = [
        each for each in runs if isinstance(each, dict) and each.get("name") == check
    ]
    return max(named, key=lambda each: str(each.get("started_at") or ""), default=None)


def findings(
    args: argparse.Namespace,
    subject: forms.Subject,
    form: config.ReviewForm,
    review: config.Review,
) -> Sequence[str]:
    """What an approval lacks of its head's check run.

    Args:
        args: the parsed arguments, with ``check_runs`` (a file, None: unchecked).
        subject: the review.
        form: the form the review takes.
        review: how reviews are read; its ``required_check`` is the check waited for
            unless ``--required-check`` names another.

    Returns:
        One finding for an approval of a head with no run, an unfinished run or a
        run that did not succeed; none for a completed green one, for a review
        that does not approve, and when no runs file is given.

    Raises:
        ValueError: when the file is not the JSON of check runs.
    """
    if args.check_runs is None or not approves(subject.body, form):
        return []
    check = args.required_check or review.required_check
    text = pathlib.Path(args.check_runs).read_text(encoding="utf-8")
    runs = json.loads(text).get("check_runs")
    if not isinstance(runs, list):
        raise ValueError(f"{args.check_runs}: no check_runs list")
    newest = _newest(runs, check)
    if newest is None:
        return [MISSING.format(name=subject.name, check=check)]
    if newest.get("status") != "completed":
        return [
            PENDING.format(name=subject.name, check=check, state=newest.get("status"))
        ]
    if newest.get("conclusion") != "success":
        return [
            RED.format(
                name=subject.name, check=check, conclusion=newest.get("conclusion")
            )
        ]
    return []
