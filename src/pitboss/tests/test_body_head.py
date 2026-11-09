"""``pitboss body-head`` adds the new head's line to a PR body (pitboss#369)."""

import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import bodydigest, bodyhead
from . import fakes, world

OLD, NEW = "a" * 40, "b" * 40
PULL = "owner/project#3"
PATH = f"{world.PROJECT}/pulls/3"
BODY = f"Fixes o/p#1\n\n## Plan\n\n1. a row\n\nHead: {OLD}\n\n## Evidence\n\n$ ls\n"
WANTED = BODY.replace(f"Head: {OLD}\n", f"Head: {OLD}\nHead: {NEW}\n")


def served(body: str, head: str = NEW) -> world.World:
    """A world whose PR 3 has a body and a head.

    Args:
        body: the PR body.
        head: the PR's head.

    Returns:
        The world, which answers the change of the body.
    """
    here = world.make_world()
    here.bodies[PATH] = fakes.pull_body(3, body=body, head={"sha": head, "ref": "b"})
    here.bodies[f"PATCH {PATH}"] = {}
    return here


def patches(here: world.World) -> Sequence[Sequence[str]]:
    """The changes of the body the commands ran.

    Args:
        here: the world.

    Returns:
        The command lines.
    """
    return [call for call in here.calls if call[2:4] == ["-X", "PATCH"]]


def run(here: world.World, *more: str) -> world.Result:
    """Run ``body-head`` on PR 3.

    Args:
        here: the world.
        *more: more arguments.

    Returns:
        What it did.
    """
    return world.invoke(here, "body-head", PULL, *more)


class TestThePieces(unittest.TestCase):
    """The new body, as text."""

    def test_a_body_whose_last_head_is_old_gets_the_new_head_after_it(self) -> None:
        """Only the one line is added."""
        found = bodyhead.with_head(BODY, NEW)
        assert_that(found, equal_to(WANTED))
        assert_that(bodyhead.last_head(found), equal_to(NEW))
        assert_that(found.replace(f"Head: {NEW}\n", ""), equal_to(BODY))

    def test_the_line_ending_of_the_last_head_line_is_kept(self) -> None:
        """A web edit's ``\\r\\n`` and a body that ends on the line."""
        crlf = BODY.replace("\n", "\r\n")
        assert_that(
            bodyhead.with_head(crlf, NEW),
            equal_to(WANTED.replace("\n", "\r\n")),
        )
        bare = f"Fixes o/p#1\nHead: {OLD}"
        assert_that(
            bodyhead.with_head(bare, NEW),
            equal_to(f"Fixes o/p#1\nHead: {OLD}\nHead: {NEW}"),
        )

    def test_the_last_of_several_head_lines_is_the_one(self) -> None:
        """An earlier head line is not read."""
        body = f"Head: {NEW}\nx\nHead: {OLD}\ny\n"
        assert_that(bodyhead.last_head(body), equal_to(OLD))
        assert_that(
            bodyhead.with_head(body, NEW).endswith(f"Head: {NEW}\ny\n"), equal_to(True)
        )

    def test_a_body_that_names_the_head_is_not_changed(self) -> None:
        """The same head again adds no line."""
        assert_that(bodyhead.with_head(WANTED, NEW), equal_to(WANTED))

    def test_a_line_that_is_not_forty_hex_digits_is_no_head_line(self) -> None:
        """The nearest forms the reading must still refuse."""
        for each in ("Head: " + OLD[:39], "Head: " + OLD.upper(), " Head: " + OLD):
            assert_that(bodyhead.last_head(f"x\n{each}\n"), equal_to(""))


class TestTheCommand(unittest.TestCase):
    """The command, through the API."""

    def test_it_patches_the_body_and_prints_the_digest_and_the_proof_input(
        self,
    ) -> None:
        """The body sent is the old one with the new line; nothing else."""
        here = served(BODY)
        done = run(here)
        sent = [call[-2] for call in patches(here)]
        digest = f"{bodydigest.PREFIX}{bodydigest.digest(WANTED)}"
        wanted = f"{digest}\nbats merge-proof {OLD} {NEW}\n"
        assert_that(
            [sent, done.out, done.code], equal_to([[f"body={WANTED}"], wanted, 0])
        )

    def test_a_body_that_names_the_head_is_not_changed_by_the_command(self) -> None:
        """The head already named."""
        here = served(WANTED)
        done = run(here)
        proof = f"bats merge-proof {NEW} {NEW}"
        assert_that(patches(here), equal_to([]))
        assert_that(done.out.splitlines()[1], equal_to(proof))

    def test_a_body_with_no_head_line_and_a_bad_reference_exit_2(self) -> None:
        """Nothing is changed."""
        here = served("Fixes o/p#1\n")
        bad = world.invoke(here, "body-head", "owner/project")
        codes = [run(here).code, bad.code, len(patches(here))]
        assert_that(codes, equal_to([2, 2, 0]))
