"""A scratch repository on a fake GitHub: fixtures, finished runs and running ones."""

import enum
import tomllib
from typing import MutableMapping, Sequence

from .. import ghapi, scratch, scratchconfig
from . import fakes, world

SLUG = "bats-lang/relock-scratch"
REPO = f"repos/{SLUG}"
NOW = world.START
OLD = "2029-12-31T00:00:00+00:00"
YOUNG = "2029-12-31T23:55:00+00:00"
TABLE = f"""
[scratch]
repositories = ["{SLUG}"]
keep = ["{SLUG}#29"]
branches = ["scratch-run-1", "scratch-run-2"]
"""


class Status(enum.Enum):
    """The status of a workflow run.

    Attributes:
        FINISHED: it completed.
        RUNNING: it is going.
    """

    FINISHED = enum.auto()
    RUNNING = enum.auto()


FINISHED, RUNNING = Status.FINISHED, Status.RUNNING


def sha_of(number: int) -> str:
    """The head commit of a scratch PR.

    Args:
        number: the PR's number.

    Returns:
        Forty hex digits.
    """
    return f"{number:x}".rjust(40, "e")


def pull(
    number: int, branch: str, *, repo: str = SLUG, created: str = OLD
) -> MutableMapping[str, object]:
    """A scratch PR as the list of open PRs gives it.

    Args:
        number: its number.
        branch: its head branch.
        repo: the repository its head is in.
        created: when it was opened.

    Returns:
        The JSON.
    """
    head = {"sha": sha_of(number), "ref": branch, "repo": {"full_name": repo}}
    return fakes.pull_body(number, head=head, created_at=created)


def runs(number: int, *statuses: Status) -> MutableMapping[str, object]:
    """The workflow runs of a scratch PR's head, as the fake GitHub holds them.

    Args:
        number: the PR's number.
        *statuses: the status of each run.

    Returns:
        The JSON, keyed by the paged path it is read from.
    """
    path = f"{REPO}/actions/runs?head_sha={sha_of(number)}"
    found = [
        {
            "id": number * 10 + index,
            "status": "completed" if status is FINISHED else "in_progress",
            "conclusion": "success" if status is FINISHED else None,
            "created_at": OLD,
            "head_branch": "x",
        }
        for index, status in enumerate(statuses)
    ]
    return {fakes.page(path): {"workflow_runs": found}}


# 29 is the fixture; 30 and 38 are finished from run branches; 31 runs; 32 is
# finished from a branch that is no run branch, 33 runs on one; 34 is a minute
# old and has no run yet, 35 is old and has none; 36 is finished with its head
# in a fork; 37 runs on the branch 30 used; 39 and 40 are finished on one branch.
SCENE = (
    (pull(29, "relock-hold/2026-10-01"), ()),
    (pull(30, "scratch-run-1"), (FINISHED, FINISHED)),
    (pull(31, "scratch-run-2"), (FINISHED, RUNNING)),
    (pull(32, "old-junk"), (FINISHED,)),
    (pull(33, "other-junk"), (RUNNING,)),
    (pull(34, "scratch-run-2", created=YOUNG), ()),
    (pull(35, "scratch-run-2"), ()),
    (pull(36, "scratch-run-2", repo="someone/fork"), (FINISHED,)),
    (pull(37, "scratch-run-1"), (RUNNING,)),
    (pull(39, "shared-junk"), (FINISHED,)),
    (pull(40, "shared-junk"), (FINISHED,)),
)


def bodies_of(
    scene: Sequence[tuple[MutableMapping[str, object], Sequence[Status]]] = SCENE,
) -> MutableMapping[str, object]:
    """The fake GitHub of a scratch repository holding the PRs of a scene.

    Args:
        scene: each open PR, and the statuses of the runs of its head.

    Returns:
        The canned bodies, with an answer for every change.
    """
    found: MutableMapping[str, object] = {
        fakes.page(f"{REPO}/pulls?state=open"): [each for each, _ in scene]
    }
    for each, statuses in scene:
        number = int(str(each["number"]))
        if number == 29:
            continue  # a fixture is never read for its runs
        found.update(runs(number, *statuses))
        found[f"PATCH {REPO}/pulls/{number}"] = {}
    for branch in ("scratch-run-1", "scratch-run-2", "old-junk", "shared-junk"):
        found[f"DELETE {REPO}/git/refs/heads/{branch}"] = ""
    return found


def source_of(api: ghapi.GitHub, table: str = TABLE) -> scratch.Source:
    """What reading the scratch repositories of a configuration needs.

    Args:
        api: the API.
        table: the TOML of the configuration.

    Returns:
        The source, at the scene's time.
    """
    found = scratchconfig.from_document(tomllib.loads(table), "bats-lang")
    return scratch.Source(github=api, scratch=found, now=NOW)


def acted(api: ghapi.GitHub) -> Sequence[str]:
    """The changes a fake API was asked to make.

    Args:
        api: an API made by ``fakes.github``.

    Returns:
        ``METHOD path`` for each change, in order.
    """
    return [
        f"{call[3]} {call[-1]}"
        for call in fakes.calls_of(api)
        if call[:3] == ["gh", "api", "-X"]
    ]
