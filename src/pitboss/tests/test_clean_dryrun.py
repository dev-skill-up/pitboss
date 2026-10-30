"""End-to-end tests of the dry run of ``clean-container``: the list to approve."""

import os
import pathlib
import unittest

from . import cleanruns, cleanworld, fakes
from .test_clean_commands import KEPT, SAFE
from .test_local import age

DRY = (
    "(its PR merged) (dry run",
    "(its PR was closed) (dry run",
    "(its tip is in the base branch) (dry run",
    "1 commits on no remote branch in",
    "2 commits on no remote branch in",
    "1 changed tracked files in",
    "fetch failed in",
    "would be freed; 7 kept",
)


class TestDryRun(unittest.TestCase):
    """The list the orchestrator approves."""

    def test_dry_run_lists_and_removes_nothing(self) -> None:
        """Dead safe paths, with sizes and reasons, and the kept ones apart."""
        here, root = cleanworld.full_world()[:2]
        result = cleanruns.clean(here)
        removed = cleanworld.lines_of(result.out, "REMOVED PATH")
        kept = cleanworld.lines_of(result.out, "KEPT PATH")
        untouched = all(pathlib.Path(path).exists() for path in removed)
        found = (
            cleanruns.names(removed),
            cleanruns.names(kept),
            untouched,
            cleanworld.absent(result.out, DRY),
        )
        cleanworld.same(found, (sorted(SAFE), sorted(KEPT), True, []))
        cleanworld.same(f"git cannot read {root}/broken" in result.out, True)
        unreadable = f"git cannot read {here.workspace}/unreadable"
        cleanworld.same(unreadable in result.out, True)

    def test_a_marked_scratch_directory_keeps_everything_in_it(self) -> None:
        """A marker on the directory above an entry makes the entry live."""
        here = (scene := cleanworld.full_world()).here
        root = scene.root
        cleanworld.mark_live(root)
        age(root.parent)
        found = [
            name for name in cleanruns.names(cleanruns.listed(here)) if name in SAFE
        ]
        cleanworld.same(found, ["base-work", "lib", "merged-work", "other-work"])

    def test_a_link_in_the_workspace_is_not_a_checkout(self) -> None:
        """A link is not judged by what it points at, nor sized through."""
        here = cleanworld.full_world().here
        elsewhere = cleanworld.clone_of(fakes.directory(), here, "target")
        fakes.run_git(elsewhere, "checkout", "-qb", "in-base-work")
        fakes.write(elsewhere / "big", "x" * 5_000_000)
        os.symlink(elsewhere, here.workspace / "linked")
        age(elsewhere)
        cleanworld.same("linked" in cleanruns.clean(here).out, False)
