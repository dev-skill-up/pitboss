"""The steps the act verbs share (keyword: act-verbs)."""

from typing import Mapping, Sequence

from .actcore import Act, Change, Options, Target, head_of, option, pull_of


def options_of(options: Options, *names: str) -> Sequence[str]:
    """A verb's options that must be given.

    Args:
        options: the options.
        *names: the options, in order.

    Returns:
        Their values, in the order named.
    """
    return [option(options, name) for name in names]


def disarm_first(act: Act, target: Target, why: str) -> None:
    """Disarm a PR with the controls' disarm, before an input of its verdict changes.

    Args:
        act: the verb's world.
        target: the PR.
        why: the reason, recorded.
    """
    act.controls.disarm(act, target, why)


def repo_write(act: Act, repo: str, kind: str, fields: Mapping[str, str]) -> str:
    """Make one write to a repository (no PR or issue of it).

    Args:
        act: the verb's world.
        repo: the repository.
        kind: what is written.
        fields: what the write carries.

    Returns:
        What GitHub answered.
    """
    return act.hub.write(Change(kind=kind, repo=repo, fields=fields))


def head_now(act: Act, target: Target) -> str:
    """A PR's head commit, read now.

    Args:
        act: the verb's world.
        target: the PR.

    Returns:
        Its sha.
    """
    return head_of(pull_of(act, target))
