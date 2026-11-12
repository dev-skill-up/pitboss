"""A Plan whose diff adds a configuration key lists it in the example (pitboss#365)."""

import pathlib
import unittest

from hamcrest import assert_that, contains_string, empty, has_length

from .. import configkeys
from . import fakes, repositories

LOADER = "src/pitboss/exampleconfig.py"
OLD = 'def load(table):\n    return table.get("known", 1)\n'
EXAMPLE = "[example]\nknown = 1\n"
IMPACT = (
    "## Plan\n\n1. Impact: `configsettle.find_or_say` is called by the new command.\n"
)


def patch_of(new: str) -> str:
    """The ``git diff -U0`` of a real repository whose loader becomes ``new``.

    Args:
        new: the loader's new text.

    Returns:
        The patch.
    """
    top = fakes.directory() / "repo"
    top.mkdir()
    repositories.run_git(top, "init", "-q")
    path = top / LOADER
    path.parent.mkdir(parents=True)
    path.write_text(OLD, encoding="utf-8")
    repositories.run_git(top, "add", "-A")
    repositories.run_git(
        top, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"
    )
    path.write_text(new, encoding="utf-8")
    return repositories.run_git(top, "diff", "-U0", "--no-color", "--no-renames")


class TestConfigExample(unittest.TestCase):
    """The diff without the example entry is refused naming it; with it, it passes."""

    def test_t365_a_new_key_the_example_does_not_list_is_refused(self) -> None:
        """The new key is named."""
        patch = patch_of(OLD + '    return table.get("fresh", 2)\n')
        found = configkeys.findings("", patch, EXAMPLE)
        assert_that(found, has_length(1))
        assert_that(found[0], contains_string("`fresh`"))

    def test_t365_the_same_diff_with_the_example_entry_passes(self) -> None:
        """The control: the example lists the key with its default."""
        patch = patch_of(OLD + '    return table.get("fresh", 2)\n')
        assert_that(configkeys.findings("", patch, EXAMPLE + "fresh = 2\n"), empty())

    def test_t365_a_new_way_to_find_the_configuration_needs_an_impact_row(
        self,
    ) -> None:
        """A new call of find_or_say without a row naming it is refused."""
        patch = patch_of(OLD + "    configsettle.find_or_say(args)\n")
        found = configkeys.findings("## Plan\n\n1. A row.\n", patch, EXAMPLE)
        assert_that(found, has_length(1))
        assert_that(found[0], contains_string("no row for `find_or_say`"))
        assert_that(configkeys.findings(IMPACT, patch, EXAMPLE), empty())
