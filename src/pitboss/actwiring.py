"""The act verbs' world as the ``act`` command builds it.

The keyword is act-verbs, pitboss#444.

``owner.json`` beside the slot ledger holds the owner's messages (ids, appended by
whoever relays the owner's words), their dispositions and the cap an ``ack --kind
cap`` set; the verbs read it and ``ack`` writes it back. The order of work reads the
configured slots, the ledger, the open PRs and the open tickets of each priority.
"""

import dataclasses
import json
import pathlib
import subprocess
import sys
from typing import Callable, Sequence

from . import acthub, actinputs, config, configrepos, gateread
from .actcore import Act, Controls, Owner, Questions, cap_of
from .ghapi import GitHub
from .running import Run
from .totaljson import listing, members, read_file, text

OWNER = "owner.json"
CONTROLS = Controls()


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


def quiet(words: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run a command line and keep its output, whatever its status.

    Args:
        words: the command line.

    Returns:
        What it did.
    """
    return subprocess.run(list(words), capture_output=True, text=True, check=False)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Asking:
    """Whom the verbs ask: the owner, and the decisions.

    Attributes:
        owner: the owner's messages.
        questions: the head of the one order and an item's decision.
    """

    owner: Owner
    questions: Questions


def act_of(github: GitHub, settings: config.Config, run: Run, asking: Asking) -> Act:
    """The verbs' world; the verbs post as the login ``gh`` is signed in as.

    Args:
        github: the reading and the writing runner.
        settings: the configuration.
        run: the runner git goes through.
        asking: the owner's messages and the one order.

    Returns:
        The world.
    """
    p90 = gateread.limits(github)
    identity = gateread.identity_of(github)
    given = actinputs.Settings(identity=identity, authors=[identity], max_lines=p90)
    return Act(
        hub=acthub.hub_of(github),
        inputs=actinputs.live_inputs(actinputs.reader(github), given),
        owner=asking.owner,
        repos=configrepos.slugs(settings),
        p90=p90,
        run=run,
        prepush=prepush(quiet),
        questions=asking.questions,
        controls=CONTROLS,
    )
