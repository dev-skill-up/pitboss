"""A Plan that an earlier Plan check approved, and the post (keyword: plan-prior).

An approved Plan is never edited (pitboss#444, cases 1, 10 and 30): when the PR
already has a comment whose first line is ``Plan check``, that ends with
``Plan check: ok`` and records the digest of the Plan as it is now, a later
``pitboss plan-check --pull`` does not judge the Plan again by the run of the
head or by the ticket's Done-when (they were checked then), and says which
comment it relied on. ``--post`` writes the check as that kind of comment itself
(case 14), so its heading cannot be wrong.
"""

import argparse
import sys
from typing import Sequence

from . import (
    expansion,
    ghapi,
    parsing,
    plancheckflow,
    plandigest,
    pullfile,
    shapes,
)

CHECK = "plan-prior"


def comments(github: ghapi.GitHub, slug: str, number: int) -> Sequence[shapes.Comment]:
    """The comments of a PR.

    Args:
        github: the API.
        slug: the repository's ``owner/name``.
        number: the PR's number.

    Returns:
        Its issue comments.
    """
    return ghapi.pages(
        github, f"repos/{slug}/issues/{number}/comments", parsing.comments
    )


def relied_on(found: Sequence[shapes.Comment], body: str) -> shapes.Comment | None:
    """The newest comment that approved the Plan of a body as it is.

    Args:
        found: the PR's comments.
        body: the PR body being checked.

    Returns:
        The newest clean ``Plan check`` that records the digest of the Plan
        section (the collapsed form or the older one), None when there is none.
    """
    digests = expansion.accepted_digests(plandigest.section(body))
    clean = [
        each
        for each in found
        if any(plancheckflow.is_plan_check(each.body, digest) for digest in digests)
    ]
    return max(clean, key=lambda each: each.created_at, default=None)


def note(comment: shapes.Comment) -> str:
    """The line that says which comment a check relied on.

    Args:
        comment: the earlier clean check.

    Returns:
        The line.
    """
    return (
        f"{CHECK}: this Plan was checked ok before ({comment.url}, "
        f"{comment.created_at}): its CI runs may be of an earlier head of this "
        "branch and its Done-when is not read again"
    )


def post(args: argparse.Namespace, pull: str, text: str) -> str:
    """Post the output of a check as a comment on the PR.

    Args:
        args: the parsed arguments.
        pull: ``OWNER/NAME#NUMBER``.
        text: the output, whose first line is ``Plan check``.

    Returns:
        The comment's address.
    """
    slug, number = pullfile.split("plan-check", pull)
    return pullfile.comment(pullfile.github_of(args), slug, number, text)


def post_if(args: argparse.Namespace, output: str) -> None:
    """Post the output of the check when ``--post`` names a PR.

    Args:
        args: the parsed arguments; ``post`` is a PR reference or None.
        output: what the check printed.
    """
    if args.post:
        print(post(args, args.post, output), file=sys.stderr)
