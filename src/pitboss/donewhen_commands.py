"""The ``done-when-check`` command: the Done-when's tests, on the head and a base."""

import argparse
import pathlib

from gather.commands import add_argument

from . import ENTRY_DATA, donewhencheck, donewhenrun, lintinput, phrases, rules

PAIRING = "donewhen.tsv"


@ENTRY_DATA.register(
    add_argument(
        "--ref",
        default="origin/main",
        help="the base the named tests must fail on (default: origin/main)",
    ),
    add_argument(
        "--repo",
        default=".",
        help="a checkout of pitboss, which the base is made of (default: here)",
    ),
    add_argument(
        "--pairing",
        default=None,
        help="a file pairing the Done-when's items with their tests (default: the"
        " one pitboss ships, donewhen.tsv)",
    ),
    name="done-when-check",
)
def done_when_check(args: argparse.Namespace) -> None:
    """Print one line: whether every Done-when item is demonstrated by its tests.

    Each named test must exist and pass on the head, and at least one test of each
    item must fail on the base ``--ref``, where the head's tests are run in a scratch
    worktree. The line is ``done-when check: ok``, or names the first finding.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 1 when an item is not demonstrated.
    """
    rows, _ = rules.parse(phrases.shipped_text("rules.tsv"))
    pairing = args.pairing and lintinput.read(args.pairing)
    items = donewhencheck.parse(pairing or phrases.shipped_text(PAIRING))
    checks = donewhenrun.measure(items, rows, (pathlib.Path(args.repo), args.ref))
    found = donewhencheck.refusals(items, rows, checks)
    print(donewhencheck.one_line(found))
    raise SystemExit(int(bool(found)))
