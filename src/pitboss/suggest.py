"""The top suggestions of ``next`` and ``slots next``, each with its brief.

The first suggestion is the one the process requires, the others are the next
ones that could start, so that a reason the model cannot name (the slot cap, a
missing checkout) does not stop the work. The order is the one ``work.queued``
gives, with the PRs at an Opus ruling before it: a ruling is owed first and
takes no slot (keyword: brief, pitboss#118).
"""

import dataclasses
import subprocess
from typing import Iterable, Mapping, Sequence

from . import (
    brief,
    briefconfig,
    config,
    fixes,
    ghapi,
    parsing,
    pulls,
    reviews,
    steps,
    work,
)
from .markers import Marker

TOP = 5
OPUS_MODEL = "Opus agent, no slot"
KIND_OF_CATEGORY = {
    work.Category.NEW_PR: brief.Kind.NEW_PR,
    work.Category.FIRST_ROUND: brief.Kind.FIRST_ROUND,
    work.Category.REVISE_PLAN: brief.Kind.REVISE_PLAN,
    work.Category.FIX_REVIEW: brief.Kind.FIX_REVIEW,
    work.Category.FIX_CI: brief.Kind.FIX_CI,
    work.Category.RESOLVE_CONFLICT: brief.Kind.RESOLVE_CONFLICT,
}


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


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Suggestion:
    """One thing to start, with the brief to paste.

    Attributes:
        kind: the kind of brief.
        reference: the PR or ticket.
        model: the model class it goes to.
        text: the brief.
    """

    kind: brief.Kind
    reference: str
    model: str
    text: str


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
    """

    github: ghapi.GitHub
    settings: config.Config
    given: str
    brief: briefconfig.Brief
    facts: Sequence[pulls.PullFacts]
    items: Sequence[work.Item]
    failed: Mapping[str, Sequence[str]]


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
        The PRs at an Opus ruling, oldest first, then the queued work.
    """
    by_reference = {pulls.reference(each): each for each in source.facts}
    ruled = sorted(
        (each for each in source.facts if each.step.step is steps.Step.OPUS_RULING),
        key=lambda each: each.pull.created_at,
    )
    return [
        *map(_ruling_pick, ruled),
        *(_queued_pick(each, by_reference) for each in source.items),
    ]


def review_kind(pull: pulls.PullFacts) -> brief.Kind:
    """The kind of review a PR is due, and so its scope.

    A head that differs from the approved one only by a merge of the base is
    checked for the merge alone; a head after a review that asked for changes
    for those findings alone, but only once the Plan is approved (a revised Plan is
    graded with the Execution as a first review is); the Plan stage for the Plan
    alone; any other head for the full review of that head.

    Args:
        pull: the PR, at a review step.

    Returns:
        The kind.
    """
    found = pull.review
    asked = found is not None and found.verdict is reviews.Verdict.CHANGES_NEEDED
    older = pull.standing is reviews.Standing.OLDER_HEAD
    resolved = pull.standing is reviews.Standing.APPROVED_BEFORE_MERGES
    if resolved or pull.merges_only:
        return brief.Kind.REVIEW_RESOLUTION
    if pull.step.stage is steps.Stage.PLAN_ONLY:
        return brief.Kind.REVIEW_PLAN
    if pull.step.stage is steps.Stage.PLAN_AND_EXECUTION:
        return brief.Kind.REVIEW_FULL  # the Plan was never approved: graded alone
    if older and asked:
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
    if pick.category is work.Category.REVIEW and pick.pull is not None:
        return review_kind(pick.pull)
    return KIND_OF_CATEGORY[pick.category]


def _ticket_title(source: Source, ticket: str, fallback: str) -> str:
    slug, _, number = ticket.rpartition("#")
    try:
        text = ghapi.get(source.github, f"repos/{slug}/issues/{number}")
    except subprocess.CalledProcessError:
        return fallback
    found = parsing.issue_of(text)
    return found[0].title if found else fallback


def goal(source: Source, pick: Pick) -> tuple[str, str]:
    """The ticket a pick is for, and its original goal in one line.

    Args:
        source: what suggestions are made from.
        pick: what could start.

    Returns:
        The ticket (empty when none is known) and the goal: the title of the
        ticket, else the title of the PR.
    """
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


def _heads(source: Source, pull: pulls.PullFacts | None) -> brief.Heads:
    base = source.settings.project.base_branch
    if pull is None:
        return brief.Heads(head="", base=base, approved="", findings="")
    found = pull.review
    return brief.Heads(
        head=pull.pull.head.sha,
        base=pull.pull.base,
        approved=found.sha if found else "",
        findings=found.url if found else "",
    )


def _rules(source: Source, slug: str, head: str) -> brief.Rules:
    footers = source.settings.lint.footers
    return brief.Rules(
        config=source.given,
        form=_form(source, slug, head),
        footer=footers[0] if footers else "",
        project=source.brief,
    )


def spec(source: Source, pick: Pick) -> brief.Spec:
    """What the brief of a pick is built from.

    Args:
        source: what suggestions are made from.
        pick: what could start.

    Returns:
        The spec.
    """
    ticket, text = goal(source, pick)
    slug = pick.reference.rpartition("#")[0]
    heads = _heads(source, pick.pull)
    return brief.Spec(
        kind=kind_of(pick),
        subject=brief.Subject(
            reference=pick.reference, ticket=ticket, repo=slug, goal=text
        ),
        heads=heads,
        rules=_rules(source, slug, heads.head),
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


def lines(source: Source) -> Iterable[str]:
    """The top suggestions, each as a header, its brief and an end line.

    Args:
        source: what suggestions are made from.

    Yields:
        The lines: up to ``TOP`` suggestions in order, then how many more
        are queued; one line when nothing could start.
    """
    marker = Marker.SUGGESTION.text
    every = picks(source)
    shown = every[:TOP]
    if not shown:
        yield f"{marker}: none: nothing is queued that could start"
    for rank, pick in enumerate(shown, start=1):
        found = suggest(source, pick)
        yield (
            f"{marker} {rank} of {len(shown)}: {found.kind.value}:"
            f" {found.reference}: {found.model}"
        )
        yield from found.text.splitlines()
        yield f"--- end of suggestion {rank} ---"
    if len(every) > len(shown):
        yield f"{marker}: {len(every) - len(shown)} more queued, not shown"
