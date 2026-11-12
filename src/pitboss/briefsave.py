"""The brief ``slots next`` prints is saved to a file named from the item (B6).

No agent is dispatched with a hand-typed brief path (coordinator, 2026-11-11
08:11Z; owner, 2026-11-10 19:44Z): each brief is written to a file beside the
ledger, named from the item (``owner-repo-N.brief``), and a ``DISPATCH`` line
prints that path (keyword: brief-save).
"""

import pathlib
import re

DIRECTORY = "briefs"
SUFFIX = ".brief"
DISPATCH = (
    "DISPATCH: {reference} ({model}): brief saved to {path}; dispatch with that"
    " file, never a path typed by hand"
)
UNSAVED = "DISPATCH: {reference}: brief NOT saved ({why}); do not hand-build one"


def name_of(reference: str) -> str:
    """The file name of an item's brief.

    Args:
        reference: ``owner/repo#N``.

    Returns:
        ``owner-repo-N.brief``.
    """
    return re.sub(r"[^\w.-]+", "-", reference) + SUFFIX


def save(ledger: pathlib.Path, reference: str, model: str, text: str) -> str:
    """Write a brief and say where.

    Args:
        ledger: the ledger's file; the briefs are in a directory beside it.
        reference: the item.
        model: the model class the item goes to.
        text: the brief.

    Returns:
        The ``DISPATCH`` line.
    """
    target = ledger.parent / DIRECTORY / name_of(reference)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text + "\n", encoding="utf-8")
    except OSError as error:
        return UNSAVED.format(reference=reference, why=error.strerror or error)
    return DISPATCH.format(reference=reference, model=model, path=target)
