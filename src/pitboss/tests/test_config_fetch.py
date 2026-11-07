"""A configuration fetched by name in a fresh container (keyword: fetched-config)."""

import dataclasses
import pathlib
import unittest
from typing import Callable, Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import configfetch, syncconfig
from . import cleanworld, configcases, fakes, world

# not quire: a container of the sweep has /home/user/.claude/pitboss/quire.toml
NAME = "fresh-app"
ORIGIN = f"https://github.com/owner/{NAME}.git"
SOURCE = configfetch.source_path(NAME)
RUN = ["gh", "api", "-H", configfetch.RAW, SOURCE]
CLEAN_CONTAINER = ("clean-container", "--now", world.FUTURE, *cleanworld.NO_MARKER)
SEARCHED = FileNotFoundError(f"none of these exists: /work/{NAME}.toml")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Fresh:
    """A container with a checkout, an empty home and the config on GitHub.

    Attributes:
        here: the world, whose fake GitHub holds the project's configuration
            in the notes repository.
        top: the checkout, which holds no configuration.
        text: the configuration.
    """

    here: world.World
    top: pathlib.Path
    text: str


def make_fresh() -> Fresh:
    """Make a fresh container.

    Returns:
        The container.
    """
    here = configcases.cleaning()
    text = pathlib.Path(here.config).read_bytes().decode()
    here.bodies[SOURCE] = text
    return Fresh(here=here, top=configcases.checkout(NAME, ORIGIN), text=text)


def kept(box: Fresh) -> pathlib.Path:
    """Where the home keeps the fetched configuration of the project.

    Args:
        box: the container.

    Returns:
        The path.
    """
    return configfetch.cache_file(world.shell_env(box.here, None), NAME)


def run(box: Fresh, *words: str) -> world.Result:
    """Run ``pitboss`` in the checkout.

    Args:
        box: the container.
        *words: the arguments.

    Returns:
        What it did.
    """
    return world.invoke(box.here, *words, directory=box.top)


def stdout_of(processes: fakes.Processes) -> Callable[[Sequence[str]], str]:
    """What the fetch reads a command line with.

    Args:
        processes: what runs the command lines.

    Returns:
        A function that runs a command line and gives its standard output.
    """
    return lambda command: processes(command).stdout


def fetched(bodies: Mapping[str, object], env: Mapping[str, str]) -> pathlib.Path:
    """Fetch the project's configuration from a fake GitHub, after a search.

    Args:
        bodies: the fake GitHub's bodies.
        env: the environment.

    Returns:
        The kept copy.
    """
    processes = fakes.FakeProcesses(bodies=dict(bodies))
    return configfetch.fetch(stdout_of(processes), env, NAME, SEARCHED)


def failure(name: str, answers: Mapping[str, int]) -> str:
    """The message of the error a fetch raises, from a GitHub with no body.

    Args:
        name: the repository's name.
        answers: the exit status of each program that is not run (127: not found).

    Returns:
        The message.
    """
    env = {"HOME": str(fakes.directory())}
    read = stdout_of(fakes.FakeProcesses(bodies={}, answers=answers))
    return fakes.error_of(lambda: configfetch.fetch(read, env, name, SEARCHED))


class TestFreshContainer(unittest.TestCase):
    """A checkout whose origin names the repository and an empty home."""

    def test_clean_container_bare_finds_the_configuration_by_name(self) -> None:
        """It runs as it does with ``--config``, and fetches once."""
        box = make_fresh()
        before = kept(box).exists()
        bare = run(box, *CLEAN_CONTAINER)
        given = world.invoke(box.here, *CLEAN_CONTAINER, "--config", box.here.config)
        seen = [
            configcases.seen(box.here, each, "clean-container")
            for each in (bare, given)
        ]
        assert_that(seen[0], equal_to(seen[1]))
        after = (bare.code, box.here.calls.count(RUN), kept(box).read_text())
        assert_that((before, after), equal_to((False, (0, 1, box.text))))

    def test_a_file_of_the_checkout_is_not_fetched(self) -> None:
        """The search comes first: the project's own file makes no call."""
        box = make_fresh()
        target = box.top / ".claude" / "pitboss" / f"{NAME}.toml"
        configcases.copy_config(box.here, target)
        found = run(box, "slots", "check")
        assert_that((found.code, box.here.calls.count(RUN)), equal_to((0, 0)))

    def test_a_failed_fetch_uses_the_copy_kept_by_an_earlier_one(self) -> None:
        """The copy is used, and standard error says so."""
        box = make_fresh()
        run(box, *CLEAN_CONTAINER)
        del box.here.bodies[SOURCE]
        again = run(box, *CLEAN_CONTAINER)
        said = f"using the copy kept at {kept(box)}"
        assert_that((again.code, said in again.err), equal_to((0, True)))


class TestFetch(unittest.TestCase):
    """The fetch, called as the lookup calls it."""

    def test_the_source_is_where_sync_keeps_the_configurations(self) -> None:
        """The repository and directory are the defaults of ``[sync]``."""
        found = (configfetch.SOURCE_REPOSITORY, configfetch.SOURCE_DIRECTORY)
        sync = syncconfig.DEFAULT_REPOSITORY, f"{syncconfig.DEFAULT_DIRECTORY}/configs"
        assert_that(found, equal_to(sync))

    def test_the_copy_is_kept_where_the_cache_variable_says(self) -> None:
        """``XDG_CACHE_HOME`` before ``.cache`` of the home."""
        cache, home = fakes.directory(), fakes.directory()
        text = {SOURCE: "[project]\n"}
        variable = {"HOME": str(home), "XDG_CACHE_HOME": str(cache)}
        found = [fetched(text, variable), fetched(text, {"HOME": str(home)})]
        under = [cache, home / ".cache"]
        expected = [each / "pitboss" / "configs" / f"{NAME}.toml" for each in under]
        assert_that(found, equal_to(expected))

    def test_no_copy_and_no_file_says_where_it_looked_and_why(self) -> None:
        """The search's message, then the fetch's and what ``gh`` said."""
        said = failure(NAME, {})
        wanted = (str(SEARCHED), f"notes-current/configs/{NAME}.toml", "gh: not found")
        assert_that(all(each in said for each in wanted), equal_to(True))

    def test_a_missing_gh_is_said_and_a_bad_name_is_not_fetched(self) -> None:
        """``gh`` not installed; ``..``, a slash, a dot first and no name."""
        said = [failure(each, {"gh": 127}) for each in (NAME, "..", "a/b", ".x", "")]
        ends = ("gh is not installed", *(["is not a name to fetch"] * 4))
        assert_that([a.endswith(b) for a, b in zip(said, ends)], equal_to([True] * 5))
