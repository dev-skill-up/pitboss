"""The ``act`` command: every write to GitHub, one verb each.

The keyword is act-verbs, pitboss#444.

``pitboss act <verb> <target> [name=value ...]``: the target is ``owner/name#N``,
``owner/name`` or ``all``; the verbs are ``actverbs.VERBS``. Each verb that changes
GitHub runs the total verdict and the gates first and refuses (exit 2) with the
reason. Writes are a dry run unless ``--no-dry-run`` is given.
"""

import argparse
import functools
import sys
from typing import Callable, Mapping, NoReturn, Sequence

from gather.commands import add_argument

from . import ENTRY_DATA, actcore, actledger, actverbs, actwiring, configsettle
from . import logline, mode, onepath, project
from .commandarguments import CONFIG_OPTION, DRY_RUN_ARGUMENT, NOW_ARGUMENT
from .commands import Context, load_context


def _refuse(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(2)


def options_of(words: Sequence[str]) -> Mapping[str, str]:
    """Read ``name=value`` words.

    Args:
        words: the words after the target.

    Returns:
        Each option's value.
    """
    found = {}
    for each in words:
        name, equals, value = each.partition("=")
        if not equals or not name:
            _refuse(f"act: {each[:40]!r} is not an option: options are `name=value`")
        found[name] = value
    return found


def run_verb(
    world: actcore.Act, verb: str, target: actcore.Target, options: Mapping[str, str]
) -> str:
    """Run one verb, refusing with its reason.

    Args:
        world: the verbs' world.
        verb: the verb.
        target: the target.
        options: the options.

    Returns:
        What it said.
    """
    if verb not in actverbs.VERBS:
        _refuse(f"act: no verb {verb!r}: {', '.join(sorted(actverbs.VERBS))}")
    try:
        return actverbs.VERBS[verb](world, target, options)
    except actverbs.REFUSALS as error:
        _refuse(f"act {verb}: refused: {error}")


@ENTRY_DATA.register(
    add_argument("verb", help="the verb: " + ", ".join(sorted(actverbs.VERBS))),
    add_argument("target", help="owner/name#N, owner/name or all"),
    add_argument("words", nargs="*", help="the options, name=value each"),
    CONFIG_OPTION,
    NOW_ARGUMENT,
    DRY_RUN_ARGUMENT,
    name="act",
)
def act(args: argparse.Namespace) -> None:
    """Make one write to GitHub through its verb.

    Args:
        args: the parsed arguments.
    """
    options = options_of(args.words)
    args.config = None  # only --config names the configuration
    configsettle.settle(args, None)
    found = load_context(args)
    path = found.settings.slots.ledger.parent / actwiring.OWNER
    owner = actwiring.owner_of(path)
    chosen = onepath.mode_of(args, found, options)
    world = actwiring.act_of(
        found.github, found.settings, owner, args.run, _dispatching(found, chosen)
    )
    target = actledger.target_of(args.target)
    print(run_verb(world, args.verb, target, options))
    if args.no_dry_run:
        actwiring.write_owner(path, owner)
        _recorded(
            found, world, actledger.Done(verb=args.verb, target=target, options=options)
        )


def _dispatching(
    found: Context, chosen: mode.Mode
) -> Callable[[], project.DispatchAnswer]:
    # keyword: one-path: dispatch-next reads the world once, as slots next does
    asked = (
        chosen
        if isinstance(chosen, mode.DispatchNext)
        else mode.DispatchNext(want="", options={})
    )
    return functools.partial(onepath.dispatch, found, asked)


def _recorded(found: Context, world: actcore.Act, done: actledger.Done) -> None:
    # the ledger's record of a write, then the PR read after it (keyword:
    # claim-readback, quire#1115)
    if event := actledger.ledger_event(world, done, found.now.isoformat()):
        logline.record(found.settings.slots.log, event)
    for line in actledger.read_back(found.github, done):
        _refuse(line)
