"""What the red-run analysis reads about one red run, as dataclasses."""

import dataclasses
import enum
from typing import Sequence

from . import shapes


class RedClass(enum.Enum):
    """Why a run was red, by the first cause named; the list is fixed.

    A report names one class for each red run, so two reports compare. The
    value is the class's name in the report.

    Attributes:
        UNLISTED_FIXTURE: a fixture that no group lists, so CI never ran it.
        STALE_ANCHOR_OR_EXPECT: an anchor or expected output out of date.
        LOCAL_ENVIRONMENT_DIFFERS: the local run differs from CI's conditions.
        PIN_MOVE: a pinned input moved.
        PRODUCT_CHANGE_BROKE_UNRUN_SPECS: a product change broke specs not run.
        KNOWN_BAD_TEST: a test with a ticket that is known to fail.
        NEW_TEST_WRONG_UNDER_CI: a new test wrong under CI's conditions.
        EXTERNAL_INFRASTRUCTURE: a service outside the project failed.
        OWN_RELEASE_OR_CONFIGURATION_BUG: our release or configuration is wrong.
        NOT_ESTABLISHED: the cause is not established.
    """

    UNLISTED_FIXTURE = "unlisted fixture"
    STALE_ANCHOR_OR_EXPECT = "stale anchor or expect"
    LOCAL_ENVIRONMENT_DIFFERS = "local environment differs from CI"
    PIN_MOVE = "pin move"
    PRODUCT_CHANGE_BROKE_UNRUN_SPECS = "product change broke unrun specs"
    KNOWN_BAD_TEST = "known-bad test (ticketed)"
    NEW_TEST_WRONG_UNDER_CI = "new test wrong under CI's conditions"
    EXTERNAL_INFRASTRUCTURE = "external infrastructure"
    OWN_RELEASE_OR_CONFIGURATION_BUG = "own release or configuration bug"
    NOT_ESTABLISHED = "not established"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Step:
    """A step of a job.

    Attributes:
        number: its number in the job.
        name: its name.
        conclusion: its conclusion, empty until it completes.
        started_at: when it started (ISO 8601), empty if it never did.
        completed_at: when it ended (ISO 8601), empty if it never did.
    """

    number: int
    name: str
    conclusion: str
    started_at: str
    completed_at: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Job:
    """A job of a run.

    Attributes:
        id: its id.
        name: its name.
        conclusion: its conclusion, empty until it completes.
        url: its page.
        started_at: when it started (ISO 8601).
        completed_at: when it ended (ISO 8601), empty until it does.
        steps: its steps.
    """

    id: int
    name: str
    conclusion: str
    url: str
    started_at: str
    completed_at: str
    steps: Sequence[Step]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class FirstError:
    """The first error line of a failed job's log.

    Attributes:
        job: the job whose log it is.
        step: the step that failed in that job.
        line: its line number in the job's log.
        text: the line.
        inferred_from: the run whose identical commit gave this line, when
            this run's own log was not readable; else zero.
    """

    job: Job
    step: Step
    line: int
    text: str
    inferred_from: int


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PullState:
    """What became of a PR.

    Attributes:
        number: its number.
        title: its title.
        url: its page.
        merged: whether it merged.
        state: ``open`` or ``closed``.
    """

    number: int
    title: str
    url: str
    merged: bool
    state: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class FixCommit:
    """The commit pushed to the PR's branch after a red run's head.

    Attributes:
        sha: its SHA.
        message: its message.
        date: when it was committed (ISO 8601).
        merge: whether it is a merge (two parents or more).
        files: the files it changes.
    """

    sha: str
    message: str
    date: str
    merge: bool
    files: Sequence[str]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class RunFacts:
    """What GitHub says about one red run.

    Attributes:
        run: the run.
        jobs: its jobs.
        error: its first error line, if its log was read.
        log_note: why there is no first error line, else empty.
        pull: its PR, if it has one.
        later: the later runs of the workflow on its branch, oldest first.
        fix: the commit pushed after its head, if any.
    """

    run: shapes.WindowRun
    jobs: Sequence[Job]
    error: FirstError | None
    log_note: str
    pull: PullState | None
    later: Sequence[shapes.WindowRun]
    fix: FixCommit | None
