"""What the review rounds of a PR show (keyword: all-findings, pitboss#169)."""

import dataclasses

from . import flowstate, missed


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Rounds:
    """What the review rounds of a PR show.

    Attributes:
        merges_only: only merges (or skill-zips/) since an older approval.
        missed_before: the findings its regular reviews up to the newest Opus
            ruling mark ``Missed earlier:`` (all of them when it has no ruling).
        missed_after: the findings the reviews after that ruling mark so.
    """

    merges_only: bool = False
    missed_before: int = 0
    missed_after: int = 0


def of(state: flowstate.PullState, merges_only: bool) -> Rounds:
    """Read the rounds of a PR.

    Args:
        state: what is recorded of the PR.
        merges_only: only merges (or skill-zips/) since an older approval.

    Returns:
        The rounds.
    """
    ruling = flowstate.newest_ruling(state)
    before, after = missed.split(state.graded, ruling.created_at if ruling else "")
    return Rounds(merges_only=merges_only, missed_before=before, missed_after=after)
