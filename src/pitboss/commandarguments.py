"""The arguments most commands share (keyword: default-config).

A command module imports them from here.
"""

import argparse

from gather.commands import add_argument

CONFIG_ARGUMENT = add_argument(
    "config",
    nargs="?",
    default=None,
    help="DEPRECATED, give --config NAME (a path, or a name in"
    " .claude/pitboss/<name>.toml): this first word is the configuration only when"
    " it ends in .toml, has a slash, or names a file in .claude/pitboss. With"
    " none: $PITBOSS_CONFIG, else pitboss.toml or <repository>.toml in the working"
    " directory, a parent, or their .claude/pitboss",
)
CONFIG_OPTION = add_argument(
    "--config",
    dest="config_option",
    default=None,
    help="a path, or a name in .claude/pitboss/<name>.toml; with none: the old"
    " first word, else $PITBOSS_CONFIG, else the search (see CONFIG)",
)
NOW_ARGUMENT = add_argument("--now", default=None, help=argparse.SUPPRESS)
DRY_RUN_ARGUMENT = add_argument("--no-dry-run", action="store_true", default=False)
CHANGING_ARGUMENTS = (CONFIG_ARGUMENT, NOW_ARGUMENT, DRY_RUN_ARGUMENT)
