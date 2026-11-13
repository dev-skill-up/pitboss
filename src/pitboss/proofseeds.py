"""Each proof of the one path fails on a seeded violation (plan section 6.5).

``python -m pitboss.proofseeds``, a step of CI's ``mutation`` job, reads
``src/pitboss`` from the current directory, requires every proof to hold on it,
then for each proof applies one edit to the text in memory and requires that
proof to find it. Nothing is written and nothing seeded is run: the proofs only
parse (keyword: one-path).
"""

import argparse
import dataclasses
import pathlib
import sys
from typing import Callable, Mapping, Sequence

from . import cli_parser, machine, mode, modeproof, pathproofs, proofsource

SOURCE = "src/pitboss/"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Seed:
    """One violation, as an edit of one file.

    Attributes:
        path: the file, under ``src/pitboss/``.
        old: the text replaced, which occurs once; empty to add at the end.
        new: what replaces it.
    """

    path: str
    old: str
    new: str


SEEDS: Mapping[str, Seed] = {
    "P1": Seed(path="render.py", old="", new="\nMADE = answer.NotEnoughWork()\n"),
    "P2": Seed(path="render.py", old="", new="\nimport subprocess\n"),
    "P3": Seed(path="onepath.py", old="", new="\nMADE = world.World()\n"),
    "P5": Seed(path="render.py", old="", new="\ndef said(given: int) -> str:\n    return ''\n"),
    "P6": Seed(path="commands.py", old="", new="\nfrom . import ghapi\n"),
    "P7": Seed(path="decide.py", old="", new="\nSAID = 'nobody acts'\n"),
    "P8": Seed(path="actinputs.py", old="", new="\nNAMED = 'totalverdict'\n"),
    "P9": Seed(path="workorder.py", old="", new="\nPATH = 'repos/o/r/issues?state=all'\n"),
    "P10": Seed(
        path="decide.py",
        old="def decide_item(record: world.Record)",
        new="def decide_item(record: world.Record, made: world.World)",
    ),
    "P11": Seed(
        path="retrying.py",
        old="def with_retries(run: KeywordRun, draw: Draw, sleep: Sleep)",
        new="def with_retries(run: KeywordRun, draw: Draw, sleep: Sleep = print)",
    ),
}
# P4's static half: a match on a mode that does not end in assert_never
UNMATCHED = Seed(
    path="onepath.py",
    old="        case _:  # pragma: no cover\n            assert_never(chosen)\n\n\ndef seen_for",
    new="        case _:  # pragma: no cover\n            pass\n\n\ndef seen_for",
)


def seeded(texts: Mapping[str, str], seed: Seed) -> Mapping[str, str]:
    """The files with one seed applied.

    Args:
        texts: each file's text, by its path from the root.
        seed: the seed.

    Returns:
        The files; a seed whose text is not there once changes nothing.
    """
    path = f"{SOURCE}{seed.path}"
    text = texts.get(path, "")
    if not seed.old:
        return {**texts, path: text + seed.new}
    if text.count(seed.old) != 1:
        return texts
    return {**texts, path: text.replace(seed.old, seed.new)}


def _other_modes(
    args: argparse.Namespace, project: object, options: Mapping[str, str]
) -> mode.Mode:
    # P4's dynamic half: a parse that sends every command line to Other
    return mode.Other(command="")


def missed(texts: Mapping[str, str], parser: argparse.ArgumentParser) -> Sequence[str]:
    """What the proofs fail to show: a finding on the package, a seed not found.

    Args:
        texts: each file's text, by its path from the root.
        parser: the command line parser, for P4.

    Returns:
        One line for each.
    """
    whole = proofsource.of_texts(texts)
    found = [*pathproofs.findings(whole), *modeproof.total_matches(whole)]
    for name, seed in SEEDS.items():
        if not pathproofs.PROOFS[name](proofsource.of_texts(seeded(texts, seed))):
            found.append(f"{name}: its seed is not found ({seed.path})")
    if not modeproof.total_matches(proofsource.of_texts(seeded(texts, UNMATCHED))):
        found.append("P4: a match on a mode without assert_never is not found")
    stand_in: Callable[..., mode.Mode] = _other_modes
    if not modeproof.images(stand_in, parser):
        found.append("P4: a parse with no image of WhatNext is not found")
    return found


def main(root: pathlib.Path) -> int:
    """Check that each proof holds and fails on its seed.

    Args:
        root: the repository's root.

    Returns:
        0 when it does, 1 otherwise.
    """
    found = missed(proofsource.read(root), cli_parser.make_parser(machine.read_usage))
    for each in found:
        print(each)
    print("seeds: ok" if not found else f"seeds: {len(found)} findings")
    return 1 if found else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(pathlib.Path.cwd()))
