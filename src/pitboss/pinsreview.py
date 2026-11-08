"""The review comment of a relock PR whose pins-check printed OK (keyword: pins-review).

pitboss#350 (owner, 2026-11-07T11:50Z: relocks are mechanical; green CI and
``bats pins-check`` printing OK merge with no agent review): a gated repository
still needs a review comment in the gate's form, so ``pitboss pins-review``
posts it, with the pins-check output and the ruling in it, and no agent is
dispatched. This module judges whether the PR may have one and writes it.
"""

import re

from . import config, pinsreading, pulls, relock

RULING = (
    "Owner ruling (2026-11-07T11:50Z): relocks are mechanical; green CI and"
    " `bats pins-check` printing OK merge with no agent review (pitboss#350)."
)
# what a gate's form refuses in a review, or reads as another line of it
UNFIT = re.compile(
    r"[^\x20-\x7e]|```|~~~|<[A-Za-z/]|^\s*\[[^\]]*\]:|Verdict:|Reviewed:",
    re.IGNORECASE,
)


def unready(facts: pulls.PullFacts, prefix: str) -> str:
    """Why a PR may not have the comment before the pins-check is run, else nothing.

    Args:
        facts: the PR.
        prefix: ``[relock] prefix``, the head branch prefix of a relock PR.

    Returns:
        Empty for a PR on a relock branch whose checks are all green; else the
        reason.
    """
    reference = pulls.reference(facts)
    if not relock.is_relock(facts.pull.head.branch, prefix):
        return f"{reference} is not on a relock branch (head {facts.pull.head.branch})"
    if pulls.green(facts):
        return ""
    failed = ",".join(check.name for check in pulls.failed_checks(facts))
    return (
        f"{reference} is not green: {len(facts.checks)} checks,"
        f" pending={pulls.pending(facts)} failed=[{failed}]"
    )


def unclear(reading: pinsreading.Reading) -> str:
    """Why what the pins-check said is no comment, else nothing.

    Args:
        reading: what the pins-check said of the head (``pinsonly.verify``; it
            is NOT_OK for a compiler older than the head's bats pin).

    Returns:
        Empty for an OK line the gate reads as plain text; else the reason.
    """
    if not pinsreading.cleared(reading):
        return f"pins-check did not print OK ({reading.detail})"
    if UNFIT.search(reading.detail):
        return f"its OK line cannot be pasted as plain text: {ascii(reading.detail)}"
    return ""


def comment(form: config.ReviewForm, head: str, reading: pinsreading.Reading) -> str:
    """The review comment.

    Args:
        form: the repository's form (``pitboss review-form``).
        head: the PR's full head SHA.
        reading: the pins-check's OK.

    Returns:
        The form's lines with the approving verdict and the head, then the
        pins-check's line and the ruling, each on a line of its own.
    """
    lines = [
        each.replace("{sha}", head).replace("{verdict}", form.approved)
        for each in form.lines
    ]
    return "\n".join([*lines, "", f"pins-check: {reading.detail}", RULING, ""])
