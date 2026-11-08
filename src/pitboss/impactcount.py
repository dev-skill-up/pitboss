"""An Impact row cites one disposition for each hit (keyword: impact-count).

Seen on pitboss#378 (pitboss#317): rows listed fewer ``file:line`` dispositions
than their Evidence printed, and the sweep could not tell which hit was not cited.
``pitboss plan-check`` compares, for each Impact row, the number of hits its search
finds (what ``| wc -l`` of its Evidence prints) with the number of distinct
``file:line`` dispositions the Plan cites under it, up to the next row, and
refuses a Plan where they differ, naming the row and both numbers. A line ``cited
under row N`` in the row's part counts the hits of the row that row N's part
cites. A disposition under a row that is a hit of another row, and not of this
one, is a finding too. A row is a numbered row (``2. ...``), or, when the Plan has
none, a ``$`` command. The module reads no file: the hits are given.
"""

import dataclasses
import re
from typing import AbstractSet, Callable, Collection, Sequence

from . import expansion, impact, impactcheck, planrowtext

CHECK = "impact-count"
CITED_UNDER = re.compile(r"\bcited under (?:an earlier )?row (\d+)\b", re.IGNORECASE)
Search = Callable[[Sequence[str]], Sequence[impact.Hit]]
Key = tuple[str, int]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Part:
    """The lines of the Plan from one row up to the next.

    Attributes:
        label: the row's number.
        first: the first Plan line of the part (the heading is line 1).
        last: the last.
        phrases: the phrases of the row's Impact command; none when the row is
            another kind.
    """

    label: int
    first: int
    last: int
    phrases: Sequence[str]


def _impact_phrases(commands: Sequence[str]) -> Sequence[str]:
    for each in commands:
        found = impactcheck.parse(each)
        if found is not None and not found.problem:
            return found.phrases
    return []


def _starts(lines: Sequence[str]) -> Sequence[tuple[int, int, Sequence[str]]]:
    # (line, label, the row's commands) for each numbered row; else for each `$`
    numbered = [
        (at, int(found["number"]), planrowtext.spans(found["text"]))
        for at, line in enumerate(lines, 1)
        if (found := planrowtext.ROW.match(line))
    ]
    if numbered:
        return numbered
    commands = [
        (at, line[len(expansion.PROMPT) :])
        for at, line in enumerate(lines, 1)
        if line.startswith(expansion.PROMPT)
    ]
    return [(at, label, [each]) for label, (at, each) in enumerate(commands, 1)]


def _cited(section: str, part: Part) -> AbstractSet[Key]:
    return {
        key
        for key, number in impactcheck.dispositions(section).items()
        if part.first <= number <= part.last
    }


def _earlier(section: str, part: Part, mine: AbstractSet[Key]) -> AbstractSet[Key]:
    # the hits of this row that the part of a row named by "cited under row N" cites
    lines = section.splitlines()[part.first - 1 : part.last]
    named = {int(each) for line in lines for each in CITED_UNDER.findall(line)}
    wanted = [each for each in parts(section) if each.label in named]
    return {key for each in wanted for key in _cited(section, each)} & mine


def commands(section: str) -> Sequence[str]:
    """The command lines of a Plan: its ``$`` lines and the spans of its rows.

    Args:
        section: the Plan section.

    Returns:
        The ``$`` commands, then every backticked span of every numbered row.
    """
    spans = [
        span
        for text in planrowtext.rows(section).values()
        for span in planrowtext.spans(text)
    ]
    return [*expansion.commands(section), *spans]


def phrases(section: str) -> Sequence[Sequence[str]]:
    """The phrases of each Impact command of a Plan.

    Args:
        section: the Plan section.

    Returns:
        The phrases of each command that is an Impact command the check can
        run, once for each distinct list.
    """
    parsed = [impactcheck.parse(each) for each in commands(section)]
    found = [tuple(each.phrases) for each in parsed if each and not each.problem]
    return list(dict.fromkeys(found))


def parts(section: str) -> Sequence[Part]:
    """The rows of a Plan and the lines under each.

    Args:
        section: the Plan section.

    Returns:
        A part for each numbered row (or each ``$`` command), in order; its
        phrases are those of its Impact command, none for another kind of row.
    """
    lines = section.splitlines()
    starts = _starts(lines)
    ends = [at - 1 for at, _, _ in starts[1:]] + [len(lines)]
    return [
        Part(label=label, first=at, last=last, phrases=_impact_phrases(commands))
        for (at, label, commands), last in zip(starts, ends)
    ]


def findings(section: str, search: Search) -> Sequence[str]:
    """What the Plan's Impact rows cite wrongly against their hits.

    Args:
        section: the Plan section.
        search: finds the hits of the phrases of an Impact command.

    Returns:
        A finding for each Impact row whose number of hits is not the number of
        distinct dispositions cited under it, and for each disposition under a
        row that is a hit of another row only.
    """
    rows = [each for each in parts(section) if each.phrases]
    everywhere = {(h.path, h.line) for each in rows for h in search(each.phrases)}
    found: list[str] = []
    for part in rows:
        found.extend(_of_row(section, part, search, everywhere))
    return found


def _of_row(
    section: str, part: Part, search: Search, everywhere: Collection[tuple[str, int]]
) -> Sequence[str]:
    hits = {(h.path, h.line) for h in search(part.phrases)}
    own = _cited(section, part)
    cited = own | _earlier(section, part, hits)
    found = []
    if len(cited) != len(hits):
        found.append(
            f"{CHECK}: row {part.label} has {len(hits)} hits and the Plan cites"
            f" {len(cited)} distinct file:line dispositions under it"
        )
    found.extend(
        f"{CHECK}: row {part.label} cites {path}:{line}, which is a hit of"
        f" another row and not of row {part.label}"
        for path, line in sorted(own - hits)
        if (path, line) in everywhere
    )
    return found
