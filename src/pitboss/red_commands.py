"""The ``analyze-red`` command: a report of a workflow's red runs in a window."""

import argparse
import pathlib

from gather.commands import add_argument

from . import ENTRY_DATA, config, ghapi, red
from .commands import CONFIG_ARGUMENT, load_settings


@ENTRY_DATA.register(
    CONFIG_ARGUMENT,
    add_argument("repository"),
    add_argument("workflow", help="the workflow's file name, or its id"),
    add_argument("--last", type=int, default=None, help="the newest N runs"),
    add_argument("--since", default=None, help="the first day (YYYY-MM-DD)"),
    add_argument("--until", default=None, help="the last day (YYYY-MM-DD)"),
    add_argument("--output", required=True, help="the Markdown file to write"),
    name="analyze-red",
)
def analyze_red(args: argparse.Namespace) -> None:
    """Write a Markdown report of a workflow's red runs in a window.

    Read-only on GitHub: it reads runs and writes only ``--output``.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: when the repository cannot be read.
    """
    repo = config.named_repo(args.repository, load_settings(args))
    window = red.window_of(args.last, args.since, args.until)
    reader = args.safe_run
    github = ghapi.GitHub(run=reader, mutate=reader)
    if ghapi.unreadable(github, [repo.slug]):
        raise SystemExit(f"cannot read {repo.slug}")
    found = red.analyze(github, repo, args.workflow, window)
    pathlib.Path(args.output).write_text(red.render(found), encoding="utf-8")
    print(f"{args.output}: {len(found.reds)} red of {found.total} runs")
