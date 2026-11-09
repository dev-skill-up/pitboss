"""The p0 tickets are read past a full page that holds a pull request."""

import unittest

from hamcrest import assert_that, equal_to

from .. import config, redtickets
from . import fakes

REPO = config.make_repo("o", "r")
PATH = "repos/o/r/issues?state=open&labels=p0"


def _issue(number: int) -> dict[str, object]:
    return {
        "number": number,
        "title": f"T{number}",
        "created_at": "2026-10-01T05:00:00Z",
        "labels": [{"name": "p0"}],
        "body": "",
    }


class TestPaging(unittest.TestCase):
    """A page of 100 raw items continues to the next."""

    def test_a_full_first_page_with_a_pull_request_pages_on(self) -> None:
        """99 tickets and a PR are a full page; the ticket of page 2 is read."""
        full = [_issue(number) for number in range(100, 199)]
        full.append({**_issue(199), "pull_request": {}})
        bodies: dict[str, object] = {
            fakes.page(PATH): full,
            fakes.page(PATH, 2): [_issue(200)],
        }
        for number in [*range(100, 199), 200]:
            bodies[fakes.page(f"repos/o/r/issues/{number}/comments")] = []
        found = redtickets.read_tickets(fakes.github(bodies), [REPO], [])
        expected = [*range(100, 199), 200]
        assert_that([each.number for each in found], equal_to(expected))
