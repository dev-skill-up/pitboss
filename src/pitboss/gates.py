"""The review gate of a repository, read from its workflow (keyword: review-gate).

A repository that has ``.github/workflows/review-gate.yml`` merges only after a
review comment in the form that file accepts (pitboss#166); the form is read
from the file on the default branch, never configured, so a worker that follows
``review-form`` writes the comment the gate reads the first time.
"""

import base64
import dataclasses
import json
import re
import subprocess
from typing import AbstractSet, Iterable, Mapping, Sequence

from . import concurrently, config, ghapi
from .markers import Marker

WORKFLOW = ".github/workflows/review-gate.yml"
NOT_FOUND = "HTTP 404"
DEFAULT_CHANGES_NEEDED = "changes needed"
_FIRST_LINE = re.compile(r'raw\[0\] != "([^"\n]+)"')
_APPROVED = re.compile(r'verdicts != \(\["Verdict: ([^"\n]+)"\]')
_CHANGES_NEEDED = re.compile(r'verdicts == \(\["Verdict: ([^"\n]+)"\]')
_REVIEWED = re.compile(r'\["(\w+): " \+ head\]')
_TRUSTED = re.compile(r"TRUSTED = \{([^}\n]*)\}")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Gate:
    """A repository's review gate.

    Attributes:
        form: the form its comments take, None when the workflow is there and
            its form could not be read.
        trusted: the author associations it counts.
    """

    form: config.ReviewForm | None
    trusted: Sequence[str]


def form_of(text: str) -> config.ReviewForm | None:
    """Read the review form a gate workflow accepts.

    Args:
        text: the workflow file.

    Returns:
        The form (the first line, the ``Verdict:`` line and the ``Reviewed:``
        line), or None when the file is not a gate this reads.
    """
    first, approved, reviewed = (
        pattern.search(text) for pattern in (_FIRST_LINE, _APPROVED, _REVIEWED)
    )
    if not (first and approved and reviewed):
        return None
    changes = _CHANGES_NEEDED.search(text)
    return config.ReviewForm(
        lines=[first.group(1), "Verdict: {verdict}", f"{reviewed.group(1)}: {{sha}}"],
        approved=approved.group(1),
        changes_needed=changes.group(1) if changes else DEFAULT_CHANGES_NEEDED,
    )


def gate_of(text: str) -> Gate:
    """Read a gate workflow.

    Args:
        text: the workflow file.

    Returns:
        The gate.
    """
    found = _TRUSTED.search(text)
    names = re.findall(r'"([A-Z_]+)"', found.group(1)) if found else []
    return Gate(
        form=form_of(text), trusted=sorted(names) or sorted(config.DEFAULT_ASSOCIATIONS)
    )


def read(github: ghapi.GitHub, repo: config.Repo) -> Gate | None:
    """Read a repository's gate through its default branch.

    Args:
        github: the API.
        repo: the repository.

    Returns:
        The gate, None when the repository has no such workflow.

    Raises:
        subprocess.CalledProcessError: when the read failed but for a missing file.
    """
    try:
        text = ghapi.get(github, f"repos/{repo.slug}/contents/{WORKFLOW}")
    except subprocess.CalledProcessError as error:
        if ghapi.status_of(error) == NOT_FOUND:
            return None
        raise
    return gate_of(base64.b64decode(json.loads(text)["content"]).decode())


def note(trusted: Iterable[str]) -> str:
    """What a gated repository's review comment must also be.

    Args:
        trusted: the author associations the gate counts.

    Returns:
        One line.
    """
    return (
        "first line exactly as below; each line below once; ASCII only; no code"
        " fences, HTML, link definitions or invisible characters; written by an"
        f" author whose association is {' or '.join(trusted)}, and never edited"
        " (a changed verdict is a new comment)"
    )


def _attempt(github: ghapi.GitHub, repo: config.Repo) -> Gate | str | None:
    try:
        return read(github, repo)
    except subprocess.CalledProcessError as error:
        return f"{WORKFLOW} answered {ghapi.status_of(error)}"


def settled(
    github: ghapi.GitHub,
    settings: config.Config,
    only: AbstractSet[str] | None = None,
) -> config.Config:
    """The configuration with the gates the repositories have.

    A repository with a gate workflow is gated, in the form the workflow
    accepts; one whose workflow could not be read is said (UNREADABLE) and left
    as the configuration has it.

    Args:
        github: the API.
        settings: the configuration.
        only: the ``owner/name`` of the repositories whose gates are read, None
            for every repository; the brief of one item reads its own
            repository's (keyword: item-brief, pitboss#453).

    Returns:
        The configuration, its ``review`` and ``lint.review`` extended.
    """
    repos = chosen(settings, only)
    answers = concurrently.each(lambda repo: _attempt(github, repo), repos)
    found = {repo.slug: each for repo, each in zip(repos, answers)}
    for line in _failures(found):
        print(line)
    review = with_gates(
        settings.review,
        {slug: each for slug, each in found.items() if isinstance(each, Gate)},
    )
    checks = dataclasses.replace(settings.lint, review=review)
    return dataclasses.replace(settings, review=review, lint=checks)


def chosen(
    settings: config.Config, only: AbstractSet[str] | None
) -> Sequence[config.Repo]:
    """The repositories whose gates are read.

    Args:
        settings: the configuration.
        only: the ``owner/name`` to read, None for every repository.

    Returns:
        The repositories.
    """
    everyone = config.repositories(settings)
    return everyone if only is None else [r for r in everyone if r.slug in only]


def _failures(found: Mapping[str, Gate | str | None]) -> Sequence[str]:
    return [
        f"{Marker.UNREADABLE.text} {slug}: {each}: gated as configured"
        for slug, each in found.items()
        if isinstance(each, str)
    ]


def with_gates(review: config.Review, read: Mapping[str, Gate]) -> config.Review:
    """The review settings with some repositories' gates.

    Args:
        review: how reviews are read.
        read: the gate of each repository that has one, by slug.

    Returns:
        The settings, those repositories gated, in the forms their workflows
        accept (a gate whose form cannot be read takes ``gated_form``).
    """
    forms = {slug: each.form for slug, each in read.items() if each.form}
    return dataclasses.replace(
        review,
        gated=frozenset({*review.gated, *read}),
        gate_forms={**review.gate_forms, **forms},
    )
