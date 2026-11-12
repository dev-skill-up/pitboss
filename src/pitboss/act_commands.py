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
from .commands import Context, load_context, open_pulls

VERBS = [actions.word(each) for each in actions.Action]


def _refuse(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(2)


def _action_of(words: Sequence[str]) -> actions.Action:
    named = [each for each in actions.Action if actions.word(each) in words[:1]]
    if not named:
        _refuse(f"act takes the action as its second word: {', '.join(VERBS)}")
    if wrong := actrun.missing(named[0], words[1:]):
        _refuse(wrong)
    return named[0]


def _facts_of(
    found: Context, reference: str
) -> tuple[pulls.PullFacts, actions.Standing]:
    every = pulls.readable(open_pulls(found))
    named = [each for each in every if pulls.reference(each) == reference]
    if not named:
        _refuse(f"{reference} is not an open PR that could be read")
    return named[0], duplicatepr.standing_of(named[0], every)


def _make(
    found: Context,
    action: actions.Action,
    facts: pulls.PullFacts,
    words: Sequence[str],
) -> None:
    # recorded first, then made; a dry run does neither
    head = facts.pull.head
    slug, number = facts.repo.slug, facts.pull.number
    target = actrun.Target(slug=slug, number=number, branch=head.branch, head=head.sha)
    if found.args.no_dry_run:
        logline.record(
            found.settings.slots.log,
            actrun.record(action, target, facts.step, found.now),
        )
    found.github.mutate(list(actrun.argv(action, target, words)))


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
    and ``--no-dry-run`` does both. The sweep names every GitHub event of these
    kinds that has no such record (keyword: action-matrix, promise#73).

    Args:
        args: the parsed arguments.
    """
    action = _action_of(args.words)
    args.config = None  # only --config names the configuration
    configsettle.settle(args, None)
    found = load_context(args)
    facts, standing = _facts_of(found, args.pull)
    grid = actions.parse(phrases.shipped_text("actionmatrix.tsv"))[1]
    if refusal := actions.refusal(grid, action, facts.step, standing):
        _refuse(f"{args.pull}: {refusal}")
    _make(found, action, facts, args.words[1:])
    print(f"act: {actions.word(action)} {args.pull} at {facts.step.step.name}")
    repoaccess.finish(found.access)
