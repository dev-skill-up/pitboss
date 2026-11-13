"""The order of work is read by organisation, not repository (keyword: org-search)."""

import unittest

from hamcrest import assert_that, equal_to

from .. import branchtaken, config, ghapi, orgsearch
from . import fakes

QUIRE = config.make_repo("o", "quire")


class TestOrgSearch(unittest.TestCase):
    """The owner: one oldest-first query of each organisation, filtered here."""

    def test_6_1_a_search_names_its_organisation_and_its_order(self) -> None:
        """The path asks for the open items of one organisation, oldest first."""
        found = orgsearch.path("o", "is:pr", "head:relock/")
        want = "search/issues?q=org:o+is:open+is:pr+head:relock%2F"
        assert_that(found, equal_to(want + "&sort=created&order=asc"))

    def test_6_1_an_answer_that_is_no_search_has_no_items(self) -> None:
        """A list, or an object with no list of items, gives no item."""
        found = [orgsearch.items(text) for text in ("[]", '{"items": 3}')]
        assert_that(found, equal_to([[], []]))

    def test_6_1_an_item_of_another_repository_is_none_of_ours(self) -> None:
        """An item is of a configured repository only by its API URL."""
        repos = {QUIRE.slug: QUIRE}
        items = [
            {"repository_url": "https://api.github.com/repos/o/quire"},
            {"repository_url": "https://api.github.com/repos/o/other"},
            {"repository_url": "https://example.com/repos/o/quire"},
            {},
        ]
        found = [orgsearch.repo_of(each, repos) for each in items]
        assert_that(found, equal_to([QUIRE, None, None, None]))


class TestBranchTaken(unittest.TestCase):
    """A ticket a branch names is taken, from its own repository's one read."""

    def test_6_2_a_branch_that_ends_in_the_number_takes_the_ticket(self) -> None:
        """``fix-12`` takes ``#12``; a row with no head or a number names none."""
        rows = [{"head": {"ref": "fix-12"}}, {"head": None}, {"head": {"ref": "x"}}]
        bodies: dict[str, object] = {fakes.page("repos/o/quire/pulls?state=open"): rows}
        github = fakes.github(bodies)
        found = branchtaken.named(github, "o/quire#12")
        assert_that(found, equal_to(frozenset({"o/quire#12"})))

    def test_6_2_an_answer_that_is_no_list_takes_nothing(self) -> None:
        """A listing that is not a list names no ticket."""
        bodies: dict[str, object] = {fakes.page("repos/o/quire/pulls?state=open"): {}}
        github: ghapi.GitHub = fakes.github(bodies)
        assert_that(branchtaken.named(github, "o/quire#1"), equal_to(frozenset()))
