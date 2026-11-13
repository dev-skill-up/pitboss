"""P4: every mode goes through the path, run by ``nox -s modes`` (plan section 6.3).

``python -m pitboss.modeproof`` builds the command line parser itself and walks
it: each subcommand, each choice of a required argument, and each optional
argument and flag both present and absent. ``mode.parse`` must map every such
command line onto a ``Mode`` constructor, and every constructor must be the image
of at least one; every ``match`` on a mode must end in ``assert_never``. A new
flag that ``parse`` cannot map fails the session (keyword: one-path).
"""

import argparse
import ast
import itertools
import pathlib
import sys
import typing
from typing import Callable, Iterator, Mapping, Sequence

from . import act_commands, actverbs, cli_parser, config, machine, mode, proofsource

ITEM = "owner/project#1"
PROJECT = config.make_repo("owner", "project")
# the values of an argument argparse gives no choices for
VALUES: Mapping[str, Sequence[str]] = {"verb": [*actverbs.VERBS, "dispatch-next"]}
WORDS: Mapping[str, Sequence[str]] = {"act": ["want=" + ITEM]}
Parse = Callable[[argparse.Namespace, config.Repo, Mapping[str, str]], mode.Mode]


def _subcommands(
    parser: argparse.ArgumentParser,
) -> Mapping[str, argparse.ArgumentParser]:
    found: dict[str, argparse.ArgumentParser] = {}
    for action in parser._actions:  # noqa: SLD402
        if isinstance(action, argparse._SubParsersAction):  # noqa: SLD402
            found.update(action.choices)
    return found


def _arguments(parser: argparse.ArgumentParser) -> Sequence[argparse.Action]:
    return [
        each
        for each in parser._actions  # noqa: SLD402
        if not isinstance(each, argparse._HelpAction)  # noqa: SLD402
    ]


def _values(action: argparse.Action) -> Sequence[object]:
    # what an argument is given when it is present
    if action.nargs == 0:
        return [True]
    named = list(action.choices or VALUES.get(action.dest, [ITEM]))
    many = action.nargs in ("*", "+")
    return [[each] for each in named] if many else named


def command_lines(
    parser: argparse.ArgumentParser,
) -> Iterator[tuple[str, argparse.Namespace]]:
    """Every command line the parser takes, one argument varied at a time.

    Args:
        parser: the parser.

    Yields:
        A label and the parsed arguments.
    """
    for name, sub in sorted(_subcommands(parser).items()):
        arguments = _arguments(sub)
        required = [each for each in arguments if each.required]
        optional = [each for each in arguments if not each.required]
        for chosen in itertools.product(*(_values(each) for each in required)):
            base = {
                **sub._defaults,
                **{a.dest: a.default for a in optional},
            }  # noqa: SLD402
            base.update({a.dest: v for a, v in zip(required, chosen)})
            label = " ".join([name, *(str(each) for each in chosen)])
            yield label, argparse.Namespace(**base)
            for each in optional:
                for value in _values(each):
                    varied = argparse.Namespace(**{**base, each.dest: value})
                    yield f"{label} {each.dest}={value}", varied


def _options(args: argparse.Namespace) -> Mapping[str, str]:
    words = WORDS.get(str(getattr(args, "__gather_name__", "")), [])
    given = getattr(args, "words", None)
    return act_commands.options_of(words) if given and words else {}


def images(parse: Parse, parser: argparse.ArgumentParser) -> Sequence[str]:
    """Map every command line through ``parse``.

    Args:
        parse: ``mode.parse``, or a stand-in.
        parser: the parser.

    Returns:
        The findings: a command line with no mode, a constructor with no command
        line.
    """
    kinds = typing.get_args(mode.Mode)
    found, seen = [], set()
    for label, args in command_lines(parser):
        try:
            given = parse(args, PROJECT, _options(args))
        except SystemExit as stopped:
            found.append(f"P4: {label} exits {stopped.code} instead of a mode")
            continue
        if not isinstance(given, kinds):
            found.append(f"P4: {label} is {type(given).__name__}, no mode")
        seen.add(type(given).__name__)
    found.extend(
        f"P4: no command line is {each}" for each in mode.NAMES if each not in seen
    )
    return found


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
    found = []
    for short, node in proofsource.nodes(package):
        if isinstance(node, ast.Match) and _is_mode_match(node):
            last = node.cases[-1].body[-1]
            ends = (
                isinstance(last, ast.Expr)
                and proofsource.called(last.value) == "assert_never"
            )
            if not ends:
                found.append(
                    f"P4: {short}:{node.lineno} matches a mode without assert_never"
                )
    return found


def main(root: pathlib.Path, parse: Parse) -> int:
    """Run P4 on the package under a repository's root.

    Args:
        root: the root.
        parse: what maps a command line to a mode.

    Returns:
        0 when it holds, 1 otherwise.
    """
    parser = cli_parser.make_parser(machine.read_usage)
    package = proofsource.of_texts(proofsource.read(root))
    found = [*images(parse, parser), *total_matches(package)]
    for each in found:
        print(each)
    print("modes: ok" if not found else f"modes: {len(found)} findings")
    return 1 if found else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(pathlib.Path.cwd(), mode.parse))
