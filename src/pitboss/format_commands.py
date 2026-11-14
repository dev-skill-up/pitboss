"""The ``format`` command: a section of a PR body from JSON (keyword: plan-format)."""

import argparse
import json
import pathlib
import sys

from gather.commands import add_argument

from . import ENTRY_DATA, planformat
from .totaljson import members


@ENTRY_DATA.register(
    add_argument("kind", choices=("plan",), help="the section: plan"),
    add_argument("file", help="the JSON, in the form of planformat.schema.json"),
    name="format",
)
def format_section(args: argparse.Namespace) -> None:
    """Print the Plan section of a JSON file; exit 1 naming each field at fault.

    Args:
        args: the parsed arguments.
    """
    try:
        found = json.loads(pathlib.Path(args.file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"{args.file}: {error}", file=sys.stderr)
        raise SystemExit(1)
    refused = list(planformat.refusals(found, planformat.schema()))
    for each in refused:
        print(f"{args.file}: {each}", file=sys.stderr)
    if refused:
        raise SystemExit(1)
    print(planformat.section(members(found)), end="")
