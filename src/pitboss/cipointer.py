"""The CI pointers of a Plan (keyword: ci-pointer, pitboss#335).

A CI pointer is a row of the Plan that names a workflow file (a backticked
``*.yml``, bare or under ``.github/workflows/``) and, after the words ``job``,
``step`` or ``greppable``, backticked names (workflow `check.yml`, job `e2e`,
step `Run e2e tests`, greppable `smoke.spec.js`). A name belongs to the last
of those words before it as long as only commas, ``and``, ``or``, ``the`` and the
like come between; any other word ends the list. A row is a pointer only when it
names a workflow file and at least one job, step or greppable string. A row under
the heading ``CI pointer rows``, and a row that says ``workflow``, ``job`` or
``step`` next to a backticked name, that is no pointer is ``unrecognized``
(keyword: ci-pointer-form, pitboss#358). The module reads no file: the Plan
section is given.
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
HEADING = re.compile(r"^\s*(?:#+\s*|\*\*|__)?CI[ -]pointer rows\b", re.I)
OTHER_HEADING = re.compile(r"^\s*(?:#+\s|(?:\*\*|__)?[\w ,-]+ rows\b)", re.I)
NAMED = re.compile(r"\b(?:workflows?|jobs?|steps?)\b[\s:]*`[^`]+`", re.I)
FORM = (
    "a pointer names its workflow file in backticks (`check.yml`), then the job,"
    " step or greppable names in backticks (workflow `check.yml`, job `check`,"
    " step `Run Nox`, greppable `test_name`)"
)
ITEM = re.compile(r"^\s*(?:\d{1,9}[.)]|[-*])\s+")
COMMAND = re.compile(r"^\$ ")
FENCE = re.compile(r"^\s*`{3,}")


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


def prose(section: str) -> Sequence[tuple[int, str]]:
    """The lines of a Plan section that are prose.

    Args:
        section: the Plan section.

    Returns:
        Each line's number (the heading is 1) and text, but a command line
        (``$ ...``) and a line inside a fenced block.
    """
    found: list[tuple[int, str]] = []
    fenced = False
    for number, line in enumerate(section.splitlines(), 1):
        if FENCE.match(line):
            fenced = not fenced
        elif not fenced and not COMMAND.match(line):
            found.append((number, line))
    return found


def rows(section: str) -> Sequence[tuple[int, str]]:
    """The rows of a Plan section.

    A row is a list item with its continuation lines, or a paragraph; a command
    line (``$ ...``) is no row, and neither is a line inside a fenced block (the
    output of a command, or a quoted text).

    Args:
        section: the Plan section.

    Returns:
        Each row's first line number and its text.
    """
    found: list[tuple[int, list[str]]] = []
    inside = False
    fenced = False
    for number, line in enumerate(section.splitlines(), 1):
        if FENCE.match(line):
            fenced, inside = not fenced, False
        elif fenced:
            continue
        elif not line.strip() or COMMAND.match(line):
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


def _pointer_lines(section: str) -> frozenset[int]:
    # the numbers of the lines under the heading `CI pointer rows`
    found: set[int] = set()
    inside = False
    for number, line in enumerate(section.splitlines(), 1):
        if HEADING.match(line):
            inside = True
        elif inside and OTHER_HEADING.match(line):
            inside = False
        elif inside:
            found.add(number)
    return frozenset(found)


def unrecognized(section: str) -> Sequence[tuple[int, str]]:
    """The rows that are meant as CI pointers and are none.

    Args:
        section: the Plan section.

    Returns:
        The line number and the text of each row that is under the heading
        ``CI pointer rows`` or says ``workflow``, ``job`` or ``step`` next to a
        backticked name, and that ``read`` does not take for a pointer.
    """
    listed = _pointer_lines(section)
    return [
        (number, text)
        for number, text in rows(section)
        if (number in listed or NAMED.search(text)) and not _pointer(number, text)
    ]
