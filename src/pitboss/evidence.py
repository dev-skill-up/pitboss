"""Find the blocks of a body's Evidence that ``expand`` did not produce.

A block is evidence when it is fenced and its first line starts with ``$ ``.
One that ``pitboss expand`` produced has its mark and the digest of its
contents on the opening line (keyword: expand, pitboss#117); a block typed or
edited by hand does not match its digest.
"""

import dataclasses
import re
from typing import Sequence

from . import expansion

FENCE = re.compile(r"^ {0,3}(?P<ticks>`{3,}|~{3,})(?P<info>.*)$")
HEADING = re.compile(r"^ {0,3}(?P<hashes>#{1,6})(?:\s+(?P<title>.*))?$")
EVIDENCE = re.compile(r"Evidence\b", re.IGNORECASE)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Block:
    """A fenced block.

    Attributes:
        line: the number of its opening line, from 1.
        info: the text after the opening fence.
        contents: the lines between the fences, each with its newline.
        closed: whether a closing fence ends it.
        in_evidence: whether it is in an Evidence section.
    """

    line: int
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
        fence: the opening fence of the block it is in, or an empty string.
        info: that block's info text.
        opened: the line that block opened on.
        kept: the lines of that block so far.
    """

    evidence_level: int = 0
    fence: str = ""
    info: str = ""
    opened: int = 0
    kept: tuple[str, ...] = ()


def _closes(fence: str, line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith(fence) and set(stripped) == {fence[0]}


def _level_after(reading: Reading, line: str) -> int:
    heading = HEADING.match(line)
    if heading is None:
        return reading.evidence_level
    level = len(heading.group("hashes"))
    if EVIDENCE.match(heading.group("title") or ""):
        return level
    return 0 if level <= reading.evidence_level else reading.evidence_level


def _finished(reading: Reading, closed: bool) -> Block:
    return Block(
        line=reading.opened,
        info=reading.info,
        contents="".join(reading.kept),
        closed=closed,
        in_evidence=reading.evidence_level > 0,
    )


def _step(reading: Reading, number: int, line: str) -> tuple[Reading, Sequence[Block]]:
    if reading.fence and _closes(reading.fence, line):
        return dataclasses.replace(reading, fence="", kept=()), [
            _finished(reading, True)
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
    return dataclasses.replace(reading, evidence_level=_level_after(reading, line)), []


def blocks(body: str) -> Sequence[Block]:
    """The fenced blocks of a body.

    Args:
        body: the text.

    Returns:
        Each block, in order; one never closed runs to the end.
    """
    found: list[Block] = []
    reading = Reading()
    for number, line in enumerate(body.splitlines(keepends=True), 1):
        reading, done = _step(reading, number, line)
        found.extend(done)
    if reading.fence:
        found.append(_finished(reading, False))
    return found


def produced(block: Block) -> bool:
    """Whether ``pitboss expand`` produced a block.

    Args:
        block: the block.

    Returns:
        True when it is closed and its opening line carries the mark and the
        digest of its contents.
    """
    return block.closed and block.info == expansion.info(block.contents)


def _holds_command(block: Block) -> bool:
    return any(row.startswith(expansion.PROMPT) for row in block.contents.splitlines())


def hand_typed(body: str) -> Sequence[int]:
    """The blocks of an Evidence section that ``expand`` did not produce.

    Args:
        body: the text.

    Returns:
        The opening line numbers of the blocks with a ``$ `` line that are
        not an ``expand`` block.
    """
    return [
        each.line
        for each in blocks(body)
        if each.in_evidence
        and _holds_command(each)
        and not produced(each)
    ]
