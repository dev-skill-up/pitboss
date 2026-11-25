"""The open PRs of the project and its libraries, and what each needs."""

import concurrent.futures
import contextlib
import dataclasses
from typing import AbstractSet, Iterator, Sequence

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
    handbackderive,
    handbacks,
    headchecks,
    ghapi,
    mergesonly,
    missed,
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
from . import totaljson
from .pullfacts import PullFacts as PullFacts
from .pullfacts import PullRead as PullRead
from .pullfacts import Read as Read

reference = pullref.reference
failed_checks = pullref.failed_checks


Source = pullsource.Source
Asks = pullsource.Asks


def _sources(source: Source, repo: config.Repo, number: int) -> reviews.Sources:
    prefix = f"repos/{repo.slug}"
    comments, sent = concurrently.pair(  # the comments and the reviews, together
        lambda: ghapi.pages(
            source.github, f"{prefix}/issues/{number}/comments", parsing.comments
        ),
        lambda: ghapi.pages(
            source.github, f"{prefix}/pulls/{number}/reviews", parsing.reviews
        ),
    )
    return reviews.Sources(comments=comments, reviews=sent)


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
        sent: every comment and GitHub review of it, as read (keyword: gate).
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
    sent: reviews.Sources
    checks: Sequence[shapes.CheckRun]
    statuses: Sequence[shapes.CommitStatus]
    premature: Sequence[earlyfound.Premature]
    fixed: Sequence[basefix.Answer]


@contextlib.contextmanager
def _base_ahead(
    source: Source, repo: config.Repo, behind: Sequence[str]
) -> Iterator[None]:
    # start the base's read (what a failed check asks for next) and go on: its
    # answer is kept by the read memo, a failure of it is said where it is needed,
    # and the read is finished when the block ends (keyword: reads-joined, #524)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        for ref in behind:
            pool.submit(_base_runs, source, repo, ref)
        yield


def _asked_next(source: Source, repo: config.Repo, pull: shapes.Pull) -> Sequence[str]:
    # the base's runs, which a failed check of a queued repository asks for next
    return [pull.base] if repo.slug in source.merge_queue else []


def _together(
    source: Source, repo: config.Repo, pull: shapes.Pull, number: int
) -> tuple[headchecks.Read, reviews.Sources]:
    # the head's reads and the PR's, together, and the base's beside them
    with _base_ahead(source, repo, _asked_next(source, repo, pull)):
        return concurrently.pair(
            lambda: headchecks.read_head(source.github, repo, pull.head.sha),
            lambda: _sources(source, repo, number),
        )


def _base_runs(source: Source, repo: config.Repo, base: str) -> None:
    headchecks.runs_of(source.github, repo, base)  # a failure stays in its future


def _fetched(source: Source, repo: config.Repo, number: int) -> Fetched:
    text = ghapi.get(source.github, f"repos/{repo.slug}/pulls/{number}")
    pull = parsing.pull(text)
    gated = pullobject.pull_object(
        totaljson.members(totaljson.read(text)), totalschema.schema()
    )
    head = pull.head.sha
    queued = repo.slug in source.merge_queue
    seen, sent = _together(source, repo, pull, number)
    posted = seen.statuses
    kept, early = source.early(repo, pull, sent.comments)
    current = headchecks.settled(source.github, repo, head, seen)
    base = pull.base
    return Fetched(
        pull=pull,
        object=gated,
        labels=parsing.labels(text),
        posted=reviews.Sources(comments=kept, reviews=sent.reviews),
        sent=sent,
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
    kept = dataclasses.replace(
        found.recorded, unchanged=_unchanged(source, repo, found)
    )
    return dataclasses.replace(found, draft=draft, recorded=kept)


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


def _relocked(source: Source, got: Fetched) -> bool:
    return relock.is_relock(got.pull.head.branch, source.relock_prefix)


def _handed(
    source: Source, got: Fetched, trusted: AbstractSet[str]
) -> handbacks.HandedBack:
    # keyword: standing: only a relock PR owes no hand-back
    if _relocked(source, got):
        return handbacks.NOT_REQUIRED
    return handbackderive.derive(got.pull, got.posted.comments, trusted)


def _base_state(source: Source, repo: config.Repo, got: Fetched) -> flow.PullState:
    trusted = source.review.trusted
    is_relock = _relocked(source, got)
    graded = reviews.recorded(source.review, repo.slug, got.posted)
    return flow.PullState(
        pull=got.pull,
        labels=got.labels,
        checks=_settled(source, got, graded),
        graded=graded,
        comments=got.posted.comments,
        trusted=trusted,
        undraft_clear=got.pull.draft and source.undraft(),
        relock=is_relock,
        recorded=flowstate.Recorded(
            unchanged=frozenset(),
            handed=_handed(source, got, trusted),
        ),
        draft=_draft(source, repo),
    )


def _settled(
    source: Source, got: Fetched, graded: Sequence[shapes.Graded]
) -> Sequence[shapes.CheckRun]:
    # keyword: red-never-reviewed: a relock has no change of its own to blame
    kept = [
        basefix.settle(got.checks, got.fixed),
        basefix.settle_approved(got.checks, got.fixed, graded),
    ]
    return kept[not _relocked(source, got)]


def _draft(source: Source, repo: config.Repo) -> draftfacts.Draft:
    return draftfacts.Draft(
        needs_e2e=False,
        plan_review_check=source.plan_review_check,
        no_drafts=source.no_drafts(repo.slug),
        hold=not source.undraft(),
    )


def _rounds(state: flowstate.PullState, merges_only: bool) -> rounds.Rounds:
    # the review rounds of a PR (keyword: all-findings, pitboss#169)
    ruling = flowstate.newest_ruling(state)
    before, after = missed.split(state.graded, ruling.created_at if ruling else "")
    return rounds.Rounds(
        merges_only=merges_only, missed_before=before, missed_after=after
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
    pins = pinsask.at_review(source.asks.pins, repo, got.pull, flow.next_step(state))
    return dataclasses.replace(
        found,
        gate=unmet,
        approved_plans=plans,
        pins=pins,
        fixed=() if any(each.failed for each in state.checks) else got.fixed,
        hold=state.draft.hold,
    )


def _posted(got: Fetched) -> pullfacts.Posted:
    # what the gate reads of the PR, from this one read (keyword: gate)
    return pullfacts.Posted(object=got.object, statuses=got.statuses, sources=got.sent)


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
        review_rounds=_rounds(state, merged),
        state=state,
        posted=_posted(got),
    )


def readable(found: Sequence[Read]) -> Sequence[PullFacts]:
    """The PRs that were read.

    Args:
        found: each open PR, read or not.

    Returns:
        The ones that were read.
    """
    return [each for each in found if isinstance(each, PullFacts)]
