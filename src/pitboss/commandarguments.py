"""The arguments most commands share (keyword: default-config).

A command module imports them from here.
"""

import argparse

from gather.commands import add_argument

CONFIG_ARGUMENT = add_argument(
    "config",
    nargs="?",
    default=None,
    help="a path, or a name in .claude/pitboss/<name>.toml; with none, $PITBOSS_CONFIG,"
    " else pitboss.toml or <directory>.toml in the working directory, a parent,"
    " or their .claude/pitboss",
)
NOW_ARGUMENT = add_argument("--now", default=None, help=argparse.SUPPRESS)
DRY_RUN_ARGUMENT = add_argument("--no-dry-run", action="store_true", default=False)
CHANGING_ARGUMENTS = (CONFIG_ARGUMENT, NOW_ARGUMENT, DRY_RUN_ARGUMENT)
