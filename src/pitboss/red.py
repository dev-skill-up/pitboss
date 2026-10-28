"""The red-run analysis: which runs of a workflow failed in a window, and as what.

Read-only on GitHub: the analysis reads runs and writes one Markdown file.
"""

import dataclasses
import datetime
import enum
import urllib.parse
from typing import Sequence

from . import config, ghapi, parsing, shapes

PAGE_SIZE = ghapi.PAGE_SIZE
READ_ONLY = (
    "This report is read-only on GitHub: it only reads (`gh api` GETs) and"
    " changes nothing there."
)


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
class LastRuns:
    """The newest runs of the workflow, whatever their conclusion.

    Attributes:
        count: how many.
    """

    count: int


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class DateRange:
    """The runs created on these days, both ends included.

    Attributes:
        since: the first day.
        until: the last day.
    """

    since: datetime.date
    until: datetime.date


Window = LastRuns | DateRange


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Analysis:
    """The runs of a window, and the red ones among them.

    Attributes:
        repo: the repository.
        workflow: the workflow's file name or id.
        window: the window.
        total: how many runs the window holds.
        reds: the red runs, newest first.
    """

    repo: config.Repo
    workflow: str
    window: Window
    total: int
    reds: Sequence[shapes.WindowRun]


def _date(text: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        raise SystemExit(f"not a date (YYYY-MM-DD): {text}") from None


def window_of(last: int | None, since: str | None, until: str | None) -> Window:
    """Make the window the command line names.

    Args:
        last: the count of runs, if given.
        since: the first day, if given.
        until: the last day, if given.

    Returns:
        The window.

    Raises:
        SystemExit: when the arguments do not name exactly one window.
    """
    if last is not None and since is None and until is None and last >= 1:
        return LastRuns(count=last)
    if last is None and since is not None and until is not None:
        return DateRange(since=_date(since), until=_date(until))
    raise SystemExit("give --last N (at least 1), or --since DATE and --until DATE")


def read_window(
    github: ghapi.GitHub, repo: config.Repo, workflow: str, window: Window
) -> Sequence[shapes.WindowRun]:
    """Read the runs of a workflow in a window.

    Args:
        github: the API.
        repo: the repository.
        workflow: the workflow's file name or id.
        window: the window.

    Returns:
        The runs, newest first.
    """
    name = urllib.parse.quote(workflow, safe="")
    path = f"repos/{repo.slug}/actions/workflows/{name}/runs"
    if isinstance(window, LastRuns):
        pages = -(-window.count // PAGE_SIZE)
        found = ghapi.pages(github, path, parsing.window_runs, limit=pages)
        return found[: window.count]
    days = f"{window.since.isoformat()}..{window.until.isoformat()}"
    return ghapi.pages(github, f"{path}?created={days}", parsing.window_runs)


def analyze(
    github: ghapi.GitHub, repo: config.Repo, workflow: str, window: Window
) -> Analysis:
    """Read the window and pick out the red runs.

    Args:
        github: the API.
        repo: the repository.
        workflow: the workflow's file name or id.
        window: the window.

    Returns:
        The analysis.
    """
    runs = read_window(github, repo, workflow, window)
    reds = [run for run in runs if run.conclusion in shapes.RED_CONCLUSIONS]
    return Analysis(
        repo=repo, workflow=workflow, window=window, total=len(runs), reds=reds
    )


def describe(window: Window) -> str:
    """Say a window in words.

    Args:
        window: the window.

    Returns:
        Its description.
    """
    if isinstance(window, LastRuns):
        return f"the newest {window.count} runs"
    return f"runs created from {window.since.isoformat()} to {window.until.isoformat()}"


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def _row(repo: config.Repo, run: shapes.WindowRun) -> str:
    site = f"https://github.com/{repo.slug}"
    pulls = ", ".join(f"[#{number}]({site}/pull/{number})" for number in run.pulls)
    return (
        f"| [{run.id}]({run.url}) | {pulls or 'none'} | {_cell(run.branch)}"
        f" | [{run.head_sha[:7]}]({site}/commit/{run.head_sha})"
        f" | {run.conclusion} | {run.created_at}"
        f" | {RedClass.NOT_ESTABLISHED.value} |"
    )


def render(found: Analysis) -> str:
    """Write the report as Markdown.

    Args:
        found: the analysis.

    Returns:
        The report: the read-only note, the window, and the summary table.
    """
    lines = [
        f"# Red runs of {found.workflow} in {found.repo.slug}",
        "",
        READ_ONLY,
        "",
        f"Window: {describe(found.window)}: {found.total} runs, {len(found.reds)} red.",
        "",
        "## Summary",
        "",
        "| Run | PR | Branch | Commit | Conclusion | Started | Class |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        *(_row(found.repo, run) for run in found.reds),
        "",
    ]
    return "\n".join(lines)
