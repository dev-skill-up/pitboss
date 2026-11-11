"""How many GitHub reads ``slots next`` makes (pitboss#453).

The per-item form read the access of every repository of the configuration, the
full form read each repository's pull requests more than once, and the ranking
read the blockers of every ticket, so the cost grew with the queue and not with
the five items shown.
"""

import pathlib
import re
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to, less_than

from .. import configfile, repoaccess, suggest, windowrun
from . import fakes, itemworld, ownerbodies, quietworld, rankworld, world
from .suggestions import with_more_tickets

REPOSITORIES = 35


def served(here: world.World, name: str) -> None:
    """Answer the lists of a repository of the owner that has no PR and no ticket.

    Args:
        here: the world.
        name: the repository's name under the owner.
    """
    prefix = f"repos/owner/{name}"
    lists = [
        ("pulls?state=open", []),
        ("actions/runs?event=merge_group", {"workflow_runs": []}),
        ("issues/comments", []),
        ("pulls?state=all", []),
        ("issues?state=open&labels=urgent", []),
        ("issues?state=all", []),
    ]
    here.bodies.update(fakes.bodies_under(prefix, lists))


def wide_world(count: int) -> world.World:
    """A configuration that names ``count`` more repositories, all listed.

    Args:
        count: how many.

    Returns:
        The world.
    """
    here = world.make_world()
    names = [f"r{number}" for number in range(count)]
    quoted = ", ".join(f'"{each}"' for each in ["lib", *names])
    quietworld.edit_config(here, 'repositories = ["lib"]', f"repositories = [{quoted}]")
    shared = 'repositories = ["project", "lib"]'  # as the real [runners] names its few
    quietworld.edit_config(here, "[runners]", f"[runners]\n{shared}")
    rows = [(f"owner/{each}", False) for each in names]
    here.bodies[ownerbodies.LISTING] = ownerbodies.listed(*rows)
    for each in names:
        served(here, each)
    return here


def paths_of(here: world.World) -> Sequence[str]:
    """The paths of the ``gh api`` calls a world has seen.

    Args:
        here: the world.

    Returns:
        The paths, in order.
    """
    return [each[2] for each in here.calls if each[:2] == ["gh", "api"]]


def count_of(paths: Sequence[str], pattern: str) -> int:
    """How many paths match a pattern.

    Args:
        paths: the paths.
        pattern: a regular expression searched in each.

    Returns:
        The count.
    """
    return sum(1 for each in paths if re.search(pattern, each))


def item_paths() -> tuple[int, Sequence[str]]:
    """Run ``slots next`` for a PR in a wide configuration.

    Returns:
        The exit code, and the paths of the ``gh api`` calls.
    """
    here = itemworld.with_pull_issues(wide_world(REPOSITORIES))
    done = itemworld.one(here, "owner/project#3")
    return int(str(done.code)), paths_of(here)


class TestTheItemForm(unittest.TestCase):
    """``slots next OWNER/REPO#N`` reads what its one item needs."""

    def test_the_item_makes_under_twenty_calls_with_many_repositories(self) -> None:
        """The access of 37 repositories is the owner's list, read once."""
        code, paths = item_paths()
        probes = count_of(paths, r"^repos/owner/(r\d+|lib|project)$")
        lists = count_of(paths, r"^orgs/owner/repos")
        assert_that((code, len(paths) < 20, probes, lists), equal_to((0, True, 0, 1)))

    def test_only_the_gate_of_the_items_repository_is_read(self) -> None:
        """The brief of one item is built from its own repository."""
        gates = [each for each in item_paths()[1] if "review-gate.yml" in each]
        assert_that(gates, equal_to([f"{world.PROJECT}/contents/{gate_file()}"]))

    def test_the_gates_of_every_repository_for_the_full_form(self) -> None:
        """No item named: every repository's gate is read, once."""
        here = wide_world(3)
        rankworld.next_output(here)
        count = count_of(paths_of(here), r"review-gate\.yml")
        assert_that(count, equal_to(5))

    def test_no_scope_reads_every_gate(self) -> None:
        """The default scope of the access check is every repository."""
        settings = configfile.load(world.make_world().config, pathlib.Path("."))
        assert_that(repoaccess.every_gate(settings), equal_to(None))


def gate_file() -> str:
    """The path of a review gate workflow under a repository.

    Returns:
        The path.
    """
    return ".github/workflows/review-gate.yml"


PULLS = r"^repos/owner/{}/pulls\?state=open"
RUNS = r"^repos/owner/{}/actions/runs\?event="
SHARING = {"lib", "project"}  # the [runners] repositories of the world


def reads_of_each(paths: Sequence[str], pattern: str) -> Mapping[str, int]:
    """How often the paths read a list of each repository.

    Args:
        paths: the paths of the ``gh api`` calls.
        pattern: a regular expression with ``{}`` for the repository's name.

    Returns:
        The count for each of the 37 repositories.
    """
    names = ["lib", "project", *(f"r{number}" for number in range(REPOSITORIES))]
    return {each: count_of(paths, pattern.format(each)) for each in names}


class TestTheFullForm(unittest.TestCase):
    """``slots next`` reads each repository's pull requests once."""

    def test_each_repositorys_pull_requests_are_read_once(self) -> None:
        """Thirty-seven repositories, a list each, no list twice."""
        here = wide_world(REPOSITORIES)
        rankworld.next_output(here)
        counted = reads_of_each(paths_of(here), PULLS)
        assert_that(counted, equal_to(dict.fromkeys(counted, 1)))

    def test_the_queue_runs_are_read_for_the_runner_repositories_only(self) -> None:
        """The added repositories share no runners: their queue is not read."""
        here = wide_world(REPOSITORIES)
        rankworld.next_output(here)
        counted = reads_of_each(paths_of(here), RUNS)
        assert_that(counted, equal_to({k: int(k in SHARING) for k in counted}))

    def test_the_full_form_makes_few_calls_for_a_wide_configuration(self) -> None:
        """The calls grow with the lists read, not with a read for each repository."""
        few, many = wide_world(2), wide_world(REPOSITORIES)
        rankworld.next_output(few)
        rankworld.next_output(many)
        grown = len(paths_of(many)) - len(paths_of(few))
        per_repository = grown / (REPOSITORIES - 2)
        assert_that(per_repository, less_than(8))


def ticket_reads(queued: int) -> int:
    """The reads of tickets' comments with this many tickets queued.

    Args:
        queued: how many tickets after the default one.

    Returns:
        How many comment lists of tickets numbered 10 and over were read.
    """
    here = world.make_world()
    with_more_tickets(here, queued)
    rankworld.next_output(here)
    return count_of(paths_of(here), r"/issues/(1\d|[2-9]\d|\d{3,})/comments")


class TestTheBlockersOfTheRanking(unittest.TestCase):
    """The blockers and comments of a ticket are read for the top items only."""

    def test_raising_the_low_ranked_tickets_raises_no_read(self) -> None:
        """Ten more tickets or forty more: the same reads."""
        assert_that(ticket_reads(40), equal_to(ticket_reads(10)))

    def test_at_most_the_top_items_are_read(self) -> None:
        """The reads of tickets are bounded by the items shown."""
        assert_that(ticket_reads(40), less_than(windowrun.TOP + 1))

    def test_the_window_and_the_suggestions_show_the_same_number(self) -> None:
        """The ranking reads as many items as ``suggest`` shows."""
        assert_that(windowrun.TOP, equal_to(suggest.TOP))

    def test_the_list_says_it_ends(self) -> None:
        """The tickets after the items read are not listed, and that is said."""
        here = world.make_world()
        with_more_tickets(here, 20)
        shown = rankworld.next_output(here)
        assert_that(shown, contains_string("The list ends at its first"))
