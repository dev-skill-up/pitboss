"""The ``act`` command: every write to GitHub, one verb each.

The keyword is act-verbs, pitboss#444.

``pitboss act <verb> <target> [name=value ...]``: the target is ``owner/name#N``,
``owner/name`` or ``all``; the verbs are ``actverbs.VERBS``. Each verb that changes
GitHub runs the total verdict and the gates first and refuses (exit 2) with the
reason. Writes are a dry run unless ``--no-dry-run`` is given.
"""

import argparse
import sys
from typing import Mapping, NoReturn, Sequence

from gather.commands import add_argument

from . import ENTRY_DATA, actcore, actrun, actverbs, actwiring, configsettle, logline
from .commandarguments import CONFIG_OPTION, DRY_RUN_ARGUMENT, NOW_ARGUMENT
from .commands import load_context
from .totaljson import mapping, text


def _refuse(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(2)


def target_of(word: str) -> actcore.Target:
    """Read a target.

    Args:
        word: ``owner/name#N``, ``owner/name`` or ``all``.

    Returns:
        The target.
    """
    repo, _, number = word.partition("#")
    return actcore.Target(repo=repo, number=int(number) if number.isdigit() else 0)


def options_of(words: Sequence[str]) -> Mapping[str, str]:
    """Read ``name=value`` words.

    Args:
        words: the words after the target.

    Returns:
        Each option's value.
    """
    found = {}
    for word in words:
        name, equals, value = word.partition("=")
        if not equals or not name:
            _refuse(f"act: {word[:40]!r} is not an option: options are `name=value`")
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


# the sweep's unledgered check reads these records (keyword: action-matrix)
LEDGERED = {
    "merge": "merge",
    "arm": "arm",
    "undraft": "undraft",
    "label": "label",
    "close": "close",
    "push": "push",
    "dispatch-workflow": "dispatch",
}


def ledger_event(
    world: actcore.Act,
    verb: str,
    target: actcore.Target,
    options: Mapping[str, str],
    now: str,
) -> logline.Event | None:
    """The slot log's record of a write the sweep checks for.

    Args:
        world: the verbs' world.
        verb: the verb.
        target: the target.
        options: the options.
        now: the time now (ISO 8601).

    Returns:
        The record, or None for a verb the sweep does not check.
    """
    word = LEDGERED.get(verb)
    if not word:
        return None
    pull = world.hub.pull(target.repo, target.number) if target.number else {}
    head = mapping(pull.get("head"))
    branch = options.get("branch") or options.get("ref") or text(head.get("ref"))
    what = f"{word} {target.repo}#{target.number} {branch} at act"
    return logline.Event(
        kind=actrun.KIND,
        time=now,
        who=actrun.WHO,
        what=what,
        head=text(head.get("sha")),
    )


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
    world = actwiring.act_of(
        found.github,
        found.settings,
        owner,
        args.run,
        actwiring.identity_of(found.github),
    )
    target = target_of(args.target)
    print(run_verb(world, args.verb, target, options))
    if args.no_dry_run:
        actwiring.write_owner(path, owner)
        if event := ledger_event(
            world, args.verb, target, options, found.now.isoformat()
        ):
            logline.record(found.settings.slots.log, event)
