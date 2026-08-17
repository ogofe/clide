from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, DirectoryTree, Footer, Label
from textual.widgets import Header as BaseHeader
from textual.widgets._header import HeaderTitle

from clide.components.editor import CLIEditor
from clide.components.sidebar import CLISidebar, SearchPanel

APP_TITLE = "Clide - Your Friendly Terminal IDE"


class AppHeader(BaseHeader):
    """The Clide title bar, with a clock and a close button."""

    ALLOW_MAXIMIZE = True

    def __init__(self, show_clock: bool = False, **kwargs):
        super().__init__(show_clock, **kwargs)
        self.tall = False

    def compose(self) -> ComposeResult:
        with Horizontal(classes="app-header"):
            yield HeaderTitle(classes="header-title", content=APP_TITLE)
            yield Label("", id="header-clock", classes="header-clock")
            yield Button("X Close", classes="close_btn", id="close-btn", compact=lambda: self.tall if self.tall else False)

    def on_mount(self) -> None:
        """Start ticking the clock (our compose replaces Header's own clock)."""
        if self._show_clock:
            self._tick_clock()
            self.set_interval(1, self._tick_clock, name="clide header clock")

    def _tick_clock(self) -> None:
        self.query_one("#header-clock", Label).update(
            datetime.now().strftime("%X")
        )


class Clide(App):
    """A simple terminal IDE."""

    CSS_PATH = "clide.tcss"
    # `priority=True` so the focused TextArea can't swallow the IDE's own keys —
    # it binds ctrl+w to delete-word-left and ctrl+d to delete-right.
    BINDINGS = [
        Binding("ctrl+b", "toggle_sidebar", "Toggle sidebar", priority=True),
        Binding("ctrl+shift+e", "show_explorer", "Explorer", priority=True),
        Binding("ctrl+shift+f", "show_search", "Search", priority=True),
        Binding("ctrl+s", "save", "Save file", priority=True),
        Binding("ctrl+w", "close_tab", "Close file", priority=True),
        Binding("ctrl+pagedown", "next_tab", "Next file", priority=True),
        Binding("ctrl+pageup", "previous_tab", "Previous file", priority=True),
        Binding("ctrl+d", "toggle_dark", "Toggle dark mode", priority=True),
        Binding("ctrl+shift+q", "quit", "Quit the app", priority=True),
    ]

    def __init__(self, workspace: str | Path = ".", files: Sequence[str | Path] = (), **kwargs):
        """
        Args:
            workspace: Directory the explorer and search are rooted at.
            files: Files to open in editor tabs at startup.
        """
        super().__init__(**kwargs)
        self.workspace = Path(workspace).resolve()
        self.startup_files = [Path(f) for f in files]

    def compose(self) -> ComposeResult:
        self.title = APP_TITLE
        yield AppHeader(show_clock=True)
        with Horizontal(classes="clide-main"):
            yield CLISidebar(self.workspace, id="sidebar")
            yield CLIEditor(id="editor")
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = str(self.workspace)
        for path in self.startup_files:
            self.editor.open_file(path)

    @property
    def editor(self) -> CLIEditor:
        return self.query_one(CLIEditor)

    @property
    def sidebar(self) -> CLISidebar:
        return self.query_one(CLISidebar)

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Open the file the user picked in the explorer."""
        event.stop()
        self.editor.open_file(event.path)

    def on_search_panel_result_selected(self, event: SearchPanel.ResultSelected) -> None:
        """Open the file a search hit points at, on the matching line."""
        event.stop()
        self.editor.open_file(event.path, line=event.line)

    def action_toggle_sidebar(self) -> None:
        self.sidebar.action_toggle_sidebar()

    def action_show_explorer(self) -> None:
        self.sidebar.show_explorer()

    def action_show_search(self) -> None:
        self.sidebar.show_search()

    def action_save(self) -> None:
        self.editor.action_save()

    def action_close_tab(self) -> None:
        self.editor.action_close_tab()

    def action_next_tab(self) -> None:
        self.editor.action_next_tab()

    def action_previous_tab(self) -> None:
        self.editor.action_previous_tab()

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.theme = ("textual-light" if self.theme == "textual-dark" else "textual-dark")

    @on(Button.Pressed, "#close-btn")
    def handle_close_button(self, event: Button.Pressed) -> None:
        """Quit the application."""
        event.stop()
        self.exit()


if __name__ == "__main__":
    from clide.cli import main

    raise SystemExit(main())
