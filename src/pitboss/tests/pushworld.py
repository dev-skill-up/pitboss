"""A world's clone set up to push: ``branch-1``, and remotes that push to the origin."""

from . import world
from .fakes import run_git

# ``pitboss push`` at the world's start, for real
PUSH_NOW = ("push", "--now", world.START.isoformat(), "--no-dry-run")


def push_now(here: world.World, *words: str) -> world.Result:
    """Run ``pitboss push`` for real at a world's start.

    Args:
        here: the world.
        *words: the options and git's arguments.

    Returns:
        What the push did.
    """
    return world.again(here, *PUSH_NOW, *words)


def configured(here: world.World, extra: str) -> None:
    """Add to the configuration of a world.

    Args:
        here: the world.
        extra: more TOML.
    """
    with open(here.config, "a", encoding="utf-8") as handle:
        handle.write(extra)


def branch_one(here: world.World) -> None:
    """Point ``branch-1`` of a world's clone at its head.

    Args:
        here: the world.
    """
    run_git(here.clone, "branch", "-f", "branch-1")


def pushes_to_origin(here: world.World, remote: str) -> None:
    """Make a remote of a world's clone push to the world's origin.

    Args:
        here: the world.
        remote: the remote's name.
    """
    run_git(
        here.clone,
        "config",
        f"remote.{remote}.pushurl",
        str(world.origin_of(here.clone)),
    )


def remote_to(here: world.World, name: str, url: str) -> None:
    """Give a world's clone ``branch-1`` and a remote that names a URL.

    The remote pushes to the world's origin, whatever repository the URL names.

    Args:
        here: the world.
        name: the remote's name.
        url: the URL the remote names.
    """
    branch_one(here)
    run_git(here.clone, "remote", "add", name, url)
    pushes_to_origin(here, name)


def elsewhere(here: world.World, url: str) -> None:
    """Give a world's clone ``branch-1`` and a remote ``elsewhere`` that names a URL.

    Args:
        here: the world.
        url: the URL the remote names.
    """
    remote_to(here, "elsewhere", url)
