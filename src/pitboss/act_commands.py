"""The ``act`` command: a state-changing action on a PR, asked of the matrix first."""

import argparse
import sys
from typing import NoReturn, Sequence

from gather.commands import add_argument

from . import (
    ENTRY_DATA,
    actions,
    actrun,
    configsettle,
    duplicatepr,
    logline,
    phrases,
    pulls,
    repoaccess,
)
from .commandarguments import CONFIG_OPTION, DRY_RUN_ARGUMENT, NOW_ARGUMENT
from .commands import load_context, open_pulls


def _refuse(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(2)


def standing_of(
    facts: pulls.PullFacts, every: Sequence[pulls.PullFacts]
) -> actions.Standing:
    """The standing of a PR besides its step.

    Args:
        facts: the PR.
        every: every open PR that was read.

    Returns:
        ``DUPLICATE`` for a second PR on a ticket, else ``PLAIN``.
    """
    if pulls.reference(facts) in duplicatepr.newer(every):
        return actions.Standing.DUPLICATE
    return actions.Standing.PLAIN


@ENTRY_DATA.register(
    add_argument("pull", help="OWNER/NAME#NUMBER: the pull request"),
    add_argument(
        "words",
        nargs="*",
        help="the action (push, merge, undraft, dispatch, close or label), then the"
        " label, the workflow file, or git push's arguments",
    ),
    CONFIG_OPTION,
    NOW_ARGUMENT,
    DRY_RUN_ARGUMENT,
    name="act",
)
def act(args: argparse.Namespace) -> None:
    """Do a state-changing action on a PR, when the matrix allows it in its step.

    The action is one of push, merge, undraft, dispatch, close and label. The PR
    is read, its step and standing are looked up in ``actionmatrix.tsv``, and a
    cell that is ``n`` refuses the action (exit 2) naming the step and the steps
    that allow it, with nothing changed. An allowed action is recorded in the
    ledger first, then made; a dry run (the default) records and changes nothing,
    and ``--no-dry-run`` does both. The sweep names
    every GitHub event of these kinds that has no such record (keyword:
    action-matrix, promise#73).

    Args:
        args: the parsed arguments.
    """
    verbs = [each.value for each in actions.Action]
    if not args.words or args.words[0] not in verbs:
        _refuse(f"act takes the action as its second word: {', '.join(verbs)}")
    action = actions.Action(args.words[0])
    rest = args.words[1:]
    if wrong := actrun.missing(action, rest):
        _refuse(wrong)
    args.config = None  # only --config names the configuration
    configsettle.settle(args, None)
    found = load_context(args)
    every = [each for each in pulls.readable(open_pulls(found))]
    named = [each for each in every if pulls.reference(each) == args.pull]
    if not named:
        _refuse(f"{args.pull} is not an open PR that could be read")
    facts = named[0]
    grid = actions.parse(phrases.shipped_text("actionmatrix.tsv"))[1]
    refusal = actions.refusal(grid, action, facts.step, standing_of(facts, every))
    if refusal:
        _refuse(f"{args.pull}: {refusal}")
    event = actrun.record(
        action, args.pull, facts.pull.head.branch, facts.step, facts.pull.head.sha,
        found.now,
    )
    if args.no_dry_run:
        logline.record(found.settings.slots.log, event)
    found.github.mutate(
        list(
            actrun.argv(
                action, facts.repo.slug, facts.pull.number, facts.pull.head.branch,
                rest,
            )
        )
    )
    print(f"act: {action.value} {args.pull} at {facts.step.step.name}")
    repoaccess.finish(found.access)
