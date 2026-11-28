"""Commands: ``next`` and one command for each action verb."""

import argparse
import sys
from collections.abc import Sequence

from . import actions, hub, machine, parse
from . import jsonish as j

TRUSTED = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})


def rows_at(call: hub.Runner, path: str) -> Sequence[j.JsonObject]:
    """Read a REST path as a list of objects.

    Args:
        call: runs ``gh``.
        path: the path.

    Returns:
        The objects.
    """
    return j.rows(hub.get(call, path))


def read_pull(call: hub.Runner, repo: str, number: int) -> parse.Pull:
    """Read one PR.

    Args:
        call: runs ``gh``.
        repo: ``owner/name``.
        number: the PR.

    Returns:
        The parsed PR.
    """
    root = f"repos/{repo}"
    data = j.obj(hub.get(call, f"{root}/pulls/{number}"))
    sha = j.text(j.obj(data.get("head")).get("sha"))
    comments = rows_at(call, f"{root}/issues/{number}/comments")
    paths = [
        j.text(f.get("filename")) for f in rows_at(call, f"{root}/pulls/{number}/files")
    ]
    thread = parse.thread_of(comments, TRUSTED)
    return parse.pull_from(
        data, rows_at(call, f"{root}/commits/{sha}/check-runs"), thread, paths
    )


def lines(call: hub.Runner, repo: str, gates: machine.Gates) -> Sequence[str]:
    """One line per open PR and open ticket: its number and its step.

    Args:
        call: runs ``gh``.
        repo: ``owner/name``.
        gates: holds and pressure.

    Returns:
        The lines.
    """
    listed = rows_at(call, f"repos/{repo}/pulls?state=open")
    pulls = [read_pull(call, repo, j.number(p)) for p in listed]
    out = [f"PR #{p.number}: {machine.pull_step(p, gates).name}" for p in pulls]
    for issue in rows_at(call, f"repos/{repo}/issues?state=open"):
        if "pull_request" not in issue:
            t = parse.ticket_from(issue)
            out.append(f"ticket #{t.number}: {machine.ticket_step(t, pulls).name}")
    return out


def command_line() -> argparse.ArgumentParser:
    """Build the command line.

    Returns:
        The parser: ``next`` and one command for each verb.
    """
    top = argparse.ArgumentParser(prog="pitboss")
    sub = top.add_subparsers(dest="command", required=True)
    for word in ("next", *actions.STEPS):
        one = sub.add_parser(word)
        one.add_argument("repo")
        one.add_argument("--hold", action="store_true")
        one.add_argument("--pressure", action="store_true")
        if word != "next":
            one.add_argument("number", type=int)
            one.add_argument("--text", default="")
    return top


def main(argv: Sequence[str] | None = None, call: hub.Runner = hub.call_gh) -> int:
    """Run a command.

    Args:
        argv: the arguments, ``sys.argv`` by default.
        call: runs ``gh``.

    Returns:
        The exit status.
    """
    options = command_line().parse_args(argv)
    gates = machine.Gates(hold=options.hold, pressure=options.pressure)
    if options.command == "next":
        print("\n".join(lines(call, options.repo, gates)))
        return 0
    pr = read_pull(call, options.repo, options.number)
    ask = actions.Ask(verb=options.command, text=options.text)
    result = actions.run(ask, hub.Github(_repo=options.repo, _run=call), pr, gates)
    print(result)
    return 0 if isinstance(result, actions.Done) else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
