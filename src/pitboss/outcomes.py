"""What became of the branches of each repository the workspace's checkouts are of."""

import subprocess
from typing import Iterable, Mapping

from . import concurrently, config, configrepos, ghapi, local, shapes


def outcomes_of(
    github: ghapi.GitHub, settings: config.Config, slugs: Iterable[str]
) -> Mapping[str, Mapping[str, shapes.Outcome]]:
    """The branch outcomes of each repository that can be read.

    A clone of a repository the configuration does not name is asked about as
    well, since its branches' PRs decide it as much as any other's.

    Args:
        github: the API.
        settings: the configuration.
        slugs: the repositories' ``owner/name``; empty ones are skipped.

    Returns:
        The outcomes of each repository whose PRs could be read.
    """
    owner = settings.project.repo.owner
    repos = {repo.slug: repo for repo in configrepos.repositories(settings)}
    wanted = sorted({slug for slug in slugs if slug})

    def attempt(slug: str) -> Mapping[str, shapes.Outcome] | None:
        repo = repos.get(slug) or config.parse_repo(slug, owner)
        try:
            return local.read_outcomes(github, repo)
        except subprocess.CalledProcessError:
            return None

    read = concurrently.each(attempt, wanted)
    return {slug: found for slug, found in zip(wanted, read) if found is not None}
