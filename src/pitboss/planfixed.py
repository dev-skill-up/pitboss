"""A review of an approved Plan prints the Plan verdict as fixed (pitboss#187)."""

import argparse
from typing import Protocol, Sequence

from gather.commands import add_argument

from . import gradeline

ARGUMENT = add_argument(
    "--plan-approved",
    action="store_true",
    default=False,
    help="review: the PR's Plan was already approved, so the review must have"
    " exactly one Plan line, `Plan: approved (fixed)`",
)


class Reviewed(Protocol):
    """A review to check: ``forms.Subject`` is one."""

    @property
    def name(self) -> str:
        """Returns what to call it in a finding."""

    @property
    def body(self) -> str:
        """Returns its text."""


class Worded(Protocol):
    """A review form: ``config.ReviewForm`` is one."""

    @property
    def approved(self) -> str:
        """Returns the form's word for an approval."""


def required(
    args: argparse.Namespace, subject: Reviewed, form: Worded
) -> Sequence[str]:
    """Check that a review of an approved Plan has the one fixed Plan line.

    Args:
        args: the parsed arguments of ``lint review``.
        subject: the review.
        form: the form the review takes.

    Returns:
        Nothing unless ``--plan-approved`` is given; then one finding unless
        exactly one line starts with ``Plan: `` and it is exactly ``Plan:
        approved (fixed)``: after the Plan was approved a review never gives
        another Plan verdict (keyword: plan-fixed).
    """
    wanted = gradeline.fixed_line(form.approved)
    plans = [
        line.rstrip()
        for line in subject.body.splitlines()
        if line.startswith(gradeline.PLAN_PREFIX)
    ]
    message = (
        f"{subject.name}: the Plan was approved: the review has exactly one Plan"
        f" line, `{wanted}` (a gap in the Plan is a request for an Opus ruling,"
        " never a Plan finding) (plan-fixed)"
    )
    return [message] if args.plan_approved and plans != [wanted] else []
