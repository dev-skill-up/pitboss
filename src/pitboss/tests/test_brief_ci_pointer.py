"""The briefs say a Plan relies on CI for what CI shows (pitboss#179)."""

import unittest

from .. import brief
from .briefmake import pinned, text
from .says import has_none
from .test_brief_nox import PLAN_WRITERS, WORKERS
from .briefmake import PLAN_REVIEWS
from .test_plan_commands import PLAN_RUNNING

PLAN_CI = (
    "CI pointer: a Plan row whose result a CI run of the commit shows asks for no"
    " long local command (a whole suite or build, or anything over `timeout"
    " 598`); it points to CI and names the workflow, the step of the run's log, a"
    " greppable string that step prints (a test name or a line), and how the run"
    " is found for the commit (the run and job URL `actions` gives for the head)."
    " Evidence in the PR body is only for what CI does not show (pitboss#179)."
)
BODY_CI = (
    "CI in the body: for a row the Plan points to CI, the PR body gives no"
    " evidence and holds only the pointer, with the run and job URL found for the"
    " head, the workflow, the step and the greppable string; evidence in the PR"
    " body is only for what CI does not show (pitboss#179)."
)
REVIEW_CI = (
    "CI pointer: a Plan row that asks for a long local command (a whole suite or"
    " build, or anything over `timeout 598`) whose result a CI run of the commit"
    " shows is changes needed; so is a row that points to CI without the"
    " workflow, the step, a greppable string and how the run is found for the"
    " commit (pitboss#179)."
)
NOT_WRITING = tuple(kind for kind in WORKERS if kind not in PLAN_WRITERS)


class TestCiPointer(unittest.TestCase):
    """The three briefs carry the rule, and the Plan review enforces it."""
