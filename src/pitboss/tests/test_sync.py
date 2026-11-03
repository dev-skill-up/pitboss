"""``pitboss sync`` and the sweep's last step: the working files go to main."""

import pathlib
import subprocess
import unittest
from typing import Sequence

from . import cleanworld, syncworld, test_commands, world

NOT_RUN = subprocess.CalledProcessError(1, ["git"])
FAILED = (1, "COULD NOT SYNC")


def kept(synced: syncworld.Synced) -> tuple[str, int]:
    """What main of the origin holds of the notes, and its commits.

    Args:
        synced: the world.

    Returns:
        The notes' content and the count of commits.
    """
    return syncworld.kept(synced, synced.notes), syncworld.commits(synced)


def pushes(here: world.World) -> Sequence[Sequence[str]]:
    """The commands a world ran that push.

    Args:
        here: the world.

    Returns:
        The command lines.
    """
    return [call for call in here.calls if "push" in call]


def failing_sync(
    word: str, error: Exception
) -> tuple[syncworld.Synced, tuple[object, str]]:
    """Sync a world whose git command with a word fails.

    Args:
        word: the word of the command.
        error: what it raises.

    Returns:
        The world, and the exit code and the start of the output.
    """
    synced = syncworld.make_synced()
    broken = syncworld.with_failing(synced.here, word, error)
    result = world.again(broken, "sync")
    return synced, (result.code, result.out[:14])


class TestSync(unittest.TestCase):
    """What the sync copies, says and refuses."""

    def test_a_changed_file_is_committed_and_pushed_to_main(self) -> None:
        """The first sync clones, copies the config, ledger and notes, and pushes."""
        synced = syncworld.make_synced()
        before = syncworld.commits(synced)
        code, lines = syncworld.sync(synced)
        files = (synced.here.config, str(synced.here.ledger), str(synced.notes))
        cleanworld.same(
            (code, sorted(lines)), (0, [f"SYNCED {each}" for each in sorted(files)])
        )
        cleanworld.same(kept(synced), ("first notes\n", before + 1))

    def test_nothing_changed_says_nothing(self) -> None:
        """A second sync with the same files prints nothing and makes no commit."""
        synced = syncworld.after_first_sync()
        before = kept(synced)
        cleanworld.same((syncworld.sync(synced), kept(synced)), ((0, []), before))

    def test_a_copy_that_stages_nothing_is_not_an_error(self) -> None:
        """Files that stage nothing: no commit, no push, the line, exit 0."""
        synced = syncworld.make_synced()
        before = syncworld.commits(synced)
        result = world.again(syncworld.with_nothing_staged(synced.here), "sync")
        cleanworld.same(
            (result.code, result.out.splitlines(), syncworld.commits(synced)),
            (0, ["sync: nothing to commit"], before),
        )

    def test_a_failing_diff_is_still_reported(self) -> None:
        """A git that fails to diff (status 128, not 1) is COULD NOT SYNC."""
        broken = subprocess.CalledProcessError(128, ["git"])
        cleanworld.same(failing_sync("diff", broken)[1], FAILED)

    def test_only_the_file_that_changed_is_copied(self) -> None:
        """A later sync updates the changed file in a new commit."""
        synced = syncworld.after_first_sync()
        count = syncworld.commits(synced)
        synced.notes.write_text("second notes\n")
        said = syncworld.sync(synced)
        cleanworld.same(
            (said, kept(synced)),
            ((0, [f"SYNCED {synced.notes}"]), ("second notes\n", count + 1)),
        )

    def test_the_optional_files_are_kept_once_they_exist(self) -> None:
        """The slot log joins in when pitboss has written it."""
        synced = syncworld.after_first_sync()
        log = synced.here.ledger.with_suffix(".log")
        log.write_text("a change\n")
        cleanworld.same(syncworld.sync(synced), (0, [f"SYNCED {log}"]))

    def test_a_missing_source_is_reported_and_the_rest_is_synced(self) -> None:
        """A named file that is not there is a line and exit 1; the others go."""
        synced = syncworld.make_synced()
        synced.notes.unlink()
        code, lines = syncworld.sync(synced)
        cleanworld.same((code, lines[-1]), (1, f"SYNC SOURCE MISSING {synced.notes}"))
        held = syncworld.kept(synced, synced.here.ledger)
        cleanworld.same(held.startswith("{"), True)

    def test_a_failed_push_is_reported_and_the_next_sync_sends_it(self) -> None:
        """A push that fails is a line and exit 1; the next sync pushes the file."""
        synced, said = failing_sync("push", NOT_RUN)
        count = syncworld.commits(synced)
        cleanworld.same((said, syncworld.sync(synced)[0]), (FAILED, 0))
        cleanworld.same(kept(synced), ("first notes\n", count + 1))

    def test_git_that_cannot_run_is_reported(self) -> None:
        """No git program is a line and exit 1, not a traceback."""
        cleanworld.same(failing_sync("clone", FileNotFoundError("git"))[1], FAILED)

    def test_without_a_table_the_command_refuses(self) -> None:
        """A configuration with no ``[sync]`` table exits 2 and says so."""
        result = world.again(world.make_world(), "sync")
        cleanworld.same((result.code, "no [sync] table" in result.err), (2, True))


class TestSweep(unittest.TestCase):
    """The sweep ends with a sync."""

    def test_the_sweep_syncs_at_its_end(self) -> None:
        """The sweep's last line is the sync's."""
        synced = syncworld.make_synced()
        lines = test_commands.sweep(synced.here).out.splitlines()
        cleanworld.same(lines[-1], f"SYNCED {synced.notes}")
        cleanworld.same(kept(synced)[0], "first notes\n")

    def test_a_sweep_with_no_table_syncs_nothing(self) -> None:
        """No ``[sync]`` table: no push."""
        here = world.make_world()
        test_commands.sweep(here)
        cleanworld.same(pushes(here), [])

    def test_a_complete_configuration_has_no_guard_line_and_exits_0(self) -> None:
        """Every file beside the configuration is kept: no line, status 0."""
        cleanworld.same(syncworld.guard(syncworld.make_healthy()), (0, []))

    def test_a_sweep_with_no_table_fails_loudly(self) -> None:
        """No table: the line is printed, and the status is 1 for it alone."""
        synced = syncworld.make_healthy()
        config = pathlib.Path(synced.here.config)
        config.write_text(config.read_text().split("\n[sync]")[0])
        line = (
            "SYNC NOT CONFIGURED: add a [sync] table "
            '(reference: sweep.md, "The orchestrator\'s working files")'
        )
        cleanworld.same(syncworld.guard(synced), (1, [line]))

    def test_a_file_beside_the_configuration_that_is_not_kept_fails(self) -> None:
        """A tsv, a md and a toml beside the configuration are each named."""
        synced = syncworld.make_healthy()
        found = syncworld.beside(synced, "slots.tsv", "o.toml", "plan.md")
        cleanworld.same(syncworld.guard(synced), syncworld.unkept_lines(found))

    def test_a_named_file_that_is_not_kept_fails(self) -> None:
        """A file the configuration names, outside its directory, is not kept."""
        synced = syncworld.make_healthy()
        named = synced.here.workspace / "named.txt"
        named.write_text("x\n")
        syncworld.add_to_config(
            synced,
            f'\n[extra]\nfiles = ["{named}", "relative.txt", 3]\n'
            'table = {file = "/nonexistent/x"}\n',
        )
        cleanworld.same(syncworld.guard(synced), (1, [f"NOT SYNCED {named}"]))

    def test_a_file_in_paths_is_not_reported(self) -> None:
        """Adding the file to ``[sync] paths`` ends the line."""
        synced = syncworld.make_healthy()
        extra = syncworld.beside(synced, "slots.tsv")[0]
        failing = syncworld.guard(synced)[0]
        config = pathlib.Path(synced.here.config)
        old = f'paths = ["{synced.notes}"]'
        config.write_text(config.read_text().replace(old, old[:-1] + f', "{extra}"]'))
        cleanworld.same((failing, syncworld.guard(synced)), (1, (0, [])))

    def test_a_failed_sync_is_reported_by_the_sweep(self) -> None:
        """A sweep whose sync fails says so, and exits 1."""
        synced = syncworld.make_synced()
        broken = syncworld.with_failing(synced.here, "clone", NOT_RUN)
        result = test_commands.sweep(broken)
        cleanworld.same(result.code, 1)
        cleanworld.same(result.out.count("COULD NOT SYNC"), 1)
