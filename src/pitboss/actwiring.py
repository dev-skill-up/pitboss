"""The act verbs' world as the ``act`` command builds it.

The keyword is act-verbs, pitboss#444.

``owner.json`` beside the slot ledger holds the owner's messages (ids, appended by
whoever relays the owner's words), their dispositions and the cap an ``ack --kind
cap`` set; the verbs read it and ``ack`` writes it back. The order of work reads the
configured slots, the ledger, the open PRs and the open tickets of each priority.
"""

import json
import pathlib
import subprocess
import sys
from typing import Callable, Sequence

from . import acthub, actinputs, config, configrepos, project, totalverdict
from .actcore import Act, Controls, Hub, Owner, Pull, cap_of
from .ghapi import GitHub, run_json
from .running import Run
from .textparts import split_at
from .totaljson import at, listing, members, name_at, read_file, records, text

SIZES = (
    "query($owner: String!, $name: String!) { repository(owner: $owner, name: $name)"
    " { pullRequests(last: 100, states: MERGED) { nodes { additions deletions } } } }"
)

OWNER = "owner.json"
CONTROLS = Controls(
    verdict=totalverdict.verdict, not_overridable=totalverdict.NOT_OVERRIDABLE
)


def owner_of(path: pathlib.Path) -> Owner:
    """Read the owner's messages.

    Args:
        path: ``owner.json``.

    Returns:
        What it holds; nothing when the file is not there.
    """
    found = members(read_file(path)) if path.exists() else {}
    dispositions = {
        key: text(value) for key, value in members(found.get("dispositions")).items()
    }
    messages = tuple(text(each) for each in listing(found.get("messages")))
    limit = int(str(found.get("cap", 0)))
    return Owner(
        messages=messages, dispositions=dispositions, caps={"": limit} if limit else {}
    )


def write_owner(path: pathlib.Path, owner: Owner) -> None:
    """Write the owner's messages back.

    Args:
        path: ``owner.json``.
        owner: what to write.
    """
    words = {
        "messages": list(owner.messages),
        "dispositions": dict(owner.dispositions),
        "cap": cap_of(owner),
    }
    path.write_text(
        json.dumps(words, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def prepush(
    run: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
) -> Callable[[], tuple[int, str]]:
    """The pre-push check: the repository's ``[[pre_push]]`` checks.

    As the hook runs them.

    Args:
        run: runs a command line without raising.

    Returns:
        What runs it and gives its status and output.
    """

    def check() -> tuple[int, str]:
        done = run([sys.executable, "-m", "pitboss", "hook", "pre-push"])
        return done.returncode, done.stdout + done.stderr

    return check


def _p90(github: GitHub, repo: str) -> int:
    # the size of 90 of 100 merged PRs; an unread size is 0, so every size needs
    # a ruling
    owner, name = split_at(repo, "/")
    words = ["gh", "api", "graphql", "-f", f"query={SIZES}"]
    words += ["-f", f"owner={owner}", "-f", f"name={name}"]
    try:
        answer = run_json(github, words)
    except Exception:  # noqa: B902 - an unread size is 0
        answer = {}
    nodes = records(at(answer, "data", "repository", "pullRequests", "nodes"))
    sizes = sorted(
        sum(int(str(each.get(key, 0))) for key in ("additions", "deletions"))
        for each in nodes
    )
    return sizes[(9 * len(sizes) + 9) // 10 - 1] if sizes else 0


def limits(github: GitHub) -> Callable[[str], int]:
    """Each repository's 90th percentile of the lines its last 100 merged PRs changed.

    Args:
        github: the reading runner.

    Returns:
        What reads a repository's percentile (0 when it has no merged PR) once,
        when first asked.
    """
    found: dict[str, int] = {}

    def limit(repo: str) -> int:
        if repo not in found:
            found[repo] = _p90(github, repo)
        return found[repo]

    return limit


def quiet(words: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run a command line and keep its output, whatever its status.

    Args:
        words: the command line.

    Returns:
        What it did.
    """
    return subprocess.run(list(words), capture_output=True, text=True, check=False)


def act_of(
    github: GitHub,
    settings: config.Config,
    owner: Owner,
    run: Run,
    dispatch: Callable[[], project.DispatchAnswer],
) -> Act:
    """The verbs' world; the verbs post as the login ``gh`` is signed in as.

    Args:
        github: the reading and the writing runner.
        settings: the configuration.
        owner: the owner's messages.
        run: the runner git goes through.
        dispatch: gives the head of the one order (``onepath.dispatch``).

    Returns:
        The world.
    """
    hub = acthub.hub_of(github)
    repos = configrepos.slugs(settings)
    p90 = limits(github)
    identity = identity_of(github)
    given = actinputs.Settings(identity=identity, authors=[identity], max_lines=p90)
    return Act(
        hub=hub,
        inputs=actinputs.live_inputs(actinputs.reader(github), given),
        owner=owner,
        repos=repos,
        p90=p90,
        run=run,
        prepush=prepush(quiet),
        dispatch=dispatch,
        controls=CONTROLS,
    )


def identity_of(github: GitHub) -> str:
    """The login ``gh`` is signed in as.

    Args:
        github: the reading runner.

    Returns:
        The login.
    """
    return name_at(json.loads(github.run(["gh", "api", "user"]).stdout), "login")
