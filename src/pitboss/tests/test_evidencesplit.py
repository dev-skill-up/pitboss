"""Tests for splitting an over-long body into comments (pitboss#177)."""

import dataclasses
import subprocess
import unittest
from typing import MutableMapping, Sequence

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import evidencesplit, expansion, ghstore
from . import fakes, world
from .memorystore import OTHER, URL, Memory, comments, store_of

LIMIT = 65536
FOOTER = "🤖 Generated with [Claude Code](https://claude.com/claude-code)\n"


def row(number: int, size: int) -> str:
    """A block expand produced, of about a given size.

    Args:
        number: which command.
        size: the characters its output has.

    Returns:
        The block.
    """
    printed = ("line of output\n" * (size // 15 + 1))[:size]
    outcome = expansion.Outcome(status=0, output=printed)
    return expansion.block(f"make step{number}", outcome)


def fixture(blocks: int, size: int = 4000) -> str:
    """A body of paragraphs and blocks that ends with a footer.

    Args:
        blocks: how many blocks.
        size: the characters of each block's output.

    Returns:
        The body.
    """
    each = (f"Step {n}\n\n{row(n, size)}\n" for n in range(blocks))
    return "Fixes #1\n\n## Evidence\n\n" + "".join(each) + "\n" + FOOTER


def run(memory: Memory, text: str, limit: int = LIMIT) -> str:
    """Put a body in a pull request in memory.

    Args:
        memory: the pull request.
        text: the body.
        limit: the limit.

    Returns:
        The description as set.
    """
    return evidencesplit.apply(store_of(memory), text, limit)


def refused(text: str, limit: int) -> bool:
    """Say whether a body cannot be put in a pull request under a limit.

    Args:
        text: the body.
        limit: the limit.

    Returns:
        Whether it is refused as too long.
    """
    try:
        run(Memory(), text, limit)
    except evidencesplit.TooLong:
        return True
    return False


def fences(text: str) -> int:
    """Count the fence lines of a text.

    Args:
        text: the text.

    Returns:
        How many lines start with three backticks.
    """
    return sum(each.startswith("```") for each in text.splitlines())


def whole(cut_up: evidencesplit.Divided) -> str:
    """Join a cut body again.

    Args:
        cut_up: the cut.

    Returns:
        Head, later parts and closing paragraph in order.
    """
    return cut_up.head + "".join(cut_up.later) + cut_up.tail


class TestSplitBody(unittest.TestCase):
    """A body over the limit goes to the description and comments."""

    def test_fixture_over_the_limit(self) -> None:
        """The description is under the limit and cites every part's URL."""
        text = fixture(40)
        memory = Memory()
        final = run(memory, text)
        assert_that(
            [len(text) > LIMIT, len(final) <= LIMIT, memory.description],
            equal_to([True, True, [final]]),
        )
        assert_that(final.endswith("\n" + FOOTER), equal_to(True))
        for each in memory.stored.values():
            assert_that(final, contains_string(each.url))
            assert_that(len(each.body) <= LIMIT, equal_to(True))
        assert_that(final, contains_string("Part 2 of 3"))
        assert_that(final, contains_string("- row `make step39`: part 3, "))

    def test_parts_split_on_paragraph_markers(self) -> None:
        """No block is cut; the parts and the description join to the body."""
        text = fixture(40)
        cut_up = evidencesplit.divide(text)
        for part in [cut_up.head, *cut_up.later]:
            assert_that(fences(part) % 2, equal_to(0))
            ends = part.endswith("\n\n") or part.endswith("```\n")
            assert_that(ends, equal_to(True))
        assert_that([whole(cut_up), cut_up.tail], equal_to([text, FOOTER]))

    def test_fits(self) -> None:
        """A body under the limit is set as it is, with no comments."""
        memory = Memory()
        text = fixture(2)
        assert_that(run(memory, text), equal_to(text))
        assert_that(memory.log, equal_to(["body"]))

    def test_closing_block_is_cut_with_the_rest(self) -> None:
        """A last paragraph that holds a block is not the footer."""
        text = fixture(40) + row(99, 10)
        cut_up = evidencesplit.divide(text)
        assert_that([cut_up.tail, whole(cut_up)], equal_to(["", text]))

    def test_block_over_a_part_is_cut_on_lines(self) -> None:
        """A block too long for any part is the one cut, at line ends."""
        text = "Top\n\n" + row(1, 30000) + "\n" + FOOTER
        cut_up = evidencesplit.divide(text, 20000)
        assert_that(cut_up.later, has_length(1))
        assert_that(whole(cut_up), equal_to(text))
        room = 20000 - evidencesplit.HEADER_ROOM
        assert_that(all(len(each) <= room for each in cut_up.later), equal_to(True))

    def test_line_over_a_part_is_cut_inside(self) -> None:
        """One line longer than a part is cut by characters."""
        text = "x" * 5000 + "\n" + FOOTER
        assert_that(whole(evidencesplit.divide(text, 2000)), equal_to(text))

    def test_limits_that_cannot_be_met(self) -> None:
        """A limit with no room for a part, or for the citations, is refused."""
        cases = [(fixture(3), 500), (fixture(6, 3000), 1000), (fixture(3), 60000)]
        assert_that(
            [refused(text, limit) for text, limit in cases],
            equal_to([True, True, False]),
        )

    def test_citations_over_the_limit(self) -> None:
        """A description whose real URLs are longer than assumed is refused."""
        text = fixture(40)
        store = dataclasses.replace(
            store_of(Memory()),
            post=lambda body: evidencesplit.Comment(
                number=0, url="u" * LIMIT, body=body
            ),
        )
        with self.assertRaises(evidencesplit.TooLong):
            evidencesplit.apply(store, text)


class TestRerun(unittest.TestCase):
    """A rerun rewrites its comments and adds none."""

    def test_rerun_replaces_the_comments(self) -> None:
        """The same body twice leaves the same comments, rewritten."""
        memory = Memory()
        text = fixture(40)
        first = run(memory, text)
        ids = sorted(memory.stored)
        memory.log.clear()
        second = run(memory, text)
        assert_that(sorted(memory.stored), equal_to(ids))
        assert_that(memory.log, equal_to([f"edit {n}" for n in ids] + ["body"]))
        assert_that(second, equal_to(first))
        assert_that(comments(memory)[0], equal_to(OTHER))

    def test_longer_body_adds_and_shorter_removes(self) -> None:
        """A body that needs more parts adds comments; fewer removes them."""
        memory = Memory()
        steps = [(40, 2, ["post 101", "body"]), (55, 3, ["post 102", "body"])]
        for blocks, count, last in steps:
            memory.log.clear()
            run(memory, fixture(blocks))
            assert_that(memory.stored, has_length(count))
            assert_that(memory.log[-len(last) :], equal_to(last))
        memory.log.clear()
        run(memory, fixture(2))
        gone = ["delete 100", "delete 101", "delete 102", "body"]
        assert_that([memory.log, memory.stored], equal_to([gone, {}]))
        assert_that(comments(memory), equal_to([OTHER]))


ANSWERED = {"id": 55, "html_url": URL + "55"}


def canned() -> MutableMapping[str, object]:
    """The canned answers of a pull request with no comments.

    Returns:
        The bodies.
    """
    return {
        fakes.page("repos/o/p/issues/7/comments"): [],
        "POST repos/o/p/issues/7/comments": ANSWERED,
        "PATCH repos/o/p/issues/comments/55": ANSWERED,
        "DELETE repos/o/p/issues/comments/55": "",
        "PATCH repos/o/p/pulls/7": {},
    }


def post_call(text: str) -> Sequence[str]:
    """The command line that adds a comment to pull request 7 of o/p.

    Args:
        text: the comment's text.

    Returns:
        The command line.
    """
    path = "repos/o/p/issues/7/comments"
    return ["gh", "api", "-X", "POST", "-f", f"body={text}", path]


class TestStore(unittest.TestCase):
    """The store through ``gh api``."""

    def test_reads_and_changes(self) -> None:
        """Each call goes to its path and its answer is read."""
        bodies = canned()
        bodies[fakes.page("repos/o/p/issues/7/comments")] = [
            {"id": 3, "html_url": URL + "3", "body": None}
        ]
        api = fakes.github(bodies)
        store = ghstore.store_of((api.run, api.mutate), "o/p", 7)
        listed = store.comments()
        posted = store.post("text")
        edited = store.edit(55, "more")
        store.delete(55)
        store.set_body("body")
        wanted = [evidencesplit.Comment(number=3, url=URL + "3", body="")]
        assert_that(listed, equal_to(wanted))
        assert_that([posted.number, posted.url], equal_to([55, URL + "55"]))
        assert_that(edited.body, equal_to("more"))
        calls = fakes.calls_of(api)
        assert_that(calls[1], equal_to(post_call("text")))
        assert_that(calls[-1][-1], equal_to("repos/o/p/pulls/7"))

    def test_dry_run_answers_nothing(self) -> None:
        """A change that a dry run did not make has no URL yet."""
        silent = fakes.github({"POST repos/o/p/issues/7/comments": ""})
        store = ghstore.store_of((silent.run, silent.mutate), "o/p", 7)
        posted = store.post("text")
        assert_that([posted.number, posted.url], equal_to([0, ghstore.DRY_RUN_URL]))


def routed(bodies: MutableMapping[str, object]) -> fakes.Processes:
    """Processes that answer ``gh`` from bodies and run the rest for real.

    Args:
        bodies: the canned GitHub.

    Returns:
        The runner.
    """
    fake = fakes.FakeProcesses(bodies=bodies)

    def runner(cmdargs: Sequence[str], /, **kwargs: object) -> fakes.Output:
        if cmdargs[0] == "gh":
            return fake(cmdargs)
        return subprocess.run(  # type: ignore[call-overload,no-any-return]
            cmdargs, **kwargs
        )

    return runner


def invoked(template: str, *options: str) -> world.Result:
    """Run ``pitboss expand`` on a template, with ``gh`` answered by a fake.

    Args:
        template: the template's text.
        *options: the options after the file.

    Returns:
        What it did.
    """
    here = dataclasses.replace(world.make_world(), processes=routed(canned()))
    path = fakes.directory() / "t.md"
    fakes.write(path, template)
    return world.invoke(here, "expand", str(path), *options)


class TestCommand(unittest.TestCase):
    """``pitboss expand --pr``."""

    def test_refusals(self) -> None:
        """A pull request not named whole, or a body that cannot be cut, is 2."""
        named = invoked("text\n", "--pr", "7")
        small = invoked("$ yes | head -n 2000\n", "--pr", "o/p#7", "--limit", "9")
        assert_that(
            [named.code, named.out, small.code, small.out],
            equal_to([2, "", 2, ""]),
        )
        said = ["not OWNER/NAME#NUMBER" in named.err, "cannot be cut" in small.err]
        assert_that(said, equal_to([True, True]))

    def test_sets_the_description(self) -> None:
        """With --no-dry-run the description and a comment are set."""
        options = ["--pr", "o/p#7", "--limit", "5000", "--no-dry-run"]
        done = invoked("Top\n\n$ yes | head -n 3000\n\n" + FOOTER, *options)
        cited = URL + "55" in done.out
        assert_that(
            [done.code, done.err, cited, done.out.endswith(FOOTER)],
            equal_to([0, "", True, True]),
        )
