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

from . import blockedby, blockedstep, cli_parser, config, decide, flow, headsignals
from . import listed, mode, modecommand, modeproof, modeseeds, onepathproofs
from . import proofsource
from . import pullfacts, reviews, rounds, steps, straycomments, witnesses
from . import witnessproofs, witnessread, witnessstates, world
from .proofcase import Case, Seed

SOURCE = "src/pitboss/"
# P4.1 to P4.4: what a command line varies (subcommand, choice, flag, positional)
KINDS = ("subcommand", "choice", "flag", "positional")


def _facts_of(pr: flow.PullState) -> pullfacts.PullFacts:
    # the facts the settlers read of a PR, at the step the flow gives it
    return pullfacts.PullFacts(
        repo=config.make_repo("o", "r"),
        pull=pr.pull,
        checks=pr.checks,
        review=None,
        standing=reviews.Standing.NONE,
        signals=headsignals.NONE,
        unreadable=straycomments.NONE,
        step=flow.next_step(pr),
        review_rounds=rounds.NONE,
        relock=False,
    )


def shipped_step(setting: witnesses.Setting) -> steps.Move | None:
    """The step the shipped decider gives a PR and what its step is decided from.

    P13.4 (keyword: witnesses) runs it on each worker task's witness; it is here
    because only this module may import the decider (the depth of the package).

    Args:
        setting: the PR, the blockers its body names and its shared red.

    Returns:
        The step ``decide.facts_of`` gives it.
    """
    facts = _facts_of(setting.pr)
    named = [setting.known[each] for each in blockedby.declared(facts)]
    record = world.PullRecord(
        row=listed.listed_row(facts.repo, "relock/", witnessstates.pull_json()),
        facts=witnessread.read_of(facts, setting.pr),
        blocked_by=blockedstep.Closure(found=named, looped=False),
        shared=setting.groups,
        waits=[],
        stuck=[],
        gated=None,
        failures={},
    )
    return decide.facts_of(record).step


CASES: Mapping[str, Case] = {
    **onepathproofs.CASES,
    **witnessproofs.cases(shipped_step),
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
        **{
            f"P4.{number}": modeproof.images(modeseeds.refusing(kind), declared)
            for number, kind in enumerate(KINDS, 1)
        },
        "P4.5": modeproof.images(seed_parse, declared),
        "P4.6": modeproof.total_matches(unmatched),
        "P4.7": modeproof.images(mode.parse, modeseeds.new_flag(declared)),
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
