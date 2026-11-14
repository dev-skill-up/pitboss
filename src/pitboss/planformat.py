"""``pitboss format plan``: a Plan section from JSON (keyword: plan-format).

The JSON's form is ``planformat.schema.json``; the command rows are numbered first,
so row N is the row of the Nth Evidence block (``plan-row``).
"""

import argparse
import pathlib
import re
import sys
from typing import Iterator, Mapping, Sequence

from gather.commands import add_argument

from . import ENTRY_DATA
from .totaljson import JsonMap, listing, members, read_file, text

SCHEMA = "planformat.schema.json"
TYPES: Mapping[str, type] = {"object": dict, "array": list, "string": str}
CI = "CI: workflow `{workflow}`, job `{job}`, step `{step}`, greppable `{grep}`."


def schema() -> JsonMap:
    """The schema ``format plan`` reads its JSON by.

    Returns:
        The schema, as the repository holds it.
    """
    return members(read_file(pathlib.Path(__file__).with_name(SCHEMA)))


def _object(value: JsonMap, rules: JsonMap, where: str) -> Iterator[str]:
    for key in listing(rules.get("required")):
        if text(key) not in value:
            yield f"{where}.{text(key)}: missing".lstrip(".")
    fields = members(rules.get("properties"))
    for key, each in value.items():
        if key in fields:
            yield from refusals(
                each, members(fields[key]), f"{where}.{key}".lstrip(".")
            )
        elif rules.get("additionalProperties") is False:
            yield f"{where}.{key}: not a field of the schema".lstrip(".")


def refusals(value: object, rules: JsonMap, where: str = "") -> Iterator[str]:
    """Why a JSON value is not in the form of a schema.

    Args:
        value: the value.
        rules: the schema (or the part of it for the value).
        where: the value's field (``rows[0].item``), "" for the whole.

    Yields:
        Each refusal, the field at fault first.
    """
    kind = text(rules.get("type"))
    if kind and not isinstance(value, TYPES[kind]):
        yield f"{where or '(the file)'}: not a JSON {kind}"
        return
    pattern = text(rules.get("pattern"))
    if pattern and not re.search(pattern, text(value)):
        yield f"{where}: does not match {pattern}"
    if isinstance(value, dict):
        yield from _object(value, rules, where)
    yield from _array(listing(value), rules, where)
    choices = [members(each) for each in listing(rules.get("oneOf"))]
    if choices and sum(not any(refusals(value, each)) for each in choices) != 1:
        names = [text(key) for each in choices for key in listing(each["required"])]
        yield f"{where}: has not exactly one of {', '.join(names)}"


def _array(items: Sequence[object], rules: JsonMap, where: str) -> Iterator[str]:
    least = rules.get("minItems")
    if isinstance(least, int) and len(items) < least:
        yield f"{where}: fewer than {least} items"
    for index, each in enumerate(items):
        yield from refusals(each, members(rules.get("items")), f"{where}[{index}]")


def _row(row: JsonMap) -> str:
    if "command" in row:
        return f"{text(row['item'])} Evidence: `{text(row['command'])}`"
    return f"{text(row['item'])} {CI.format(**members(row['ci']))}"


def section(plan: JsonMap) -> str:
    """The Plan section of a JSON the schema takes.

    Args:
        plan: the JSON.

    Returns:
        The ``## Plan`` heading, the intro, then the rows, the command rows first.
    """
    rows = [members(each) for each in listing(plan.get("rows"))]
    ordered = sorted(rows, key=lambda row: "command" not in row)
    numbered = [f"{number}. {_row(row)}" for number, row in enumerate(ordered, 1)]
    intro = [text(plan["intro"]), ""] if "intro" in plan else []
    return "\n".join(["## Plan", "", *intro, *numbered]) + "\n"


@ENTRY_DATA.register(
    add_argument("kind", choices=("plan",), help="the section: plan"),
    add_argument("file", help="the JSON, in the form of planformat.schema.json"),
    name="format",
)
def format_section(args: argparse.Namespace) -> None:
    """Print the Plan section of a JSON file; exit 1 naming each field at fault.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: a file that is no JSON, or a JSON the schema refuses.
    """
    try:
        found = read_file(pathlib.Path(args.file))
    except (OSError, ValueError) as error:
        print(f"{args.file}: {error}", file=sys.stderr)
        raise SystemExit(1)
    refused = list(refusals(found, schema()))
    for each in refused:
        print(f"{args.file}: {each}", file=sys.stderr)
    if refused:
        raise SystemExit(1)
    print(section(members(found)), end="")
