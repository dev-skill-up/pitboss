"""The ticket reader: a ticket's Done-when items, read closed-world (pitboss#444).

The keyword is ticket-reader. The items are under the ticket's one ``## Done when``
heading, up to the next ``## `` heading or a ``---`` rule: its list items
(``-``, ``*``, ``1.``; an indented line continues one, a paragraph before the
first is the introduction), or, when it has no list, its paragraphs. A known key
line (``Paths:``, ``Priority:``, ``Found by`` ...) ends the items and is never
one; any other line after a list makes the body ``NotInForm``, a value the act
verb's decision reads (plan 6.5: no refusal raised as an answer). ``started`` says
which open PRs close a ticket, by GitHub's closing keywords.
"""

import dataclasses
import re
from typing import Callable, Sequence

HEADING = re.compile(r"(?mi)^## done[- ]when\s*$")
ITEM = re.compile(r"(?:[-*]|\d+\.) +")
KEYS = re.compile(
    r"^(Paths|Max-lines|Priority|Found by|Refs|Blocked-by|Related|Not in this ticket"
    r"|Order|Research|Fixtures)\b"
)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Items:
    """A ticket body in the reader's form.

    Attributes:
        found: its Done-when items, in order.
    """

    found: Sequence[str]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class NotInForm:
    """A ticket body the reader does not take.

    Attributes:
        problem: what is not in the form, in one line.
    """

    problem: str


Read = Items | NotInForm  # what the reader makes of a body


def _section(body: str | None) -> Sequence[str] | NotInForm:
    parts = HEADING.split(body or "")
    if len(parts) != 2:
        return NotInForm(
            problem=f"the ticket has {len(parts) - 1} `## Done when` headings, not one"
        )
    found = []
    for line in parts[1].splitlines():
        if line.startswith("## ") or re.match(r"-{3,}\s*$", line):
            break
        found.append(line)
    return found


def _listed(section: Sequence[str]) -> Read:
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
            return NotInForm(
                problem="a line under Done-when that is neither an item nor a known"
                f" key: {line[:50]!r}"
            )
    return Items(found=items)


def _paragraphs(lines: Sequence[str]) -> Read:
    paragraphs = re.split(r"\n\s*\n", "\n".join(lines))
    return Items(
        found=[
            " ".join(each.split())
            for each in paragraphs
            if each.strip() and not KEYS.match(each.strip())
        ]
    )


Reader = Callable[[str | None], Read]


def done_when(body: str | None) -> Read:
    """The Done-when items of a ticket body, or what is not in the form.

    Args:
        body: the ticket's body.

    Returns:
        The items, in order; or, for no heading or two, no item, or a line in no
        known form, what it is.
    """
    lines = _section(body)
    if isinstance(lines, NotInForm):
        return lines
    marked = any(ITEM.match(each) for each in lines)
    found = _listed(lines) if marked else _paragraphs(lines)
    if isinstance(found, Items) and not found.found:
        return NotInForm(problem="the ticket has no Done-when item")
    return found


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
