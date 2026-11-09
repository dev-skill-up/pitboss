"""Tests for the environment of the nox sessions (keyword: nox-home, pitboss#364)."""

import os
import pathlib
import subprocess
import tempfile
import unittest
from collections.abc import Mapping

from hamcrest import assert_that, equal_to

from .. import noxenv

GITCONFIG = "[user]\n\tname = Real Person\n\temail = real@example.org\n"


def user_name(
    directory: str, environ: Mapping[str, str]
) -> subprocess.CompletedProcess[str]:
    """Ask real git for ``user.name`` outside any repository.

    Args:
        directory: where git runs.
        environ: the environment it gets.

    Returns:
        The finished process.
    """
    return subprocess.run(
        ["git", "config", "user.name"],
        cwd=directory,
        env=environ,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )


class TestIsolatedEnvironment(unittest.TestCase):
    """The child sees no global git config and no identity; this process, all."""

    def setUp(self) -> None:
        """Make a home that has a git identity, and an environment that has more."""
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.top = str(pathlib.Path(holder.name).resolve())
        self.real = os.path.join(self.top, "real")
        os.mkdir(self.real)
        self.gitconfig = pathlib.Path(self.real, ".gitconfig")
        self.gitconfig.write_text(GITCONFIG)
        self.environ = {
            "HOME": self.real,
            "PATH": os.environ["PATH"],
            "GIT_AUTHOR_NAME": "Author",
            "GIT_COMMITTER_EMAIL": "committer@example.org",
            "EMAIL": "mail@example.org",
        }

    def test_git_finds_the_identity_here_and_none_in_the_child(self) -> None:
        """The control reads the real config; the child gets nothing and exit 1."""
        assert_that(user_name(self.top, self.environ).stdout, equal_to("Real Person\n"))
        with noxenv.throwaway_home() as home:
            done = user_name(self.top, noxenv.isolated(self.environ, home))
        assert_that((done.returncode, done.stdout), equal_to((1, "")))

    def test_the_identity_variables_are_left_out_and_the_others_kept(self) -> None:
        """A variable that is not an identity goes through, the identity ones not."""
        with noxenv.throwaway_home() as home:
            found = noxenv.isolated({**self.environ, "KEPT": "yes"}, home)
        assert_that(found["KEPT"], equal_to("yes"))
        assert_that([each for each in noxenv.IDENTITY if each in found], equal_to([]))

    def test_home_and_the_git_config_are_in_the_throwaway_directory(self) -> None:
        """HOME, GIT_CONFIG_GLOBAL and XDG_CONFIG_HOME are inside it."""
        with noxenv.throwaway_home() as home:
            found = noxenv.isolated(self.environ, home)
            assert_that(found["HOME"], equal_to(home))
            assert_that(
                found["GIT_CONFIG_GLOBAL"], equal_to(os.path.join(home, "gitconfig"))
            )
            assert_that(
                found["XDG_CONFIG_HOME"].startswith(home + os.sep), equal_to(True)
            )
            assert_that(os.path.isdir(home), equal_to(True))
        assert_that(os.path.exists(home), equal_to(False))

    def test_this_process_and_the_real_home_are_not_changed(self) -> None:
        """The mapping given, the real ~/.gitconfig and the real home stay."""
        before = dict(self.environ)
        with noxenv.throwaway_home() as home:
            noxenv.isolated(self.environ, home)
        assert_that(self.environ, equal_to(before))
        assert_that(self.gitconfig.read_text(), equal_to(GITCONFIG))
        assert_that(sorted(os.listdir(self.real)), equal_to([".gitconfig"]))

    def test_the_caches_stay_where_they_were(self) -> None:
        """pip and virtualenv keep their caches: the real ones, or the set ones."""
        with noxenv.throwaway_home() as home:
            found = noxenv.isolated(self.environ, home)
            set_one = noxenv.isolated(
                {**self.environ, "XDG_CACHE_HOME": "/elsewhere"}, home
            )
        assert_that(
            found["XDG_CACHE_HOME"], equal_to(os.path.join(self.real, ".cache"))
        )
        assert_that(
            found["XDG_DATA_HOME"], equal_to(os.path.join(self.real, ".local/share"))
        )
        assert_that(set_one["XDG_CACHE_HOME"], equal_to("/elsewhere"))

    def test_with_no_home_at_all_no_cache_is_invented(self) -> None:
        """The nearest input: nothing to keep, so the variables are not set."""
        with noxenv.throwaway_home() as home:
            found = noxenv.isolated({"PATH": "/bin"}, home)
        assert_that(
            "XDG_CACHE_HOME" in found or "XDG_DATA_HOME" in found, equal_to(False)
        )
