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
from typing import Mapping, Sequence

from gather.api import Wrapper, unique
from gather.commands import add_argument

from . import cli_parser, config, mode, modecommand, modeproof, pathproofs, proofsource

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
    "P1": Seed(
        path="decide.py",
        old="def decide(made: world.World) -> Judgement:",
        new="def decide(made: world.World, more: int) -> Judgement:",
    ),
    "P2": Seed(path="render.py", old="", new="\nimport subprocess\n"),
    "P3": Seed(
        path="shapes.py",
        old="    said: tuple[str, str]\n",
        new="    said: tuple[str, str] = ('', '')\n",
    ),
    "P5": Seed(
        path="render.py", old="", new="\ndef said(given: int) -> str:\n    return ''\n"
    ),
    "6.1": Seed(path="gaterows.py", old="", new="\nfrom . import totaljson\n"),
    # a second derivation of "CI is green", as flowquestions.ci_result was
    "6.1 facts": Seed(
        path="pullref.py", old="", new="\nRED = any(each.failed for each in ())\n"
    ),
    "P6": Seed(
        path="commands.py", old="", new="\nREAD = readworld.read_world(None, None)\n"
    ),
    "P7": Seed(path="decide.py", old="", new="\nSAID = 'nobody acts'\n"),
    "P8": Seed(path="actinputs.py", old="", new="\nNAMED = 'totalverdict'\n"),
    "P9": Seed(
        path="workorder.py", old="", new="\nPATH = 'repos/o/r/issues?state=all'\n"
    ),
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
        The files; a seed whose text is not there once changes nothing.
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
        ``Unasked``, so the other modes are the image of no command line.
    """
    return mode.Unasked(command=next(iter(modecommand.Command)))


def new_command(declared: cli_parser.Declared) -> cli_parser.Declared:
    """P4's seeded table: a command no mode names.

    Args:
        declared: the table the parser is built from.

    Returns:
        The table with its first command's registration under a new name.
    """
    return {**declared, "seeded": next(iter(declared.values()))}


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
    found = [*pathproofs.findings(whole), *modeproof.total_matches(whole)]
    for name, seed in SEEDS.items():
        if not pathproofs.PROOFS[name](proofsource.of_texts(seeded(texts, seed))):
            found.append(f"{name}: its seed is not found ({seed.path})")
    if not modeproof.total_matches(proofsource.of_texts(seeded(texts, UNMATCHED))):
        found.append("P4: a match on a mode without assert_never is not found")
    if not modeproof.images(seed_parse, declared):
        found.append("P4: a parse that leaves a mode with no image is not found")
    tables = (("command", new_command), ("flag", new_flag))
    found += [
        f"P4: a new {name} with no mode is not found"
        for name, table in tables
        if not modeproof.images(mode.parse, table(declared))
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
    print("seeds: ok" if not found else f"seeds: {len(found)} findings")
    return 1 if found else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(pathlib.Path.cwd(), cli_parser.table()))
