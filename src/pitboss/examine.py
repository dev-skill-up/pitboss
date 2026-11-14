"""The examination of one item: its details and its closure, read (keyword: one-path).

The walk (``readworld``) examines an item when it reaches it and ``decide`` has
not already said from the grounds that no actor takes it; ``onepath`` hands the
walk these two functions bound to their context (``readworld.Examiner``). Each
examination reads and records; nothing here decides (plan 6.1: the reader only
reads).
"""

import dataclasses
import datetime
from typing import AbstractSet, Sequence

from . import (
    allowlistmiss,
    blockedby,
    blockedstep,
    blockers,
    config,
    configrepos,
    failures,
    flowstep,
    gatefacts,
    ghapi,
    listed,
    pullfacts,
    pullnames,
    pullrecords,
    pulls,
    sharedstep,
    steps,
    stuckci,
    world,
    workorder,
)

GATED = frozenset({steps.Step.MERGE, steps.Step.UNDRAFT})  # keyword: gate


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Context:
    """What an examination reads with.

    Attributes:
        github: the API (its reads are tried again, then fail: ``retrying``).
        settings: the configuration.
        now: the time now.
        pull: a pull request read (``decide.facts_of`` gives its step from what
            was read and the closure ``examine_pull`` reads).
        closures: how a pull request's gate and shared red are read.
    """

    github: ghapi.GitHub
    settings: config.Config
    now: datetime.datetime
    pull: world.PullReader
    closures: world.Closures


def _blockers_of(
    github: ghapi.GitHub,
    settings: config.Config,
    facts: pulls.PullFacts,
    closure: blockedstep.Closure,
) -> Sequence[str]:
    # the open items a pull request waits for: its own Blocked-by lines, and the
    # blockers of the tickets it fixes (keyword: blocked-pull)
    me = pulls.reference(facts)
    open_ones = [each for each in closure.found if each.state is blockedstep.State.OPEN]
    declared = [each.reference for each in open_ones]
    named = pullnames.names(
        facts.pull.title, facts.pull.body, facts.pull.head.branch, facts.repo
    )
    waits = {
        each: blockers.pull_waits(github, settings, facts, each)
        for each in sorted(named)
    }
    found = [
        *declared,
        *(b for w in waits.values() if w is not None for b in w.blockers),
    ]
    for ticket in (each for each, w in waits.items() if w is not None):
        refused = blockers.refusal_blockers(github, settings, me, ticket)
        # a ticket the PR works on never blocks it (keyword: plan-refusal)
        found += [each for each in refused if each not in waits]
        found += _allowlist(github, facts)
    return [each for each in dict.fromkeys(found) if each != me]


def _fixing(facts: pulls.PullFacts) -> bool:
    # whether the pull request's step is a fix of its CI
    step = facts.step
    return isinstance(step, steps.Next) and step.task is steps.Task.FIX_CI


def _allowlist(github: ghapi.GitHub, facts: pulls.PullFacts) -> Sequence[str]:
    # keyword: allowlist-miss (pitboss#448): a red only a merged allowlist line fixes
    return allowlistmiss.missing(github, facts)[1] if _fixing(facts) else ()


def examine_pull(
    reading: Context,
    row: listed.Listed,
    others: Sequence[listed.Listed],
    holds: Sequence[pullrecords.Hold],
) -> world.PullRecord:
    """Read one open pull request and its closure.

    Args:
        reading: what the read starts from.
        row: its listing row.
        others: the other open rows of its repository (a shared red's closure).
        holds: its repository's hold issues (its gate's, keyword: gate).

    Returns:
        Its record.
    """
    github = reading.github
    read = reading.pull(row)
    facts = flowstep.at_flow(read)  # the flow's step chooses the closures read
    blocked_by = blockedby.read_closure(github, facts)
    named = _blockers_of(github, reading.settings, facts, blocked_by)
    fixing = _fixing(facts)
    return world.PullRecord(
        row=row,
        facts=read,
        blocked_by=blocked_by,
        shared=_shared(reading, facts, others) if not named else (),
        blockers=named,
        stuck=stuckci.runs_of(github, [facts], reading.now),  # keyword: stuck-ci
        gated=_gated(reading, read, facts, holds),
        failures=failures.read_all(github, facts) if fixing else {},
    )


def _shared(
    reading: Context, facts: pulls.PullFacts, others: Sequence[listed.Listed]
) -> Sequence[sharedstep.Shared]:
    # keyword: shared-red: read only for a red PR that names no blocker, the one
    # that is printed (plan 3.1(4))
    return reading.closures.shared(facts, others) if _fixing(facts) else ()


def _gated(
    reading: Context,
    read: pullfacts.PullRead,
    facts: pulls.PullFacts,
    holds: Sequence[pullrecords.Hold],
) -> gatefacts.Gate | None:
    # keyword: gate: read only at the merge or the undraft step
    gated = steps.step_is(facts.step, GATED)
    return reading.closures.gated(read, holds) if gated else None


def examine_ticket(
    reading: Context, ticket: workorder.Ticket, branches: Sequence[str]
) -> world.TicketRecord:
    """Read one open ticket's closure.

    Args:
        reading: what the read starts from.
        ticket: the ticket.
        branches: the head branches of its repository's open pull requests.

    Returns:
        Its record.
    """
    reference = ticket.reference
    found, superseded = blockers.waiting(
        reading.github, reading.settings, ticket.issue, reference
    )
    return world.TicketRecord(
        reference=reference,
        issue=ticket.issue,
        priority=ticket.priority,
        superseded=superseded,
        blockers=found,
        opens_ready=_opens_ready(reading.settings.project, reference),
        branch_named=_branch_named(reference, branches),
    )


def _branch_named(reference: str, branches: Sequence[str]) -> AbstractSet[str]:
    # keyword: taken: the tickets the open pull requests' branches name
    repo = configrepos.repo_of(reference)
    return frozenset().union(
        *(pullnames.names("", "", each, repo) for each in branches)
    )


def _opens_ready(project: config.Project, reference: str) -> bool:
    # keyword: no-drafts
    return not project.drafts or reference.rpartition("#")[0] in project.no_drafts
