"""Commands: ``next`` and one command for each action verb."""

import argparse
import dataclasses
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


def act(
    ask: actions.Ask,
    runners: tuple[hub.Runner, hub.Runner],
    target: tuple[str, int, machine.Gates],
) -> actions.Outcome:
    """Run one verb on its subject: a new ticket, a ticket or a PR.

    Args:
        ask: the verb and its text.
        runners: runs ``gh`` and runs ``git``.
        target: the repository, the number of the ticket or PR, and the gates.

    Returns:
        What happened.
    """
    call, git = runners
    repo, number, gates = target
    github = hub.Github(_repo=repo, _run=call)
    if ask.verb in actions.GIT:
        return actions.run(ask, hub.Git(_run=git), read_pull(call, repo, number), gates)
    if ask.verb == actions.NEW:
        return actions.file_ticket(ask, github)
    if ask.verb in actions.TICKET_STEPS:
        issue = j.obj(hub.get(call, f"repos/{repo}/issues/{number}"))
        listed = rows_at(call, f"repos/{repo}/pulls?state=open")
        pulls = [read_pull(call, repo, j.number(p)) for p in listed]
        return actions.run_ticket(ask, github, parse.ticket_from(issue), pulls)
    pr = read_pull(call, repo, number)
    if ask.verb in actions.CITES:
        ask = dataclasses.replace(ask, tickets=ticket_lines(call, repo, pr.body.refs))
    return actions.run(ask, github, pr, gates)


def ticket_lines(call: hub.Runner, repo: str, refs: Sequence[str]) -> Sequence[str]:
    """The ``Ticket: <ref> <digest>`` lines of a review, in the order of the refs.

    Args:
        call: runs ``gh``.
        repo: ``owner/name`` of the PR.
        refs: the tickets its body fixes, as written.

    Returns:
        One line for each ticket: its ref in full and the digest of its body.
    """
    full = sorted(f"{repo}{r}" if r.startswith("#") else r for r in refs)
    out = []
    for each in full:
        slug, number = each.split("#")
        issue = j.obj(hub.get(call, f"repos/{slug}/issues/{number}"))
        out.append(f"Ticket: {each} {parse.text_digest(j.text(issue.get('body')))}")
    return out


def command_line() -> argparse.ArgumentParser:
    """Build the command line.

    Returns:
        The parser: ``next`` and one command for each verb.
    """
    top = argparse.ArgumentParser(prog="pitboss")
    sub = top.add_subparsers(dest="command", required=True)
    for word in ("next", *actions.STEPS, *actions.TICKET_STEPS, actions.NEW):
        one = sub.add_parser(word)
        one.add_argument("repo")
        one.add_argument("--hold", action="store_true")
        one.add_argument("--pressure", action="store_true")
        one.add_argument("number", type=int, nargs="?", default=0)
        if word != "next":
            one.add_argument("--text", default="")
            one.add_argument("--verdict", default="")
            one.add_argument("--plan", default="")
            one.add_argument("--execution", default="")
    return top


def show(shown: Sequence[str], number: int) -> str:
    """Pick the lines of one item, or all of them for number 0.

    Args:
        shown: the lines of ``lines``.
        number: the item, 0 for all.

    Returns:
        The lines, one on each line.
    """
    return "\n".join(x for x in shown if f"#{number}:" in x or not number)


def main(
    argv: Sequence[str] | None = None,
    call: hub.Runner = hub.call_gh,
    git: hub.Runner = hub.call_git,
) -> int:
    """Run a command.

    Args:
        argv: the arguments, ``sys.argv`` by default.
        call: runs ``gh``.
        git: runs ``git``.

    Returns:
        The exit status.
    """
    options = command_line().parse_args(argv)
    gates = machine.Gates(hold=options.hold, pressure=options.pressure)
    if options.command == "next":
        print(show(lines(call, options.repo, gates), options.number))
        return 0
    ask = actions.Ask(
        verb=options.command,
        text=options.text,
        verdict=options.verdict,
        plan=options.plan,
        execution=options.execution,
    )
    result = act(ask, (call, git), (options.repo, options.number, gates))
    print(result)
    return 0 if isinstance(result, actions.Done) else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
