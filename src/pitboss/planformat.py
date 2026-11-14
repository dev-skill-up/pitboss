"""The Plan section of a PR body, written from JSON (keyword: plan-format, pitboss#483).

``planformat.schema.json`` is the form of the JSON: an ``intro`` and the ``rows``, each
a Done-when ``item`` with the ``command`` its Evidence runs or the ``ci`` pointer. The
command rows are numbered first, so row N is the row of the Nth Evidence block.
"""

import importlib.resources
import json
import re
from typing import Iterator, Mapping

from .totaljson import JsonMap, listing, members, text

SCHEMA = "planformat.schema.json"
TYPES: Mapping[str, type] = {"object": dict, "array": list, "string": str}
CI = "CI: workflow `{workflow}`, job `{job}`, step `{step}`, greppable `{grep}`."


def schema() -> JsonMap:
    """The schema ``format plan`` reads its JSON by.

    Returns:
        The schema, as the repository holds it.
    """
    found = importlib.resources.files("pitboss") / SCHEMA
    return members(json.loads(found.read_text(encoding="utf-8")))


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
    items = listing(value)
    if len(items) < int(str(rules.get("minItems", 0))):
        yield f"{where}: fewer than {rules.get('minItems')} items"
    for index, each in enumerate(items):
        yield from refusals(each, members(rules.get("items")), f"{where}[{index}]")
    choices = [members(each) for each in listing(rules.get("oneOf"))]
    if choices and sum(not any(refusals(value, each)) for each in choices) != 1:
        names = [text(key) for each in choices for key in listing(each["required"])]
        yield f"{where}: has not exactly one of {', '.join(names)}"


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
