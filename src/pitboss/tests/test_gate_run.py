"""A gate passes only on an explicit ok (keyword: gate-run, bats-lang/bats#654).

Each gate that is a command (a repository's pre-push check, a ``nox`` session) is
played with each way a command fails: a non-zero status, a crash, an empty output,
a timeout and a missing argument.
"""

import argparse
import subprocess
import sys
import unittest
from typing import Sequence

from commander_data.run import Runner
from hamcrest import assert_that, contains_string, equal_to, has_length, is_

from .. import config, configfile, gaterun, nox_commands, prepush
from . import fakes, world

Mode = gaterun.Mode


def answering(
    status: int = 0, out: str = "", raises: Exception | None = None
) -> gaterun.Runner:
    """A runner that answers one way.

    Args:
        status: the exit status it answers.
        out: what it prints.
        raises: what it raises instead, if anything.

    Returns:
        The runner.
    """

    def run(cmdargs: Sequence[str], /, *args: object, **kwargs: object) -> fakes.Output:
        if raises is not None:
            raise raises
        return fakes.Output(stdout=out, returncode=status)

    return run


WAYS: Sequence[tuple[Mode, gaterun.Runner]] = (
    (Mode.NONZERO, answering(status=3, out="FAIL: pinned was refused\n")),
    (Mode.CRASH, answering(status=0, out="Traceback (most recent call last)\n")),
    (Mode.CRASH, answering(status=-11, out="boom\n")),
    (Mode.CRASH, answering(raises=FileNotFoundError("no such program"))),
    (Mode.EMPTY, answering(status=0, out="")),
    (Mode.TIMEOUT, answering(raises=subprocess.TimeoutExpired("x", 1))),
    (
        Mode.MISSING_ARGUMENT,
        answering(status=1, out="check.sh: line 3: $1: unbound variable\n"),
    ),
    (Mode.MISSING_ARGUMENT, answering(status=0, out="$1: unbound variable\nok\n")),
)


def pre_push(runner: gaterun.Runner) -> Sequence[str]:
    """The refusals of one declared check run by a runner.

    Args:
        runner: the fake.

    Returns:
        The lines of refusal.
    """
    check = config.PrePush(
        name="check-pins", command=("check.sh", "{bats}"), arguments={"bats": "b"}
    )
    return prepush.refusals(runner, [check], fakes.directory())


def session(runner: gaterun.Runner) -> gaterun.Judged:
    """One ``nox`` session run by a runner.

    Args:
        runner: the fake.

    Returns:
        What the session's command came to, as the sessions read it.
    """
    args = argparse.Namespace(safe_run=runner)
    done = nox_commands.gate_command(args, ["nox", "-r", "-s", "lint"], {})
    return gaterun.judge(done.status, done.output)


DECLARED = {
    "pre_push": [
        {
            "name": "check-pins",
            "command": ["c.sh", "{bats}"],
            "ok": "all passed",
            "timeout": 5,
            "arguments": {"bats": "b"},
        },
        {"command": ["d.sh"]},
    ]
}


class TestEachGateEachWay(unittest.TestCase):
    """Every failure mode refuses at every gate."""

    def test_c32_the_pre_push_check_refuses_every_way(self) -> None:
        """No failure mode lets the push go."""
        for mode, runner in WAYS:
            lines = pre_push(runner)
            assert_that(bool(lines), is_(True), mode.name)
            assert_that(lines[0], contains_string("refused the push"))

    def test_c32_a_nox_session_fails_every_way(self) -> None:
        """No failure mode is a green session."""
        for mode, runner in WAYS:
            done = nox_commands.gate_command(
                argparse.Namespace(safe_run=runner), ["nox"], {}
            )
            assert_that(done.status != 0, is_(True), mode.name)

    def test_c32_the_verdict_names_the_mode(self) -> None:
        """Each way is its own mode."""
        for mode, runner in WAYS:
            judged = gaterun.run(runner, gaterun.Gate(command=["x"], timeout=1))
            assert_that(judged.mode, equal_to(mode))

    def test_c32_an_explicit_ok_passes(self) -> None:
        """Exit 0, an output and (when declared) the ok text pass."""
        assert_that(
            gaterun.run(
                answering(out="x\n"), gaterun.Gate(command=["x"], timeout=1)
            ).passed,
            is_(True),
        )
        said = answering(out="check-pins: all passed\n")
        assert_that(
            gaterun.run(
                said,
                gaterun.Gate(
                    command=["x"], timeout=1, ok_text="check-pins: all passed"
                ),
            ).passed,
            is_(True),
        )
        assert_that(
            gaterun.run(
                said, gaterun.Gate(command=["x"], timeout=1, ok_text="other")
            ).mode,
            equal_to(Mode.EMPTY),
        )
        assert_that(pre_push(answering(out="fine\n")), has_length(0))

    def test_c32_the_runner_pitboss_runs_with_takes_the_gate(self) -> None:
        """commander_data's own runner, which captures by default, runs a gate."""
        words = [
            sys.executable,
            "-c",
            "import sys; print('out'); print('err', file=sys.stderr)",
        ]
        judged = gaterun.run(Runner().safe_run, gaterun.Gate(command=words, timeout=60))
        assert_that((judged.passed, judged.output), equal_to((True, "out\nerr\n")))

    def test_c32_a_session_that_checks_its_status_still_fails(self) -> None:
        """A runner that raises for a non-zero status is a refusal too."""
        failing = answering(
            raises=subprocess.CalledProcessError(2, "x", "bad\n", "worse\n")
        )
        assert_that(
            gaterun.run(failing, gaterun.Gate(command=["x"], timeout=1)).mode,
            equal_to(Mode.NONZERO),
        )


class TestDeclaredArguments(unittest.TestCase):
    """The arguments come from the declared check or the push is refused naming them."""

    def test_c32_a_word_with_no_value_is_named_and_the_check_is_not_run(self) -> None:
        """bats#654: ``check.sh`` was run with no arguments."""
        ran = answering(out="never\n")
        check = config.PrePush(
            name="check-pins",
            command=("check.sh", "{bats}", "{repository}"),
            arguments={"bats": "dist/bats", "repository": ""},
        )
        lines = prepush.refusals(ran, [check], fakes.directory())
        assert_that(lines, has_length(1))
        assert_that(lines[0], contains_string("no value for repository"))
        assert_that(prepush.missing(check), equal_to(["repository"]))

    def test_c32_the_arguments_are_put_in_the_command(self) -> None:
        """The declared values are the arguments."""
        check = config.PrePush(
            name="c", command=("c.sh", "{bats}", "x"), arguments={"bats": "b/bats"}
        )
        assert_that(list(prepush.argv(check)), equal_to(["c.sh", "b/bats", "x"]))

    def test_c32_the_configuration_declares_checks(self) -> None:
        """``[[pre_push]]`` is read, and a bad one is an error."""
        first, second = configfile.pre_push_checks(DECLARED)
        assert_that(
            (first.ok, first.timeout, first.arguments["bats"]),
            equal_to(("all passed", 5, "b")),
        )
        assert_that(second.name, equal_to("d.sh"))
        assert_that(configfile.pre_push_checks({}), equal_to(()))
        for bad in (
            {"pre_push": 1},
            {"pre_push": [1]},
            {"pre_push": [{"command": ["x"], "arguments": 1}]},
        ):
            with self.assertRaises(ValueError):
                configfile.pre_push_checks(bad)


def push(script: str, declared: str) -> world.Result:
    """Push the branch of a world whose configuration declares a check.

    Args:
        script: the check's script.
        declared: the check's arguments, in TOML.

    Returns:
        What the push did.
    """
    here = world.make_world()
    path = here.clone / "check.sh"
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)
    with open(here.config, "a", encoding="utf-8") as handle:
        handle.write(declared)
    fakes.run_git(here.clone, "branch", "-f", "branch-1")
    argv = ["push", here.config, "--no-dry-run", "--draft", "origin", "branch-1"]
    return world.invoke(here, *argv, directory=here.clone)


def declared(value: str) -> str:
    """A declared check with its argument.

    Args:
        value: the argument.

    Returns:
        The TOML.
    """
    return (
        '\n[[pre_push]]\nname = "c"\ncommand = ["./check.sh", "{bats}"]\n'
        f'[pre_push.arguments]\nbats = "{value}"\n'
    )


class TestPushRefuses(unittest.TestCase):
    """``pitboss push`` itself, with a declared check."""

    def test_c32_a_check_without_its_argument_blocks_the_push(self) -> None:
        """The case of bats#654: the script needs ``$1`` and gets none."""
        script = '#!/bin/bash\nset -u\necho "$1"\n'
        declared = '\n[[pre_push]]\nname = "c"\ncommand = ["./check.sh", "{bats}"]\n'
        done = push(script, declared)
        assert_that(done.code, equal_to(1))
        assert_that(done.out, contains_string("no value for bats"))

    def test_c32_a_failing_check_blocks_and_a_good_one_lets_it_go(self) -> None:
        """Exit 1 blocks; the declared argument and an ok let the push go."""
        bad = push("#!/bin/sh\necho FAIL\nexit 1\n", declared("x"))
        good = push("#!/bin/sh\necho ok\n", declared("x"))
        assert_that((bad.code, good.code), equal_to((1, 0)))
        assert_that(bad.out, contains_string("refused the push"))
