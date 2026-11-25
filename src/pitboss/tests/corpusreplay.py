"""The recorded reads of open PRs, replayed through the shipped reader (pitboss#526).

Each ``corpus/<repo>-<number>.json.gz`` holds the GET answers ``pitboss next`` got
from GitHub for one PR of bats-lang on 2026-11-24, with the keys no code of the
package reads dropped, and the step the decider gives it (``expected``).
"""

import gzip
import json
import pathlib
from typing import Mapping, Sequence

from .. import config, configfile, gate, gateread, pullread, pulls, steps
from . import fakes

DIRECTORY = pathlib.Path(__file__).parent.joinpath("corpus")


def names() -> Sequence[str]:
    """The recorded PRs.

    Returns:
        ``repo-number`` of each, in order.
    """
    return sorted(each.name.removesuffix(".json.gz") for each in DIRECTORY.glob("*.gz"))


def load(name: str) -> Mapping[str, object]:
    """One recorded PR.

    Args:
        name: ``repo-number``.

    Returns:
        Its record: repo, number, reads, expected, recorded_dead_end, was.
    """
    found = json.loads(gzip.decompress((DIRECTORY / f"{name}.json.gz").read_bytes()))
    return found if isinstance(found, dict) else {}


def read(record: Mapping[str, object]) -> pulls.PullRead:
    """Read a recorded PR as ``pitboss next`` reads it.

    Args:
        record: the record.

    Returns:
        The PR as read, from its recorded answers alone.
    """
    reads = record["reads"]
    assert isinstance(reads, dict)
    slug = str(record["repo"])
    text = (DIRECTORY / "config.toml").read_text().replace("REPO", slug)
    here = fakes.directory()
    (here / "config.toml").write_text(text)
    settings = configfile.load(str(here / "config.toml"), here)
    repo = config.make_repo("bats-lang", slug)
    source = pullread.source_for(
        fakes.github(dict(reads)), settings, lambda: True, repo
    )
    return pulls.fetch(source, repo, int(str(record["number"])))


def first_stop(record: Mapping[str, object]) -> str:
    """The route of the first stop of a recorded PR's merge, as ``act`` reads it.

    Args:
        record: the record, whose reads hold the gate's.

    Returns:
        The name of the route; empty when nothing stops the merge.
    """
    reads = record["reads"]
    assert isinstance(reads, dict)
    pull = read(record)
    gated = gateread.reader(fakes.github(dict(reads)))(pull, [])
    stops = gate.stops_of(steps.Step.MERGE, gated)
    return stops[0].route.name if stops else ""
