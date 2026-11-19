"""Every body check, on a corpus of real tickets and PRs (pitboss#482).

The keyword is plan-corpus. ``planpairs/`` holds the ticket body and the PR body of
each pair as GitHub gave them, and its manifest names the source URL, the head SHA,
the bad states of the pair and what each check gave on it, recorded. A test for
each check that failed on main runs the check on every pair and compares. The
ticket the Done-when checks read comes from the fixture, through a runner that fails any other call.
"""

import json
import re
import unittest
from typing import Callable

from hamcrest import (
    any_of,
    assert_that,
    contains_string,
    equal_to,
    greater_than_or_equal_to,
    is_,
    is_not,
)

from . import planoutcomes, planpairs

KINDS = ("body", "ticket")
LEAST_PAIRS = 30
LEAST_REPOSITORIES = 5
SHA = re.compile(r"[0-9a-f]{40}")
POSTED = ("Plan check: ok", "Plan check: refused", "none")


# the checks whose corpus test failed on main (pitboss#482, item 37: a corpus test that
# passes on main is kept only where main is wrong or the test too weak, else removed)
FAILED_ON_MAIN = ("plan-done-when",)
NOT_THE_NETWORK = (
    ["gh", "api", "repos/owner/name/pulls/1"],
    ["curl", "https://api.github.com/"],
)


def assert_pair(pair: planpairs.Pair) -> None:
    """Check one pair of the manifest.

    Args:
        pair: the pair.
    """
    source, record = pair.source, pair.record
    assert_that(
        source.url,
        equal_to(f"https://github.com/{source.repository}/pull/{source.pull}"),
    )
    assert_that(source.ticket_url, contains_string("https://github.com/"))
    assert_that(SHA.fullmatch(source.head), is_not(equal_to(None)))
    assert_that(record.posted, is_(any_of(*[equal_to(each) for each in POSTED])))
    # the fixtures are committed verbatim: the recorded hash is of their bytes
    for kind in KINDS:
        assert_that(planpairs.sha256_of(pair.name, kind), equal_to(record.sha256[kind]))
    # the entry names the bad states the pair is in, as its fixtures and facts show
    assert_that(list(record.states), equal_to(list(planoutcomes.states_of(pair))))
    # every check has its recorded outcome, and the reason when it cannot run
    assert_that(list(record.checks), equal_to(list(planpairs.CHECKS)))
    for name, entry in record.checks.items():
        assert_that(
            entry.get("not_offline", ""), equal_to(planpairs.REASONS.get(name, ""))
        )
        if entry["outcome"] == planpairs.NOT_OFFLINE:
            assert_that(entry["not_offline"], is_not(equal_to("")))


class TestCorpus(unittest.TestCase):
    """The corpus and what each check gives on it."""

    def test_corpus_manifest(self) -> None:
        """Done-when: the manifest names every pair, source, head, states, checks."""
        found = planpairs.pairs()
        assert_that(len(found), greater_than_or_equal_to(LEAST_PAIRS))
        assert_that(
            len({each.source.repository for each in found}),
            greater_than_or_equal_to(LEAST_REPOSITORIES),
        )
        posted = {each.record.posted for each in found}
        assert_that("Plan check: ok" in posted, is_(True))
        assert_that("Plan check: refused" in posted, is_(True))
        for pair in found:
            with self.subTest(pair=pair.name):
                assert_pair(pair)
        # every bad state of the Done-when is in a pair
        held = {state for each in found for state in planoutcomes.states_of(each)}
        assert_that(held, equal_to(set(planpairs.STATES)))
        # no pair twice and no fixture left over
        names = [each.name for each in found]
        assert_that(len(set(names)), equal_to(len(names)))
        listed = sorted(each.name for each in planpairs.ROOT.glob("*.txt"))
        wanted = sorted(f"{name}.{kind}.txt" for name in names for kind in KINDS)
        assert_that(listed, equal_to(wanted))

    def test_corpus_pr_main_yml(self) -> None:
        """Done-when: no network request: the runner serves the ticket, no more."""
        for pair in planpairs.pairs():
            with self.subTest(pair=pair.name):
                run = planoutcomes.served(pair)
                for other in NOT_THE_NETWORK:
                    with self.assertRaises(planoutcomes.NetworkCalled):
                        run(other)
                slug, _, number = pair.source.ticket.rpartition("#")
                served = run(["gh", "api", f"repos/{slug}/issues/{number}"])
                assert_that(json.loads(served.stdout)["body"], equal_to(pair.text))
                # every check runs on the pair through that runner, and none fails it
                for check in planpairs.CHECKS:
                    assert_that(planoutcomes.outcome(check, pair), is_not(equal_to("")))


def _gives(check: str) -> Callable[[TestCorpus], None]:
    # a test of one check: it gives each pair its recorded outcome
    def test(self: TestCorpus) -> None:
        for pair in planpairs.pairs():
            with self.subTest(pair=pair.name, check=check):
                assert_that(
                    planoutcomes.outcome(check, pair),
                    equal_to(pair.record.checks[check]["outcome"]),
                )

    test.__doc__ = f"Done-when: `{check}` gives every pair its recorded outcome."
    return test


# one test for each check that failed on main, named by the check
for _check in FAILED_ON_MAIN:
    setattr(TestCorpus, f"test_corpus_{re.sub(r'[-.]', '_', _check)}", _gives(_check))
