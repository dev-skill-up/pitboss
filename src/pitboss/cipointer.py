"""The CI pointers of a Plan (keyword: ci-pointer, pitboss#335).

A CI pointer is a row of the Plan that names a workflow file (a backticked
``*.yml``, bare or under ``.github/workflows/``) and, after the words ``job``,
``step`` or ``greppable``, backticked names (workflow `check.yml`, job `e2e`,
step `Run e2e tests`, greppable `smoke.spec.js`). A name belongs to the last
of those words before it as long as only commas, ``and``, ``or``, ``the`` and the
like come between; any other word ends the list. A row is a pointer only when it
names a workflow file and at least one job, step or greppable string. The module
reads no file: the Plan section is given.
"""

import dataclasses
import re
from typing import Sequence

DIRECTORY = ".github/workflows/"
WORKFLOW = re.compile(r"^(?:\.github/workflows/)?[A-Za-z0-9._-]+\.ya?ml$")
TOKEN = re.compile(
    r"`(?P<span>[^`]+)`|\b(?P<word>workflows?|jobs?|steps?|greppable)\b", re.I
)
CONNECTIVE = re.compile(
    r"^[\s,;:()&]*(?:(?:and|or|the|then|also|name|names|string|strings|title|titles"
    r"|test|called|named)[\s,;:()&]*)*$",
    re.I,
)
ITEM = re.compile(r"^\s*(?:\d{1,9}[.)]|[-*])\s+")
COMMAND = re.compile(r"^\$ ")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Pointer:
    """A CI pointer.

    Attributes:
        line: the number of the Plan line the row starts at (the heading is 1).
        workflow: its workflow file, as a path from the repository's root.
        jobs: the job names it gives.
        steps: the step names it gives.
        greppable: the strings it gives.
    """

    line: int
    workflow: str
    jobs: Sequence[str]
    steps: Sequence[str]
    greppable: Sequence[str]


def path_of(span: str) -> str:
    """The path of a workflow file named in a pointer.

    Args:
        span: the backticked text, a bare file name or a path.

    Returns:
        The path from the repository's root.
    """
    return span if "/" in span else DIRECTORY + span


def rows(section: str) -> Sequence[tuple[int, str]]:
    """The rows of a Plan section.

    A row is a list item with its continuation lines, or a paragraph; a command
    line (``$ ...``) is no row.

    Args:
        section: the Plan section.

    Returns:
        Each row's first line number and its text.
    """
    found: list[tuple[int, list[str]]] = []
    inside = False
    for number, line in enumerate(section.splitlines(), 1):
        if not line.strip() or COMMAND.match(line):
            inside = False
        elif inside and not ITEM.match(line):
            found[-1][1].append(line.strip())
        else:
            found.append((number, [line.strip()]))
            inside = True
    return [(number, " ".join(text)) for number, text in found]


def _entries(text: str) -> tuple[Sequence[str], Sequence[tuple[str, str, int]]]:
    # the workflow files named, and each (role, name, files named before it)
    files: list[str] = []
    named: list[tuple[str, str, int]] = []
    role = ""
    end = 0
    for found in TOKEN.finditer(text):
        if role and not CONNECTIVE.match(text[end : found.start()]):
            role = ""
        end = found.end()
        span = found["span"]
        if span is None:
            word = found["word"].lower().rstrip("s")
            role = "" if word == "workflow" else word
        elif WORKFLOW.match(span):
            files.append(path_of(span))
            role = ""
        elif role:
            named.append((role, span, len(files)))
    return files, named


def _of(named: Sequence[tuple[str, str, int]], role: str, owner: int) -> Sequence[str]:
    # a name belongs to the last workflow before it, else to the first one
    return [n for r, n, before in named if r == role and max(before - 1, 0) == owner]


def _pointer(number: int, text: str) -> Sequence[Pointer]:
    files, named = _entries(text)
    if not files or not named:
        return []
    return [
        Pointer(
            line=number,
            workflow=path,
            jobs=_of(named, "job", i),
            steps=_of(named, "step", i),
            greppable=_of(named, "greppable", i),
        )
        for i, path in enumerate(files)
    ]


def read(section: str) -> Sequence[Pointer]:
    """The CI pointers of a Plan section.

    Args:
        section: the Plan section.

    Returns:
        A pointer for each workflow file a row names, in order, with the names
        that belong to it; none for a row that names no job, step or greppable
        string.
    """
    return [each for number, text in rows(section) for each in _pointer(number, text)]
