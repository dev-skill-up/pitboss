"""A read started beside another is finished before the command goes on (#524).

The tests-3.14 failure of 467ddb4 (the bare form of ``sweep`` made one more
``gh api repository`` read than the others): the owner's search was started with
the organization's list and not waited for, so whether its call was made before
the command ended depended on timing.
"""

import dataclasses
import time
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import ghapi, ownerrepos
from . import fakes

LIST = fakes.page("orgs/owner/repos")
SEARCH = fakes.page("search/repositories?q=org:owner%20archived:false")
NAMED = [{"full_name": "owner/project", "archived": False}]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class SlowSearch:
    """A fake ``gh`` whose searches take their time, and which says what it ran.

    Attributes:
        inner: the fake with the canned answers.
    """

    inner: fakes.Processes

    def __call__(self, cmdargs: Sequence[str], /, **kwargs: object) -> fakes.Output:
        """Run one command, a search a little later.

        Args:
            cmdargs: the command line.
            **kwargs: what gather passes to ``subprocess.run``.

        Returns:
            The finished process.
        """
        if cmdargs[-1].startswith("search/"):
            time.sleep(0.3)
        return self.inner(cmdargs, **kwargs)


class TestTheSearchIsFinished(unittest.TestCase):
    """The owner's listing."""

    def test_the_search_is_run_before_the_listing_returns(self) -> None:
        """The list answers at once; the search was made all the same."""
        fake = fakes.FakeProcesses(bodies={LIST: NAMED, SEARCH: {"items": NAMED}})
        slow = SlowSearch(inner=fake)
        found = ownerrepos.listed_slugs(ghapi.GitHub(run=slow, mutate=slow), "owner")
        searches = sum(1 for each in fake.calls if "search" in each[-1])
        assert_that(sorted(found), equal_to(["owner/project"]))
        assert_that(searches, equal_to(1))
