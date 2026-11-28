"""A change to GitHub is done when GitHub shows it (keyword: landed, pitboss#531).

The scenarios are the package's own builders (``acthub.WRITES``, ``ghstore``,
``ghapi``) over a GitHub held in a dictionary, so a builder added without a reading
fails ``test_every_kind_of_change_has_a_scenario``.
"""

import subprocess
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to, has_length, instance_of

from .. import (
    acthub,
    ghapi,
    ghstore,
    landed,
    landedseen,
    landedtext,
    landedwords,
    retrying,
    running,
)
from . import landedscenarios as scenarios
from .landedhub import BAD_GATEWAY, LAGGING, TIMEOUT, Hub

COMMENT_POSTED = scenarios.KINDS[0]
SEEN = ("Outcome", 1, 1)
UNSAID = landed.NotLanded.__name__
FAILED = subprocess.CalledProcessError.__name__
UNSEEN = (UNSAID, 0, 1)


def no_wait(seconds: float) -> None:
    """A wait that does not wait.

    Args:
        seconds: how long it would.
    """


def hub_of(each: scenarios.Scenario, **changes: object) -> Hub:
    """GitHub as a scenario holds it before the write.

    Args:
        each: the scenario.
        **changes: other fields of the hub.

    Returns:
        The hub.
    """
    held = dict(each.before)
    return Hub(state=held, after=each.after, **changes)  # type: ignore[arg-type]


def make(hub: Hub, words: Sequence[str]) -> landed.Outcome:
    """The change, made through a runner that reads it back.

    Args:
        hub: GitHub.
        words: the ``gh`` line.

    Returns:
        What it printed.
    """
    runner = landed.checked(hub.run, hub.mutate, True, no_wait)
    return runner(words)  # type: ignore[return-value]


def result(hub: Hub, words: Sequence[str]) -> tuple[str, int, int]:
    """What making the change came to.

    Args:
        hub: GitHub.
        words: the ``gh`` line.

    Returns:
        What it ended in (``Outcome`` or the error's class), how many times the
        change was made by it (0 for an error) and how many writes GitHub saw.
    """
    try:
        done = make(hub, words)
    except (landed.NotLanded, subprocess.CalledProcessError) as error:
        return type(error).__name__, 0, len(hub.writes)
    return "Outcome", done.attempts, len(hub.writes)


class TestEveryKind(unittest.TestCase):
    """Each change the package can make has a reading, and it sees the change."""

    def test_every_kind_of_change_has_a_scenario(self) -> None:
        """No kind of ``acthub.WRITES`` is left without a reading."""
        kinds = {each.name for each in scenarios.KINDS}
        assert_that(kinds, equal_to(set(acthub.WRITES)))

    def test_each_change_that_landed_is_seen(self) -> None:
        """The reading after the change sees what the change did."""
        for each in scenarios.ALL:
            with self.subTest(each.name):
                assert_that(result(hub_of(each), each.words), equal_to(SEEN))

    def test_each_change_that_did_nothing_is_not_landed(self) -> None:
        """A change that returned and left GitHub as it was is not made again."""
        for each in scenarios.ALL:
            with self.subTest(each.name):
                hub = hub_of(each, lands=False)
                assert_that(result(hub, each.words), equal_to(UNSEEN))

    def test_every_builder_of_the_package_is_read(self) -> None:
        """What ``ghstore`` and ``ghapi`` write has a reading too."""
        seen: list[Sequence[str]] = []

        def spy(cmdargs: Sequence[str], /) -> landed.Outcome:
            seen.append(list(cmdargs))
            return landed.Outcome(stdout="", attempts=1)

        api = ghapi.GitHub(run=Hub(state={}, after={}).run, mutate=spy)
        ghstore.send(api, "PATCH", scenarios.ONE_COMMENT, "b")
        ghstore.send(api, "POST", f"{scenarios.R}/issues/3/comments", "b")
        ghstore.send(api, "DELETE", scenarios.ONE_COMMENT, None)
        ghstore.set_body(api, scenarios.PULL, "b")
        ghapi.post(api, f"{scenarios.ONE_RUN}/cancel")
        ghapi.close_pull(api, "o/r", 3)
        ghapi.delete_branch(api, "o/r", "w/1")
        parsed = [landedwords.parse(words) for words in seen]
        assert_that(parsed, has_length(7))
        for each in parsed:
            assert each is not None
            assert_that(landedseen.watch_of(each), instance_of(landedseen.Watch))


class TestFailures(unittest.TestCase):
    """A change that raised is looked for before it is made again, once."""

    def test_a_504_after_the_post_landed_is_not_made_twice(self) -> None:
        """The comment is there: nothing more is posted."""
        hub = hub_of(COMMENT_POSTED, fails=[TIMEOUT], kept=True)
        assert_that(result(hub, COMMENT_POSTED.words), equal_to(SEEN))

    def test_a_failed_change_that_left_nothing_is_made_again_once(self) -> None:
        """The first POST raised and nothing is there: the second lands."""
        hub = hub_of(COMMENT_POSTED, fails=[TIMEOUT])
        assert_that(result(hub, COMMENT_POSTED.words), equal_to(("Outcome", 2, 2)))

    def test_two_failures_raise_the_command_s_error(self) -> None:
        """Raised twice and nothing shown: the command's own error."""
        hub = hub_of(COMMENT_POSTED, fails=[TIMEOUT, BAD_GATEWAY], lands=False)
        assert_that(result(hub, COMMENT_POSTED.words), equal_to((FAILED, 0, 2)))

    def test_a_second_try_that_returned_and_is_not_shown_is_not_landed(self) -> None:
        """Raised, then returned, and still not shown: not landed."""
        hub = hub_of(COMMENT_POSTED, fails=[TIMEOUT], lands=False)
        assert_that(result(hub, COMMENT_POSTED.words), equal_to((UNSAID, 0, 2)))

    def test_a_reading_that_fails_is_not_an_answer(self) -> None:
        """A 502 of the reading is not a 404: a deletion is not shown by it."""
        deleted = scenarios.KINDS[2]
        hub = Hub(state={scenarios.ONE_COMMENT: LAGGING}, after={}, lands=False)
        assert_that(result(hub, deleted.words), equal_to((UNSAID, 0, 1)))

    def test_words_with_no_reading_are_refused_unwritten(self) -> None:
        """Words no rule reads are not written."""
        for words in (
            ["gh", "api", "-X", "POST", f"{scenarios.R}/hooks"],
            ["gh", "repo", "delete", "o/r"],
            ["gh", "api", "-X", "POST", "-f", "a=b"],
        ):
            with self.subTest(words):
                hub = Hub(state={}, after={})
                assert_that(result(hub, words), equal_to((UNSAID, 0, 0)))


def kept(each: scenarios.Scenario) -> Hub:
    """GitHub, whose first write raised after GitHub kept it.

    Args:
        each: the scenario.

    Returns:
        The hub.
    """
    return hub_of(each, fails=[TIMEOUT], kept=True)


class TestRaisedEveryKind(unittest.TestCase):
    """A write that raised is looked for, for every shape of write there is."""

    def test_a_write_that_raised_and_landed_is_not_made_twice(self) -> None:
        """Seen after the first write: one write, one attempt."""
        for each in scenarios.ALL:
            with self.subTest(each.name):
                assert_that(result(kept(each), each.words), equal_to(SEEN))

    def test_a_write_that_raised_and_left_nothing_is_made_again_once(self) -> None:
        """Not seen after the first write: the second lands."""
        for each in scenarios.ALL:
            with self.subTest(each.name):
                hub = hub_of(each, fails=[TIMEOUT])
                assert_that(result(hub, each.words), equal_to(("Outcome", 2, 2)))

    def test_a_write_that_raised_twice_is_the_command_s_error(self) -> None:
        """Raised twice and nothing shown: the command's own error."""
        for each in scenarios.ALL:
            with self.subTest(each.name):
                hub = hub_of(each, fails=[TIMEOUT, BAD_GATEWAY], lands=False)
                assert_that(result(hub, each.words), equal_to((FAILED, 0, 2)))

    def test_what_it_made_is_told_by_the_reading_not_the_lost_answer(self) -> None:
        """A comment, an issue and a pull request print their id or number."""
        told = {
            each.name: make(kept(each), each.words).stdout for each in scenarios.ALL
        }
        made = {name: said for name, said in told.items() if said}
        assert_that(made, equal_to({"comment": "8", "issue": "5", "pr": "5"}))


class TestReadingsThatMissWhatTheyShow(unittest.TestCase):
    """A reading that is satisfied by less than the write did is wrong."""

    def test_a_patch_with_no_field_the_reading_knows_is_not_shown(self) -> None:
        """There is nothing to compare, so nothing is shown."""
        hub = Hub(state={scenarios.PULL: {"title": "t"}}, after={})
        words = ["gh", "api", "-X", "PATCH", "-f", "draft=true", scenarios.PULL]
        assert_that(result(hub, words), equal_to(UNSEEN))

    def test_every_label_sent_is_held_not_the_first(self) -> None:
        """Two labels sent and one held is not landed."""
        words = ["gh", "api", "-X", "POST", "-f", "labels[]=a", "-f", "labels[]=b"]
        words.append(f"{scenarios.ISSUE}/labels")
        both = {"labels": [{"name": "a"}, {"name": "b"}]}
        one = {"labels": [{"name": "a"}]}
        held = Hub(
            state={scenarios.ISSUE: {"labels": []}}, after={scenarios.ISSUE: one}
        )
        assert_that(result(held, words), equal_to(UNSEEN))
        both_held = Hub(
            state={scenarios.ISSUE: {"labels": []}}, after={scenarios.ISSUE: both}
        )
        assert_that(result(both_held, words), equal_to(SEEN))

    def test_a_graphql_mutation_that_is_not_the_dequeue_is_refused_unwritten(
        self,
    ) -> None:
        """The rule is keyed by the mutation the query names."""
        query = "mutation($id: ID!) { deleteEverything(input: {}) { x } }"
        words = ["gh", "api", "graphql", "-f", f"query={query}", "-f", "id=N"]
        hub = Hub(state={}, after={})
        assert_that(result(hub, words), equal_to((UNSAID, 0, 0)))


class TestReadFailed(unittest.TestCase):
    """A reading that fails on every try through the retrying runner is "not yet"."""

    def test_a_reading_that_cannot_be_had_is_not_landed_not_a_crash(self) -> None:
        """The write returned; the reading after it fails: ``NotLanded``."""
        each = scenarios.KINDS[2]
        hub = hub_of(each)
        failing = Hub(state={scenarios.ONE_COMMENT: LAGGING}, after={})

        def sleep(seconds: float) -> None:
            return None

        draw = lambda bound: 0.0  # noqa: E731
        read = retrying.with_retries(failing.run, draw, sleep)  # type: ignore[arg-type]
        runner = landed.checked(read, hub.mutate, True, no_wait)
        with self.assertRaises(landed.NotLanded):
            runner(each.words)


class TestRunners(unittest.TestCase):
    """What the runner of an API is."""

    def test_a_dry_runner_makes_the_change_and_reads_nothing(self) -> None:
        """A dry run makes no change, so there is nothing to read back."""
        hub = Hub(state={}, after={})
        done = landed.checked(hub.run, hub.mutate, False)(["gh", "api", "x"])
        assert_that(done.stdout, equal_to("7"))
        assert_that(hub.writes, has_length(1))

    def test_a_lagging_reading_is_looked_at_after_each_wait(self) -> None:
        """The reading is tried after each wait, and the last is shown."""
        each = scenarios.KINDS[-1]
        waited: list[float] = []
        hub = hub_of(each, lands=False)

        def pause(seconds: float) -> None:
            waited.append(seconds)
            if len(waited) == 3:
                hub.state.update(each.after)

        landed.checked(hub.run, hub.mutate, True, pause)(each.words)
        assert_that(tuple(waited), equal_to(landed.WAITS[:3]))

    def test_a_read_only_api_refuses_a_change(self) -> None:
        """Nothing is made through an API built for reading."""
        api = running.read_only(Hub(state={}, after={}).run)
        with self.assertRaisesRegex(running.ReadOnlyApi, "read-only"):
            api.mutate(["gh", "api", "-X", "POST", "x"])


class TestReadings(unittest.TestCase):
    """The parts of a reading the scenarios do not reach."""

    def test_more_than_a_page_of_comments_is_every_page(self) -> None:
        """A hundred comments on a page are followed by the next page."""
        full = [{"body": "x"}] * landedseen.PAGE
        hub = Hub(
            state={scenarios.COMMENTS: full, scenarios.SECOND_PAGE: [{"body": "y"}]},
            after={scenarios.SECOND_PAGE: [{"body": "y"}, {"body": "b"}]},
        )
        assert_that(result(hub, COMMENT_POSTED.words), equal_to(SEEN))

    def test_a_head_with_its_owner_is_sent_as_it_is(self) -> None:
        """``owner:branch`` is not prefixed again."""
        named = f"{scenarios.R}/pulls?state=open&head=x%3Ah&per_page=30"
        hub = Hub(
            state={scenarios.NEWEST_PULL: [], named: []},
            after={scenarios.NEWEST_PULL: [{"number": 1}], named: [{"number": 1}]},
        )
        words = ["gh", "api", "-X", "POST", "-f", "head=x:h", f"{scenarios.R}/pulls"]
        assert_that(result(hub, words), equal_to(SEEN))

    def test_a_path_that_is_not_there_is_gone_and_a_held_one_is_not(self) -> None:
        """GONE is a 404, and nothing else is."""
        api = running.GitHub(
            run=Hub(state={"p": {}}, after={}).run, mutate=running.refused
        )
        assert_that(landedseen.get(api, "q") is landedseen.GONE)
        assert_that(landedseen.get(api, "p"), equal_to({}))

    def test_the_text_is_the_one_sent_up_to_the_line_ends(self) -> None:
        """GitHub keeps a body with CRLF line ends and trailing blanks."""
        assert_that(landedtext.same("a\r\nb \n", "a\nb"))
        assert_that(not landedtext.same(None, "a"))
