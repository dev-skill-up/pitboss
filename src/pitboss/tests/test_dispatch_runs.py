"""A repository with no check.yml has no dispatched run (no-check-workflow).

The cause: ``pitboss next dev-skill-up/pitboss#486`` ended with READ FAILED on
``actions/workflows/check.yml/runs`` (404), because pitboss has no check.yml;
the 404 is the answer that no run was dispatched.
"""

import subprocess
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import dispatchruns, ghapi
from . import fakes

HEAD = "a" * 40
PATH = (
    f"repos/o/r/actions/workflows/check.yml/runs?head_sha={HEAD}"
    "&event=workflow_dispatch&status=completed"
)


def _server_error(cmdargs: Sequence[str], /) -> fakes.Output:
    raise subprocess.CalledProcessError(
        1, list(cmdargs), output="", stderr="gh: Server Error (HTTP 500)\n"
    )


class TestNoWorkflow(unittest.TestCase):
    """The runs of a head, where check.yml may not exist."""

    def test_a_404_is_no_dispatched_run(self) -> None:
        """A repository with no check.yml answers no run, completed or not."""
        api = fakes.github({})
        found = (
            dispatchruns.completed(api, "o/r", HEAD),
            dispatchruns.completed_before(api, "o/r", HEAD, "2026-01-01T00:00:00Z"),
        )
        assert_that(found, equal_to((False, False)))

    def test_a_run_is_read_where_the_workflow_exists(self) -> None:
        """The runs of check.yml still count."""
        api = fakes.github({fakes.page(PATH): {"workflow_runs": [{"id": 5}]}})
        assert_that(dispatchruns.completed(api, "o/r", HEAD), equal_to(True))

    def test_another_failure_is_not_an_answer(self) -> None:
        """A 500 is a failed read."""
        api = ghapi.GitHub(run=_server_error, mutate=_server_error)
        with self.assertRaises(subprocess.CalledProcessError):
            dispatchruns.completed(api, "o/r", HEAD)
