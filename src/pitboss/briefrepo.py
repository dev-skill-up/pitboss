"""What a repository's briefs say, from the project's ``[slots.brief]``.

A repository with no drafts opens its PRs ready, and an exempt one is pushed with
no hold (keyword: pitboss-exempt, pitboss#113).
"""

import dataclasses
from typing import AbstractSet, Sequence

from . import briefconfig, exempt


def of_repository(
    given: briefconfig.Brief,
    slug: str,
    never_drafts: AbstractSet[str],
    never_held: AbstractSet[str],
    rules: Sequence[str] = (),
) -> briefconfig.Brief:
    """The ``[slots.brief]`` as it holds for one repository.

    Args:
        given: what the project's briefs say.
        slug: the repository.
        never_drafts: the repositories whose PRs open ready.
        never_held: the repositories that are never held.
        rules: the repository's own review rules (keyword: repo-rules).

    Returns:
        The same, with drafts off for a repository with no drafts and holds off
        for an exempt one.
    """
    return dataclasses.replace(
        given,
        drafts=given.drafts and slug not in never_drafts,
        holds=given.holds and not exempt.is_exempt(slug, never_held),
        review_lines=[*given.review_lines, *rules],
    )
