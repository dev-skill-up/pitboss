"""The ticket reader: a ticket's Done-when items, read closed-world (pitboss#444).

The keyword is ticket-reader. The items are under the ticket's one ``## Done when``
heading, up to the next ``## `` heading or a ``---`` rule: its list items
(``-``, ``*``, ``1.``; an indented line continues one, a paragraph before the
first is the introduction), or, when it has no list, its paragraphs. A known key
line (``Paths:``, ``Priority:``, ``Found by`` ...) ends the items and is never
one; any other line after a list refuses the read. ``started`` says which open
PRs close a ticket, by GitHub's closing keywords.
"""

import re
from typing import Iterable, Sequence

HEADING = re.compile(r"(?mi)^## done[- ]when\s*$")
ITEM = re.compile(r"(?:[-*]|\d+\.) +")
KEYS = re.compile(
    r"^(Paths|Max-lines|Priority|Found by|Refs|Blocked-by|Related|Not in this ticket"
    r"|Order|Research|Fixtures)\b"
)
# docs: linking a pull request to an issue (the nine closing keywords)
CLOSING = re.compile(
    r"\b(close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s+((?:[\w.-]+/[\w.-]+)?#\d+)", re.I
)


class Refused(Exception):
    """The text is not in the form its reader takes."""


def _section(body: str | None) -> Sequence[str]:
    parts = HEADING.split(body or "")
    if len(parts) != 2:
        raise Refused(
            f"the ticket has {len(parts) - 1} `## Done when` headings, not one"
        )
    found = []
    for line in parts[1].splitlines():
        if line.startswith("## ") or re.match(r"-{3,}\s*$", line):
            break
        found.append(line)
    return found


def _listed(section: Sequence[str]) -> Sequence[str]:
    items: list[str] = []
    ended = False
    for line in section:
        start = ITEM.match(line)
        if not line.strip() or (not items and not start and not KEYS.match(line)):
            continue
        if KEYS.match(line):
            ended = True
        elif start and not ended:
            items.append(line[start.end() :].strip())
        elif line[:1] in " \t" and items and not ended:
            items[-1] += " " + line.strip()
        else:
            raise Refused(
                "a line under Done-when that is neither an item nor a known key:"
                f" {line[:50]!r}"
            )
    return items


def _paragraphs(lines: Sequence[str]) -> Sequence[str]:
    paragraphs = re.split(r"\n\s*\n", "\n".join(lines))
    return [
        " ".join(each.split())
        for each in paragraphs
        if each.strip() and not KEYS.match(each.strip())
    ]


def items(body: str | None) -> Sequence[str]:
    """The Done-when items of a ticket body.

    Args:
        body: the ticket's body.

    Returns:
        The items, in order.

    Raises:
        Refused: no heading or two, no item, or a line in no known form.
    """
    lines = _section(body)
    found = (
        _listed(lines)
        if any(ITEM.match(each) for each in lines)
        else _paragraphs(lines)
    )
    if not found:
        raise Refused("the ticket has no Done-when item")
    return found


def closes(body: str | None, repo: str, number: int) -> bool:
    """Whether a PR body closes a ticket, by any of GitHub's closing keywords.

    Args:
        body: the PR's body.
        repo: the ticket's repository (``owner/name``).
        number: the ticket's number.

    Returns:
        True when a closing keyword names ``#number`` or ``repo#number``.
    """
    for match in CLOSING.finditer(body or ""):
        where, _, named = match.group(2).partition("#")
        if named == str(number) and where in ("", repo):
            return True
    return False


def started(
    bodies: Iterable[tuple[int, str | None]], repo: str, number: int
) -> Sequence[int]:
    """The open PRs whose body closes a ticket.

    Args:
        bodies: each open PR's number and body.
        repo: the ticket's repository.
        number: the ticket's number.

    Returns:
        The numbers of the PRs that close it.
    """
    return [pull for pull, body in bodies if closes(body, repo, number)]


def written(
    done_when: Sequence[str], paths: Sequence[str], max_lines: int, priority: str
) -> str:
    """The body ``act ticket`` writes, in the one form the reader takes.

    Args:
        done_when: the items.
        paths: the paths the work may change.
        max_lines: the most lines the PR may change.
        priority: p0 to p3.

    Returns:
        The body.
    """
    listed = "".join(f"- {each}\n" for each in done_when)
    keys = f"Paths: {' '.join(paths)}\nMax-lines: {max_lines}\nPriority: {priority}\n"
    return f"## Done when\n\n{listed}\n{keys}"
