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
    " directory, a parent, or their .claude/pitboss, else <repository>.toml"
    " fetched from the notes repository (moshez/claude-jsonl)",
)
CONFIG_OPTION = add_argument(
    "--config",
    dest="config_option",
    default=None,
    help="a path, or a name in .claude/pitboss/<name>.toml; with none: the old"
    " first word, else $PITBOSS_CONFIG, else the search, else the fetch (see CONFIG)",
)
NOW_ARGUMENT = add_argument("--now", default=None, help=argparse.SUPPRESS)
DRY_RUN_ARGUMENT = add_argument("--no-dry-run", action="store_true", default=False)
RUNNING_ARGUMENT = add_argument(
    "--running",
    nargs="*",
    default=None,
    help="the names of the agents the session runs: slots next, show and the sweep"
    " hold a slot only for an agent named here, so a ledger row of a finished agent"
    " is an empty slot; an agent named here that holds no row prints one UNRECORDED"
    " AGENT line, and no start is offered until every live agent holds one"
    " (pitboss#291, pitboss#94)",
)
SWEEP_ARGUMENTS = (CONFIG_ARGUMENT, NOW_ARGUMENT, RUNNING_ARGUMENT)
CHANGING_ARGUMENTS = (CONFIG_ARGUMENT, NOW_ARGUMENT, DRY_RUN_ARGUMENT)
WATCH_ARGUMENTS = (
    add_argument(
        "--interval",
        type=int,
        default=None,
        help="seconds between rounds of 'slots watch' ([slots] poll-seconds, 15)",
    ),
    add_argument(
        "--rounds", type=int, default=0, help="rounds of 'slots watch'; 0: no end"
    ),
    add_argument("--process-start", default=None, help=argparse.SUPPRESS),
)
