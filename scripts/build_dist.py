#!/usr/bin/env python3
"""Build skill-zips/<skill>.zip for every skill, deterministically.

Entries are sorted and timestamps fixed, so the same tree always produces
byte-identical zips — which lets CI detect a stale skill-zips/ with a plain
`git diff --exit-code skill-zips/`. Run after changing any skill content.
"""

import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "skill-zips"
EPOCH = (2020, 1, 1, 0, 0, 0)


def build(skill_dir):
    out = DIST / f"{skill_dir.name}.zip"
    files = sorted(
        p for p in skill_dir.rglob("*") if p.is_file() and "__pycache__" not in p.parts
    )
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            arcname = f"{skill_dir.name}/{path.relative_to(skill_dir)}"
            info = zipfile.ZipInfo(arcname, date_time=EPOCH)
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes(), zipfile.ZIP_DEFLATED)
    print(f"built {out.relative_to(ROOT)} ({len(files)} files)")


def main():
    DIST.mkdir(exist_ok=True)
    for skill_dir in sorted(ROOT.glob("plugins/*/skills/*/")):
        build(skill_dir)


if __name__ == "__main__":
    main()
