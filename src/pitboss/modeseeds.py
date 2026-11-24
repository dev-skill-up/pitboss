"""P4's seeds of the command line (keyword: one-path, ``proofseeds``)."""

import argparse
from typing import Mapping, Sequence

from gather.api import Wrapper, unique
from gather.commands import add_argument

from . import cli_parser, config, mode, modeproof


def new_flag(declared: cli_parser.Declared) -> cli_parser.Declared:
    """P4's seeded table: a flag of ``next`` that ``ASKS_NOTHING`` does not list.

    Args:
        declared: the table the parser is built from.

    Returns:
        The table with ``--seeded`` added to ``next``.
    """
    registered = unique(declared)["next"]
    extra: Sequence[object] = getattr(registered, "extra")
    flag = add_argument("--seeded", action="store_true")
    changed = Wrapper(original=getattr(registered, "original"), extra=[*extra, flag])
    return {**declared, "next": [changed]}


def refusing(kind: str) -> mode.ModeOf:
    """P4's seeded parse: it refuses the command lines of one kind.

    Args:
        kind: what the line varies (subcommand, choice, flag or positional).

    Returns:
        A parse that exits on such a line and parses the others.
    """

    def parse(
        args: argparse.Namespace, project: config.Repo, options: Mapping[str, str]
    ) -> mode.Mode:
        if getattr(args, modeproof.KIND) == kind:
            raise SystemExit(2)
        return mode.parse(args, project, options)

    return parse
