"""The ``env-check`` command: is the environment a worker needs there.

The keyword is env-check.
"""

import argparse

from gather.commands import add_argument

from . import ENTRY_DATA, commands, configsettle, envcheck, envrules


@ENTRY_DATA.register(
    add_argument(
        "--config",
        default=None,
        help=(
            "the project's configuration (a path, or a name in"
            " .claude/pitboss/<name>.toml; default: the search): its repository decides"
            " which tools are needed"
        ),
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
    lines = envcheck.verdicts(args, envrules.NEEDS, envrules.kinds_of(slug))
    for each in lines or [envrules.OK_LINE]:
        print(each)
    if lines:
        raise SystemExit(1)
