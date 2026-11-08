"""The open PRs of the project and its libraries, and what each needs."""

import dataclasses
import subprocess
from typing import AbstractSet, Callable, Sequence

from . import (
    analysis,
    basefix,
    bodydigest,
    config,
    conflicts,
    dispatchruns,
    draftfacts,
    earlyfound,
    flow,
    flowstate,
    folds,
    headchecks,
    ghapi,
    mergesonly,
    parsing,
    pinsask,
    pinsreading,
    pullfiles,
    relock,
    reviews,
    rounds,
    shapes,
    steps,
    straycomments,
    unreadableform,
)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PullFacts:
    """What one open PR looks like now.

    Attributes:
        repo: its repository.
        pull: the PR.
        checks: the check runs of its head.
        review: its newest review that counts.
        standing: where its head stands with that review.
        signals: what may block it besides its checks (keyword: red-status).
        unreadable: its comments that try to be reviews and are not (keyword:
            unreadable-review).
        step: the one step the PR is at (keyword: review-flow).
        review_rounds: what its review rounds show.
        relock: whether its head branch starts with the relock prefix
            (keyword: relock).
    """

    repo: config.Repo
    pull: shapes.Pull
    checks: Sequence[shapes.CheckRun]
    review: reviews.Found | None
    standing: reviews.Standing
    signals: headchecks.HeadSignals = dataclasses.field(
        default_factory=headchecks.HeadSignals
    )
    unreadable: straycomments.StrayComments = dataclasses.field(
        default_factory=straycomments.StrayComments
    )
    step: steps.Next
    review_rounds: rounds.Rounds = dataclasses.field(default_factory=rounds.Rounds)
    relock: bool = False


def unhealthy(facts: PullFacts) -> bool:
    """Whether the PR has a failed check, a conflict or is a draft.

    Args:
        facts: the PR.

    Returns:
        True when it is any of them.
    """
    return bool(failed_checks(facts)) or conflicted(facts) or facts.pull.draft


def reference(facts: PullFacts) -> str:
    """The PR's ``owner/name#number``.

    Args:
        facts: the PR.

    Returns:
        The reference.
    """
    return f"{facts.repo.slug}#{facts.pull.number}"


def failed_checks(facts: PullFacts) -> Sequence[shapes.CheckRun]:
    """The head's failed checks.

    Args:
        facts: the PR.

    Returns:
        The checks.
    """
    return [check for check in facts.checks if check.failed]


def pending(facts: PullFacts) -> int:
    """How many of the head's checks have not finished.

    Args:
        facts: the PR.

    Returns:
        The count.
    """
    return sum(1 for check in facts.checks if not check.finished)


def waiting_for_ci(facts: PullFacts) -> bool:
    """Whether the head has no completed check run.

    Args:
        facts: the PR.

    Returns:
        True when no check run of the head has completed.
    """
    return not any(check.finished for check in facts.checks)


def green(facts: PullFacts) -> bool:
    """Whether a check of the head finished, all did, and none failed.

    A head with no completed check run is waiting for CI, never green.

    Args:
        facts: the PR.

    Returns:
        True when green.
    """
    return not waiting_for_ci(facts) and not pending(facts) and not failed_checks(facts)


def conflicted(facts: PullFacts) -> bool:
    """Whether the PR has a merge conflict.

    Args:
        facts: the PR.

    Returns:
        True on a conflict.
    """
    return conflicts.is_dirty(facts.pull)


def approved(facts: PullFacts) -> bool:
    """Whether the head's review approves it.

    Args:
        facts: the PR.

    Returns:
        True when approved.
    """
    return facts.standing in (
        reviews.Standing.APPROVED,
        reviews.Standing.APPROVED_BEFORE_MERGES,
    )


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
        if bodydigest.changed(found.body, bodydigest.digest(pull.body)):
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
        labels: its labels.
        posted: its comments and GitHub reviews that count.
        checks: the check runs of its head.
        statuses: the newest commit status of each context of its head.
        premature: its Execution reviews left out of ``posted``.
        fixed: what the base answered of its failed checks (keyword:
            fixed-on-base, pitboss#314).
    """

    pull: shapes.Pull
    labels: AbstractSet[str]
    posted: reviews.Sources
    checks: Sequence[shapes.CheckRun]
    statuses: Sequence[shapes.CommitStatus] = ()
    premature: Sequence[earlyfound.Premature] = ()
    fixed: Sequence[basefix.Answer] = ()


def _fetched(source: Source, repo: config.Repo, number: int) -> Fetched:
    text = ghapi.get(source.github, f"repos/{repo.slug}/pulls/{number}")
    pull = parsing.pull(text)
    posted = headchecks.statuses(source.github, repo, pull.head.sha)
    sent = _sources(source, repo, number)
    kept, early = source.early(repo, pull, sent.comments)
    current = headchecks.checks(source.github, repo, pull.head.sha, posted)
    queued = repo.slug in source.merge_queue
    base = pull.base
    return Fetched(
        pull=pull,
        labels=parsing.labels(text),
        posted=reviews.Sources(comments=kept, reviews=sent.reviews),
        checks=current,
        statuses=posted,
        premature=early,
        fixed=headchecks.answered(source.github, repo, base, current) if queued else (),
    )


def _state(source: Source, repo: config.Repo, got: Fetched) -> flow.PullState:
    return flow.PullState(
        pull=got.pull,
        labels=got.labels,
        checks=basefix.settle(got.checks, got.fixed),
        graded=reviews.recorded(source.review, repo.slug, got.posted),
        comments=got.posted.comments,
        trusted=source.review.trusted,
        undraft_clear=got.pull.draft and source.undraft(),
        merges_only_since=lambda sha: mergesonly.carries(
            source.github, repo, got.pull, sha
        ),
        relock=relock.is_relock(got.pull.head.branch, source.relock_prefix),
        draft=draftfacts.Draft(
            needs_e2e=lambda: pullfiles.touches(
                source.github, repo.slug, got.pull.number, source.run_by_e2e
            )
            and not dispatchruns.completed(source.github, repo.slug, got.pull.head.sha),
            plan_review_check=source.plan_review_check,
        ),
    )


def _unreadable(
    source: Source, repo: config.Repo, got: Fetched, found: reviews.Found | None
) -> straycomments.StrayComments:
    rules = reviews.rules(source.review, repo.slug)
    seen = (got.posted.comments, source.review.trusted)
    return straycomments.StrayComments(
        newer=unreadableform.unread(*seen, rules, found.when if found else ""),
        graded=unreadableform.find(*seen, rules[1], reviews.line_pattern),
        unanalysed=analysis.unanalysed(*seen),
        premature=earlyfound.newer(got.premature, found.when if found else ""),
    )


def _signals(
    source: Source, repo: config.Repo, got: Fetched, state: flow.PullState
) -> headchecks.HeadSignals:
    ruled = folds.ruling_comments(got.posted.comments, source.review.trusted)
    found = headchecks.signals(got.statuses, got.checks, got.labels, ruled)
    unmet = headchecks.gate(got.statuses, repo.slug, source.review.gated)
    # keyword: plan-approved (pitboss#296): the Plans that reviews approved
    approved = flowstate.approved_digests(state.graded)
    # keyword: pins-only (pitboss#34): asked only where a review would be offered
    pins = pinsask.at_review(source.pins, repo, got.pull, flow.next_step(state))
    return dataclasses.replace(
        found, gate=unmet, approved_plans=approved, pins=pins, fixed=got.fixed
    )


def _step(state: flow.PullState, signals: headchecks.HeadSignals) -> steps.Next:
    # keyword: fixed-on-base: the flow read the answered failures as passed
    step = pinsask.unreviewed(flow.next_step(state), signals.pins)
    return dataclasses.replace(step, on_base=bool(signals.fixed))


def fetch(source: Source, repo: config.Repo, number: int) -> PullFacts:
    """Read one PR: its details, its head's checks and its review.

    Args:
        source: where to read from.
        repo: its repository.
        number: its number.

    Returns:
        The PR's facts.
    """
    got = _fetched(source, repo, number)
    found = reviews.newest(got.posted, source.review, repo.slug)
    standing, merged = _standing(source, repo, got.pull, found)
    state = _state(source, repo, got)
    signals = _signals(source, repo, got, state)
    return PullFacts(
        repo=repo,
        pull=got.pull,
        checks=got.checks,
        review=found,
        standing=standing,
        signals=signals,
        unreadable=_unreadable(source, repo, got, found),
        step=_step(state, signals),
        review_rounds=rounds.of(state, merged),
        relock=relock.is_relock(got.pull.head.branch, source.relock_prefix),
    )


Read = PullFacts | shapes.Unreadable


def readable(found: Sequence[Read]) -> Sequence[PullFacts]:
    """The PRs that were read.

    Args:
        found: each open PR, read or not.

    Returns:
        The ones that were read.
    """
    return [each for each in found if isinstance(each, PullFacts)]


def fetch_or_unreadable(source: Source, repo: config.Repo, number: int) -> Read:
    """Read one PR, or say which of its API calls failed.

    Args:
        source: where to read from.
        repo: its repository.
        number: its number.

    Returns:
        The PR's facts, or the failed call.
    """
    try:
        return fetch(source, repo, number)
    except subprocess.CalledProcessError as error:
        return shapes.Unreadable(
            reference=f"{repo.slug}#{number}",
            call=ghapi.call_of(error),
            status=ghapi.status_of(error),
        )
