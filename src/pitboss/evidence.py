"""Find the command rows of a body that ``expand`` did not produce.

A row is a command when it starts with ``$`` and a space, a tab or nothing,
after any quote marks, list markers and white space (so a row in a quote, a
list item or an indented code block is one too). A command row is evidence
only inside a fenced block that ``pitboss expand`` produced: its opening line
carries the mark and the digest of its contents (keyword: expand,
pitboss#117). Every other command row is refused rather than parsed, so no
container GitHub shows a block in can hide a typed one.

The match is on the canonical form of a line (``canonical``): HTML entities
decoded, then NFKC normalisation, then every format character (category Cf)
dropped, then leading HTML tags removed. A fullwidth ``$``, a no-break space,
a zero-width character, ``&#36;`` or a ``<pre>`` before the row therefore do
not hide it. A produced block is exempt on its raw lines, so its digest still
covers exactly what ``expand`` printed.
"""

import dataclasses
import html
import re
import unicodedata
from typing import Sequence

from . import expansion

FENCE = re.compile(r"^ {0,3}(?P<ticks>`{3,}|~{3,})(?P<info>.*)$")
CLOSING = re.compile(r"^ {0,3}(?P<ticks>`+|~+)[ \t]*$")
# one definition of a heading, for the evidence check and the hand-typed one
HEADING = re.compile(r"^ {0,3}(?P<hashes>#{1,6})(?:[ \t]+(?P<title>.*))?$")
EVIDENCE = re.compile(r"Evidence\b", re.IGNORECASE)
ADOPT_LINE = "`adopt` (tools/adopt of repository-prototype) made this pull request"
ADOPT_COMMANDS = ("git rev-parse HEAD", "git show --stat")
REV_PARSE = "$ git rev-parse HEAD"
HEAD_LINES = re.compile(r"^Head:\s*([0-9a-f]{40})\s*$", re.MULTILINE)
COMMAND = re.compile(r"^(?:[ \t>]|[-+*](?=[ \t])|\d{1,9}[.)](?=[ \t]))*\$(?:[ \t]|$)")
# a row ending in `; echo $?`, `&& echo $?` or `|| echo ...` (pitboss#170)
HEAD_CHECK = "evidence-head"
STALE_HEAD = (
    "{check}: the Evidence block of `{command}` (line {line}) was expanded at"
    " {recorded} but the head is {head}: run `pitboss expand` again at the head"
)
ECHOED = re.compile(r"(?:[;&]\s*echo\s+[^|;&]*\$\?[^|;&]*|\|\|\s*echo\b.*)\s*$")
LEADING_TAGS = re.compile(r"^(?:\s*<[^>]*>)*")


def canonical(line: str) -> str:
    """The form of a line that a reader sees, for the command match.

    The keyword is expand (pitboss#117).

    Args:
        line: a raw line of a body.

    Returns:
        The line with HTML entities decoded, NFKC normalised, format
        characters (category Cf) removed and leading HTML tags removed.
    """
    normal = unicodedata.normalize("NFKC", html.unescape(line))
    visible = "".join(c for c in normal if unicodedata.category(c) != "Cf")
    return LEADING_TAGS.sub("", visible)


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
        digest of its contents, and the head ``expand`` ran at when it records
        one (``expansion.recorded_head``); the digest is over the form a store keeps
        (``expansion.stored_form``: no BOM, no carriage return, a wrapped URL
        unwrapped; pitboss#164), so a stored block verifies as the file's.
    """
    head = expansion.recorded_head(block.info)
    return block.closed and block.info == expansion.info(block.contents, head)


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


def appended(body: str) -> Sequence[int]:
    """The command rows of produced blocks that end in an exit-status echo.

    The keyword is appended (pitboss#170). ``expand`` prints ``exit status: N`` for
    a status that is not zero, so a row that ends in ``; echo $?`` or
    ``|| echo`` was changed from the Plan's command by hand.

    Args:
        body: the text.

    Returns:
        The numbers of the command rows' lines, from 1, in the Evidence
        section.
    """
    return [
        each.line + 1
        for each in blocks(body)
        if produced(each) and each.in_evidence and ECHOED.search(first_row(each))
    ]


def first_row(block: Block) -> str:
    """The command row of a block ``expand`` produced.

    Args:
        block: the block.

    Returns:
        Its first line, without the newline.
    """
    return block.contents.partition("\n")[0]


def hand_typed(body: str) -> Sequence[int]:
    """The command rows of a body that are not in a block ``expand`` produced.

    The whole body is read, not only its Evidence section: a heading that
    lint does not see can still be shown as one. A produced block elsewhere is
    fine. A row is matched in its canonical form (``canonical``).

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
        if COMMAND.match(canonical(line))
        and number not in inside
        and not _scripted(body, line)
    ]


def made_by_adopt(body: str) -> bool:
    """Whether the first paragraph of a body says the ``adopt`` script made it.

    The keyword is adopt-made (pitboss#423): the output of such a body is
    captured by the program (tools/adopt of repository-prototype), not typed by
    an agent, and the review is of the script.

    Args:
        body: the PR's body.

    Returns:
        True when the first paragraph holds the line adopt writes.
    """
    first = body.strip().split("\n\n")[0]
    return ADOPT_LINE in first


def _scripted(body: str, line: str) -> bool:
    # a row of one of the two commands adopt runs, in a body adopt made
    row = canonical(line).lstrip().removeprefix("$").strip()
    return made_by_adopt(body) and row.startswith(ADOPT_COMMANDS)


def _stale(block: Block, head: str) -> str:
    # the finding of a produced block whose recorded head is not the head, else ""
    recorded = expansion.recorded_head(block.info)
    if not recorded or recorded == head:
        return ""
    command = first_row(block).removeprefix(expansion.PROMPT)
    return STALE_HEAD.format(
        check=HEAD_CHECK,
        command=command,
        line=block.line,
        recorded=recorded,
        head=head,
    )


def stale_heads(body: str, head: str) -> Sequence[str]:
    """The Evidence blocks that were expanded at another commit than the head.

    The keyword is evidence-head (pitboss#398). ``pitboss expand`` records the
    commit it ran at in the opening line of each block (``head=``); a block
    expanded at the commit before the head shows the output of another tree. A
    block with no recorded head (made before the record) is not judged.

    Args:
        body: the PR's body.
        head: the head's SHA; empty when it is not known (nothing is judged).

    Returns:
        A finding for each produced block of the Evidence section whose
        recorded head is not ``head``, naming its command and line.
    """
    found = [
        _stale(each, head)
        for each in blocks(body)
        if head and produced(each) and each.in_evidence
    ]
    return [each for each in found if each]


def rev_parse_blocks(body: str, head: str) -> Sequence[str]:
    """The Evidence blocks that print `git rev-parse HEAD` and print another SHA.

    The keyword is rev-parse-head (pitboss#329): a fix round that moved the head
    and the ``Head:`` line but not this block leaves the old output in the body.

    Args:
        body: the PR's body.
        head: the SHA the body is judged against, empty to use its last
            ``Head:`` line (nothing is judged when it has none).

    Returns:
        A finding for each produced block whose command is `git rev-parse HEAD`
        and whose first output line is not that SHA, naming both SHAs and the
        block's line.
    """
    heads = HEAD_LINES.findall(body)
    wanted = head or (heads[-1] if heads else "")
    found = [
        (each.line, printed)
        for each in blocks(body)
        if wanted and produced(each) and first_row(each) == REV_PARSE
        for printed in [_printed(each)]
        if printed != wanted
    ]
    return [
        f"line {line}: the block of `git rev-parse HEAD` prints {printed or 'no SHA'}"
        f" but the last Head: line is {wanted}: run pitboss expand again"
        " (rev-parse-head)"
        for line, printed in found
    ]


def _printed(block: Block) -> str:
    # the first output line of a block, after its command row
    lines = block.contents.split("\n")
    return lines[1].strip() if len(lines) > 1 else ""


def prose(body: str) -> str:
    """The body with every line of a block ``expand`` produced blanked.

    The keyword is expand-output (pitboss#223): the lines inside a block are the
    raw output of a command, not the author's words, so a words check never
    reads them; the line numbers stay.

    Args:
        body: the PR's body.

    Returns:
        The body whose produced blocks, fences included, are empty lines.
    """
    inside = {
        number
        for each in blocks(body)
        if produced(each)
        for number in range(each.line, each.end + 1)
    }
    return "\n".join(
        "" if number in inside else line
        for number, line in enumerate(body.split("\n"), 1)
    )
