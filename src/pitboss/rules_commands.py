"""The ``rules`` command: check the register of the owner's rules (pitboss#444)."""

import argparse
import importlib
import importlib.resources
import sys
from typing import Sequence

from gather.commands import add_argument

from . import ENTRY_DATA, decidable, lintinput, phrases, ruleconflicts, rules

REGISTER = "rules.tsv"


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


def table_ids() -> Sequence[str]:
    """The ids of the coverage table.

    Returns:
        The ids, from ``tests/coverage_ids.txt``.
    """
    path = importlib.resources.files("pitboss") / "tests" / "coverage_ids.txt"
    return path.read_text(encoding="utf-8").split()


@ENTRY_DATA.register(
    add_argument("action", choices=("check",)),
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
    rows, bad = rules.parse(_text(args.register, REGISTER))
    found = [*bad, *rules.findings(rows, function_known, module_text)]
    if not args.register:
        found += rules.coverage_findings(rows, table_ids())
        held = decidable.parse(phrases.shipped_text("decidable.tsv"))
        found += decidable.findings(rows, held)
        found += ruleconflicts.findings(rows, ruleconflicts.shipped())
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
