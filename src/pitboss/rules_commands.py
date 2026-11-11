"""The ``rules`` command: check the register of the owner's rules (pitboss#444)."""

import argparse
import importlib
import importlib.resources
import pathlib
import sys

from gather.commands import add_argument

from . import ENTRY_DATA, phrases, rules

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
    text = (
        pathlib.Path(args.register).read_text(encoding="utf-8")
        if args.register
        else phrases.shipped_text(REGISTER)
    )
    rows, bad = rules.parse(text)
    found = [*bad, *rules.findings(rows, function_known, module_text)]
    for each in found:
        print(each)
    unenforced = rules.open_ids(rows)
    print(f"rules: {len(rows)} rows, {len(unenforced)} open: {' '.join(unenforced)}")
    if found:
        print(f"rules check: refused, {len(found)} findings", file=sys.stderr)
        raise SystemExit(1)
    print("rules check: ok")
