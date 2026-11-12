"""I18 of pitboss#444: a resolver error in a package install is not this PR's."""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import redclass, redshapes, redsynth
from .test_redunits import _facts

LINE = "Temporary failure resolving 'azure.archive.ubuntu.com'"


def _failing(text: str) -> redshapes.RunFacts:
    step = redshapes.Step(
        number=4,
        name="Install libgmp-dev and wasm-ld (wasm fixtures)",
        conclusion="failure",
        started_at="",
        completed_at="",
    )
    job = redshapes.Job(
        id=1,
        name="fixtures (shard 3)",
        conclusion="failure",
        url="https://example.org/job/1",
        started_at="",
        completed_at="",
        steps=[step],
    )
    error = redshapes.FirstError(job=job, step=step, line=9, text=text, inferred_from=0)
    return redshapes.RunFacts(
        run=_facts([], None).run,
        jobs=[job],
        error=error,
        log_note="",
        pull=None,
        later=[],
        fix=None,
    )


class TestResolverError(unittest.TestCase):
    """The install step failed on the runner's DNS."""

    def test_i18_a_resolver_error_is_external_and_the_next_push_reruns_it(self) -> None:
        """The class, the log line it matched, and the step it prints."""
        found = redclass.classify(_failing(LINE), 0, [])
        assert_that(
            found.red_class, equal_to(redshapes.RedClass.EXTERNAL_INFRASTRUCTURE)
        )
        assert_that(found.basis.lower(), contains_string("temporary failure resolving"))
        mechanism = redsynth.MECHANISMS[found.red_class]
        assert_that(mechanism.text, contains_string("the next push re-runs it"))

    def test_i18_a_failure_with_no_resolver_error_is_not_established(self) -> None:
        """The nearest input that must stay: another error line."""
        found = redclass.classify(_failing("E: Unable to locate package lld"), 0, [])
        assert_that(found.red_class, equal_to(redshapes.RedClass.NOT_ESTABLISHED))
