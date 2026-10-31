"""Find the command rows of a body that ``expand`` did not produce.

A row is a command when it starts with ``$`` and a space, a tab or nothing,
after any quote marks, list markers and white space (so a row in a quote, a
list item or an indented code block is one too). A command row is evidence
only inside a fenced block that ``pitboss expand`` produced: its opening line
carries the mark and the digest of its contents (keyword: expand,
pitboss#117). Every other command row is refused rather than parsed, so no
container GitHub shows a block in can hide a typed one.
"""

import dataclasses
import re
from typing import Sequence

from . import expansion

FENCE = re.compile(r"^ {0,3}(?P<ticks>`{3,}|~{3,})(?P<info>.*)$")
CLOSING = re.compile(r"^ {0,3}(?P<ticks>`+|~+)[ \t]*$")
# one definition of a heading, for the evidence check and the hand-typed one
HEADING = re.compile(r"^ {0,3}(?P<hashes>#{1,6})(?:[ \t]+(?P<title>.*))?$")
EVIDENCE = re.compile(r"Evidence\b", re.IGNORECASE)
COMMAND = re.compile(r"^(?:[ \t>]|[-+*](?=[ \t])|\d{1,9}[.)](?=[ \t]))*\$(?:[ \t]|$)")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Block:
    """A fenced block.

    Attributes:
        line: the number of its opening line, from 1.
        end: the number of its last line, from 1.
        info: the text after the opening fence.
        contents: the lines between the fences, each with its newline.
        closed: whether a closing fence ends it.
        in_evidence: whether it is in an Evidence section.
    """

    line: int
    end: int
    info: str
    contents: str
    closed: bool
    in_evidence: bool


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Reading:
    """Where a reader of a body is.

    Attributes:
        evidence_level: the level of the Evidence heading whose section it is
            in, or 0 outside one.
        headed: whether an Evidence heading has been read.
        fence: the opening fence of the block it is in, or an empty string.
        info: that block's info text.
        opened: the line that block opened on.
        kept: the lines of that block so far.
    """

    evidence_level: int = 0
    headed: bool = False
    fence: str = ""
    info: str = ""
    opened: int = 0
    kept: Sequence[str] = ()


def _closes(fence: str, line: str) -> bool:
    # CommonMark: at most 3 spaces, only fence characters, at least as long
    closing = CLOSING.match(line.rstrip("\r\n"))
    if closing is None:
        return False
    ticks = closing.group("ticks")
    return ticks[0] == fence[0] and len(ticks) >= len(fence)


def _heading(reading: Reading, line: str) -> Reading:
    title_line = HEADING.match(line.rstrip("\r\n"))
    if title_line is None:
        return reading
    level = len(title_line.group("hashes"))
    if EVIDENCE.match(title_line.group("title") or ""):
        return dataclasses.replace(reading, evidence_level=level, headed=True)
    ended = level <= reading.evidence_level
    return dataclasses.replace(
        reading, evidence_level=0 if ended else reading.evidence_level
    )


def _finished(reading: Reading, end: int, closed: bool) -> Block:
    return Block(
        line=reading.opened,
        end=end,
        info=reading.info,
        contents="".join(reading.kept),
        closed=closed,
        in_evidence=reading.evidence_level > 0,
    )


def _step(reading: Reading, number: int, line: str) -> tuple[Reading, Sequence[Block]]:
    if reading.fence and _closes(reading.fence, line):
        return dataclasses.replace(reading, fence="", kept=()), [
            _finished(reading, number, True)
        ]
    if reading.fence:
        return dataclasses.replace(reading, kept=(*reading.kept, line)), []
    opening = FENCE.match(line.rstrip("\r\n"))
    if opening is not None:
        return (
            dataclasses.replace(
                reading,
                fence=opening.group("ticks"),
                info=opening.group("info").strip(),
                opened=number,
            ),
            [],
        )
    return _heading(reading, line), []


def _read(body: str) -> tuple[Sequence[Block], bool]:
    found: list[Block] = []
    reading = Reading()
    rows = body.splitlines(keepends=True)
    for number, text in enumerate(rows, 1):
        reading, done = _step(reading, number, text)
        found.extend(done)
    if reading.fence:
        found.append(_finished(reading, len(rows), False))
    return found, reading.headed


def blocks(body: str) -> Sequence[Block]:
    """The fenced blocks of a body.

    Args:
        body: the text.

    Returns:
        Each block, in order; one never closed runs to the end.
    """
    return _read(body)[0]


def produced(block: Block) -> bool:
    """Whether ``pitboss expand`` produced a block.

    Args:
        block: the block.

    Returns:
        True when it is closed and its opening line carries the mark and the
        digest of its contents.
    """
    return block.closed and block.info == expansion.info(block.contents)


def has_section(body: str) -> bool:
    """Whether a body has an Evidence section.

    Args:
        body: the text.

    Returns:
        True when a line outside a fenced block is an Evidence heading: one to
        six ``#``, a space or a tab, up to three spaces of indentation.
    """
    return _read(body)[1]


def has_produced(body: str) -> bool:
    """Whether a block ``expand`` produced is in the Evidence section.

    Args:
        body: the text.

    Returns:
        True when the section, from its heading to the next heading of the
        same or a higher level, holds such a block.
    """
    return any(produced(each) and each.in_evidence for each in blocks(body))


def hand_typed(body: str) -> Sequence[int]:
    """The command rows of a body that are not in a block ``expand`` produced.

    The whole body is read, not only its Evidence section: a heading that
    lint does not see can still be shown as one. A produced block elsewhere is
    fine.

    Args:
        body: the text.

    Returns:
        The numbers of the lines, from 1.
    """
    inside = {
        number
        for each in blocks(body)
        if produced(each)
        for number in range(each.line, each.end + 1)
    }
    return [
        number
        for number, line in enumerate(body.splitlines(), 1)
        if COMMAND.match(line) and number not in inside
    ]
