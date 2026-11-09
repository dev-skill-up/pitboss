"""The agents a test world's ledger holds, named as ``--running`` (pitboss#94)."""

import re
from typing import Sequence

from . import world


def running(here: world.World, *finished: str) -> Sequence[str]:
    """The ``--running`` arguments that name the agents the ledger's rows hold.

    A test that is not about the derived slots passes these, so the live agents
    are the ones its ledger records (pitboss#94).

    Args:
        here: the world.
        *finished: agents a row holds that have finished, so do not run.

    Returns:
        ``--running`` and the name of each agent a row holds but those.
    """
    names = re.findall(r'"agent": "([^"]+)"', here.ledger.read_text())
    return ["--running", *(name for name in names if name not in finished)]
