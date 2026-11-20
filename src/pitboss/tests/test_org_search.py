"""The order of work is read by organisation, not repository (keyword: org-search)."""

import unittest

from hamcrest import assert_that, equal_to

from .. import branchtaken, config, configrepos, ghapi, holdissues, orgsearch
from .. import pullrecords
from .. import pullsearch
from . import fakes

QUIRE = config.make_repo("o", "quire")


def _no_relock() -> config.Config:
    # a configuration whose relock prefix names no branch: one search of the PRs
    return fakes.settings(fakes.directory(), '[relock]\nprefix = ""\n')


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

    def test_6_1_each_repository_has_one_listing_of_its_open_pull_requests(
        self,
    ) -> None:
        """Plan 6.1: one oldest-first listing of each configured repository."""
        settings = _no_relock()
        slugs = configrepos.slugs(settings)
        github = fakes.github(
            {fakes.page(f"repos/{each}/pulls?state=open"): [] for each in slugs}
        )
        found = pullsearch.opened(github, settings)
        calls = len(fakes.calls_of(github))
        assert_that((found.read, calls), equal_to(([], len(slugs))))

    def test_3_1_a_page_both_kinds_of_row_reach_is_read_once(self) -> None:
        """Plan 3.1: the pull requests and the relock reviews share a read page."""
        settings = fakes.settings(fakes.directory())
        project = settings.project.repo
        made = [
            {
                "number": n,
                "created_at": f"2026-01-01T00:{n // 60:02d}:{n % 60:02d}Z",
                "head": {"ref": "relock/x" if n % 2 else "x"},
            }
            for n in range(1, 102)
        ]
        path = f"repos/{project.slug}/pulls?state=open"
        github = fakes.github(
            {fakes.page(path, 1): made[:100], fakes.page(path, 2): made[100:]}
        )
        found = pullsearch.opened(github, settings)
        reached = [
            [row.number for row in each] for each in (found.pulls, found.relocks)
        ]
        asked = [call for call in fakes.calls_of(github) if call[-1].endswith("page=2")]
        assert_that(
            (reached[0][:2], reached[1][:2], reached[0][-1], len(asked)),
            equal_to(([2, 4], [1, 3], 100, 1)),
        )

    def test_6_1_the_holds_are_one_search_of_the_organisation(self) -> None:
        """A hold of a configured repository is parsed; another repository's is not."""
        terms = ("owner", "is:issue", "label:pitboss-hold")
        api = "https://api.github.com/repos/owner/"
        items = [
            {"repository_url": api + "project", "title": "", "number": 4},
            {"repository_url": api + "other", "title": "freeze", "number": 5},
        ]
        github = fakes.github({fakes.page(orgsearch.path(*terms)): {"items": items}})
        found = holdissues.read(github, fakes.settings(fakes.directory()))
        held = [pullrecords.Hold(title="4", scope="all")]
        assert_that(found, equal_to({"owner/project": held}))


class TestBranchTaken(unittest.TestCase):
    """Plan 3.1: a ticket's repository's open branches, from one read of it."""

    def test_3_1_each_open_pull_requests_branch_is_read(self) -> None:
        """A row with no head gives no branch."""
        rows = [{"head": {"ref": "fix-12"}}, {"head": None}, {"head": {"ref": "x"}}]
        bodies: dict[str, object] = {fakes.page("repos/o/quire/pulls?state=open"): rows}
        found = branchtaken.branches(fakes.github(bodies), "o/quire")
        assert_that(found, equal_to(["fix-12", "x"]))

    def test_3_1_an_answer_that_is_no_list_has_no_branch(self) -> None:
        """A listing that is not a list gives no branch."""
        bodies: dict[str, object] = {fakes.page("repos/o/quire/pulls?state=open"): {}}
        github: ghapi.GitHub = fakes.github(bodies)
        assert_that(branchtaken.branches(github, "o/quire"), equal_to([]))
