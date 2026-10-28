"""The first error line of a job's log, and the signature that groups reds."""

import re
from typing import Sequence

from . import redshapes

ERROR_MARK = "##[error]"
_ERROR_WORD = re.compile(r"\b(error|failed|failure|fatal)\b", re.IGNORECASE)
_STAMP = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z\s*")
_VARIABLE = re.compile(r"[0-9a-f]{7,40}|\d+", re.IGNORECASE)
SIGNATURE_LENGTH = 120
FAILED_CONCLUSIONS = frozenset({"failure", "timed_out"})


def failing_step(job: redshapes.Job) -> redshapes.Step | None:
    """Find the first step of a job that failed.

    Args:
        job: the job.

    Returns:
        The step, or ``None`` when no step is marked failed.
    """
    failed = [step for step in job.steps if step.conclusion == "failure"]
    return failed[0] if failed else None


def failed_jobs(jobs: Sequence[redshapes.Job]) -> Sequence[redshapes.Job]:
    """The jobs that failed, earliest start first.

    Args:
        jobs: a run's jobs.

    Returns:
        The failed ones.
    """
    failed = [job for job in jobs if job.conclusion in FAILED_CONCLUSIONS]
    return sorted(failed, key=lambda job: job.started_at)


def first_error(log: str) -> tuple[int, str] | None:
    """Find the first error line of a log.

    A ``##[error]`` line wins; failing that the first line with an error word.

    Args:
        log: the job's log.

    Returns:
        The 1-based line number and the line, or ``None`` when there is none.
    """
    lines = list(enumerate(log.splitlines(), start=1))
    marked = [(number, text) for number, text in lines if ERROR_MARK in text]
    worded = [(number, text) for number, text in lines if _ERROR_WORD.search(text)]
    found = marked or worded
    if not found:
        return None
    number, text = found[0]
    return number, _STAMP.sub("", text.split(ERROR_MARK, 1)[-1].strip())


def signature(step: str, error: str) -> str:
    """The key that two reds of one cause share.

    Numbers and hex ids are blanked, so a run id or a commit does not make
    two lines differ.

    Args:
        step: the failing step's name.
        error: the first error line.

    Returns:
        The signature.
    """
    blanked = _VARIABLE.sub("#", error.lower())
    return f"{step.lower()}: {blanked}"[:SIGNATURE_LENGTH]


def failing(
    jobs: Sequence[redshapes.Job],
) -> tuple[redshapes.Job, redshapes.Step] | None:
    """Find the first failed job that has a failed step.

    Args:
        jobs: a run's jobs.

    Returns:
        The job and its step, or ``None``.
    """
    for candidate in failed_jobs(jobs):
        step = failing_step(candidate)
        if step is not None:
            return candidate, step
    return None


_FILE = re.compile(r"[\w./-]+\.(?:py|bats|ts|js|sh|yml|toml)")


def error_files(error: str) -> Sequence[str]:
    """The file names an error line mentions.

    Args:
        error: the line.

    Returns:
        The names, in order.
    """
    return _FILE.findall(error)
