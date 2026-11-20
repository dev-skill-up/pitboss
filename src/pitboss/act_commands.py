"""The ``act`` command: every write to GitHub, one verb each.

The keyword is act-verbs, pitboss#444.

``pitboss act <verb> <target> [name=value ...]``: the target is ``owner/name#N``,
``owner/name`` or ``all``; the verbs are ``actverbs.VERBS``. Each verb that changes
GitHub is looked up in the decisions of the command's one read (``actverbs.run``),
and what stands instead of it is printed with exit 2. Writes are a dry run unless
``--no-dry-run`` is given.
"""

import argparse
import functools
import sys
from typing import Callable, Mapping, NoReturn, Sequence

from gather.commands import add_argument

from . import ENTRY_DATA, actcore, actfacts, actledger, actread, actverbs, actwiring
from . import answer, configsettle, logline, onepath, render
from .commandarguments import CONFIG_OPTION, DRY_RUN_ARGUMENT, NOW_ARGUMENT
from .commands import Context, load_context


def _printed(said: str) -> None:
    # P8: a verb whose decision is another prints the one that stands, and exits 2
    print(said)
    if said.startswith(render.NOT_DONE):
        raise SystemExit(2)


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


def run_verb(world: actcore.Act, asked: actfacts.Asked) -> str:
    """Run one verb through ``actverbs.run``, refusing with its reason.

    Args:
        world: the verbs' world.
        asked: the verb, its target and its options.

    Returns:
        What it said.
    """
    try:
        return actverbs.run(world, asked, actverbs.VERBS)
    except actverbs.REFUSALS as error:
        _refuse(f"act {asked.verb}: refused: {error}")


def _decided(
    found: Context, args: argparse.Namespace, options: Mapping[str, str]
) -> tuple[actcore.Questions, Callable[[actcore.Act], None]]:
    # the one read of the command line's mode, made once, with the act's own facts
    # (actread) read in it; the world is given once it is made
    chosen = onepath.mode_of(args, found, options)
    made: dict[str, answer.Decided] = {}
    worlds: list[actcore.Act] = []

    def decided(asked: actfacts.Asked) -> answer.Decided:
        if "decided" not in made:
            acts = functools.partial(actread.read, worlds[0], asked)
            made["decided"] = onepath.looked(found, chosen, acts).decided
        return made["decided"]

    return actcore.Questions(decided=decided), worlds.append


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
    questions, given = _decided(found, args, options)
    asking = actwiring.Asking(owner=owner, questions=questions)
    world = actwiring.act_of(found.github, found.settings, args.run, asking)
    given(world)
    target = actledger.target_of(args.target)
    asked = actfacts.Asked(verb=args.verb, target=target, options=options)
    _printed(run_verb(world, asked))
    if args.no_dry_run:
        actwiring.write_owner(path, owner)
        _recorded(
            found, world, actledger.Done(verb=args.verb, target=target, options=options)
        )


def _recorded(found: Context, world: actcore.Act, done: actledger.Done) -> None:
    # the ledger's record of a write, then the PR read after it (keyword:
    # claim-readback, quire#1115)
    if event := actledger.ledger_event(world, done, found.now.isoformat()):
        logline.record(found.settings.slots.log, event)
    for line in actledger.read_back(found.github, done):
        _refuse(line)
