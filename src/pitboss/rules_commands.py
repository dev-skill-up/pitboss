"""The ``rules`` command: check the register of the owner's rules (pitboss#444)."""

import argparse
import importlib
import importlib.resources
import pathlib
import sys

from gather.commands import add_argument

from . import ENTRY_DATA, donewhencheck, donewhenrun, lintinput, phrases, rules

REGISTER = "rules.tsv"
TABLE = "coverage_ids.txt"
PAIRING = "donewhen.tsv"


def function_known(name: str) -> bool:
    """Whether ``module.name`` is a function of a module of pitboss.

    Args:
        name: the function, ``module.name``.

    Returns:
        True when the module imports and has the attribute.
    """
    try:
        found = importlib.import_module("pitboss." + name.rsplit(".", 1)[0])
    except ImportError:
        return False
    return callable(getattr(found, name.rsplit(".", 1)[1], None))


def module_text(module: str) -> str | None:
    """The text of a test module of pitboss.

    Args:
        module: its name (``test_rules``).

    Returns:
        The text, None when there is no such module.
    """
    path = importlib.resources.files("pitboss") / "tests" / f"{module}.py"
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


@ENTRY_DATA.register(
    add_argument("action", choices=("check", "done-when")),
    add_argument(
        "--ref",
        default="origin/main",
        help="done-when: the base the named tests must fail on (default: origin/main)",
    ),
    add_argument(
        "--repo",
        default=".",
        help="done-when: a checkout of pitboss, which the base is made of",
    ),
    add_argument(
        "--pairing",
        default=None,
        help="done-when: a file pairing the Done-when's items with their tests"
        " (default: the one pitboss ships, donewhen.tsv)",
    ),
    add_argument(
        "--register",
        default=None,
        help="a register file to check (default: the one pitboss ships, rules.tsv)",
    ),
    name="rules",
)
def rules_check(args: argparse.Namespace) -> None:
    """Check the register of the owner's rules; exit 1 on any finding.

    Each row's function must exist and each test must exist and name the rule's
    id. Rules of kind ``open`` are counted and listed: they are not enforced yet.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 1 when the register has a finding.
    """
    if args.action == "done-when":
        done_when(args)
        return
    rows, bad = rules.parse(_text(args.register, REGISTER))
    found = [*bad, *rules.findings(rows, function_known, module_text)]
    if not args.register:
        found += rules.coverage_findings(rows, phrases.shipped_text(TABLE).split())
    for each in found:
        print(each)
    unenforced = rules.open_ids(rows)
    print(f"rules: {len(rows)} rows, {len(unenforced)} open: {' '.join(unenforced)}")
    if found:
        print(f"rules check: refused, {len(found)} findings", file=sys.stderr)
        raise SystemExit(1)
    print("rules check: ok")


def _text(path: str | None, shipped: str) -> str:
    if path is None:
        return phrases.shipped_text(shipped)
    return lintinput.read(path)


def done_when(args: argparse.Namespace) -> None:
    """Print one line: whether every Done-when item is demonstrated by its tests.

    Each named test must exist and pass on the head, and at least one test of each
    item must fail on the base ``--ref``, where the head's tests are run in a scratch
    worktree. The line is ``done-when check: ok``, or names the first finding.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 1 when an item is not demonstrated.
    """
    rows, _ = rules.parse(phrases.shipped_text(REGISTER))
    items = donewhencheck.parse(_text(args.pairing, PAIRING))
    checks = donewhenrun.measure(items, rows, (pathlib.Path(args.repo), args.ref))
    found = donewhencheck.refusals(items, rows, checks)
    print(donewhencheck.verdict(found))
    raise SystemExit(int(bool(found)))
