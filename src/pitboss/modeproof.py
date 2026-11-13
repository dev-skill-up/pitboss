"""P4: every mode goes through the path, run by ``nox -s modes`` (plan section 6.3).

``python -m pitboss.modeproof`` reads the one table the command line parser is
built from (``cli_parser.table``) and walks each command, each choice of a
required argument, and each optional argument and flag both present and absent.
``mode.parse`` must map every such command line onto a ``Mode`` constructor, and
every constructor must be the image of at least one; every ``match`` on a mode
must end in ``assert_never``. A new flag that ``parse`` cannot map fails the
session (keyword: one-path).
"""

import argparse
import ast
import itertools
import pathlib
import sys
import typing
from typing import AbstractSet, Iterator, Mapping, Protocol, Sequence, runtime_checkable

from gather.api import Wrapper, unique

from . import actverbs, cli_parser, config, mode, proofsource

ITEM = "owner/project#1"
PROJECT = config.make_repo("owner", "project")
# the values of an argument argparse gives no choices for
VALUES: Mapping[str, Sequence[str]] = {"verb": [*actverbs.VERBS, "dispatch-next"]}
# the options an act command line gives, as ``name=value`` words read
OPTIONS: Mapping[str, Mapping[str, str]] = {"act": {"want": ITEM}}
# the counts of words that make an argument a list
MANY = (argparse.ZERO_OR_MORE, argparse.ONE_OR_MORE)


@runtime_checkable
class Argument(Protocol):
    """An argument as a command declares it (``gather.commands.add_argument``)."""

    @property
    def args(self) -> Sequence[str]:
        """The names the argument is given as.

        Returns:
            The names (``config``, or ``--now``).
        """

    @property
    def kwargs(self) -> AbstractSet[tuple[str, object]]:
        """The rest of what ``add_argument`` is given.

        Returns:
            Each keyword and its value.
        """


def _arguments(name: str, registered: object) -> Sequence[argparse.Action]:
    # each argument a command declares, made by argparse as its parser makes it
    extra = registered.extra if isinstance(registered, Wrapper) else ()
    listed = extra if isinstance(extra, Sequence) else ()
    made = argparse.ArgumentParser(prog=name, add_help=False)
    return [
        made.add_argument(*each.args, **dict(each.kwargs))  # type: ignore[arg-type]
        for each in listed
        if isinstance(each, Argument)
    ]


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
    name: str, arguments: Sequence[argparse.Action]
) -> Iterator[tuple[str, argparse.Namespace]]:
    required = [each for each in arguments if each.required]
    optional = [each for each in arguments if not each.required]
    for chosen in itertools.product(*(_values(each) for each in required)):
        base = {
            "__gather_name__": name,
            **{each.dest: each.default for each in optional},
            **{each.dest: value for each, value in zip(required, chosen)},
        }
        label = " ".join([name, *(str(each) for each in chosen)])
        yield label, argparse.Namespace(**base)
        yield from _varied(label, base, optional)


def command_lines(
    declared: cli_parser.Declared,
) -> Iterator[tuple[str, argparse.Namespace]]:
    """Every command line the declared commands take, one argument varied at a time.

    Args:
        declared: the table the parser is built from (``cli_parser.table``).

    Yields:
        A label and the parsed arguments.
    """
    for name, registered in sorted(unique(declared).items()):
        yield from _lines(name, _arguments(name, registered))


def _options(args: argparse.Namespace) -> Mapping[str, str]:
    given = getattr(args, "words", None)
    return OPTIONS.get(str(getattr(args, "__gather_name__", "")), {}) if given else {}


def _mapped(
    mode_of: mode.ModeOf, declared: cli_parser.Declared
) -> tuple[Sequence[str], AbstractSet[str]]:
    # each command line that maps to no mode, and the modes that were mapped to
    kinds = typing.get_args(mode.Mode)
    found, seen = [], set()
    for label, args in command_lines(declared):
        try:
            given = mode_of(args, PROJECT, _options(args))
        except SystemExit as stopped:
            found.append(f"P4: {label} exits {stopped.code} instead of a mode")
            continue
        if not isinstance(given, kinds):
            found.append(f"P4: {label} is {type(given).__name__}, no mode")
        seen.add(type(given).__name__)
    return found, seen


def images(mode_of: mode.ModeOf, declared: cli_parser.Declared) -> Sequence[str]:
    """Map every command line through ``mode_of``.

    Args:
        mode_of: ``mode.parse``, or a stand-in.
        declared: the table the parser is built from.

    Returns:
        The findings: a command line with no mode, a constructor with no command
        line.
    """
    found, seen = _mapped(mode_of, declared)
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
    found = [
        *images(mode_of, cli_parser.table()),
        *total_matches(proofsource.package_at(root)),
    ]
    for each in found:
        print(each)
    print("modes: ok" if not found else f"modes: {len(found)} findings")
    return 1 if found else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(pathlib.Path.cwd(), mode.parse))
