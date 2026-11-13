"""The open PRs of the project and its libraries, and what each needs."""

import dataclasses
import json
from typing import AbstractSet, Sequence

from . import (
    basefix,
    bodydigest,
    concurrently,
    config,
    expansion,
    dispatchruns,
    draftfacts,
    earlyfound,
    flow,
    flowquestions,
    flowstate,
    folds,
    headchecks,
    ghapi,
    mergesonly,
    parsing,
    pinsask,
    pullfacts,
    pullobject,
    pullrecords,
    pullfiles,
    pullref,
    pullsource,
    relock,
    reviews,
    reviewunread,
    rounds,
    shapes,
    straycomments,
    totalschema,
    unreadableform,
)
from .pullfacts import PullFacts as PullFacts
from .pullfacts import PullRead as PullRead
from .pullfacts import Read as Read

reference = pullref.reference
failed_checks = pullref.failed_checks


Source = pullsource.Source


def _sources(source: Source, repo: config.Repo, number: int) -> reviews.Sources:
    prefix = f"repos/{repo.slug}"
    return reviews.Sources(
        comments=ghapi.pages(
            source.github, f"{prefix}/issues/{number}/comments", parsing.comments
        ),
        reviews=ghapi.pages(
            source.github, f"{prefix}/pulls/{number}/reviews", parsing.reviews
        ),
    )


def _standing(
    source: Source, repo: config.Repo, pull: shapes.Pull, found: reviews.Found | None
) -> tuple[reviews.Standing, bool]:
    standing = reviews.head_standing(found, pull.head.sha)
    if found and standing is not reviews.Standing.OLDER_HEAD:
        if not expansion.current_for(
            expansion.Subject.BODY, found.body, bodydigest.digest(pull.body)
        ):
            standing = reviews.Standing.OLDER_BODY  # keyword: body-digest
    merged = (
        found is not None
        and standing is reviews.Standing.OLDER_HEAD
        and found.verdict is reviews.Verdict.APPROVED
        and not reviews.plan_only(found)
        and mergesonly.carries(source.github, repo, pull, found.sha)
    )
    if merged and repo.slug not in source.review.gated:
        return reviews.Standing.APPROVED_BEFORE_MERGES, True
    return standing, merged


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Fetched:
    """What the API gave for one PR.

    Attributes:
        pull: its details.
        object: the PR as the gate reads it, from the same answer as ``pull``
            (keyword: gate).
        labels: its labels.
        posted: its comments and GitHub reviews that count.
        checks: the check runs of its head.
        statuses: the newest commit status of each context of its head.
        premature: its Execution reviews left out of ``posted``.
        fixed: what the base answered of its failed checks (keyword:
            fixed-on-base, pitboss#314).
    """

    pull: shapes.Pull
    object: pullrecords.PullObject
    labels: AbstractSet[str]
    posted: reviews.Sources
    checks: Sequence[shapes.CheckRun]
    statuses: Sequence[shapes.CommitStatus] = ()
    premature: Sequence[earlyfound.Premature] = ()
    fixed: Sequence[basefix.Answer] = ()


def _fetched(source: Source, repo: config.Repo, number: int) -> Fetched:
    text = ghapi.get(source.github, f"repos/{repo.slug}/pulls/{number}")
    pull = parsing.pull(text)
    gated = pullobject.pull_object(json.loads(text), totalschema.schema())
    posted, sent = concurrently.pair(
        lambda: headchecks.statuses(source.github, repo, pull.head.sha),
        lambda: _sources(source, repo, number),
    )
    kept, early = source.early(repo, pull, sent.comments)
    current = headchecks.checks(source.github, repo, pull.head.sha, posted)
    queued = repo.slug in source.merge_queue
    base = pull.base
    return Fetched(
        pull=pull,
        object=gated,
        labels=parsing.labels(text),
        posted=reviews.Sources(comments=kept, reviews=sent.reviews),
        checks=current,
        statuses=posted,
        premature=early,
        fixed=headchecks.answered(source.github, repo, base, current) if queued else (),
    )


def _state(source: Source, repo: config.Repo, got: Fetched) -> flow.PullState:
    # the questions the flow asks are read here, each only where it is asked
    found = _base_state(source, repo, got)
    needs = _needs_e2e(source, repo, found)
    draft = dataclasses.replace(found.draft, needs_e2e=needs)
    unchanged = _unchanged(source, repo, found)
    return dataclasses.replace(found, draft=draft, unchanged=unchanged)


def _unchanged(
    source: Source, repo: config.Repo, state: flow.PullState
) -> AbstractSet[str]:
    # keyword: unfixed-execution: asked only of the rejecting review's head
    asked = flowquestions.asked_rejection(state)
    if asked is None:
        return frozenset()
    same = mergesonly.unchanged(source.github, repo, state.pull, asked.sha)
    return frozenset({asked.sha}) if same else frozenset()


def _needs_e2e(source: Source, repo: config.Repo, state: flow.PullState) -> bool:
    # keyword: run-e2e: asked only for a draft whose Plan is approved
    pull = state.pull
    if not (pull.draft and flowquestions.plan_approved(state)):
        return False
    github, slug = source.github, repo.slug
    touched = pullfiles.touches(github, slug, pull.number, source.run_by_e2e)
    return touched and not dispatchruns.completed(github, slug, pull.head.sha)


def _base_state(source: Source, repo: config.Repo, got: Fetched) -> flow.PullState:
    return flow.PullState(
        pull=got.pull,
        labels=got.labels,
        checks=basefix.settle(got.checks, got.fixed),
        graded=reviews.recorded(source.review, repo.slug, got.posted),
        comments=got.posted.comments,
        trusted=source.review.trusted,
        undraft_clear=got.pull.draft and source.undraft(),
        relock=relock.is_relock(got.pull.head.branch, source.relock_prefix),
        unchanged=frozenset(),
        draft=draftfacts.Draft(
            needs_e2e=False,
            plan_review_check=source.plan_review_check,
            no_drafts=source.no_drafts(repo.slug),
            hold=not source.undraft(),
        ),
    )


def _unreadable(
    source: Source,
    repo: config.Repo,
    got: Fetched,
    read: tuple[reviews.Found | None, flow.PullState],
) -> straycomments.StrayComments:
    found, state = read
    rules = reviews.rules(source.review, repo.slug)
    seen = (got.posted.comments, source.review.trusted)
    return straycomments.StrayComments(
        newer=unreadableform.unread(*seen, rules, found.when if found else ""),
        graded=unreadableform.find(*seen, rules[1], reviews.line_pattern),
        premature=earlyfound.newer(got.premature, found.when if found else ""),
        no_execution=reviewunread.without_execution(state),
    )


def _signals(
    source: Source, repo: config.Repo, got: Fetched, state: flow.PullState
) -> headchecks.HeadSignals:
    ruled = folds.ruling_comments(got.posted.comments, source.review.trusted)
    found = headchecks.signals(got.statuses, got.checks, got.labels, ruled)
    unmet = headchecks.gate(got.statuses, repo.slug, source.review.gated)
    # keyword: plan-approved (pitboss#296): the Plans that reviews approved
    plans = flowstate.approved_digests(state.graded)
    # keyword: pins-only (pitboss#34): asked only where a review would be offered
    pins = pinsask.at_review(source.pins, repo, got.pull, flow.next_step(state))
    return dataclasses.replace(
        found,
        gate=unmet,
        approved_plans=plans,
        pins=pins,
        fixed=got.fixed,
        hold=state.draft.hold,
    )


def fetch(source: Source, repo: config.Repo, number: int) -> PullRead:
    """Read one PR: its details, its head's checks and its review.

    Args:
        source: where to read from.
        repo: its repository.
        number: its number.

    Returns:
        The PR as read; ``decide.facts_of`` gives its step.
    """
    got = _fetched(source, repo, number)
    found = reviews.newest(got.posted, source.review, repo.slug)
    standing, merged = _standing(source, repo, got.pull, found)
    state = _state(source, repo, got)
    signals = _signals(source, repo, got, state)
    return PullRead(
        repo=repo,
        pull=got.pull,
        checks=got.checks,
        review=found,
        standing=standing,
        signals=signals,
        unreadable=_unreadable(source, repo, got, (found, state)),
        review_rounds=rounds.of(state, merged),
        state=state,
        posted=pullfacts.Posted(object=got.object, statuses=got.statuses),
    )


def readable(found: Sequence[Read]) -> Sequence[PullFacts]:
    """The PRs that were read.

    Args:
        found: each open PR, read or not.

    Returns:
        The ones that were read.
    """
    return [each for each in found if isinstance(each, PullFacts)]
