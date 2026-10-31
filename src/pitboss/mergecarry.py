"""Whether a head differs from an older approved head only by merges of the base."""

from . import ghapi, parsing, reviews, shapes


def carries(github: ghapi.GitHub, slug: str, pull: shapes.Pull, sha: str) -> bool:
    """Whether the head differs from ``sha`` only by merges of the base.

    Args:
        github: the API.
        slug: the repository.
        pull: the PR.
        sha: the older head.

    Returns:
        True when no commit but merges is new since ``sha``.
    """
    compare = f"repos/{slug}/compare/{pull.base}..."
    since_base = ghapi.get(github, compare + pull.head.sha)
    reviewed = ghapi.get(github, compare + sha)
    return reviews.only_merges(
        parsing.comparison(since_base), parsing.comparison(reviewed)
    )


def merged_since(
    github: ghapi.GitHub, slug: str, pull: shapes.Pull, found: reviews.Found | None
) -> bool:
    """Whether an older full approval carries to the head over merges alone.

    Args:
        github: the API.
        slug: the repository.
        pull: the PR.
        found: its newest review.

    Returns:
        True for an older approval of more than the Plan, with merges since.
    """
    if found is None or reviews.head_standing(found, pull.head.sha) is not (
        reviews.Standing.OLDER_HEAD
    ):
        return False
    approves = found.verdict is reviews.Verdict.APPROVED
    return (
        approves
        and not reviews.plan_only(found)
        and carries(github, slug, pull, found.sha)
    )
