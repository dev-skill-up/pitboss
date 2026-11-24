"""Arguments a command takes, with a world of fakes (keyword: fake-args, #524)."""

import argparse
import typing
from collections.abc import Mapping

from gather.commands import ProcessRunner

from .. import shell
from .fakes import Output


def _unrun(*_words: object, **_keywords: object) -> Output:
    return Output(stdout="")


def args(
    *,
    run: object = None,
    safe_run: object = None,
    env: Mapping[str, str] | None = None,
    orig_run: object = None,
    **given: object,
) -> argparse.Namespace:
    """Arguments a command takes, with the world its keywords name.

    Args:
        run: the runner of ``run``; one that answers nothing when None.
        safe_run: the runner of ``safe_run``; one that answers nothing when None.
        env: the environment; empty when None.
        orig_run: the runner both are made from; one that answers nothing when None.
        **given: the other arguments.

    Returns:
        The arguments, with a ``world``.
    """
    made = shell.World(
        run=_runner(run),
        safe_run=_runner(safe_run),
        env={} if env is None else env,
        orig_run=_original(orig_run),
    )
    return argparse.Namespace(world=made, **given)


def _runner(given: object) -> shell.ProcessRun:
    return typing.cast(shell.ProcessRun, given or _unrun)  # noqa: SLD203


def _original(given: object) -> ProcessRunner:
    return typing.cast(ProcessRunner, given or _unrun)  # noqa: SLD203
