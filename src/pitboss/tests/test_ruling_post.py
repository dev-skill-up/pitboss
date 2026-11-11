"""``pitboss ruling post`` posts an Opus ruling file as a PR comment (pitboss#466)."""

import dataclasses
import re
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, empty, equal_to, has_length

from .. import brief
from . import briefmake, world

PULL = "owner/project#3"
COMMENTS = f"POST {world.PROJECT}/issues/3/comments"
URL = "https://github.example/owner/project/pull/3#c5"
GOOD = (
    "Opus ruling\nRuling: do these steps\n\n## How we got here\n\n"
    "Finding one, the rule, pitboss#1.\n\n1. Do it.\n"
)
REFUSED = "pitboss ruling post: refused: "
WORD = "the second line is not `Ruling: <word>` with a word of: do these steps"
GONE = "/nonexistent/ruling.md"
# the text, the pull request, the file (none: a file holding the text), the reason
REFUSALS: Sequence[tuple[str, str, str, str]] = [
    (GOOD.replace("Opus ruling", "A ruling", 1), PULL, "", "the first line is not"),
    (GOOD.replace("do these steps", "maybe"), PULL, "", WORD),
    ("Opus ruling\n", PULL, "", WORD),
    ("Opus ruling\nRuling: split\n\nSteps.\n", PULL, "", "no `How we got here`"),
    (GOOD, "three", "", "three: not OWNER/NAME#NUMBER"),
    (GOOD, PULL, GONE, GONE),
]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Attempt:
    """What one run of ``ruling post`` did in a world whose PR 3 takes comments.

    Attributes:
        sent: the texts posted to PR 3's comments.
        code: the exit code.
        out: standard output.
        err: standard error.
    """

    sent: Sequence[str]
    code: object
    out: str
    err: str


def run_post(text: str, pull: str, name: str) -> Attempt:
    """Run ``ruling post`` on a file.

    Args:
        text: the text of the file.
        pull: the pull request argument.
        name: the file to name; empty: a file in the workspace holding the text.

    Returns:
        What it did.
    """
    here = world.make_world()
    here.bodies[COMMENTS] = {"id": 5, "html_url": URL}
    path = here.workspace / "ruling.md"
    path.write_text(text, encoding="utf-8")
    done = world.invoke(here, "ruling", "post", pull, name or str(path))
    posted = [each for each in here.calls if each[-1].endswith("issues/3/comments")]
    return Attempt(
        sent=[each[each.index("-f") + 1].removeprefix("body=") for each in posted],
        code=done.code,
        out=done.out,
        err=done.err,
    )


class TestPost(unittest.TestCase):
    """A ruling in the form is posted, and its URL printed."""

    def test_a_good_file_is_posted_as_it_is(self) -> None:
        """The comment is the file."""
        assert_that(run_post(GOOD, PULL, "").sent, equal_to([GOOD]))

    def test_the_url_of_the_comment_is_printed(self) -> None:
        """One line, the comment's address."""
        assert_that(run_post(GOOD, PULL, "").out, equal_to(URL + "\n"))


class TestRefusals(unittest.TestCase):
    """A file not in the form is refused and nothing is posted."""

    def test_each_refusal_says_why_and_posts_nothing(self) -> None:
        """A first line, a word, a second line, a section, a pull, a file."""
        for text, pull, name, why in REFUSALS:
            with self.subTest(why=why):
                got = run_post(text, pull, name)
                assert_that(str(got.code) + got.err, contains_string(why))
                assert_that(got.sent, empty())

    def test_a_refusal_is_status_two_with_its_prefix(self) -> None:
        """The exit status and the first words of the message."""
        got = run_post("A ruling\n", PULL, "")
        assert_that((got.code, got.err.startswith(REFUSED)), equal_to((2, True)))


class TestBrief(unittest.TestCase):
    """The ruling brief names the command."""

    def test_the_record_line_names_the_command(self) -> None:
        """The ``Record:`` line holds ``pitboss ruling post``."""
        records = re.findall(r"(?m)^Record:.*$", briefmake.text(brief.Kind.RULING))
        assert_that(records, has_length(1))
        assert_that(records[0], contains_string("pitboss ruling post"))
