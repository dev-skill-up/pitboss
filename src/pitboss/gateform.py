"""The review form of a repository, with its gate read (keyword: review-gate)."""

import dataclasses
import subprocess

from . import config, gates, ghapi, repoarg, reviews, running


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class RepoForm:
    """What a repository's review comments must take.

    Attributes:
        repo: the repository.
        gate: its workflow's gate, None when it has none.
        review: the review settings with the gate read added.
        form: the form of its review comments.
    """

    repo: config.Repo
    gate: gates.Gate | None
    review: config.Review
    form: config.ReviewForm


def read(run: running.Run, settings: config.Config, name: str) -> RepoForm:
    """Read the gate of the repository named and the form its reviews take.

    Args:
        run: the runner the reads go through.
        settings: the configuration.
        name: ``name`` or ``owner/name``.

    Returns:
        The form.

    Raises:
        SystemExit: when the gate could not be read.
    """
    repo = repoarg.named_repo(name, settings)
    try:
        gate = gates.read(ghapi.GitHub(run=run, mutate=run), repo)
    except subprocess.CalledProcessError as error:
        status = ghapi.status_of(error)
        raise SystemExit(f"cannot read {gates.WORKFLOW} of {repo.slug}: {status}")
    review = gates.with_gates(settings.review, {repo.slug: gate} if gate else {})
    form = reviews.rules(review, repo.slug)[1]
    return RepoForm(repo=repo, gate=gate, review=review, form=form)
