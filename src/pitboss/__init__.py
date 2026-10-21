"""Sweep a project's pull requests, merge queue, worktrees and worker slots."""

import importlib.metadata

from gather import entry

__version__ = importlib.metadata.version(__name__)
ENTRY_DATA = entry.EntryData.create(__name__)
