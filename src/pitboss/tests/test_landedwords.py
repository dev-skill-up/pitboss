"""A write's words are read once (keyword: landed); a fake follows them."""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to, none

from .. import landedtext, landedwords
from . import fakeapply

REPO = "repos/o/r"
PULL = f"{REPO}/pulls/3"
PULL_WORDS = ["gh", "pr", "{}", "3", "-R", "o/r"]
BRANCH = ["gh", "api", "-X", "PUT", f"{PULL}/update-branch"]
LABELS = ["gh", "api", "-X", "{}", f"{REPO}/issues/3/labels"]
HEAD = {"head": {"sha": "a"}}
# each write, the world it meets and the world after it
CASES: Sequence[
    tuple[str, Sequence[str], Mapping[str, object], Mapping[str, object]]
] = (
    (
        "arm",
        [*PULL_WORDS[:2], "merge", *PULL_WORDS[3:], "--auto"],
        {},
        {"auto_merge": {"enabled_by": {"login": "fake"}}},
    ),
    (
        "disarm",
        [*PULL_WORDS[:2], "merge", *PULL_WORDS[3:], "--disable-auto"],
        {"auto_merge": {}},
        {"auto_merge": None},
    ),
    (
        "ready",
        [*PULL_WORDS[:2], "ready", *PULL_WORDS[3:]],
        {"draft": True},
        {"draft": False},
    ),
    (
        "merge",
        [*PULL_WORDS[:2], "merge", *PULL_WORDS[3:], "--merge"],
        {},
        {"merged": True},
    ),
    ("update", BRANCH, HEAD, {"head": {"sha": "f" * 40}}),
    ("update of a pull with no head", BRANCH, {}, {}),
)


def _after(words: Sequence[str], held: Mapping[str, object]) -> object:
    bodies: dict[str, object] = {PULL: dict(held)}
    fakeapply.apply(bodies, words)
    return bodies[PULL]


class TestWords(unittest.TestCase):
    """What ``parse`` makes of the command lines the package writes with."""

    def test_a_graphql_query_is_a_post_named_by_its_mutation(self) -> None:
        """Its path is ``graphql/`` and the mutation it names; its fields are read."""
        found = landedwords.parse(["gh", "api", "graphql", "-f", "query=q"])
        assert found is not None
        assert_that((found.verb, found.path), equal_to(("POST", "graphql/")))
        assert_that(landedwords.value_of(found, "query"), equal_to("q"))
        mutation = "mutation($id: ID!) { dequeuePullRequest(input: {}) { x } }"
        named = landedwords.parse(["gh", "api", "graphql", "-f", f"query={mutation}"])
        assert named is not None
        assert_that(named.path, equal_to("graphql/dequeuePullRequest"))

    def test_words_that_are_neither_shape_are_not_a_write(self) -> None:
        """A flag last, too few words, a ``pr`` with no ``-REPO``, another program."""
        for words in (
            ["gh", "api", "-X"],
            ["gh", "api"],
            ["gh", "pr", "merge", "3"],
            ["git", "push"],
        ):
            with self.subTest(words=words):
                assert_that(landedwords.parse(words), none())


class TestSame(unittest.TestCase):
    """A text GitHub holds is the one sent, a footer after it apart."""

    def test_a_footer_after_the_text_is_the_text_shown(self) -> None:
        """Another text, or the text cut short, is not."""
        sent = "the body\r\n"
        host = landedtext.HOST_FOOTER
        held = (
            f"the body\n\n{host}",
            "the body",
            "other",
            "the bo",
            "the body\n\nmore",
        )
        found = [landedtext.same(each, sent) for each in held]
        assert_that(found, equal_to([True, True, False, False, False]))

    def test_a_text_cut_off_before_its_end_is_not_the_text_sent(self) -> None:
        """What GitHub holds is longer than what was sent: another text."""
        assert_that(landedtext.same("A\n\nB", "A"), equal_to(False))

    def test_a_control_character_the_host_writes_in_caret_notation(self) -> None:
        """An escape sent as itself is held as ``^[``."""
        assert_that(landedtext.same("ok ^[[1mx", "ok \x1b[1mx"), equal_to(True))


class TestFakeApply(unittest.TestCase):
    """The fake GitHub changes what a write says it changes."""

    def test_each_write_changes_the_pull_it_names(self) -> None:
        """Arm, disarm, ready, merge and a branch update."""
        for name, words, before, after in CASES:
            with self.subTest(name):
                assert_that(_after(words, before), equal_to({**before, **after}))

    def test_a_label_is_added_and_removed_on_the_kind_the_world_holds(self) -> None:
        """Only the issue is held: the pull path is skipped, both ways."""
        bodies: dict[str, object] = {f"{REPO}/issues/3": {"labels": [{"name": "x"}]}}
        post = [*LABELS[:3], "POST", "-f", "labels[]=y", LABELS[4]]
        fakeapply.apply(bodies, post)
        fakeapply.apply(bodies, ["gh", "api", "-X", "DELETE", f"{LABELS[4]}/x"])
        assert_that(bodies[f"{REPO}/issues/3"], equal_to({"labels": [{"name": "y"}]}))
