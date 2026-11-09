"""The ``next`` command: the one step a ticket is at (keyword: review-flow)."""

import argparse
import re
import sys
from typing import NoReturn, Sequence

from gather.commands import add_argument

from . import (
    ENTRY_DATA,
    blockers,
    brief,
    commandscan,
    configfile,
    donewhen,
    draftrule,
    fixes,
    flake,
    ledger,
    nextguide,
    nextlist,
    pulls,
    repeatruns,
    repoaccess,
    shapes,
    steps,
    tracefs,
    unreadableline,
)
from .commandarguments import CONFIG_ARGUMENT, NOW_ARGUMENT, RUNNING_ARGUMENT
from .commands import Context, load_context, open_pulls, working_directory

_FULL_REFERENCE = re.compile(r"^[\w.-]+/[\w.-]+#\d+$")


def fixing(
    found: Sequence[pulls.Read], ticket: str
) -> tuple[pulls.PullFacts | None, Sequence[shapes.Unreadable]]:
    """Pick the open PR that says it fixes a ticket.

    Args:
        found: the open PRs, read or not (read once for the run).
        ticket: the ticket, as ``owner/repo#N``.

    Returns:
        The first PR whose body says ``Fixes`` or ``Closes`` the ticket, or
        None, and the PRs that could not be read (one of them may be the
        ticket's).
    """
    named = (
        each for each in pulls.readable(found) if ticket in fixes.fixed_tickets(each)
    )
    failed = [each for each in found if isinstance(each, shapes.Unreadable)]
    return next(named, None), failed


def _refuse(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(2)


def _line(ticket: str, pull: pulls.PullFacts) -> str:
    step = pull.step
    return (
        f"{step.step.name}: {ticket} ({pulls.reference(pull)}): "
        f"{steps.describe(step)}"
    )


@ENTRY_DATA.register(
    CONFIG_ARGUMENT,
    add_argument("ticket", nargs="?", default=None),
    NOW_ARGUMENT,
    RUNNING_ARGUMENT,
    name="next",
)
def show_next(args: argparse.Namespace) -> None:
    """Print a ticket's step, or the LOG lines to post as is and the top suggestions.

    With no TICKET it prints what ``slots next`` prints: on a volume 90 % used or
    under 1 GiB free, first the ``clean the disk`` suggestion (keyword:
    disk-watch), then up to five ranked suggestions (none under 1 GiB free),
    each with the complete brief to dispatch unchanged (keyword: brief; a ruling
    brief has one line, ``How we got here:``, that the orchestrator replaces).

    TICKET is ``owner/repo#N``, ``repo#N`` or ``#N``. The open PRs are read
    once; the one whose body says ``Fixes`` or ``Closes`` the ticket is
    parsed, and its step is ``flow.next_step``. With no such PR the step is
    the ticket's first.

    For a ticket no PR fixes it first prints a ``MISSING NAMES`` line when the
    ticket's Done-when names a ``brief.Kind``, a file path or a ``pitboss``
    command that does not exist (keyword: done-when-names): no worker is spent
    on that ticket, the ticket is fixed to name what exists (a file it asks to
    create is named by its directory, not as a path) before a worker starts,
    and a worker that sees the line hands back NOT STARTED with it.

    It exits 1 when no PR names the ticket but a PR could not be read, so none
    is said not to exist. It also exits 1, with an ``INCOMPLETE`` last line, when
    a repository could not be read: no statement about its PRs is true.

    Args:
        args: the parsed arguments.
    """
    tracefs.say(args.safe_run)
    found = load_context(args)
    if args.ticket is None:
        nextlist.require_ledger(found.settings.slots.ledger)
        book = ledger.configured(found.settings)
        nextlist.show(found, open_pulls(found), book)
    else:
        _step_of(found, args.ticket)
    repoaccess.finish(found.access)


def _say_missing_names(found: Context, ticket: str) -> None:
    # the names of the ticket's Done-when that are not in this tree
    read = blockers.read(found.github, ticket)
    known = donewhen.Known(
        kinds=frozenset(brief.Kind.__members__),
        commands=frozenset(commandscan.scanned(ENTRY_DATA.collector.collect)),
        tree=working_directory(found.args),
    )
    body = read.body if read else ""
    said = donewhen.missing_line(ticket, body, known)
    if said:
        print(said)
    if repeated := repeatruns.line(ticket, donewhen.section(body)):
        print(repeated)  # keyword: repeat-runs (pitboss#278)
    for each in nextguide.done_when_lines(ticket, body):
        print(each)  # keyword: next-guide (pitboss#282)
    if jobs := nextguide.ci_jobs_line(ticket, _check_workflow(found)):
        print(jobs)
    flaky = read is not None and flake.is_flake(read.labels, read.title, body)
    if flaky and (unmarked := _unmarked(found, ticket)):
        print(unmarked)


def _check_workflow(found: Context) -> str | None:
    # the text of the checkout's check workflow, None when it has none
    path = working_directory(found.args) / nextguide.CHECK_WORKFLOW
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _unmarked(found: Context, ticket: str) -> str:
    # keyword: flake (pitboss#278): the line is empty when the test is marked
    tree = working_directory(found.args)
    globs = configfile.load_brief(configfile.named(found.args), tree).quarantine_globs
    return flake.unmarked_line(ticket, tree, globs)


def _step_of(found: Context, named: str) -> None:
    ticket = ledger.reference(named, found.settings.project.repo)
    if not _FULL_REFERENCE.match(ticket):
        _refuse("next takes a ticket as owner/repo#N, repo#N or #N")
    pull, unread = fixing(open_pulls(found), ticket)
    if pull is not None:
        print(_line(ticket, pull))
        return
    for each in unread:
        print(unreadableline.unreadable_line(each))
    if unread:
        raise SystemExit(1)
    _say_missing_names(found, ticket)
    off = draftrule.drafts_off(
        configfile.named(found.args),
        working_directory(found.args),
        ticket.rpartition("#")[0],  # keyword: pitboss-exempt (pitboss#113)
    )
    first = steps.FIRST_STEP_READY if off else steps.FIRST_STEP
    print(f"{steps.Step.WORKER.name}: {ticket}: {first}")
