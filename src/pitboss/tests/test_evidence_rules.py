"""The skill says where evidence comes from (pitboss#117, Done-when 3)."""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .test_inventory_landing import REFERENCES, ROOT

SKILL = ROOT / REFERENCES
FILES = ("rules.md", "adversarial-review.md")
PHRASES = (
    "Evidence line",
    "come only from `pitboss expand`",
    "never retype or abbreviate output",
    "$ cat < path",
)


def words(text: str) -> str:
    """A text with each run of white space made one space.

    Args:
        text: the text.

    Returns:
        The text, so a phrase is found whichever way a line is wrapped.
    """
    return " ".join(text.split())


def missing(name: str, text: str) -> Sequence[str]:
    """The phrases a file of the skill does not hold.

    Args:
        name: the file's name.
        text: its text.

    Returns:
        A finding for each phrase missing, naming the file and the phrase.
    """
    return [f"{name}: no `{phrase}`" for phrase in PHRASES if phrase not in words(text)]


def read(name: str) -> str:
    """A file of the skill's references.

    Args:
        name: the file's name.

    Returns:
        Its text.
    """
    return (SKILL / name).read_text(encoding="utf-8")


class TestEvidenceRules(unittest.TestCase):
    """The worker rules and the review reference say where evidence comes from."""

    def test_the_skill_says_it(self) -> None:
        """Each file holds the Evidence line, its source and its file form."""
        found = [each for name in FILES for each in missing(name, read(name))]
        assert_that(found, equal_to([]))

    def test_each_phrase_is_needed(self) -> None:
        """Dropping a phrase from a file makes the check name that phrase."""
        for name in FILES:
            for phrase in PHRASES:
                with self.subTest(f"{name}: {phrase}"):
                    dropped = words(read(name)).replace(phrase, "")
                    found = missing(name, dropped)
                    assert_that(len(found), equal_to(1))
                    assert_that(found[0], contains_string(f"{name}: no `{phrase}`"))
