"""The Plan section of a PR body, which a review digests (keyword: plan-digest).

An approved Plan is never reopened (pitboss#172): a review that grades the Plan
records the Plan section it read as a ``Plan digest: <digest>`` line
(``bodydigest.PLAN_PREFIX``, the digest of ``bodydigest.digest``), and the sweep
compares it with the Plan section of the body now. The section is the text from
the ``## Plan`` heading to the next ``## `` heading, without its ``Head:`` lines
(the head moves with every push and is not the Plan). The module imports only
``expansion``, so the flow and the command both read it.

``collapsed`` is the text the digest covers (keyword: plan-digest-collapse,
pitboss#358): a block ``pitboss expand`` produced, whose ``sha256=`` header
matches its contents, is its ``$ command`` line alone, so a fix round that
re-expands the blocks at a new head keeps the digest. A block whose header does
not match its contents (one edited by hand) stays in verbatim.
"""

import re

from . import expansion

_PLAN_HEADING = re.compile(r"^## Plan\s*$")
_ANY_HEADING = re.compile(r"^## ")
_HEAD_LINE = re.compile(r"^Head: ")
_OPENING = re.compile(
    rf"^(?P<fence>`{{3,}}){re.escape(expansion.MARK)}"
    rf" {re.escape(expansion.DIGEST_KEY)}(?P<digest>[0-9a-f]{{{expansion.DIGEST_LENGTH}}})\s*$"
)


def section(body: str) -> str:
    """The Plan section of a PR body.

    Args:
        body: the PR body.

    Returns:
        The lines from the ``## Plan`` heading up to the next ``## `` heading,
        without ``Head:`` lines; empty when the body has no Plan heading.
    """
    kept: list[str] = []
    inside = False
    for line in body.splitlines():
        if _PLAN_HEADING.match(line):
            inside = True
        elif inside and _ANY_HEADING.match(line):
            break
        if inside and not _HEAD_LINE.match(line):
            kept.append(line)
    return "\n".join(kept)


def _closing(lines: list[str], start: int, fence: str) -> int | None:
    # the index of the line after `start` that is the fence alone
    return next(
        (n for n in range(start + 1, len(lines)) if lines[n].rstrip() == fence), None
    )


def _command_line(inside: list[str], digest: str) -> str | None:
    # the `$ command` line of a block whose header matches its contents
    text = "".join(f"{each}\n" for each in inside)
    if inside and inside[0].startswith(expansion.PROMPT):
        return inside[0] if expansion.digest(text) == digest else None
    return None


def collapsed(text: str) -> str:
    """The Plan section with each block ``pitboss expand`` produced as its command.

    Args:
        text: the Plan section, as ``section`` returns it.

    Returns:
        The text in which each fenced block whose ``pitboss-expand sha256=``
        header is the digest of its contents is replaced by its ``$ command``
        line; any other block (a hand-edited one, one with no closing fence)
        and every other line is kept as it is.
    """
    lines = text.split("\n")
    out: list[str] = []
    at = 0
    while at < len(lines):
        opening = _OPENING.match(lines[at])
        end = _closing(lines, at, opening["fence"]) if opening else None
        command = (
            _command_line(lines[at + 1 : end], opening["digest"])
            if opening and end is not None
            else None
        )
        if command is None or end is None:
            out.append(lines[at])
            at += 1
        else:
            out.append(command)
            at = end + 1
    return "\n".join(out)
