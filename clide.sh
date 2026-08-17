#!/usr/bin/env sh
# Run Clide from this checkout without installing it globally.
# Once `pip install -e .` has been run in the venv, `clide` works on its own.
cd "$(dirname "$0")" || exit 1
. venv/Scripts/activate
exec python -m clide.cli "$@"
