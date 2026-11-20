"""Each proof of the one path fails on its seed (plan section 6.5).

``python -m pitboss.proofseeds``, a step of CI's ``mutation`` job, reads
``src/pitboss`` from the current directory, requires every proof (P1 to P11, one
for each bullet of ticket #481) to hold on it, then for each applies its one seed
(an edit of the text in memory, or for P4 a table or a parse that breaks it) and
requires that proof to find it, printing ``seed P1.1: found`` for each. Nothing is
written and nothing seeded is run (keyword: one-path).
"""

import argparse
import pathlib
import sys
from typing import Mapping, Sequence

from gather.api import Wrapper, unique
from gather.commands import add_argument

from . import cli_parser, config, mode, modecommand, modeproof, proofsource
from .onepathproofs import CASES
from .proofcase import Seed

SOURCE = "src/pitboss/"

# P4's static half: a match on a mode that does not end in assert_never
UNMATCHED = Seed(
    path="mode.py",
    old=(
        "        case _:  # pragma: no cover\n"
        "            assert_never(chosen)\n\n\ndef item_of"
    ),
    new="        case _:  # pragma: no cover\n            pass\n\n\ndef item_of",
)


def seeded(texts: Mapping[str, str], seed: Seed) -> Mapping[str, str]:
    """The files with one seed applied.

    Args:
        texts: each file's text, by its path from the root.
        seed: the seed.

    Returns:
        The files; a seed whose text is not there once changes nothing, and one
        with no text to replace adds its text at the end.
    """
    path = f"{SOURCE}{seed.path}"
    before = texts.get(path, "")
    if not seed.old:
        return {**texts, path: before + seed.new}
    if before.count(seed.old) != 1:
        return texts
    return {**texts, path: before.replace(seed.old, seed.new)}


def other_modes(
    args: argparse.Namespace, project: config.Repo, options: Mapping[str, str]
) -> mode.Mode:
    """P4's seeded parse: every command line asks nothing.

    Args:
        args: the parsed arguments.
        project: the project.
        options: the options.

    Returns:
        A command that asks nothing, so the other modes are the image of none.
    """
    return next(iter(modecommand.Command))


def new_flag(declared: cli_parser.Declared) -> cli_parser.Declared:
    """P4's seeded table: a flag of ``next`` that ``ASKS_NOTHING`` does not list.

    Args:
        declared: the table the parser is built from.

    Returns:
        The table with ``--seeded`` added to ``next``.
    """
    registered = unique(declared)["next"]
    extra: Sequence[object] = getattr(registered, "extra")
    flag = add_argument("--seeded", action="store_true")
    changed = Wrapper(original=getattr(registered, "original"), extra=[*extra, flag])
    return {**declared, "next": [changed]}


def refusing(kind: str) -> mode.ModeOf:
    """P4's seeded parse: it refuses the command lines of one kind.

    Args:
        kind: what the line varies (subcommand, choice, flag or positional).

    Returns:
        A parse that exits on such a line and parses the others.
    """

    def parse(
        args: argparse.Namespace, project: config.Repo, options: Mapping[str, str]
    ) -> mode.Mode:
        if getattr(args, modeproof.KIND) == kind:
            raise SystemExit(2)
        return mode.parse(args, project, options)

    return parse


def seeded_runs(
    texts: Mapping[str, str], declared: cli_parser.Declared, seed_parse: mode.ModeOf
) -> Mapping[str, Sequence[str]]:
    """What each proof says of its seed.

    Args:
        texts: each file's text, by its path from the root.
        declared: the table the command line parser is built from, for P4.
        seed_parse: P4's seeded parse, which must leave a mode with no image.

    Returns:
        The findings of each proof on its seed, by its bullet.
    """
    unmatched = proofsource.of_texts(seeded(texts, UNMATCHED))
    return {
        "P4.1": modeproof.images(refusing("subcommand"), declared),
        "P4.2": modeproof.images(refusing("choice"), declared),
        "P4.3": modeproof.images(refusing("flag"), declared),
        "P4.4": modeproof.images(refusing("positional"), declared),
        "P4.5": modeproof.images(seed_parse, declared),
        "P4.6": modeproof.total_matches(unmatched),
        "P4.7": modeproof.images(mode.parse, new_flag(declared)),
        **{
            bullet: case.proof(proofsource.of_texts(seeded(texts, case.seed)))
            for bullet, case in CASES.items()
        },
    }


def missed(
    texts: Mapping[str, str], declared: cli_parser.Declared, seed_parse: mode.ModeOf
) -> Sequence[str]:
    """What the proofs fail to show: a finding on the package, a seed not found.

    Args:
        texts: each file's text, by its path from the root.
        declared: the table the command line parser is built from, for P4.
        seed_parse: P4's seeded parse, which must leave a mode with no image.

    Returns:
        One line for each.
    """
    whole = proofsource.of_texts(texts)
    found = [*modeproof.total_matches(whole), *modeproof.images(mode.parse, declared)]
    found += [each for case in CASES.values() for each in case.proof(whole)]
    found += [
        f"{bullet}: its seed is not found"
        for bullet, said in seeded_runs(texts, declared, seed_parse).items()
        if not any(each.startswith(f"{bullet}:") for each in said)
    ]
    return found


def main(root: pathlib.Path, declared: cli_parser.Declared) -> int:
    """Check that each proof holds and fails on its seed.

    Args:
        root: the repository's root.
        declared: the table the command line parser is built from, for P4.

    Returns:
        0 when it does, 1 otherwise.
    """
    found = missed(proofsource.read(root), declared, other_modes)
    for each in found:
        print(each)
    bullets = [*(f"P4.{n}" for n in range(1, 8)), *CASES]
    for each_bullet in bullets:
        if not any(each.startswith(f"{each_bullet}:") for each in found):
            print(f"seed {each_bullet}: found")
    print("seeds: ok" if not found else f"seeds: {len(found)} findings")
    return 1 if found else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(pathlib.Path.cwd(), cli_parser.table()))
