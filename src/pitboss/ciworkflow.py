"""The names in a GitHub Actions workflow file (keyword: ci-pointer, pitboss#335).

A CI pointer of a Plan names a job and a step of a workflow, and ``pitboss
plan-check`` holds them to the file. The file is read by its lines, not as YAML
(pitboss has no YAML reader at run time): a job is a key directly under the
top-level ``jobs:`` (its ``name:`` is a line directly under it), and a step is an
item of the job's ``steps:`` list, whose ``name:`` is read as written, so a matrix
job named ``e2e (${{ matrix.group }})`` is that string.
"""

import dataclasses
import re
from typing import AbstractSet, Sequence

KEY = re.compile(r"^(?P<key>[^\s#-][^:]*?):(?:\s+.*)?$")
NAME = re.compile(r"^name:(?:\s+(?P<value>.*))?$")
COMMENT = re.compile(r"\s+#.*$")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Workflow:
    """What a workflow file calls its jobs and steps.

    Attributes:
        jobs: each job's key and its ``name:``, as written.
        steps: each step's ``name:``, as written.
    """

    jobs: AbstractSet[str]
    steps: AbstractSet[str]


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _unquoted(value: str | None) -> str:
    text = (value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return COMMENT.sub("", text)


def _name_of(text: str) -> str | None:
    matched = NAME.match(text)
    return None if matched is None else _unquoted(matched["value"])


def _under(lines: Sequence[str], start: int) -> Sequence[str]:
    # the lines under lines[start], which are indented deeper than it
    found = []
    for each in lines[start + 1 :]:
        if _indent(each) <= _indent(lines[start]):
            break
        found.append(each)
    return found


def _list_under(lines: Sequence[str], start: int) -> Sequence[str]:
    # as _under, and a list may sit at the indent of its key
    found = []
    level = _indent(lines[start])
    for each in lines[start + 1 :]:
        listed = each.lstrip().startswith("-")
        if _indent(each) < level or (_indent(each) == level and not listed):
            break
        found.append(each)
    return found


def _step_names(items: Sequence[str]) -> Sequence[str]:
    dashes = [_indent(each) for each in items if each.lstrip().startswith("-")]
    level = min(dashes, default=0)
    found = []
    for each in items:
        text = each.strip()
        if _indent(each) == level and text.startswith("- "):
            found.append(_name_of(text[2:].strip()))
        elif _indent(each) == level + 2:
            found.append(_name_of(text))
    return [each for each in found if each is not None]


def _direct(lines: Sequence[str]) -> Sequence[tuple[int, str]]:
    # the lines at the shallowest indent: their numbers and their text
    level = min((_indent(each) for each in lines), default=0)
    return [(n, each.strip()) for n, each in enumerate(lines) if _indent(each) == level]


def _job(chunk: Sequence[str]) -> tuple[Sequence[str], Sequence[str]]:
    # the names of a job (its key, its name:) and of its steps
    key = KEY.match(chunk[0].strip())
    body = chunk[1:]
    direct = _direct(body)
    labels = [_name_of(text) for _, text in direct]
    lists = [
        _step_names(_list_under(body, n)) for n, text in direct if text == "steps:"
    ]
    ids = [key["key"]] if key else []
    return [*ids, *(each for each in labels if each)], [
        each for item in lists for each in item
    ]


def _chunks(lines: Sequence[str]) -> Sequence[Sequence[str]]:
    begin = next((n for n, each in enumerate(lines) if each.rstrip() == "jobs:"), None)
    under = [] if begin is None else _under(lines, begin)
    firsts = [n for n, _ in _direct(under)]
    return [under[a:b] for a, b in zip(firsts, [*firsts[1:], len(under)])]


def read(text: str) -> Workflow:
    """Read the jobs and steps a workflow file names.

    Args:
        text: the file's text.

    Returns:
        The names of its jobs (each job's key and its ``name:``) and of its
        steps, as written in the file.
    """
    lines = [
        each
        for each in text.splitlines()
        if each.strip() and not each.lstrip().startswith("#")
    ]
    parsed = [_job(each) for each in _chunks(lines)]
    return Workflow(
        jobs=frozenset(each for found, _ in parsed for each in found),
        steps=frozenset(each for _, found in parsed for each in found),
    )
