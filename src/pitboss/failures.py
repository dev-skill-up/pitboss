"""Why a check failed, read from api.github.com only (job logs are not).

A job's log is a redirect to blob storage that a sandbox may block, so the
failed step, the output and the annotations stand in for it.
"""

import subprocess
from typing import Callable, Mapping, Sequence, TypeVar

from . import concurrently, config, ghapi, parsing, shapes

_Found = TypeVar("_Found")
NONE: Sequence[str] = ()


def _fetch(
    github: ghapi.GitHub,
    path: str,
    parse: Callable[[str], _Found],
    empty: _Found,
) -> _Found:
    try:
        return parse(ghapi.get(github, path))
    except subprocess.CalledProcessError:
        return empty


def read(
    github: ghapi.GitHub, repo: config.Repo, check: shapes.CheckRun
) -> shapes.Failure:
    """Read what api.github.com says of a failed check.

    A piece GitHub does not answer (a check that is no Actions job has no
    steps) is left empty.

    Args:
        github: the API.
        repo: the check's repository.
        check: the failed check (for an Actions check its id is the job's).

    Returns:
        The failure.
    """
    prefix = f"repos/{repo.slug}"
    run = f"{prefix}/check-runs/{check.id}"
    job = f"{prefix}/actions/jobs/{check.id}"
    (title, summary), (notes, steps) = concurrently.pair(  # the three reads together
        lambda: _fetch(github, run, parsing.output_text, ("", "")),
        lambda: concurrently.pair(
            lambda: _fetch(
                github, run + "/annotations?per_page=20", parsing.annotations, NONE
            ),
            lambda: _fetch(github, job, parsing.failed_steps, NONE),
        ),
    )
    return shapes.Failure(steps=steps, title=title, summary=summary, annotations=notes)


def read_all(
    github: ghapi.GitHub,
    repo: config.Repo,
    failed: Sequence[shapes.CheckRun],
) -> Mapping[int, shapes.Failure]:
    """Read, for each failed check of a PR, what api.github.com gives of it.

    Args:
        github: the API.
        repo: the PR's repository.
        failed: the failed checks nothing answered (``headchecks.unanswered``).

    Returns:
        Each failed check's id and what was read of it.
    """
    return {check.id: read(github, repo, check) for check in failed}


def describe(failure: shapes.Failure, limit: int = 300) -> str:
    """Say a failure on one line, cut to ``limit`` characters.

    Args:
        failure: what was read.
        limit: the most characters.

    Returns:
        The text (empty when nothing was read).
    """
    parts = [
        *(f"failed step {name!r}" for name in failure.steps),
        failure.title,
        failure.summary,
        *failure.annotations,
    ]
    text = " | ".join(" ".join(part.split()) for part in parts if part.strip())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def lines(
    github: ghapi.GitHub, repo: config.Repo, failed: Sequence[shapes.CheckRun]
) -> Sequence[str]:
    """Say each failed check of a PR for a brief (keyword: failure-text, #524).

    Args:
        github: the API.
        repo: the PR's repository.
        failed: the failed checks nothing answered.

    Returns:
        One line for each: its name, then its failed steps, title, summary and
        annotations, so the worker starts from what failed.
    """
    names = {check.id: check.name for check in failed}
    return [
        f"Failed check {names[number]!r}: {describe(failure, 600)}"
        for number, failure in read_all(github, repo, failed).items()
    ]
