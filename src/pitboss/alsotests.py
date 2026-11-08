"""Tests named on the command line beyond the selection (keyword: test-selection).

``pitboss nox --also MODULE=REASON`` adds one test module to what the diff
selected, with the reason it is wanted (pitboss#331, owner ruling of
2026-11-08 07:15Z). A module without a reason is refused. When the module was
not selected, the selection missed it, and the output says to file a ticket
against that limitation, with the ``pitboss ticket-find`` command to run first
(pitboss#361).
"""

import argparse
import dataclasses
from collections.abc import Sequence

from .testselect import Selection

SEPARATOR = "="
NO_REASON = (
    "{!r} has no reason: give it as MODULE=REASON, such as {}=the helper it reads"
)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Also:
    """A test module added to the selection.

    Attributes:
        module: the test module's dotted name.
        reason: why it is wanted.
    """

    module: str
    reason: str


def also_of(text: str) -> Also:
    """Read ``MODULE=REASON``.

    Args:
        text: the argument.

    Returns:
        The test module and its reason.

    Raises:
        argparse.ArgumentTypeError: when the module or the reason is empty.
    """
    module, _, reason = text.partition(SEPARATOR)
    if not (module.strip() and reason.strip()):
        raise argparse.ArgumentTypeError(NO_REASON.format(text, "pitboss.tests.test_x"))
    return Also(module=module.strip(), reason=reason.strip())


def lines_of(alsos: Sequence[Also], selection: Selection) -> Sequence[str]:
    """What ``pitboss nox`` prints about the tests added by hand.

    Args:
        alsos: the added tests.
        selection: what the diff selected.

    Returns:
        A line for each, with its reason; for each that the selection did not
        pick (the whole suite picks all), the ticket to file and the command
        to run first.
    """
    lines = [f"test-selection also {each.module}: {each.reason}" for each in alsos]
    for each in alsos:
        if selection.everything or each.module in selection.chosen:
            continue
        words = " ".join([*selection.changed[:1], each.module])
        lines.append(
            f"test-selection {each.module} was added though the diff did not"
            f" select it (changed: {', '.join(selection.changed)}): file a ticket"
            " against the selection's limitation, naming the changed file and"
            f" {each.module}, or add it to an open one; run first:"
            f" pitboss ticket-find CONFIG test selection {words}"
        )
    return lines
