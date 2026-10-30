"""End-to-end tests of ``clean-container``: the removal and its refusals."""

import dataclasses
import pathlib
import unittest

from . import cleanruns, cleanworld, fakes

SAFE = (
    "merged-work",
    "base-work",
    "lib",
    "other-work",
    "old",
    "untracked",
    "dangling",
)
KEPT = ("holder", "dirty", "broken", "deep", "branchy", "stashy", "unreadable")
LEFT_SCRATCH = ("fresh", "marked", "shared", "holder2", "link", "outer")
LEFT_WORKSPACE = ("pinned-work", "open-work", "project", "unreadable")
SUMMARY = [" freed; 7 kept", "disk: "]


class TestRemoval(unittest.TestCase):
    """The sweep that frees the space."""

    def test_removes_only_the_safe_list_in_parts(self) -> None:
        """Safe paths go, ``rm`` gets at most batch paths, the rest is untouched."""
        here, root = cleanworld.full_world()
        before = cleanruns.listed(here)
        result = cleanruns.clean(here, "--no-dry-run", "--batch", "2")
        removed = cleanworld.lines_of(result.out, "REMOVED PATH")
        calls = [call for call in here.calls if call[0] == "rm"]
        worktrees = fakes.run_git(here.clone, "worktree", "list")
        gone = [pathlib.Path(path).exists() for path in removed]
        cleanworld.same((removed, gone), (before, [False] * len(removed)))
        sizes = [len(call) - 4 for call in calls]
        cleanworld.same((max(sizes), len(calls)), (2, (len(removed) + 1) // 2))
        cleanworld.same(all("--one-file-system" in call for call in calls), True)
        cleanworld.same("merged-work" in worktrees, False)
        left = [
            *(root / name for name in (*LEFT_SCRATCH, *KEPT[:6])),
            *(here.workspace / name for name in LEFT_WORKSPACE),
            root.parent / "locked/entry",
        ]
        present = [each.exists() or each.is_symlink() for each in left]
        cleanworld.same(present, [True] * len(left))
        cleanworld.same(cleanworld.absent(result.out, SUMMARY), [])

    def test_approved_list_limits_the_removal(self) -> None:
        """Only approved safe paths go; an unsafe, unknown or outside one is refused."""
        scene = cleanworld.full_world()
        here, root = scene.here, scene.root
        approved = fakes.directory() / "approved"
        merged = here.workspace / "merged-work"
        unknown = here.workspace / "unknown"
        outside = fakes.directory() / "outside"
        outside.mkdir()
        holder = root / "holder"
        approved.write_text(f"{merged}\n{holder}\n{unknown}\n{outside}\n")
        out = cleanruns.clean(here, "--no-dry-run", "--approved", str(approved)).out
        refused = sorted(map(str, (holder, unknown, outside)))
        cleanworld.same(cleanworld.lines_of(out, "REMOVED PATH"), [str(merged)])
        cleanworld.same(cleanworld.lines_of(out, "COULD NOT REMOVE PATH"), refused)
        cleanworld.same(((root / "old").exists(), outside.exists()), (True, True))

    def test_an_agent_that_starts_after_the_listing_is_left_alone(self) -> None:
        """The path is looked at again just before its rm: a new file stops it."""
        scene = cleanworld.full_world()
        root = scene.root
        agent = root / "old/agent.log"
        runner = cleanworld.Starting(inner=scene.here.processes, path=agent)
        busy = dataclasses.replace(scene.here, processes=runner)
        result = cleanruns.clean(busy, "--no-dry-run", "--batch", "1")
        refused = cleanworld.lines_of(result.out, "COULD NOT REMOVE PATH")
        cleanworld.same((refused, (root / "old").exists()), ([str(root / "old")], True))
        cleanworld.same("changed within the idle hours" in result.out, True)
        cleanworld.same((root / "untracked").exists(), False)
