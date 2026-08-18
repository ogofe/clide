# Clide 
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/clide-tui?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLUE&right_color=ORANGE&left_text=downloads)](https://pepy.tech/projects/clide-tui)

Your friendly terminal IDE — a file explorer, a project-wide search, and a
tabbed editor, in the terminal.

## Install

Globally, via [pipx](https://pipx.pypa.io) — `clide` then works in any terminal,
in its own isolated environment:

```sh
pipx install --editable .
```

`--editable` means the installed command runs this checkout directly, so edits
here take effect immediately. Drop it for a frozen copy, and after bumping the
version run `pipx reinstall clide`.

Or into a local venv for development only:

```sh
pip install -e .
```

## Usage

```sh
clide                 # open the current directory
clide .               # same thing, explicitly
clide ~/projects/app  # open a directory
clide main.py         # open a file (workspace becomes its directory)
clide src/ a.py b.py  # open a directory and two files in tabs
```

The workspace root — what the explorer shows and what search scans — is the
first directory argument, or the common parent of the files given, or the
current directory.

## Keys

| Key | Action |
| --- | --- |
| `ctrl+b` | Toggle the sidebar |
| `ctrl+shift+e` | Show the Explorer |
| `ctrl+shift+f` | Show Search |
| `ctrl+s` | Save the active file |
| `ctrl+w` | Close the active file |
| `ctrl+pgdn` / `ctrl+pgup` | Next / previous file |
| `ctrl+d` | Toggle dark mode |
| `ctrl+shift+q` | Quit |

Tabs show `●` when a file has unsaved changes, and `✕` closes one. Closing a
file with unsaved changes warns once (with a summary of what would be lost)
before discarding.

These keys are bound with `priority=True` so the focused editor cannot swallow
them; as a result `ctrl+w` and `ctrl+d` do not perform their usual `TextArea`
edits. Use `ctrl+backspace` and `delete` for those.
