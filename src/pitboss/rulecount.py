"""The recount of a brief's rule files, written apart from the writer (pitboss#444).

The keyword is brief-rules. Another discovery (``os.walk`` of the whole checkout),
another reading of the front matter (a split on ``---`` and a key scan, which
takes any form of ``paths:``) and another matcher (``fnmatch`` one path segment at
a time, ``**`` any number of them). The files it finds are compared with what the
brief holds, byte for byte, so a writer that drops a file is caught.
"""

import fnmatch
import hashlib
import os
import pathlib
from typing import Iterator, Sequence

from .rulefiles import NAMES, RULES, WORKER, Ticket, files_of

SKIPPED = frozenset({".git", "node_modules", "build", "bats_modules"})


def segments_match(path: Sequence[str], glob: Sequence[str]) -> bool:
    """Whether a path's segments match a glob's, ``**`` being any number of them.

    Args:
        path: the path's segments.
        glob: the glob's segments.

    Returns:
        True on a match.
    """
    if not glob:
        return not path
    if glob[0] == "**":
        return any(
            segments_match(path[index:], glob[1:]) for index in range(len(path) + 1)
        )
    return (
        bool(path)
        and fnmatch.fnmatchcase(path[0], glob[0])
        and segments_match(path[1:], glob[1:])
    )


def globs_of(text: str) -> Sequence[str] | None:
    """The ``paths:`` of a rule file, read loosely (any form a YAML reader takes).

    Args:
        text: the file's text.

    Returns:
        The globs, or None when there is no ``paths:``.
    """
    pieces = text.split("---\n")
    if not text.startswith("---\n") or len(pieces) < 3:
        return None
    lines = pieces[1].splitlines()
    starts = [index for index, line in enumerate(lines) if line.startswith("paths:")]
    if not starts:
        return None
    rest = lines[starts[0]][len("paths:") :].strip()
    if rest:
        return [each.strip(" \"'") for each in rest.strip("[]").split(",")]
    taken = []
    for row in lines[starts[0] + 1 :]:
        if not row.lstrip().startswith("-"):
            break
        taken.append(row.lstrip()[1:].strip().strip("\"'"))
    return taken


def _binds(where: str, files: Sequence[str], ticket: Ticket) -> bool:
    inside = any(each == where or each.startswith(where + "/") for each in files)
    below = any(
        where == each.rstrip("/") or where.startswith(each.rstrip("/") + "/")
        for each in ticket.paths
    )
    return where == "" or inside or below


def _wanted(relative: str, files: Sequence[str], ticket: Ticket) -> bool:
    name = os.path.basename(relative)
    if name in NAMES:
        return _binds(os.path.dirname(relative), files, ticket)
    if relative == WORKER:
        return True
    if not (relative.startswith(RULES + "/") and name.endswith(".md")):
        return False
    globs = globs_of((ticket.checkout / relative).read_text(encoding="utf-8"))
    return globs is None or any(
        segments_match(each.split("/"), glob.split("/"))
        for glob in globs
        for each in files
    )


def _walk(root: pathlib.Path) -> Iterator[str]:
    for directory, folders, files in os.walk(root):
        folders[:] = [each for each in folders if each not in SKIPPED]
        for each in files:
            yield os.path.normpath(os.path.join(os.path.relpath(directory, root), each))


def missing(brief: str, ticket: Ticket) -> Sequence[str]:
    """The files that bind the ticket and that the brief lacks or holds altered.

    Args:
        brief: the brief.
        ticket: the ticket.

    Returns:
        Each such file (relative to the checkout, or the user's file in full).
    """
    files = files_of(ticket)
    wanted = [
        ticket.checkout / each
        for each in _walk(ticket.checkout)
        if _wanted(each, files, ticket)
    ]
    user = ticket.home / ".claude" / "CLAUDE.md"
    return [
        (
            str(path.relative_to(ticket.checkout))
            if path.is_relative_to(ticket.checkout)
            else str(path)
        )
        for path in [*wanted, *([user] if user.is_file() else [])]
        if _quoted(path) not in brief
    ]


def _quoted(path: pathlib.Path) -> str:
    # how a brief holds a file: its sha256 line, then its text
    text = path.read_text(encoding="utf-8")
    return f"sha256 {hashlib.sha256(text.encode()).hexdigest()}\n{text}"
