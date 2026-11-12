"""A .md or .rst file a script writes is not hand-written.

The keyword is generated-markup, T433.
"""

import argparse
import pathlib
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import generatedfiles, plancheck_commands
from . import fakes

STAT = "1\t1\treports/r.md\x002\t0\tdocs/a.md\x003\t3\tsrc/x.py\x00"
PATCH = (
    "diff --git a/reports/r.md b/reports/r.md\n@@ -1 +1 @@\n-1\n+2\n"
    "diff --git a/docs/a.md b/docs/a.md\n@@ -0,0 +1,2 @@\n+a\n+b\n"
    "diff --git a/src/x.py b/src/x.py\n@@ -1 +1 @@\n-x\n+y\n"
)


def named(paths: Mapping[str, Sequence[str]]):  # type: ignore[no-untyped-def]
    """A ``git grep -l -F`` that lists the files naming a path.

    Args:
        paths: by path, the files that name it.

    Returns:
        The function.
    """
    return lambda path: paths.get(path, [])


class TestGenerated(unittest.TestCase):
    """What a script names, and what is left of a diff."""

    def test_t433_a_script_that_names_the_file_makes_it_generated(self) -> None:
        """Not itself, and not another .md or .rst file."""
        generated = generatedfiles.scripted(
            named(
                {
                    "reports/r.md": ["scripts/r.py", "reports/r.md"],
                    "docs/a.md": ["docs/b.md", "docs/c.RST"],
                }
            )
        )
        assert_that(generated("reports/r.md"), equal_to(True))
        assert_that(generated("docs/a.md"), equal_to(False))
        assert_that(generated("nowhere.md"), equal_to(False))

    def test_t433_the_numstat_and_the_patch_lose_only_generated_markup(self) -> None:
        """The report goes; the hand-written .md and the .py stay."""
        generated = generatedfiles.scripted(named({"reports/r.md": ["scripts/r.py"]}))
        stat, patch = generatedfiles.handwritten(STAT, PATCH, generated)
        assert_that(stat, equal_to("2\t0\tdocs/a.md\x003\t3\tsrc/x.py\x00"))
        assert_that("reports/r.md" in patch, equal_to(False))
        assert_that("docs/a.md" in patch and "src/x.py" in patch, equal_to(True))

    def test_t433_a_patch_that_starts_with_no_header_is_kept(self) -> None:
        """Text before the first section has no name."""
        stat, patch = generatedfiles.handwritten("", "free text\n", lambda path: True)
        assert_that((stat, patch), equal_to(("", "free text\n")))

    def test_t433_the_head_tree_is_grepped_for_the_path(self) -> None:
        """The runner's ``git grep`` output lists the files that name it."""
        listed = fakes.Output(stdout="tools/gen.py\n")
        args = argparse.Namespace(safe_run=lambda words: listed)
        scripted = plancheck_commands.scripted_in(args, pathlib.Path("."))
        assert_that(scripted("reports/r.md"), equal_to(True))
