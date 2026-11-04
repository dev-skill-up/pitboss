"""The command that records the daily summary of the Opus rulings.

Keyword: ruling-summary (pitboss#237).
"""

import argparse

from . import ENTRY_DATA, commands, rulingsummary, timing


@ENTRY_DATA.register(
    commands.CONFIG_ARGUMENT, commands.NOW_ARGUMENT, name="ruling-summary"
)
def record_summary(args: argparse.Namespace) -> None:
    """Record that the summary of the Opus rulings of the day was written.

    Args:
        args: the parsed arguments.
    """
    settings = commands.load_settings(args)
    now = timing.current_time(args)
    path = rulingsummary.record_path(settings.project.main_clone)
    rulingsummary.note(path, now)
    print(
        f"recorded the Opus ruling summary of {rulingsummary.pacific_day(now)} in {path}"
    )
