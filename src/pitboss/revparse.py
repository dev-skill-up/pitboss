"""The Evidence blocks of ``git rev-parse HEAD`` that print another head.

The keyword is rev-parse-head (pitboss#329).
"""

import re
from typing import Sequence

from . import evidence

REV_PARSE = "$ git rev-parse HEAD"
HEAD_LINES = re.compile(r"^Head:\s*([0-9a-f]{40})\s*$", re.MULTILINE)


def _rev_parse(body: str) -> Sequence[evidence.Block]:
    return [
        each
        for each in evidence.blocks(body)
        if evidence.produced(each) and evidence.first_row(each) == REV_PARSE
    ]


def _last_head(body: str) -> str:
    written = HEAD_LINES.findall(body)
    return written[-1] if written else ""


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
    wanted = head or _last_head(body)
    found = [
        (each.line, printed)
        for each in _rev_parse(body)
        if wanted
        for printed in [_printed(each)]
        if printed != wanted
    ]
    return [
        f"line {line}: the block of `git rev-parse HEAD` prints {printed or 'no SHA'}"
        f" but the last Head: line is {wanted}: run pitboss expand again"
        " (rev-parse-head)"
        for line, printed in found
    ]


def _printed(block: evidence.Block) -> str:
    # the first output line of a block, after its command row
    lines = block.contents.split("\n")
    return lines[1].strip() if len(lines) > 1 else ""
