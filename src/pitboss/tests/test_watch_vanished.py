"""A tasks directory is full of files that come and go (pitboss#441)."""

import argparse
import dataclasses
import datetime
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import cleanconfig, config, configfile, ghapi, watchrun
from . import fakes, watchworld, world
from .autocleanworld import plain
from .test_slots_watch import worker

TAKES = watchworld.TAKES.format("owner/project#7") + "\n"
RUNNING = {"a1": worker("a1", 7)}
GONE = ["a0.output", "a1.output"]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Seen:
    """The context of one round, as the watcher reads it.

    Attributes:
        settings: the configuration.
        args: the arguments of the round.
        now: the time of the round.
        github: the API, which a round does not call.
        clean: the cleaning configuration, which a round does not read.
    """

    settings: config.Config
    args: argparse.Namespace
    now: datetime.datetime
    github: ghapi.GitHub
    clean: cleanconfig.Clean


def round_of(here: world.World, names: Sequence[str]) -> watchrun.Report:
    """One round of the watcher over a lister that returns these names.

    Args:
        here: the world.
        names: the file names the lister returns, present or not.

    Returns:
        What the round found.
    """
    found = Seen(
        settings=configfile.load(start=here.workspace, name=here.config),
        args=argparse.Namespace(process_start=watchworld.PROCESS),
        now=datetime.datetime.fromisoformat(watchworld.NOW),
        github=fakes.github({}),
        clean=plain(),
    )
    return watchrun.once(
        lambda: found,
        lambda *_: "",
        0,
        lambda folder: [folder / each for each in names],
    )


def left_after(here: world.World) -> tuple[str, Sequence[str]]:
    """What a watch of one round printed, and the agents it left in the ledger.

    Args:
        here: the world.

    Returns:
        The output and the agents.
    """
    return watchworld.watch(here).out, watchworld.held(here)


def beside(files: Mapping[str, Sequence[Mapping[str, object]]]) -> world.World:
    """A watched world with these transcripts and a link to nothing beside them.

    Args:
        files: each agent id and the records of its transcript.

    Returns:
        The world.
    """
    here = watchworld.planted(files)
    (here.workspace / "tasks" / "a2.output").symlink_to("nowhere.jsonl")
    return here


class TestVanished(unittest.TestCase):
    """What the watcher does with a name that is no transcript."""

    def test_a_file_listed_and_gone_leaves_the_agents_row_and_no_failure(
        self,
    ) -> None:
        """The lister names a file the reader cannot open; the round goes on."""
        said = round_of(watchworld.planted(RUNNING), GONE).said
        assert_that(said, equal_to([watchworld.TAKES.format("owner/project#7")]))

    def test_a_dangling_link_and_a_name_that_is_not_an_agent_are_ignored(
        self,
    ) -> None:
        """A link to nothing, and a background command's output, beside a transcript."""
        others = beside({"a1": worker("a1", 7), "b7a777en3": worker("b7", 8)})
        assert_that(left_after(others), equal_to((TAKES, ["a1"])))
