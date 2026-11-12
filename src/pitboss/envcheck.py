"""The checks of ``env-check``: is each tool a worker needs there (keyword: env-check).

Each tool is judged by ``gaterun``, so a check that crashes or prints nothing is a
missing tool.
"""

import argparse
from typing import AbstractSet, Sequence

from . import envrules, gaterun


def verdicts(
    args: argparse.Namespace, needs: Sequence[envrules.Need], kinds: AbstractSet[str]
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
    return [
        envrules.MISSING_LINE.format(name=each.name, why=each.why, command=each.get)
        for each in needs
        if each.kinds & kinds and not _there(args, each)
    ]


def _there(args: argparse.Namespace, need: envrules.Need) -> bool:
    gate = gaterun.Gate(
        command=["sh", "-c", need.check], timeout=60, directory=str(args.repo)
    )
    done = gaterun.run(args.safe_run, gate)
    return done.passed
