"""The keys of ``[sync]``."""

import pathlib
import tomllib
import unittest
from typing import Sequence

from .. import syncconfig
from . import cleanworld

CHECKOUT = pathlib.Path("/c")
REFUSED = (
    ('repository = "one"', "repository must be owner/name"),
    ('directory = "../out"', "directory must stay inside"),
    ('directory = "/abs"', "directory must stay inside"),
    ('paths = "x"', "paths must be a list"),
    ('paths = ["rel"]', "paths must be absolute"),
    ('checkout = "rel"', "checkout must be absolute"),
)


def parse_sync(text: str) -> syncconfig.Sync | None:
    """Read a configuration.

    Args:
        text: the TOML.

    Returns:
        The settings.
    """
    return syncconfig.from_document(tomllib.loads(text), CHECKOUT)


def fields(text: str) -> Sequence[object]:
    """Every setting of a configuration's table.

    Args:
        text: the TOML.

    Returns:
        The repository, directory, paths, checkout and url.
    """
    found = parse_sync(text)
    assert found is not None
    return (found.repository, found.directory, found.paths, found.checkout, found.url)


def refusal(text: str) -> str:
    """The message of the error a table gives.

    Args:
        text: the TOML under the header.

    Returns:
        The message.
    """
    try:
        parse_sync(f"[sync]\n{text}")
    except ValueError as error:
        return str(error)
    return ""  # pragma: no cover


class TestConfig(unittest.TestCase):
    """The table, its defaults and its refusals."""

    def test_no_table_means_no_sync(self) -> None:
        """A configuration without the table syncs nothing."""
        cleanworld.same(parse_sync(""), None)

    def test_the_defaults(self) -> None:
        """An empty table is the owner's notes repository and directory."""
        cleanworld.same(
            fields("[sync]"),
            (
                "moshez/claude-jsonl",
                "notes-current",
                (),
                CHECKOUT,
                "https://github.com/moshez/claude-jsonl.git",
            ),
        )

    def test_the_keys_are_read(self) -> None:
        """Every key can be set."""
        text = (
            '[sync]\nrepository = "o/r"\ndirectory = "a/b"\npaths = ["/x/y"]\n'
            'checkout = "/k"\nurl = "/bare"\n'
        )
        cleanworld.same(
            fields(text),
            ("o/r", "a/b", (pathlib.Path("/x/y"),), pathlib.Path("/k"), "/bare"),
        )

    def test_a_table_that_is_not_a_table_is_refused(self) -> None:
        """``sync = 1`` is an error."""
        with self.assertRaises(ValueError):
            parse_sync("sync = 1")

    def test_bad_values_are_refused(self) -> None:
        """Each bad value is refused with its key named."""
        for text, message in REFUSED:
            with self.subTest(text):
                cleanworld.same(message in refusal(text), True)
