"""A started ticket's Done-when rows are corrected, the others kept (pitboss#488).

The keyword is act-verbs: ``act ticket-edit corrects=N`` on a ticket a PR closes.
"""

import unittest

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import donewhencorrection
from . import fakehub
from .knownkit import BODY, REPO, act, change, made
from .knownshipped import GIVEN, refusal

OLD = "## Done when\n\n- a demonstrated by x\n- b demonstrated by y\n\nPaths: src/\n"
NEW = "## Done when\n\n- a demonstrated by z\n- b demonstrated by y\n\nPaths: src/\n"


def _started(body: str = OLD) -> fakehub.Made:
    # a world where an open PR closes ticket 9, which holds ``body``
    hub = made(GIVEN, change(pull={"body": f"Fixes {REPO}#9\n\n" + BODY}))
    hub.hub.issues_made[(REPO, 9)] = {
        "number": 9,
        "state": "open",
        "body": body,
        "labels": "",
    }
    return hub


class TestCorrection(unittest.TestCase):
    """The rows named are the only change."""

    def test_the_named_row_is_corrected_and_recorded(self) -> None:
        """The edit goes and the old and new row are a comment on the ticket."""
        hub = _started()
        act(GIVEN, hub, "ticket-edit", number="9", body=NEW, corrects="1")
        kinds = [each.kind for each in hub.hub.writes]
        assert_that(kinds, equal_to(["comment", "issue-edit"]))
        said = str(hub.hub.writes[0].fields["body"])
        assert_that(said, contains_string("- was: a demonstrated by x"))
        assert_that(said, contains_string("- now: a demonstrated by z"))

    def test_another_row_changed_is_refused(self) -> None:
        """A row not named that changed stops the edit with that row's number."""
        hub = _started()
        other = NEW.replace("by y", "by q")
        said = refusal(hub, "ticket-edit", number="9", body=other, corrects="1")
        assert_that(said, contains_string("row 2 is not named in corrects"))
        assert_that(hub.hub.writes, has_length(0))

    def test_a_line_outside_the_rows_changed_is_refused(self) -> None:
        """The Paths line is not a row."""
        hub = _started()
        other = NEW.replace("Paths: src/", "Paths: lib/")
        said = refusal(hub, "ticket-edit", number="9", body=other, corrects="1")
        assert_that(said, contains_string("no part of a corrected row"))

    def test_a_started_ticket_without_corrects_is_still_refused(self) -> None:
        """No ``corrects``: nothing is added to a started ticket."""
        hub = _started()
        said = refusal(hub, "ticket-edit", number="9", body=NEW)
        assert_that(said, contains_string("a worker started"))


class TestFindings(unittest.TestCase):
    """The check on two bodies."""

    def test_each_reason(self) -> None:
        """Rows named wrong, a row count changed, a line count changed."""
        assert_that(donewhencorrection.findings(OLD, NEW, "1"), equal_to([]))
        gained = NEW.replace("\n\nPaths", "\n- c by w\n\nPaths")
        wrapped = NEW.replace("by z", "by\n  z")
        bare = "no section\n"
        asked = [(NEW, "x"), (NEW, "3"), (gained, "1"), (wrapped, "1")]
        said = [donewhencorrection.findings(OLD, *each)[0] for each in asked]
        said.append(donewhencorrection.findings(bare, bare, "1")[0])
        for each, words in zip(
            said,
            ["names the Done-when rows", "not row 3", "the body has 3"]
            + ["line count", "0 Done-when rows"],
        ):
            assert_that(each, contains_string(words))
