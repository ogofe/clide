"""Command line entry point for Clide."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from clide import __version__

DESCRIPTION = "Clide - Your Friendly Terminal IDE"

EPILOG = """\
examples:
  clide                 open the current directory
  clide .               same thing, explicitly
  clide ~/projects/app  open a directory
  clide main.py         open a file (workspace becomes its directory)
  clide src/ a.py b.py  open a directory and two files in tabs
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clide",
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "paths",
        nargs="*",
        metavar="PATH",
        help="Directories and/or files to open. Defaults to the current directory.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"clide {__version__}",
    )
    return parser


def resolve_targets(paths: list[str]) -> tuple[Path, list[Path]]:
    """Split CLI paths into a workspace root and the files to open.

    The root is the first directory given; failing that, the common parent of
    the file arguments; failing that, the current directory.

    Raises:
        FileNotFoundError: If a path does not exist.
    """
    resolved = []
    for raw in paths or ["."]:
        path = Path(os.path.expandvars(raw)).expanduser()
        if not path.exists():
            raise FileNotFoundError(raw)
        resolved.append(path.resolve())

    directories = [p for p in resolved if p.is_dir()]
    files = [p for p in resolved if not p.is_dir()]

    if directories:
        root = directories[0]
    elif files:
        root = Path(os.path.commonpath([f.parent for f in files]))
    else:
        root = Path.cwd()

    return root, files


def main(argv: list[str] | None = None) -> int:
    """Run Clide. Returns a process exit code."""
    args = build_parser().parse_args(argv)

    try:
        workspace, files = resolve_targets(args.paths)
    except FileNotFoundError as error:
        print(f"clide: no such file or directory: {error}", file=sys.stderr)
        return 2
    except OSError as error:  # e.g. paths on different drives
        print(f"clide: {error}", file=sys.stderr)
        return 2

    from clide.app import Clide

    Clide(workspace=workspace, files=files).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
