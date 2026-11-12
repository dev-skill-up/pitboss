"""The ``env-check`` command: is the environment a worker needs there (keyword: env-check)."""

import argparse
from typing import Sequence

from gather.commands import add_argument

from . import ENTRY_DATA, commands, configsettle, envrules, gaterun


def verdicts(
    args: argparse.Namespace, needs: Sequence[envrules.Need], kinds: frozenset[str]
) -> Sequence[str]:
    """Run the checks of the needs of some kinds of repository.

    Args:
        args: the parsed arguments, with a ``safe_run``.
        needs: the tools that are known.
        kinds: the kinds of the repository.

    Returns:
        A line for each missing tool naming it and the command to get it; none
        when every tool is there.
    """
    missing = []
    for each in needs:
        if not each.kinds & kinds:
            continue
        done = gaterun.run(
            args.safe_run,
            ["sh", "-c", each.check],
            timeout=60,
            directory=str(args.repo),
        )
        if not done.passed:
            line = envrules.MISSING_LINE.format(
                name=each.name, why=each.why, command=each.get
            )
            missing.append(line)
    return missing


@ENTRY_DATA.register(
    add_argument(
        "--config",
        default=None,
        help="the project's configuration (a path, or a name in"
        " .claude/pitboss/<name>.toml; default: the search): its repository decides"
        " which tools are needed",
    ),
    add_argument(
        "--repo",
        default=".",
        help="the worker's worktree (default: the current directory)",
    ),
    name="env-check",
)
def env_check(args: argparse.Namespace) -> None:
    """Print ``env: ok``, or each tool that is missing and the command to get it.

    This is the env-check area (quire#1065): a worker that cannot find a tool runs
    it before giving up, and ``hand-back-check`` refuses a hand-back that gives up
    for a missing environment without its output. The tools are those of the
    kinds of the configuration's repository (``envrules.NEEDS``); each is judged by
    ``gaterun``, so a check that crashes or prints nothing is a missing tool.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 1 when a tool is missing.
    """
    configsettle.find_or_say(args)
    slug = commands.load_settings(args).project.repo.slug
    lines = verdicts(args, envrules.NEEDS, envrules.kinds_of(slug))
    for each in lines or [envrules.OK_LINE]:
        print(each)
    if lines:
        raise SystemExit(1)
