"""Full clones in the workspace, and the account the cleaning gives under pressure.

The cleaner judges every directory of the workspace that is not a registered
worktree, a full clone of a repository the configuration does not name
included, by its branch's PRs; under pressure it says why it kept each one,
and what each kind of cleaning freed (pitboss#194).
"""

import pathlib
import unittest

from .. import deadscan, shapes
from . import cleanruns, cleanworld, fakes, test_autoclean_world, world, worldcopy

same = cleanworld.same
shows = test_autoclean_world.shows
FOREIGN = "other/elsewhere"
HIDDEN = "other/hidden"
NAMES = ("clone-open", "clone-merged", "clone-nopr", "clone-unread", "notes")
MERGED = {"state": "closed", "merged_at": "x"}
OPEN = {"state": "open"}


def foreign_clone(
    here: world.World, name: str, branch: str, slug: str = FOREIGN
) -> pathlib.Path:
    """A full clone of the world's origin, of a repository the configuration lacks.

    Args:
        here: the world.
        name: the directory's name.
        branch: the branch it is on.
        slug: the repository its ``origin`` names.

    Returns:
        The clone.
    """
    clone = cleanworld.clone_of(here.workspace, here, name)
    url = f"https://github.com/{slug}.git"
    origin = fakes.run_git(clone, "config", "remote.origin.url").strip()
    for key, value in (("remote.origin.url", url), (f"url.{origin}.insteadOf", url)):
        fakes.run_git(clone, "config", key, value)
    fakes.run_git(clone, "checkout", "-qb", branch)
    fakes.commit_file(clone, branch)  # a tip that is not in the base branch
    fakes.push(clone)
    return clone


def built_scene() -> worldcopy.Made:
    """Build the world of ``scene``: the clones and the notes, 99 hours old.

    Returns:
        The world, and no directory outside its workspace.
    """
    here = world.make_world()
    for name in ("clone-open", "clone-merged", "clone-nopr"):
        foreign_clone(here, name, name)
    foreign_clone(here, "clone-unread", "clone-unread", HIDDEN)
    (here.workspace / "notes").mkdir()
    fakes.write(here.workspace / "notes/file", "x")
    pulls = [
        test_autoclean_world.pull("clone-open", OPEN),
        test_autoclean_world.pull("clone-merged", MERGED),
    ]
    here.bodies[fakes.page(f"repos/{FOREIGN}/pulls?state=all")] = pulls
    for name in NAMES:
        test_autoclean_world.touch_all(here.workspace / name, 99)
    return here, []


scene_template = worldcopy.cached(built_scene)


def scene(percent: str) -> world.World:
    """A copy of a world with full clones of a repository the configuration lacks.

    ``clone-open``'s branch has an open PR, ``clone-merged``'s a merged one,
    ``clone-nopr``'s none; ``clone-unread`` is a clone of a repository whose
    PRs cannot be read, and ``notes`` is no checkout.

    Args:
        percent: the TOML number of ``pressure_percent``.

    Returns:
        The world; everything in the workspace is 99 hours old.
    """
    here, _ = worldcopy.copy_of(scene_template())
    settings = f"min_free_gib = 0\ntmp_roots = []\npressure_percent = {percent}\n"
    cleanworld.rewrite(here, settings)
    return here


class TestClonesUnderPressure(unittest.TestCase):
    """Under pressure a clone is judged by its branch, whatever its repository."""

    def test_a_clone_with_an_open_pr_is_kept_and_a_merged_one_removed(self) -> None:
        """The negative test: the open branch stays, the merged and the PR-less go."""
        here = scene("0.001")
        out = test_autoclean_world.swept(here, "sweep")
        root = here.workspace
        same(cleanruns.present(here, NAMES), [True, False, False, True, True])
        shows(
            out,
            [
                "clean: DISK OVER 0.001%",
                f"REMOVED PATH {root}/clone-merged",
                "(its PR merged)",
                f"REMOVED PATH {root}/clone-nopr",
                "(disk pressure: it has no open PR)",
            ],
        )

    def test_each_directory_kept_is_named_with_why(self) -> None:
        """One line each: an open PR, PRs that cannot be read, no checkout."""
        here = scene("0.001")
        out = test_autoclean_world.swept(here, "sweep")
        root = here.workspace
        shows(
            out,
            [
                f"clean: kept {root}/clone-open (its branch has an open PR)",
                f"clean: kept {root}/clone-unread"
                f" (the PRs of {HIDDEN} could not be read)",
                f"clean: kept {root}/notes (not a git checkout)",
            ],
        )

    def test_a_checkout_git_cannot_read_that_changed_lately_is_kept(self) -> None:
        """A broken clone inside the idle hours is held, with the reason."""
        here = scene("0.001")
        broken = here.workspace / "clone-broken"
        (broken / ".git").mkdir(parents=True)
        (broken / ".git/file").write_text("x")
        test_autoclean_world.touch_all(broken, 0)
        out = test_autoclean_world.swept(here, "sweep")
        names = [*NAMES, broken.name]
        same(out.count("clone-broken"), 3)
        same(cleanruns.present(here, names), [True, False, False, True, True, True])
        shows(out, [f"clean: kept {broken} (changed within the idle hours)"])

    def test_with_room_on_the_disk_a_merged_clone_goes_and_nothing_is_said(
        self,
    ) -> None:
        """No pressure: the merged clone goes; the no-PR one stays, no kept lines."""
        here = scene("99.9")
        out = test_autoclean_world.swept(here, "sweep")
        same(cleanruns.present(here, NAMES), [True, False, True, True, True])
        same("clean: kept" in out, False)
        same("by kind" in out, False)


LIVE = shapes.Outcome(branch="live", still_open=True, merged=False)


def why(slug: str, branch: str) -> str:
    """Why a checkout that is not dead is kept.

    Args:
        slug: its repository (``o/r`` has an open PR on ``live``).
        branch: its branch.

    Returns:
        The reason.
    """
    look = cleanworld.look_in(fakes.directory())
    path = pathlib.Path("/w/x")
    each = deadscan.Checkout(path=path, branch=branch, slug=slug, common=path)
    return deadscan.explain_keeping(look, {"o/r": {"live": LIVE}}, each)


class TestExplaining(unittest.TestCase):
    """The reason given for keeping a checkout that is not dead."""

    def test_a_checkout_that_cannot_be_judged_says_why(self) -> None:
        """No remote origin, and PRs that cannot be read."""
        same(why("", "b"), "it has no remote origin to ask about its PRs")
        same(why("p/q", "b"), "the PRs of p/q could not be read")

    def test_a_persistent_checkout_says_so(self) -> None:
        """Detached, or on the base branch."""
        same(why("o/r", ""), "detached: a persistent checkout")
        same(why("o/r", "main"), "on the base branch: a persistent checkout")

    def test_a_branch_says_what_became_of_its_pr(self) -> None:
        """An open PR; or none that merged or closed."""
        same(why("o/r", "live"), "its branch has an open PR")
        same(why("o/r", "other"), "its branch is not merged or closed")


class TestAccount(unittest.TestCase):
    """Under pressure the cleaning says what each kind freed and what it left."""

    def test_a_sweep_says_the_bytes_freed_by_each_kind(self) -> None:
        """The line names the four kinds; a shortfall is said."""
        out = test_autoclean_world.swept(scene("0.001"), "sweep")
        shows(
            out,
            [
                "clean: freed by kind: worktrees ",
                ", checkouts ",
                ", test tempdirs ",
                ", package caches ",
                " short of the ",
                " needed to get under 0.001%",
            ],
        )
