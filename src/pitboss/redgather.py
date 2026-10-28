"""Reading one red run's facts from GitHub (read-only, through ``ghapi``)."""

import dataclasses
import subprocess
import urllib.parse
from typing import Sequence

from . import config, ghapi, parsing, redlog, redparsing, redshapes, shapes

RUN_PAGES = 3


def _why(error: subprocess.CalledProcessError) -> str:
    lines = str(error.stderr or "").strip().splitlines()
    return lines[0] if lines else f"gh exited {error.returncode}"


def read_error(
    github: ghapi.GitHub, repo: config.Repo, jobs: Sequence[redshapes.Job]
) -> tuple[redshapes.FirstError | None, str]:
    """Read the first error line of the run's first failed job.

    Args:
        github: the API.
        repo: the repository.
        jobs: the run's jobs.

    Returns:
        The line, or ``None`` with the reason there is none.
    """
    found = redlog.failing(jobs)
    if found is None:
        return None, "no job has a failed step"
    culprit, step = found
    try:
        log = ghapi.get(github, f"repos/{repo.slug}/actions/jobs/{culprit.id}/logs")
    except subprocess.CalledProcessError as error:
        return None, f"log of job {culprit.id} not readable: {_why(error)}"
    line = redlog.first_error(log)
    if line is None:
        return None, f"log of job {culprit.id} has no error line"
    number, text = line
    error_line = redshapes.FirstError(
        job=culprit, step=step, line=number, text=text, inferred_from=0
    )
    return error_line, ""


def _fix(
    github: ghapi.GitHub, repo: config.Repo, number: int, head: str
) -> redshapes.FixCommit | None:
    commits = ghapi.pages(
        github, f"repos/{repo.slug}/pulls/{number}/commits", redparsing.pull_commits
    )
    shas = [commit.sha for commit in commits]
    if head not in shas or head == shas[-1]:
        return None
    fix = commits[shas.index(head) + 1]
    files = redparsing.commit_files(
        ghapi.get(github, f"repos/{repo.slug}/commits/{fix.sha}")
    )
    return dataclasses.replace(fix, files=files)


def _later(
    github: ghapi.GitHub, repo: config.Repo, workflow: str, run: shapes.WindowRun
) -> Sequence[shapes.WindowRun]:
    branch = urllib.parse.quote(run.branch, safe="")
    path = f"{ghapi.workflow_runs_path(repo.slug, workflow)}?branch={branch}"
    found = ghapi.pages(github, path, parsing.window_runs, limit=RUN_PAGES)
    return sorted(
        (each for each in found if each.created_at > run.created_at),
        key=lambda each: each.created_at,
    )


def _pull(github: ghapi.GitHub, repo: config.Repo, number: int) -> redshapes.PullState:
    return redparsing.pull_state(ghapi.get(github, f"repos/{repo.slug}/pulls/{number}"))


def read_facts(
    github: ghapi.GitHub, repo: config.Repo, workflow: str, run: shapes.WindowRun
) -> redshapes.RunFacts:
    """Read what GitHub says about one red run.

    Args:
        github: the API.
        repo: the repository.
        workflow: the workflow's file name or id.
        run: the red run.

    Returns:
        The facts.
    """
    jobs = ghapi.pages(
        github, f"repos/{repo.slug}/actions/runs/{run.id}/jobs", redparsing.jobs
    )
    error, note = read_error(github, repo, jobs)
    number = run.pulls[0] if run.pulls else 0
    return redshapes.RunFacts(
        run=run,
        jobs=jobs,
        error=error,
        log_note=note,
        pull=_pull(github, repo, number) if number else None,
        later=_later(github, repo, workflow, run),
        fix=_fix(github, repo, number, run.head_sha) if number else None,
    )


def infer(facts: Sequence[redshapes.RunFacts]) -> Sequence[redshapes.RunFacts]:
    """Give a run with no readable log the first error of an identical run.

    Identical means the same commit and the same failing step.

    Args:
        facts: every red run's facts.

    Returns:
        The facts, with the inferred lines marked by ``inferred_from``.
    """
    known = {
        (each.run.head_sha, each.error.step.name): each
        for each in reversed(facts)
        if each.error is not None
    }
    return [_inferred(each, known) for each in facts]


def _inferred(
    each: redshapes.RunFacts,
    known: dict[tuple[str, str], redshapes.RunFacts],
) -> redshapes.RunFacts:
    step = redlog.failing(each.jobs)
    twin = known.get((each.run.head_sha, step[1].name)) if step else None
    if each.error is not None or step is None or twin is None or twin.error is None:
        return each
    borrowed = dataclasses.replace(
        twin.error, job=step[0], step=step[1], inferred_from=twin.run.id
    )
    return dataclasses.replace(each, error=borrowed)
