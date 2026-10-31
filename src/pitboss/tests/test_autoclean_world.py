"""End-to-end tests of the automatic cleaning: a sweep first, and ``clean``."""

import os
import pathlib
import unittest
from typing import AbstractSet, Mapping, Sequence

from . import cleanworld, fakes, world

same = cleanworld.same
AFTER = ("--now", world.FUTURE)
HOUR = 3600
EVERYTHING = {
    "merged-work",
    "quiet-work",
    "open-work",
    "running-work",
    "quiet-clone",
    "pip",
    "young-tmp",
    "old-tmp",
    "keep-me",
}
NORMAL = EVERYTHING - {"merged-work", "old-tmp"}
AGGRESSIVE = {"open-work", "running-work", "keep-me"}


def touch_all(top: pathlib.Path, hours_ago: float) -> None:
    """Make everything under a path last changed some hours before the test's now.

    Args:
        top: the path.
        hours_ago: how long before.
    """
    stamp = world.START.timestamp() - hours_ago * HOUR
    for place, _, files in os.walk(top):
        for name in files:
            os.utime(os.path.join(place, name), (stamp, stamp))
        os.utime(place, (stamp, stamp))


def tmp_of(here: world.World) -> pathlib.Path:
    """The scene's tempdir root.

    Args:
        here: the world.

    Returns:
        The path.
    """
    return here.workspace.parent / f"{here.workspace.name}-tmp"


def places(here: world.World) -> Mapping[str, pathlib.Path]:
    """The scene's paths, by name.

    Args:
        here: the world.

    Returns:
        The paths.
    """
    top, tmp = here.workspace, tmp_of(here)
    return {
        **{name: top / name for name in EVERYTHING if name.endswith(("work", "clone"))},
        "pip": top / "home/.cache/pip",
        "young-tmp": tmp / "tmpAAAAAAAA",
        "old-tmp": tmp / "tmpBBBBBBBB",
        "keep-me": tmp / "keep-me",
    }


def remaining(here: world.World) -> AbstractSet[str]:
    """Which of the scene's paths are still on disk.

    Args:
        here: the world.

    Returns:
        Their names.
    """
    return {name for name, path in places(here).items() if path.exists()}


def scene(percent: str, extra: str = "") -> world.World:
    """A world with a finished worktree, one with no PR, one with an open PR and more.

    Args:
        percent: the TOML number of ``pressure_percent``.
        extra: more settings for ``[clean]``.

    Returns:
        The world; ``merged-work`` is finished, ``quiet-work`` has no PR,
        ``open-work`` an open one, ``running-work`` was changed within the idle
        hours; ``tmp`` holds a tempdir 2 hours old and one 50 hours old, and the
        home holds a pip cache.
    """
    here = world.make_world()
    for name in ("quiet-work", "open-work", "running-work"):
        path = fakes.add_worktree(here.clone, name)
        fakes.commit_file(path, name)
        fakes.push(path)
    done = {"state": "closed", "merged_at": "x"}
    here.bodies[world.project_page("pulls?state=all")] = [
        {"head": {"ref": "merged-work"}, **done},
        {"head": {"ref": "open-work"}, "state": "open"},
    ]
    cleanworld.library_clone(here, "quiet-clone")
    tmp = tmp_of(here)
    files = {
        tmp / "tmpAAAAAAAA/file": "young",
        tmp / "tmpBBBBBBBB/file": "old",
        tmp / "keep-me/file": "not a tempdir",
        here.workspace / "home/.cache/pip/wheel": "w",
    }
    for path, text in files.items():
        fakes.write(path, text)
    settings = (
        f'min_free_gib = 0\ntmp_roots = ["{tmp}"]\npressure_percent = {percent}\n'
    )
    cleanworld.rewrite(here, settings + extra)
    for name, path in places(here).items():
        touch_all(path, 0.5 if name == "running-work" else 99)
    touch_all(places(here)["young-tmp"], 2)
    touch_all(places(here)["old-tmp"], 50)
    touch_all(here.workspace / "home", 99)
    return here


def swept(here: world.World, command: str, *arguments: str) -> str:
    """Run a command of the world at the test's now.

    Args:
        here: the world.
        command: the command.
        *arguments: its arguments after the config.

    Returns:
        What it printed.
    """
    return world.again(here, command, *arguments, *AFTER).out


def shows(out: str, pieces: Sequence[str]) -> None:
    """Assert that the output holds every piece.

    Args:
        out: the output.
        pieces: what it should hold.
    """
    same(cleanworld.absent(out, pieces), [])


class TestSweepCleansFirst(unittest.TestCase):
    """A sweep cleans before it reports, with no prompt and no dry run."""

    def test_below_the_pressure_only_the_finished_and_the_old_go(self) -> None:
        """Merged worktree and the 50 hour tempdir go; the rest stays."""
        here = scene("99.9")
        out = swept(here, "sweep")
        same(remaining(here), NORMAL)
        shows(
            out,
            [
                "clean: disk under 99.9% used",
                f"REMOVED WORKTREE {here.workspace}/merged-work (its PR merged)",
                f"REMOVED PATH {tmp_of(here)}/tmpBBBBBBBB",
                "test tempdir untouched for 24 hours",
                "clean: 1 paths removed,",
                "never touched: a worktree with an open PR, a running worker's",
            ],
        )

    def test_the_cleaning_is_the_first_thing_a_sweep_prints(self) -> None:
        """The clean section comes before the stragglers and the rest."""
        out = swept(scene("99.9"), "sweep")
        same(out.index("clean: disk") < out.index("stragglers:"), True)

    def test_over_the_pressure_everything_not_in_use_goes(self) -> None:
        """Over the limit the no-PR worktree and clone, the young tempdir and
        the cache go; the open PR's worktree and the running worker stay."""
        here = scene("0.001")
        out = swept(here, "sweep")
        same(remaining(here), AGGRESSIVE)
        shows(
            out,
            [
                "clean: DISK OVER 0.001%",
                "(disk pressure: it has no open PR)",
                f"REMOVED PATH {here.workspace}/quiet-clone",
                "(disk pressure: its repository has no open PR)",
                f"REMOVED PATH {tmp_of(here)}/tmpAAAAAAAA",
                f"REMOVED PATH {here.workspace}/home/.cache/pip",
                "package cache, regenerates",
            ],
        )

    def test_over_the_pressure_the_output_says_what_it_never_touches(self) -> None:
        """The open PR's worktree is named, the running worker is kept with its reason."""
        here = scene("0.001")
        out = swept(here, "sweep")
        shows(
            out,
            [
                f"clean: kept {here.workspace}/open-work [open-work] (open PR)",
                f"KEPT WORKTREE {here.workspace}/running-work (changed within",
                "never touched: a worktree with an open PR",
            ],
        )

    def test_list_mode_still_cleans_tempdirs_but_lists_worktrees(self) -> None:
        """Under ``worktrees = "list"`` the worktrees are only listed."""
        here = scene("99.9", 'worktrees = "list"\n')
        out = swept(here, "sweep")
        same(remaining(here), EVERYTHING - {"old-tmp"})
        same("STALE WORKTREE" in out, True)


class TestCleanCommand(unittest.TestCase):
    """``pitboss clean`` is the cleaning on its own."""

    def test_it_removes_by_default(self) -> None:
        """No flag is needed to remove."""
        here = scene("99.9")
        out = swept(here, "clean")
        same(remaining(here), NORMAL)
        same("freed; disk free" in out, True)

    def test_a_dry_run_removes_nothing(self) -> None:
        """``--dry-run`` lists what would go and changes nothing."""
        here = scene("0.001")
        out = swept(here, "clean", "--dry-run")
        same(remaining(here), EVERYTHING)
        shows(out, ["(dry run", "would be freed", "REMOVED PATH"])
