"""Where PRs are read from (keyword: pull-read)."""

import dataclasses
from typing import AbstractSet, Callable, Sequence

from . import config, earlyfound, ghapi, pinsask, pinsreading


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Source:
    """Where PRs are read from.

    Attributes:
        github: the API.
        review: how reviews are read.
        undraft: says whether the runners allow an undraft now; it is asked
            only for a draft.
        relock_prefix: the head branch prefix of a relock PR.
        run_by_e2e: the path prefixes whose change the e2e suite runs on
            (keyword: run-e2e).
        plan_review_check: the check a draft's Plan review waits for
            (keyword: plan-review-check).
        merge_queue: the repositories with a merge queue (keyword: fixed-on-base).
        early: takes the Execution reviews written before green out of a
            PR's comments (keyword: execution-before-green, pitboss#202).
        pins: asks the pins-check command about a PR at a review step
            (keyword: pins-only, pitboss#34).
        no_drafts: says whether a repository's PRs open ready (keyword: no-drafts).
    """

    github: ghapi.GitHub
    review: config.Review
    undraft: Callable[[], bool]
    relock_prefix: str = config.DEFAULT_RELOCK_PREFIX
    run_by_e2e: Sequence[str] = config.DEFAULT_RUN_BY_E2E
    plan_review_check: str = ""
    merge_queue: AbstractSet[str] = frozenset()
    early: earlyfound.Split = earlyfound.keep_all
    pins: pinsask.Ask = lambda repo, pull: pinsreading.NOTHING
    no_drafts: Callable[[str], bool] = lambda slug: False
