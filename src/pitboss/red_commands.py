"""The ``analyze-red`` command: a report of a workflow's red runs in a window."""

import argparse
import datetime
import pathlib
from typing import Sequence

from gather.commands import add_argument

from . import (
    ENTRY_DATA,
    config,
    ghapi,
    red,
    redrender,
    redreport,
    repoarg,
    redtranscripts,
)
from .commands import CONFIG_ARGUMENT, NOW_ARGUMENT, load_settings

TRANSCRIPTS = pathlib.Path.home() / ".claude" / "projects"


def _repos(settings: config.Config, repo: config.Repo) -> Sequence[config.Repo]:
    named = {each.slug: each for each in (*config.repositories(settings), repo)}
    return list(named.values())


def _now(args: argparse.Namespace) -> str:
    if args.now:
        return str(args.now)
    return datetime.datetime.now(tz=datetime.UTC).isoformat()


def _sources(
    args: argparse.Namespace, settings: config.Config, repo: config.Repo
) -> redreport.Sources:
    reader = args.safe_run
    github = ghapi.GitHub(run=reader, mutate=reader)
    wanted = _repos(settings, repo)
    failures = ghapi.unreadable(github, [each.slug for each in wanted])
    if repo.slug in failures:
        raise SystemExit(f"cannot read {repo.slug}")
    return redreport.Sources(
        github=github,
        repos=[each for each in wanted if each.slug not in failures],
        transcripts=redtranscripts.directory(pathlib.Path(args.transcripts)),
    )


@ENTRY_DATA.register(
    CONFIG_ARGUMENT,
    NOW_ARGUMENT,
    add_argument("repository"),
    add_argument("workflow", help="the workflow's file name, or its id"),
    add_argument("--last", type=int, default=None, help="the newest N runs"),
    add_argument("--since", default=None, help="the first day (YYYY-MM-DD)"),
    add_argument("--until", default=None, help="the last day (YYYY-MM-DD)"),
    add_argument("--output", required=True, help="the Markdown file to write"),
    add_argument(
        "--transcripts",
        default=str(TRANSCRIPTS),
        help="the directory of the subagents' agent-<id>.jsonl transcripts",
    ),
    name="analyze-red",
)
def analyze_red(args: argparse.Namespace) -> None:
    """Write a Markdown report of a workflow's red runs in a window.

    Read-only on GitHub: it reads runs, jobs, logs, PRs, commits and tickets,
    reads the transcripts, and writes only ``--output``.

    Args:
        args: the parsed arguments.
    """
    settings = load_settings(args)
    window = red.window_of(args.last, args.since, args.until)
    repo = repoarg.named_repo(args.repository, settings)
    sources = _sources(args, settings, repo)
    found = red.analyze(sources.github, repo, args.workflow, window)
    report = redreport.build(sources, found, _now(args))
    pathlib.Path(args.output).write_text(redrender.render(report), encoding="utf-8")
    print(f"{args.output}: {len(found.reds)} red of {found.total} runs")
