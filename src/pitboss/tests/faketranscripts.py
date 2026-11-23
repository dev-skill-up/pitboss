"""Transcripts and a ledger the tests make (keyword: fake-transcripts)."""

import dataclasses
import pathlib
from collections.abc import Mapping, Sequence


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class FakeTranscripts:
    """Transcripts held in a dict (``_texts``: each agent id and its text)."""

    _texts: Mapping[str, str]

    def names(self) -> Sequence[str]:
        """List the agents.

        Returns:
            The ids.
        """
        return sorted(self._texts)

    def read(self, agent: str) -> str:
        """Read a transcript.

        Args:
            agent: the id.

        Returns:
            The text.
        """
        return self._texts[agent]


def seed_ledger(path: pathlib.Path, names: Sequence[str]) -> None:
    """Write a ledger of empty slots, as the owner would create it.

    Args:
        path: the ledger file.
        names: the slot names, each on the model of the same position in
            ``small``, ``large``.
    """
    models = ("small", "large")
    rows = [f'{{"name": "{n}", "model": "{m}"}}' for n, m in zip(names, models)]
    path.write_text('{"slots": [' + ", ".join(rows) + '], "failed": {}}')
