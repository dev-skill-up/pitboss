"""``pitboss body-head`` adds the new head's line to a PR body (pitboss#369)."""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import bodydigest, bodyhead, shapes
from . import fakes, world
from .says import exits, says

OLD, NEW = "a" * 40, "b" * 40
PULL = "owner/project#3"
PATH = f"{world.PROJECT}/pulls/3"
BODY = f"Fixes o/p#1\n\n## Plan\n\n1. a row\n\nHead: {OLD}\n\n## Evidence\n\n$ ls\n"
WANTED = BODY.replace(f"Head: {OLD}\n", f"Head: {OLD}\nHead: {NEW}\n")
REVIEWED = "c" * 40
COMMENTS = f"{world.PROJECT}/issues/3/comments?per_page=100&page=1"


def review(
    sha: str, verdict: str = "approved", when: str = "2026-11-10T00:00:00Z"
) -> Mapping[str, str]:
    """An adversarial review comment of a trusted author.

    Args:
        sha: the head it names.
        verdict: its verdict word.
        when: when it was written.

    Returns:
        The comment as the API gives it.
    """
    body = f"## Adversarial review\n\nReviewed: {sha}\n\nVerdict: {verdict}\n"
    return {
        "body": body,
        "author_association": "OWNER",
        "created_at": when,
        "html_url": "https://example.org/c/1",
    }


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
    here.bodies[COMMENTS] = [review(REVIEWED)]
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
        wanted = f"{digest}\nbats merge-proof {REVIEWED} {NEW}\n"
        assert_that(
            [sent, done.out, done.code], equal_to([[f"body={WANTED}"], wanted, 0])
        )

    def test_a_body_that_names_the_head_is_not_changed_by_the_command(self) -> None:
        """The head already named."""
        here = served(WANTED)
        done = run(here)
        proof = f"bats merge-proof {REVIEWED} {NEW}"
        assert_that(patches(here), equal_to([]))
        assert_that(done.out.splitlines()[1], equal_to(proof))

    def test_a_body_with_no_head_line_and_a_bad_reference_exit_2(self) -> None:
        """Nothing is changed."""
        here = served("Fixes o/p#1\n")
        bad = world.invoke(here, "body-head", "owner/project")
        codes = [run(here).code, bad.code, len(patches(here))]
        assert_that(codes, equal_to([2, 2, 0]))


class TestTheReviewedHead(unittest.TestCase):
    """The first argument of the proof is the head the newest approving review names."""

    def test_t394_a_pr_merged_with_main_twice_names_the_reviewed_head(self) -> None:
        """The body has moved past the review twice; the proof starts at the review."""
        later = f"Head: {OLD}\nHead: {NEW}\n"
        here = served(BODY.replace(f"Head: {OLD}\n", later), head="d" * 40)
        done = run(here)
        assert_that(
            done.out.splitlines()[1],
            equal_to(f"bats merge-proof {REVIEWED} {'d' * 40}"),
        )
        assert_that(OLD in done.out.splitlines()[1], equal_to(False))

    def test_t394_the_newest_approving_review_is_the_one(self) -> None:
        """An older approval and a newer changes-needed: the approval is the proof's."""
        here = served(BODY)
        here.bodies[COMMENTS] = [
            review("e" * 40, when="2026-11-09T00:00:00Z"),
            review(REVIEWED, when="2026-11-10T00:00:00Z"),
            review("f" * 40, "changes needed", "2026-11-11T00:00:00Z"),
        ]
        assert_that(run(here).out.splitlines()[1], contains_string(REVIEWED))

    def test_t394_the_command_says_so_when_no_review_names_a_head(self) -> None:
        """No approving review: no proof line, and the reason."""
        here = served(BODY)
        here.bodies[COMMENTS] = [review(REVIEWED, "changes needed")]
        done = run(here)
        says(done.out, "no approving review names a head")
        assert_that(
            "bats merge-proof" in done.out.replace("`bats merge-proof`", ""),
            equal_to(False),
        )
        exits(done, 0)

    def test_t394_a_review_of_an_untrusted_author_is_not_read(self) -> None:
        """Only OWNER, MEMBER and COLLABORATOR count."""
        made = review(REVIEWED)
        other = {
            "body": made["body"],
            "author_association": "NONE",
            "created_at": made["created_at"],
        }
        assert_that(bodyhead.approved_head([]), equal_to(""))
        assert_that(bodyhead.approved_head([shapes.Comment(**other)]), equal_to(""))
