from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    ContentSwitcher,
    DirectoryTree,
    Input,
    Label,
    Static,
    Tree,
)

IGNORED = {".git", "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache"}
MAX_FILE_BYTES = 1_000_000
MAX_RESULTS = 500

EXPLORER_PANEL = "explorer-panel"
SEARCH_PANEL = "search-panel"


class IconButton(Static):
    """A one-line clickable icon whose meaning lives in its tooltip."""

    can_focus = True

    BINDINGS = [("enter,space", "press", "Press")]

    class Pressed(Message):
        """The icon was clicked or activated from the keyboard."""

        def __init__(self, button: "IconButton") -> None:
            self.button = button
            super().__init__()

        @property
        def control(self) -> "IconButton":
            return self.button

    def __init__(self, icon: str, tooltip: str, **kwargs):
        super().__init__(icon, **kwargs)
        self.tooltip = tooltip

    def on_click(self, event) -> None:
        event.stop()
        self.action_press()

    def action_press(self) -> None:
        self.post_message(self.Pressed(self))


class NamePrompt(ModalScreen[str | None]):
    """Ask for a name, showing which directory it will be created in."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, title: str, target: Path, root: Path, placeholder: str):
        super().__init__()
        self.prompt_title = title
        self.target = target
        self.root = root
        self.placeholder = placeholder

    def compose(self) -> ComposeResult:
        try:
            where = self.target.relative_to(self.root)
            where = "." if str(where) == "." else str(where)
        except ValueError:
            where = str(self.target)
        with Vertical(classes="prompt-box"):
            yield Label(self.prompt_title, classes="prompt-title")
            yield Label(f"in {where}{'' if where.endswith('/') else '/'}",
                        classes="prompt-where")
            yield Input(placeholder=self.placeholder, id="prompt-input")
            yield Label("enter to create · esc to cancel", classes="prompt-hint")

    def on_mount(self) -> None:
        self.query_one("#prompt-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.dismiss(event.value.strip() or None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ExplorerToolbar(Horizontal):
    """The row of create/refresh icons above the file tree."""

    def compose(self) -> ComposeResult:
        yield IconButton("+📄", "New File", id="new-file-btn", classes="tool-icon")
        yield IconButton("+📁", "New Folder", id="new-folder-btn", classes="tool-icon")
        yield IconButton("🔄", "Refresh", id="refresh-btn", classes="tool-icon")


class ActivityTab(Static):
    """A single icon in the activity bar. The name lives in its tooltip."""

    can_focus = True

    BINDINGS = [("enter,space", "select", "Show")]

    class Selected(Message):
        """An activity icon was chosen."""

        def __init__(self, panel_id: str) -> None:
            self.panel_id = panel_id
            super().__init__()

    def __init__(self, icon: str, name: str, panel_id: str, **kwargs):
        super().__init__(icon, classes="activity-tab", **kwargs)
        self.panel_id = panel_id
        self.tooltip = name

    def on_click(self, event) -> None:
        event.stop()
        self.action_select()

    def action_select(self) -> None:
        self.post_message(self.Selected(self.panel_id))


class ActivityBar(Vertical):
    """The narrow vertical strip of icons down the left of the sidebar."""

    def compose(self) -> ComposeResult:
        yield ActivityTab("📁", "Explorer", EXPLORER_PANEL, id="tab-explorer")
        yield ActivityTab("🔍", "Search", SEARCH_PANEL, id="tab-search")

    def highlight(self, panel_id: str) -> None:
        """Mark the icon owning `panel_id` as the active one."""
        for tab in self.query(ActivityTab):
            tab.set_class(tab.panel_id == panel_id, "-active")


class CLISidebar(Horizontal):
    """The activity sidebar: an icon strip plus the panel it selects."""

    IGNORED = IGNORED

    def __init__(self, path: str | Path = ".", **kwargs):
        super().__init__(**kwargs)
        self.path = Path(path).resolve()
        self.add_class("sidebar")

    def compose(self) -> ComposeResult:
        yield ActivityBar(id="activity-bar")
        with ContentSwitcher(initial=EXPLORER_PANEL, id="sidebar-panels"):
            yield ExplorerPanel(self.path, id=EXPLORER_PANEL)
            yield SearchPanel(self.path, id=SEARCH_PANEL)

    def on_mount(self) -> None:
        self.query_one(ActivityBar).highlight(EXPLORER_PANEL)

    def on_activity_tab_selected(self, event: ActivityTab.Selected) -> None:
        event.stop()
        if event.panel_id == SEARCH_PANEL:
            self.show_search()
        else:
            self.show_explorer()

    def action_toggle_sidebar(self) -> None:
        """Show or hide the sidebar."""
        self.toggle_class("hidden")
        if not self.has_class("hidden"):
            self.query_one(DirectoryTree).focus()

    def show_explorer(self) -> None:
        """Reveal the sidebar on the Explorer panel."""
        self._show(EXPLORER_PANEL)
        self.query_one(DirectoryTree).focus()

    def show_search(self) -> None:
        """Reveal the sidebar on the Search panel, ready to type."""
        self._show(SEARCH_PANEL)
        self.query_one("#search-box", Input).focus()

    def _show(self, panel_id: str) -> None:
        self.remove_class("hidden")
        self.query_one("#sidebar-panels", ContentSwitcher).current = panel_id
        self.query_one(ActivityBar).highlight(panel_id)

    def reload(self) -> None:
        """Re-read the directory from disk."""
        self.query_one(DirectoryTree).reload()


class Explorer(DirectoryTree):
    """A directory tree that hides noise like `.git` and `__pycache__`."""

    def filter_paths(self, paths):
        return [p for p in paths if p.name not in IGNORED]


class ExplorerPanel(Vertical):
    """The file tree plus its create/refresh toolbar."""

    class FileCreated(Message):
        """A new file was created and should be opened."""

        def __init__(self, path: Path) -> None:
            self.path = path
            super().__init__()

    def __init__(self, root: str | Path = ".", **kwargs):
        super().__init__(**kwargs)
        self.root = Path(root).resolve()

    def compose(self) -> ComposeResult:
        yield ExplorerToolbar(id="explorer-toolbar")
        yield Explorer(self.root, id="file-tree")

    @property
    def tree(self) -> Explorer:
        return self.query_one("#file-tree", Explorer)

    def target_directory(self) -> Path:
        """Where a new entry should go, based on what's selected.

        A highlighted directory is used as-is; a highlighted file contributes
        its parent; with nothing highlighted we fall back to the root.
        """
        node = self.tree.cursor_node
        if node is None or node.data is None:
            return self.root
        path = Path(node.data.path)
        return path if path.is_dir() else path.parent

    def on_icon_button_pressed(self, event: IconButton.Pressed) -> None:
        event.stop()
        if event.button.id == "refresh-btn":
            self.tree.reload()
            self.notify("Explorer refreshed.")
            return

        is_file = event.button.id == "new-file-btn"
        target = self.target_directory()
        self.app.push_screen(
            NamePrompt(
                "New File" if is_file else "New Folder",
                target,
                self.root,
                "name.py" if is_file else "folder-name",
            ),
            lambda name: self._create(name, target, is_file),
        )

    def _create(self, name: str | None, target: Path, is_file: bool) -> None:
        """Create `name` under `target`, then reveal it."""
        if not name:
            return

        candidate = (target / name).resolve()
        # Keep creation inside the workspace, so a stray `../` can't escape it.
        if not candidate.is_relative_to(self.root):
            self.notify(f"{name} is outside the workspace.", severity="error")
            return
        if candidate.exists():
            self.notify(f"{candidate.name} already exists.", severity="warning")
            return

        try:
            if is_file:
                # Intermediate directories let you type `pkg/mod.py` in one go.
                candidate.parent.mkdir(parents=True, exist_ok=True)
                candidate.touch()
            else:
                candidate.mkdir(parents=True)
        except OSError as error:
            self.notify(f"Could not create {name}: {error}", severity="error")
            return

        shown = candidate.relative_to(self.root)
        self.notify(f"Created {shown}")
        self.tree.reload()
        if is_file:
            self.post_message(self.FileCreated(candidate))


class SearchPanel(Vertical):
    """Search file contents across the workspace and jump to a hit."""

    class ResultSelected(Message):
        """A search hit was chosen."""

        def __init__(self, path: Path, line: int) -> None:
            self.path = path
            self.line = line
            super().__init__()

    def __init__(self, root: str | Path = ".", **kwargs):
        super().__init__(**kwargs)
        self.root = Path(root).resolve()

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search in files…", id="search-box", classes="search_box")
        # `compact` drops Button's top/bottom border rows, which is what makes a
        # height of 1 leave any room for the label.
        yield Button("🔍 Search", id="search-btn", classes="search_btn", compact=True)
        yield Label("", id="search-status", classes="search-status")
        tree: Tree[tuple[Path, int] | None] = Tree("Results", id="search-results")
        tree.show_root = False
        yield tree

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.search(self.query_one("#search-box", Input).value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.search(event.value)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        event.stop()
        target = event.node.data
        if target is not None:
            path, line = target
            self.post_message(self.ResultSelected(path, line))

    def search(self, query: str) -> None:
        """Kick off a search for `query`."""
        tree = self.query_one("#search-results", Tree)
        tree.clear()
        query = query.strip()
        if not query:
            self._set_status("Type something to search for.")
            return
        self._set_status(f"Searching for {query!r}…")
        self._run_search(query)

    @work(thread=True, exclusive=True, group="file-search")
    def _run_search(self, query: str) -> None:
        """Scan the workspace off the UI thread and stream hits back."""
        needle = query.lower()
        hits = 0
        files = 0
        for path in sorted(self.root.rglob("*")):
            if hits >= MAX_RESULTS:
                break
            if not path.is_file() or any(part in IGNORED for part in path.parts):
                continue
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            matches = [
                (number, line)
                for number, line in enumerate(text.splitlines(), start=1)
                if needle in line.lower()
            ]
            if not matches:
                continue
            files += 1
            hits += len(matches)
            self.app.call_from_thread(self._add_file_results, path, matches)

        self.app.call_from_thread(
            self._set_status,
            f"No results for {query!r}." if not hits else f"{hits} hits in {files} files"
            + (" (truncated)" if hits >= MAX_RESULTS else ""),
        )

    def _add_file_results(
        self, path: Path, matches: list[tuple[int, str]]
    ) -> None:
        tree = self.query_one("#search-results", Tree)
        try:
            label = str(path.relative_to(self.root))
        except ValueError:
            label = str(path)
        node = tree.root.add(label, data=None, expand=True)
        for number, line in matches:
            node.add_leaf(f"{number}: {line.strip()[:120]}", data=(path, number))

    def _set_status(self, message: str) -> None:
        self.query_one("#search-status", Label).update(message)
