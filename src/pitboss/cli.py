"""Commands: ``next``, ``merge``, ``undraft``. Each reads, decides and (for actions) checks state."""

import argparse
import sys
from typing import Any, Callable, Sequence

from . import actions, hub, machine, parse

Get = Callable[[str], Any]
TRUSTED = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})


def read_pull(get: Get, repo: str, number: int) -> parse.Pull:
    """Read one PR.

    Args:
        get: reads a REST path.
        repo: ``owner/name``.
        number: the PR.

    Returns:
        The parsed PR.
    """
    data = get(f"repos/{repo}/pulls/{number}")
    runs = get(f"repos/{repo}/commits/{data['head']['sha']}/check-runs")
    comments = get(f"repos/{repo}/issues/{number}/comments")
    return parse.pull(data, runs, comments, TRUSTED)


def lines(get: Get, repo: str) -> list[str]:
    """One line per open PR and open ticket: its number and its step.

    Args:
        get: reads a REST path.
        repo: ``owner/name``.

    Returns:
        The lines.
    """
    listed = get(f"repos/{repo}/pulls?state=open")
    pulls = [read_pull(get, repo, p["number"]) for p in listed]
    out = [f"PR #{p.number}: {machine.pull_step(p).name}" for p in pulls]
    for issue in get(f"repos/{repo}/issues?state=open"):
        if "pull_request" not in issue:
            t = parse.ticket(issue)
            out.append(f"ticket #{t.number}: {machine.ticket_step(t, pulls).name}")
    return out


def main(argv: Sequence[str] | None = None, get: Get = hub.get, gh: Callable[[str], actions.Hub] = hub.Gh) -> int:
    """Run a command.

    Args:
        argv: the arguments, ``sys.argv`` by default.
        get: reads a REST path.
        gh: makes the writes for a repository.

    Returns:
        The exit status.
    """
    top = argparse.ArgumentParser(prog="pitboss")
    sub = top.add_subparsers(dest="command", required=True)
    sub.add_parser("next").add_argument("repo")
    for word in ("merge", "undraft"):
        one = sub.add_parser(word)
        one.add_argument("repo")
        one.add_argument("number", type=int)
    args = top.parse_args(argv)
    if args.command == "next":
        print("\n".join(lines(get, args.repo)))
        return 0
    act = actions.merge if args.command == "merge" else actions.undraft
    result = act(gh(args.repo), read_pull(get, args.repo, args.number))
    print(result)
    return 0 if isinstance(result, actions.Done) else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
