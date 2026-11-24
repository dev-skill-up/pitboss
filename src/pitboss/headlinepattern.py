"""The ``Head:`` line of a PR body (keyword: hand-back-done)."""

import re

HEAD_LINE = re.compile(r"^Head:\s*([0-9a-f]{40})\s*$", re.MULTILINE)
