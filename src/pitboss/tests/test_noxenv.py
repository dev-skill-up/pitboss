"""Tests for the environment of the nox sessions (keyword: nox-home, pitboss#364)."""

import os
import pathlib
import subprocess
import tempfile
import unittest
from collections.abc import Mapping

from hamcrest import assert_that, equal_to

from .. import noxenv
from . import captured

GITCONFIG = "[user]\n\tname = Real Person\n\temail = real@example.org\n"


def real_home(case: unittest.TestCase) -> Mapping[str, str]:
    """An environment whose home has a git identity, and more identity variables.

    Args:
        case: the test, whose end removes the home.

    Returns:
        The environment.
    """
    real = pathlib.Path(case.enterContext(tempfile.TemporaryDirectory())).resolve()
    (real / ".gitconfig").write_text(GITCONFIG)
    return {
        "HOME": str(real),
        "PATH": os.environ["PATH"],
        "GIT_AUTHOR_NAME": "Author",
        "GIT_COMMITTER_EMAIL": "committer@example.org",
        "EMAIL": "mail@example.org",
    }


def isolated(environ: Mapping[str, str]) -> tuple[Mapping[str, str], str]:
    """The environment of a run, and its home, which is gone when this returns.

    Args:
        environ: the environment of the process.

    Returns:
        The isolated environment and the throwaway home.
    """
    with noxenv.throwaway_home() as home:
        return noxenv.isolated(environ, home), home


def git_user_name(
    environ: Mapping[str, str], where: str
) -> subprocess.CompletedProcess[str]:
    """Ask real git for ``user.name`` where no repository is.

    Args:
        environ: the environment it gets.
        where: the directory it runs in.

    Returns:
        The finished process, with its command, status and output.
    """
    return captured.run(
        ["git", "config", "user.name"], check=False, cwd=where, env=environ
    )


class TestIsolatedEnvironment(unittest.TestCase):
    """The child sees no global git config and no identity; this process, all."""

    def test_git_finds_the_identity_here_and_none_in_the_child(self) -> None:
        """The control reads the real config; the child gets nothing, exit 1."""
        environ = real_home(self)
        real = environ["HOME"]
        with noxenv.throwaway_home() as home:
            child = noxenv.isolated(environ, home)
            seen = git_user_name(child, real)
        control = git_user_name(environ, real)
        assert_that(
            (control.returncode, control.stdout),
            equal_to((0, "Real Person\n")),
            captured.described(control),
        )
        assert_that(
            (seen.returncode, seen.stdout),
            equal_to((1, "")),
            captured.described(seen),
        )

    def test_the_layout_of_the_child_environment(self) -> None:
        """Identity left out, others kept, config in the home, caches kept."""
        environ = {**real_home(self), "KEPT": "yes"}
        found, home = isolated(environ)
        real = environ["HOME"]
        expected = {
            "KEPT": "yes",
            "HOME": home,
            "GIT_CONFIG_GLOBAL": os.path.join(home, "gitconfig"),
            "XDG_CONFIG_HOME": os.path.join(home, "config"),
            "XDG_CACHE_HOME": os.path.join(real, ".cache"),
            "XDG_DATA_HOME": os.path.join(real, ".local/share"),
        }
        assert_that({key: found[key] for key in expected}, equal_to(expected))
        assert_that([key for key in noxenv.IDENTITY if key in found], equal_to([]))

    def test_the_home_is_removed_and_the_real_one_is_not_changed(self) -> None:
        """The mapping given, the real ~/.gitconfig and its home stay as they were."""
        environ = real_home(self)
        before = dict(environ)
        _, home = isolated(environ)
        real = pathlib.Path(environ["HOME"])
        assert_that(os.path.exists(home), equal_to(False))
        assert_that(environ, equal_to(before))
        assert_that(
            sorted(each.name for each in real.iterdir()), equal_to([".gitconfig"])
        )

    def test_a_cache_that_is_set_is_kept_and_none_is_invented(self) -> None:
        """The nearest inputs: a set XDG_CACHE_HOME stays; no home, no variable."""
        set_one, _ = isolated({**real_home(self), "XDG_CACHE_HOME": "/elsewhere"})
        none_set, _ = isolated({"PATH": "/bin"})
        assert_that(set_one["XDG_CACHE_HOME"], equal_to("/elsewhere"))
        assert_that(
            [key for key in none_set if key.endswith(("_CACHE_HOME", "_DATA_HOME"))],
            equal_to([]),
        )
