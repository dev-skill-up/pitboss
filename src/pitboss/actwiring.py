"""The act verbs' world as the ``act`` command builds it (keyword: act-verbs, pitboss#444).

``owner.json`` beside the slot ledger holds the owner's messages (ids, appended by
whoever relays the owner's words), their dispositions and the cap an ``ack --kind
cap`` set; the verbs read it and ``ack`` writes it back. The order of work reads the
configured slots, the ledger, the open PRs and the open tickets of each priority.
"""

import collections.abc
import dataclasses
import json
import pathlib
import subprocess
import sys
from typing import Callable, Iterator, Sequence

from . import acthub, actinputs, config, dispatchnext, ledger
from .actcore import Act, Controls, Hub, Owner
from .running import Run
from .totaljson import mapping, name_at, records, text

SIZES = (
    "query($owner: String!, $name: String!) { repository(owner: $owner, name: $name)"
    " { pullRequests(last: 100, states: MERGED) { nodes { additions deletions } } } }"
)

OWNER = "owner.json"


def owner_of(path: pathlib.Path) -> Owner:
    """Read the owner's messages.

    Args:
        path: ``owner.json``.

    Returns:
        What it holds; nothing when the file is not there.
    """
    found = (
        mapping(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else {}
    )
    dispositions = {
        key: text(value) for key, value in mapping(found.get("dispositions")).items()
    }
    messages = [text(each) for each in found.get("messages", []) or []]  # type: ignore[union-attr]
    return Owner(
        messages=messages, dispositions=dispositions, cap=int(str(found.get("cap", 0)))
    )


def write_owner(path: pathlib.Path, owner: Owner) -> None:
    """Write the owner's messages back.

    Args:
        path: ``owner.json``.
        owner: what to write.
    """
    words = {
        "messages": owner.messages,
        "dispositions": owner.dispositions,
        "cap": owner.cap,
    }
    path.write_text(
        json.dumps(words, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def _item(
    pull: actinputs.Pull, repo: str, kind: str, priority: str = ""
) -> dispatchnext.Item:
    reference = f"{repo}#{pull.get('number')}"
    return dispatchnext.Item(
        ref=reference,
        kind=kind,
        created=text(pull.get("created_at")),
        priority=priority,
    )


def work(hub: Hub, settings: config.Config) -> Callable[[], dispatchnext.State]:
    """What the order of work reads.

    Args:
        hub: GitHub.
        settings: the configuration.

    Returns:
        What reads it when asked.
    """

    def read() -> dispatchnext.State:
        found = ledger.configured(settings)
        repos = [each.slug for each in config.repositories(settings)]
        items = [_item(pull, repo, "pr") for repo in repos for pull in hub.pulls(repo)]
        for label in settings.slots.priority_labels:
            items += [
                _item(each, repo, "ticket", label)
                for repo in repos
                for each in hub.issues(repo, label)
                if "pull_request" not in each
            ]
        slots = [each.name for each in settings.slots.default]
        return dispatchnext.State(
            cap=len(slots),
            slots=slots,
            ledger={each.name: each.agent for each in found.slots},
            items=items,
        )

    return read


def prepush(
    run: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
) -> Callable[[], tuple[int, str]]:
    """The pre-push check: the repository's ``[[pre_push]]`` checks, as the hook runs them.

    Args:
        run: runs a command line without raising.

    Returns:
        What runs it and gives its status and output.
    """

    def check() -> tuple[int, str]:
        done = run([sys.executable, "-m", "pitboss", "hook", "pre-push"])
        return done.returncode, done.stdout + done.stderr

    return check


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class P90(collections.abc.Mapping[str, int]):
    """Each repository's 90th percentile of the lines its last 100 merged PRs changed, read when asked.

    Attributes:
        github: the reading runner.
        found: what was read.
    """

    github: acthub.ghapi.GitHub
    found: dict[str, int] = dataclasses.field(default_factory=dict)

    def __getitem__(self, repo: str) -> int:
        """Read a repository's percentile.

        Args:
            repo: ``owner/name``.

        Returns:
            The percentile (0 when it has no merged PR).
        """
        if repo not in self.found:
            owner, _, name = repo.partition("/")
            words = [
                "gh",
                "api",
                "graphql",
                "-f",
                f"query={SIZES}",
                "-f",
                f"owner={owner}",
                "-f",
                f"name={name}",
            ]
            try:
                answer = json.loads(self.github.run(words).stdout)
            except (
                Exception
            ):  # noqa: B902 - an unread size is 0: every size then needs a ruling
                answer = {}
            nodes = records(
                mapping(
                    mapping(mapping(mapping(answer).get("data")).get("repository")).get(
                        "pullRequests"
                    )
                ).get("nodes")
            )
            sizes = sorted(
                int(str(each.get("additions", 0))) + int(str(each.get("deletions", 0)))
                for each in nodes
            )
            self.found[repo] = sizes[(9 * len(sizes) + 9) // 10 - 1] if sizes else 0
        return self.found[repo]

    def __iter__(self) -> Iterator[str]:
        """The repositories read so far.

        Returns:
            An iterator over them.
        """
        return iter(self.found)

    def __len__(self) -> int:
        """How many were read.

        Returns:
            The count.
        """
        return len(self.found)


def act_of(
    github: acthub.ghapi.GitHub,
    settings: config.Config,
    owner: Owner,
    run: Run,
    identity: str,
) -> Act:
    """The verbs' world.

    Args:
        github: the reading and the writing runner.
        settings: the configuration.
        owner: the owner's messages.
        run: the runner git goes through.
        identity: the login the verbs post with.

    Returns:
        The world.
    """
    hub = acthub.GhHub(github=github)
    repos = [each.slug for each in config.repositories(settings)]
    limits = P90(github=github)
    given = actinputs.Settings(identity=identity, authors=[identity], max_lines=limits)
    return Act(
        hub=hub,
        inputs=actinputs.inputs(actinputs.reader(github), given),
        owner=owner,
        repos=repos,
        p90=limits,
        run=run,
        prepush=prepush(
            lambda words: subprocess.run(
                list(words), capture_output=True, text=True, check=False
            )
        ),
        work=work(hub, settings),
        controls=Controls(),
    )


def identity_of(github: acthub.ghapi.GitHub) -> str:
    """The login ``gh`` is signed in as.

    Args:
        github: the reading runner.

    Returns:
        The login.
    """
    return name_at(json.loads(github.run(["gh", "api", "user"]).stdout), "login")
