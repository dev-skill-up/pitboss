"""Where the skill's files are, for the tests that read them."""

import pathlib

ROOT = pathlib.Path(*pathlib.Path(__file__).resolve().parts[:-4])
SKILL = pathlib.Path("plugins/pitboss/skills/sweep")
REFERENCES = SKILL / "references"
