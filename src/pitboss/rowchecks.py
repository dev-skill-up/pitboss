"""The findings about the command rows of a PR body (keyword: appended).

``hand-typed`` (pitboss#117) is a ``$ `` row that ``pitboss expand`` did not
produce; ``appended`` (pitboss#170) is an Evidence row that ``expand``
produced but whose command ends in an echo of the exit status. Each finding
names its line and ends with the check's name in parentheses.
"""

from typing import Sequence

from . import evidence

HAND_TYPED = (
    'a "$ " row that pitboss expand did not produce: put the command in a'
    " template and run pitboss expand"
)
APPENDED = (
    "an Evidence row ends in an echo of the exit status: pitboss expand prints"
    " exit status: N for a status that is not zero, so run the Plan's command as"
    " written"
)


def _each_line(name: str, check: str, lines: Sequence[int], rule: str) -> Sequence[str]:
    return [f"{name}: line {each}: {rule} ({check})" for each in lines]


def typed_by_hand(name: str, body: str) -> Sequence[str]:
    """The findings for the rows not produced by ``expand``.

    Args:
        name: what to call the text in a finding.
        body: the text.

    Returns:
        One finding for each row.
    """
    return _each_line(name, "hand-typed", evidence.hand_typed(body), HAND_TYPED)


def appended(name: str, body: str) -> Sequence[str]:
    """The findings for the rows that end in an echo of the exit status.

    Args:
        name: what to call the text in a finding.
        body: the text.

    Returns:
        One finding for each row.
    """
    return _each_line(name, "appended", evidence.appended(body), APPENDED)


def command_rows(name: str, body: str, head: str) -> Sequence[str]:
    """The findings about the command rows of a PR body.

    Args:
        name: what to call the text in a finding.
        body: the text.
        head: the PR's head SHA, empty when it is not known.

    Returns:
        The hand-typed rows, the rows that end in an echo and the blocks that
        were expanded at another head (keyword: evidence-head, pitboss#398).
    """
    return [
        *typed_by_hand(name, body),
        *appended(name, body),
        *[f"{name}: {each}" for each in evidence.stale_heads(body, head)],
        *[f"{name}: {each}" for each in evidence.rev_parse_blocks(body, "")],
    ]
