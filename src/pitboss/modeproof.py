"""P4: every mode goes through the path, run by ``nox -s modes`` (plan section 6.3).

``python -m pitboss.modeproof`` builds the command line parser itself and walks
each subcommand, each choice of a required argument, and each optional argument
and flag both present and absent. ``mode.parse`` must map every such command
line onto a ``Mode`` constructor, and every constructor must be the image of at
least one; every ``match`` on a mode must end in ``assert_never``. A new flag
that ``parse`` cannot map fails the session (keyword: one-path).
"""

import argparse
import ast
import itertools
import pathlib
import sys
import typing
from typing import AbstractSet, Iterator, Mapping, Sequence

from . import actverbs, cli_parser, config, machine, mode, proofsource

ITEM = "owner/project#1"
PROJECT = config.make_repo("owner", "project")
# the values of an argument argparse gives no choices for
VALUES: Mapping[str, Sequence[str]] = {"verb": [*actverbs.VERBS, "dispatch-next"]}
# the options an act command line gives, as ``name=value`` words read
OPTIONS: Mapping[str, Mapping[str, str]] = {"act": {"want": ITEM}}
# the counts of words that make an argument a list
MANY = (argparse.ZERO_OR_MORE, argparse.ONE_OR_MORE)


def recorded() -> argparse.ArgumentParser:
    """The command line parser of every pitboss command.

    Returns:
        The parser.
    """
    return cli_parser.make_parser(machine.read_usage)


# argparse has no public list of a parser's arguments or subcommands; gather reads
# its subcommands' action the same way (keyword: one-path)
def _actions(parser: argparse.ArgumentParser) -> Sequence[argparse.Action]:
    return parser._actions  # noqa: SLD901


def _commands(
    parser: argparse.ArgumentParser,
) -> Mapping[str, argparse.ArgumentParser]:
    found: dict[str, argparse.ArgumentParser] = {}
    for action in _actions(parser):
        if isinstance(action, argparse._SubParsersAction):  # noqa: SLD905
            found.update(action.choices)
    return found


def _defaults(parser: argparse.ArgumentParser) -> Mapping[str, object]:
    return parser._defaults  # noqa: SLD901


def _arguments(parser: argparse.ArgumentParser) -> Sequence[argparse.Action]:
    help_kind = argparse._HelpAction  # noqa: SLD905
    return [each for each in _actions(parser) if not isinstance(each, help_kind)]


def _values(action: argparse.Action) -> Sequence[object]:
    # what an argument is given when it is present
    if action.nargs == 0:
        return [True]
    named = list(action.choices or VALUES.get(action.dest, [ITEM]))
    return [[each] for each in named] if action.nargs in MANY else named


def _varied(
    label: str, base: Mapping[str, object], optional: Sequence[argparse.Action]
) -> Iterator[tuple[str, argparse.Namespace]]:
    # each optional argument present, one at a time
    for each in optional:
        for value in _values(each):
            varied = argparse.Namespace(**{**base, each.dest: value})
            yield f"{label} {each.dest}={value}", varied


def _lines(
    name: str, sub: argparse.ArgumentParser
) -> Iterator[tuple[str, argparse.Namespace]]:
    arguments = _arguments(sub)
    required = [each for each in arguments if each.required]
    optional = [each for each in arguments if not each.required]
    for chosen in itertools.product(*(_values(each) for each in required)):
        base = {
            **_defaults(sub),
            **{each.dest: each.default for each in optional},
            **{each.dest: value for each, value in zip(required, chosen)},
        }
        label = " ".join([name, *(str(each) for each in chosen)])
        yield label, argparse.Namespace(**base)
        yield from _varied(label, base, optional)


def command_lines(
    parser: argparse.ArgumentParser,
) -> Iterator[tuple[str, argparse.Namespace]]:
    """Every command line the parser takes, one argument varied at a time.

    Args:
        parser: the parser.

    Yields:
        A label and the parsed arguments.
    """
    for name, sub in sorted(_commands(parser).items()):
        yield from _lines(name, sub)


def _options(args: argparse.Namespace) -> Mapping[str, str]:
    given = getattr(args, "words", None)
    return OPTIONS.get(str(getattr(args, "__gather_name__", "")), {}) if given else {}


def _mapped(
    mode_of: mode.ModeOf, parser: argparse.ArgumentParser
) -> tuple[Sequence[str], AbstractSet[str]]:
    # each command line that maps to no mode, and the modes that were mapped to
    kinds = typing.get_args(mode.Mode)
    found, seen = [], set()
    for label, args in command_lines(parser):
        try:
            given = mode_of(args, PROJECT, _options(args))
        except SystemExit as stopped:
            found.append(f"P4: {label} exits {stopped.code} instead of a mode")
            continue
        if not isinstance(given, kinds):
            found.append(f"P4: {label} is {type(given).__name__}, no mode")
        seen.add(type(given).__name__)
    return found, seen


def images(mode_of: mode.ModeOf, parser: argparse.ArgumentParser) -> Sequence[str]:
    """Map every command line through ``mode_of``.

    Args:
        mode_of: ``mode.parse``, or a stand-in.
        parser: the parser.

    Returns:
        The findings: a command line with no mode, a constructor with no command
        line.
    """
    found, seen = _mapped(mode_of, parser)
    return [
        *found,
        *(f"P4: no command line is {each}" for each in mode.NAMES if each not in seen),
    ]


def _is_mode_match(node: ast.Match) -> bool:
    return any(
        isinstance(each.pattern, ast.MatchClass)
        and proofsource.dotted(each.pattern.cls).startswith("mode.")
        or isinstance(each.pattern, ast.MatchOr)
        and any(
            isinstance(alternative, ast.MatchClass)
            and proofsource.dotted(alternative.cls).startswith("mode.")
            for alternative in each.pattern.patterns
        )
        for each in node.cases
    )


def total_matches(package: proofsource.Package) -> Sequence[str]:
    """Every ``match`` on a mode ends in ``assert_never``.

    Args:
        package: the package.

    Returns:
        Each match that does not.
    """
    return [
        f"P4: {short}:{node.lineno} matches a mode without assert_never"
        for short, node in proofsource.nodes(package)
        if isinstance(node, ast.Match)
        and _is_mode_match(node)
        and not proofsource.ends_never(node.cases[-1].body)
    ]


def main(root: pathlib.Path, mode_of: mode.ModeOf) -> int:
    """Run P4 on the package under a repository's root.

    Args:
        root: the root.
        mode_of: what maps a command line to a mode.

    Returns:
        0 when it holds, 1 otherwise.
    """
    found = [*images(mode_of, recorded()), *total_matches(proofsource.package_at(root))]
    for each in found:
        print(each)
    print("modes: ok" if not found else f"modes: {len(found)} findings")
    return 1 if found else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(pathlib.Path.cwd(), mode.parse))
