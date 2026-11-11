"""The refusal of ``slots check N``: a ledger with fewer rows than expected."""

import sys

from . import ledger, nextfound


def refuse(message: str) -> SystemExit:
    """Print a refusal on standard error.

    Args:
        message: what it says.

    Returns:
        The exit, status 2, for the caller to raise.
    """
    print(message, file=sys.stderr)
    return SystemExit(2)


def fewer(found: nextfound.Found, book: ledger.Ledger) -> None:
    """Refuse a ledger with fewer rows than 'slots check N' expects.

    Args:
        found: the context, whose arguments hold the words.
        book: the ledger.

    Raises:
        SystemExit: 1 for a ledger with fewer rows than the number.
        refuse: the exit 2 for words that are not one number of rows.
    """
    words = found.args.words
    # int() takes only ASCII digits here, and refuses more than 4300 of them.
    if len(words) > 1 or (
        words
        and not (words[0].isascii() and words[0].isdigit() and len(words[0]) < 1000)
    ):
        raise refuse("slots check takes one number of rows, or none")
    if words and int(words[0]) > len(book.slots):
        print(
            f"LEDGER TOO SHORT: the ledger has fewer rows ({len(book.slots)})"
            f" than the {words[0]} expected",
            file=sys.stderr,
        )
        raise SystemExit(1)
