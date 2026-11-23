"""Every PR of a test world was handed back, unless the test says it was not (#513)."""

import json
import pathlib
import re
from typing import Protocol, Sequence, TypeVar

from .. import handbackrecord, handbacks

SHA = re.compile(r"[0-9a-f]{40}")
BRANCH = re.compile(r'"ref": "([^"]+)"')
COMMENT = re.compile(r'\{[^{}]*"html_url": "([^"]*)"[^{}]*\}')
CREATED = re.compile(r'"created_at": "([^"]+)"')


class Held(Protocol):
    """The world, as far as the hand-backs go."""

    @property
    def clone(self) -> pathlib.Path:
        """The main clone.

        Returns:
            The value.
        """

    @property
    def bodies(self) -> object:
        """The fake GitHub's bodies.

        Returns:
            The value.
        """


WorldT = TypeVar("WorldT", bound=Held)


def _followed(text: str) -> Sequence[str]:
    # the address of each comment a later comment follows: its steps were taken
    found = [
        (CREATED.findall(each.group(0)), each.group(1))
        for each in COMMENT.finditer(text)
    ]
    stamped = [(created[0], address) for created, address in found if created]
    newest = max((when for when, _ in stamped), default="")
    return sorted({address for when, address in stamped if address and when < newest})


def plant(here: WorldT) -> WorldT:
    """Record, in the main clone, a hand-back of each head for each branch named.

    A hand-back is required of every PR that is not a relock PR, so a world that
    is about something else has each PR handed back: its records hold the head
    and each ruling's address, which covers any body.

    Args:
        here: the world.

    Returns:
        The world.
    """
    text = json.dumps(here.bodies, default=str)
    heads, branches = sorted(set(SHA.findall(text))), set(BRANCH.findall(text))
    rulings = [handbacks.NO_RULING, *_followed(text)]
    common = here.clone / ".git"
    for branch in branches:
        kept = handbackrecord.kept(common, branch)
        kept.mkdir(parents=True, exist_ok=True)
        lines = [f"{h} {handbacks.ANY} {r}\n" for h in heads for r in rulings]
        (kept / handbackrecord.RECORD).write_text("".join(lines))
    return here
