"""The top suggestions of ``next`` and ``slots next``, each with its brief.

On a crowded volume (90% used or more) the clean suggestion comes first; the
first of the picks is the one the process requires, the others are the next
ones that could start, so that a reason the model cannot name (a missing
checkout) does not stop the work. The order is the one ``work.queued``
gives, with the PRs at an Opus ruling before it: a ruling is owed first and
takes no slot (keyword: brief, pitboss#118).
"""

import dataclasses
import pathlib
from typing import Iterable, Mapping, Sequence

from . import (
    brief,
    briefconfig,
    briefheads,
    briefrepo,
    config,
    configfile,
    diskwatch,
    fixes,
    gates,
    ghapi,
    nextfound,
    pullfiles,
    pulls,
    reviews,
    slotheld,
    steps,
    suggestflake,
    suggestkind,
    suggestlogs,
    suggestwhen,
    ticketread,
    work,
)
from .markers import Marker

TOP = 5
OPUS_MODEL = "Opus agent, no slot"
RELOCK_GOAL = (
    "relock PR {reference} ({title}): move the pins; moves of pins are safe when"
    " the lock matches and CI is green"
)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Pick:
    """One thing that could start.

    Attributes:
        reference: the PR, or the ticket of a new PR.
        title: its title.
        category: what it needs, None for a ruling.
        item: the queued work it is, None for a ruling.
        pull: the PR it is about, None for a ticket.
    """

    reference: str
    title: str
    category: work.Category | None
    item: work.Item | None
    pull: pulls.PullFacts | None


Suggestion = suggestkind.Suggestion


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Source:
    """What suggestions are made from.

    Attributes:
        github: the API.
        settings: the configuration.
        given: the configuration as the command was given it.
        brief: what the project's briefs say beyond the process.
        facts: the open PRs that were read.
        items: the queued work, in order.
        failed: each reference's failed models.
        volume: the workspace's volume as read (keyword: disk-watch,
            pitboss#288), None when unread.
        big: the largest scratch entries, read only for a crowded volume.
        occupancy: what holds the slots (keyword: slot-held, pitboss#291).
    """

    github: ghapi.GitHub
    settings: config.Config
    given: str
    brief: briefconfig.Brief
    facts: Sequence[pulls.PullFacts]
    items: Sequence[work.Item]
    failed: Mapping[str, Sequence[str]]
    volume: diskwatch.Reading | None = None
    big: Sequence[diskwatch.Big] = ()
    occupancy: slotheld.Occupancy = slotheld.UNLIMITED


def sourced(
    found: nextfound.Found,
    facts: Sequence[pulls.PullFacts],
    items: Sequence[work.Item],
    failed: Mapping[str, Sequence[str]],
) -> Source:
    """What suggestions are made from, with the briefs the project gives.

    Args:
        found: the context.
        facts: the open PRs that were read.
        items: the queued work, in order.
        failed: each reference's failed models.

    Returns:
        The source, with no volume read.
    """
    given = configfile.named(found.args)
    start = pathlib.Path(found.args.env.get("PWD", "."))
    return Source(
        github=found.github,
        settings=found.settings,
        given=given,
        brief=configfile.load_brief(given, start),
        facts=facts,
        items=items,
        failed=failed,
    )


def _ruling_pick(each: pulls.PullFacts) -> Pick:
    return Pick(
        reference=pulls.reference(each),
        title=each.pull.title,
        category=None,
        item=None,
        pull=each,
    )


def _queued_pick(each: work.Item, by_reference: Mapping[str, pulls.PullFacts]) -> Pick:
    return Pick(
        reference=each.reference,
        title=each.title,
        category=each.category,
        item=each,
        pull=by_reference.get(each.reference),
    )


def picks(source: Source) -> Sequence[Pick]:
    """Everything that could start, in the order to take it.

    Args:
        source: what suggestions are made from.

    Returns:
        The PRs at a ruling, oldest first, then the queued work (keyword: slot-held).
    """
    by_reference = {pulls.reference(each): each for each in source.facts}
    ruled = sorted(
        (each for each in source.facts if each.step.step is steps.Step.OPUS_RULING),
        key=lambda each: each.pull.created_at,
    )
    return [
        *map(_ruling_pick, ruled),
        *(
            _queued_pick(each, by_reference)
            for each in source.items
            if source.occupancy.known
            and not slotheld.waits(source.occupancy, each.reference)
        ),
    ]


def review_kind(pull: pulls.PullFacts) -> brief.Kind:
    """The kind of review a PR is due, and so its scope.

    A head that differs from the approved one only by a merge of the base is
    checked for the merge alone; a head after a review that asked for changes
    for those findings alone, but only once the Plan is approved; the Plan stage
    (a draft's, or a Plan revised after its rejection, pitboss#167) for the Plan
    alone; any other head for the full review of that head. A relock PR
    (keyword: relock) is reviewed for the relock itself, at any head but a
    merge of the base or a fix round.

    Args:
        pull: the PR, at a review step.

    Returns:
        The kind.
    """
    resolved = pull.standing is reviews.Standing.APPROVED_BEFORE_MERGES
    if resolved or pull.review_rounds.merges_only:
        return brief.Kind.REVIEW_RESOLUTION
    if pull.relock and not work.fix_round(pull):
        return brief.Kind.REVIEW_RELOCK  # keyword: relock (pitboss#126)
    if pull.step.stage is steps.Stage.PLAN_ONLY:
        return brief.Kind.REVIEW_PLAN
    if pull.step.stage is steps.Stage.PLAN_AND_EXECUTION:
        return brief.Kind.REVIEW_FULL  # the Plan was never approved: graded alone
    if work.fix_round(pull):
        return brief.Kind.REVIEW_FIX_ROUND
    return brief.Kind.REVIEW_EXECUTION


def kind_of(pick: Pick) -> brief.Kind:
    """The kind of brief a pick gets.

    Args:
        pick: what could start.

    Returns:
        The kind.
    """
    if pick.category is None:
        return brief.Kind.RULING
    reviewed = (work.Category.REVIEW, work.Category.REVIEW_FIX_ROUND)
    if pick.category in reviewed and pick.pull is not None:
        return review_kind(pick.pull)
    if pick.pull is not None and pick.pull.step.task is steps.Task.FIX_ROUND:
        return brief.Kind.FIX_ROUND  # keyword: fix-round-kind (pitboss#390)
    return suggestkind.OF_CATEGORY[pick.category]


def _ticket_title(source: Source, ticket: str, fallback: str) -> str:
    found = ticketread.issue(source.github, ticket)
    return found.title if found else fallback


def goal(source: Source, pick: Pick) -> tuple[str, str]:
    """The ticket a pick is for, and its original goal in one line.

    Args:
        source: what suggestions are made from.
        pick: what could start.

    Returns:
        The ticket (empty when none is known) and the goal: the title of the
        ticket, else the title of the PR.
    """
    if pick.pull is not None and pick.pull.relock:
        return "", RELOCK_GOAL.format(reference=pick.reference, title=pick.title)
    named = sorted(fixes.fixed_tickets(pick.pull)) if pick.pull else [pick.reference]
    if not named:
        return "", f"PR {pick.reference}, which names no ticket: {pick.title}"
    title = _ticket_title(source, named[0], pick.title) if pick.pull else pick.title
    return named[0], f"ticket {named[0]}: {title}"


def _form(source: Source, slug: str, head: str) -> Sequence[str]:
    form = reviews.rules(source.settings.review, slug)[1]
    verdict = f"<{form.approved} or {form.changes_needed}>"
    return [
        line.replace("{sha}", head).replace("{verdict}", verdict) for line in form.lines
    ]


def _rules(source: Source, slug: str, head: str) -> brief.Rules:
    review = source.settings.review
    return brief.Rules(
        config=source.given,
        form=_form(source, slug, head),
        project=briefrepo.of_repository(
            source.brief,
            slug,
            source.settings.project.no_drafts,
            source.settings.runners.exempt,
        ),
        gate_note=gates.note(sorted(review.trusted)) if slug in review.gated else "",
        plan_check=source.settings.project.plan_review_check,
    )


def _touches_e2e(source: Source, pick: Pick, kind: brief.Kind) -> bool:
    # keyword: run-e2e (pitboss#199): read the files only for a review of a PR
    found = pick.pull
    if found is None or kind not in brief.E2E_KINDS:
        return False
    slug = found.repo.slug
    prefixes = source.settings.project.run_by_e2e
    return pullfiles.touches(source.github, slug, found.pull.number, prefixes)


def spec(source: Source, pick: Pick) -> brief.Spec:
    """What the brief of a pick is built from.

    Args:
        source: what suggestions are made from.
        pick: what could start.

    Returns:
        The spec.
    """
    about = goal(source, pick)
    slug = pick.reference.rpartition("#")[0]
    heads = briefheads.of(source.settings.project.base_branch, pick.pull)
    kind = kind_of(pick)
    rules = _rules(source, slug, heads.head)
    return brief.Spec(
        kind=kind,
        subject=suggestwhen.subject(source.github, pick.reference, about, kind),
        heads=heads,
        rules=suggestflake.rules_of(source.github, about[0], rules),
        ready=pick.pull is not None and not pick.pull.pull.draft,
        e2e=_touches_e2e(source, pick, kind),
        logs=(
            suggestlogs.of(pick.pull) if pick.pull and kind is brief.Kind.FIX_CI else ()
        ),
    )


def model_class(source: Source, pick: Pick) -> str:
    """The model class a pick goes to.

    Args:
        source: what suggestions are made from.
        pick: what could start.

    Returns:
        A slot and the smallest model it may go to, or the Opus agent of a
        ruling, which takes no slot.
    """
    if pick.item is None:
        return OPUS_MODEL
    slots = source.settings.slots
    model = work.smallest_model(pick.item, slots, source.failed) or "none left"
    return f"slot, smallest model {model}"


def suggest(source: Source, pick: Pick) -> Suggestion:
    """The suggestion for a pick.

    Args:
        source: what suggestions are made from.
        pick: what could start.

    Returns:
        The suggestion, with its brief.
    """
    made = spec(source, pick)
    return Suggestion(
        kind=made.kind,
        reference=pick.reference,
        model=model_class(source, pick),
        text=brief.build(made),
    )


def _ranked(
    source: Source, shown: Sequence[Pick], first: int, total: int
) -> Iterable[str]:
    marker = Marker.SUGGESTION.text
    for rank, pick in enumerate(shown, start=first):
        found = suggest(source, pick)
        yield (
            f"{marker} {rank} of {total}: {found.kind.value}:"
            f" {found.reference}: {found.model}"
        )
        yield from found.text.splitlines()
        yield f"--- end of suggestion {rank} ---"


def lines(source: Source) -> Iterable[str]:
    """The top suggestions, each as a header, its brief and an end line.

    Args:
        source: what suggestions are made from.

    Yields:
        The lines: up to ``TOP`` suggestions in order, then how many more
        are queued; one line when nothing could start. On a volume 90 % used or
        with under 1 GiB free the first suggestion is ``clean the disk``; under
        1 GiB free no worker is suggested (keyword: disk-watch, pitboss#288).
    """
    marker = Marker.SUGGESTION.text
    every = [] if diskwatch.starved(source.volume) else picks(source)
    shown = every[:TOP]
    if not shown and not diskwatch.starved(source.volume):
        yield f"{marker}: none: nothing is queued that could start"
    cleaning = diskwatch.crowded(source.volume)
    total = len(shown) + cleaning
    yield from diskwatch.opening(source.volume, source.big, total)
    yield from _ranked(source, shown, 1 + cleaning, total)
    if len(every) > len(shown):
        yield f"{marker}: {len(every) - len(shown)} more queued, not shown"
