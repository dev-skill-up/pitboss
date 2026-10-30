"""Why a check failed, read from api.github.com only (job logs are not).

A job's log is a redirect to blob storage that a sandbox may block, so the
failed step, the output and the annotations stand in for it.
"""

import subprocess
from typing import Callable, Mapping, Sequence, TypeVar

from . import config, ghapi, parsing, pulls, shapes

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
    title, summary = _fetch(github, run, parsing.output_text, ("", ""))
    notes = _fetch(github, run + "/annotations?per_page=20", parsing.annotations, NONE)
    job = f"{prefix}/actions/jobs/{check.id}"
    steps = _fetch(github, job, parsing.failed_steps, NONE)
    return shapes.Failure(steps=steps, title=title, summary=summary, annotations=notes)


def read_all(
    github: ghapi.GitHub, pull: pulls.PullFacts
) -> Mapping[int, shapes.Failure]:
    """Read, for each failed check of a PR, what api.github.com gives of it.

    Args:
        github: the API.
        pull: the PR.

    Returns:
        Each failed check's id and what was read of it.
    """
    return {
        check.id: read(github, pull.repo, check) for check in pulls.failed_checks(pull)
    }


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
