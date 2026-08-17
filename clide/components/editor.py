import difflib
from pathlib import Path

from textual import events
from textual.app import ComposeResult
from textual.await_complete import AwaitComplete
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import (
    ContentSwitcher,
    Label,
    TabbedContent,
    TabPane,
    TextArea,
)
from textual.widgets._tabbed_content import ContentTab, ContentTabs

DIRTY_MARK = "●"
CLEAN_MARK = " "
CLOSE_MARK = "✕"

LANGUAGES = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "javascript",
    ".tsx": "javascript",
    ".json": "json",
    ".html": "html",
    ".h": "c++",
    ".c": "c",
    ".css": "css",
    ".tcss": "css",
    ".md": "markdown",
    ".sh": "bash",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".sql": "sql",
    ".toml": "toml",
    ".xml": "xml",
    ".yml": "yaml",
    ".yaml": "yaml",
}


_AVAILABLE: set[str] | None = None


def _language_for(path: Path) -> str | None:
    """Pick a syntax language for `path`, or `None` if we have no highlighter."""
    global _AVAILABLE
    language = LANGUAGES.get(path.suffix.lower())
    if language is None:
        return None
    # Not every language in the table ships with the installed tree-sitter set.
    if _AVAILABLE is None:
        _AVAILABLE = TextArea("").available_languages
    return language if language in _AVAILABLE else None


class FileTab(ContentTab):
    """A tab label with a trailing ✕ that closes the file.

    Textual's `Tab` renders a single string rather than child widgets, so the ✕
    is part of the label and we tell a close-click from an activate-click by
    where in the tab the pointer landed.
    """

    class CloseRequested(Message):
        """The ✕ on a tab was clicked."""

        def __init__(self, tab: "FileTab") -> None:
            self.tab = tab
            super().__init__()

        @property
        def control(self) -> "FileTab":
            return self.tab

    @property
    def pane_id(self) -> str:
        """The id of the `EditorTab` this tab drives."""
        return ContentTab.sans_prefix(self.id or "")

    def _on_click(self, event: events.Click) -> None:
        # `event.x` is relative to the outer region (padding included) while
        # `size.width` is the content width, so shift into content coordinates
        # before testing. The label ends with ✕, so it owns the last content
        # cell; the right padding counts as part of the hit area too.
        content_x = event.x - self.styles.padding.left
        if content_x >= self.size.width - 1:
            event.stop()
            self.post_message(self.CloseRequested(self))
            return
        self.post_message(self.Clicked(self))


class EditorTabs(TabbedContent):
    """A `TabbedContent` whose tabs are `FileTab`s.

    `TabbedContent.add_pane` hardcodes `ContentTab`, so the mount step is
    reproduced here with our own tab class.
    """

    def add_pane(
        self,
        pane: TabPane,
        *,
        before: TabPane | str | None = None,
        after: TabPane | str | None = None,
    ) -> AwaitComplete:
        if isinstance(before, TabPane):
            before = before.id
        if isinstance(after, TabPane):
            after = after.id
        tabs = self.get_child_by_type(ContentTabs)
        pane = self._set_id(pane, self._generate_tab_id())
        assert pane.id is not None
        pane.display = False
        label = pane.tab_label if isinstance(pane, EditorTab) else pane._title
        return AwaitComplete(
            tabs.add_tab(
                FileTab(label, pane.id),
                before=before if before is None else ContentTab.add_prefix(before),
                after=after if after is None else ContentTab.add_prefix(after),
            ),
            self.get_child_by_type(ContentSwitcher).mount(pane),
        )


class EditorTab(TabPane):
    """One open file: a tab label plus its own text area."""

    def __init__(self, path: Path, text: str, **kwargs):
        self.file_path = path
        self.dirty = False
        self._saved_text = text
        self._initial_text = text
        self._close_armed = False
        super().__init__(path.name, **kwargs)

    def compose(self) -> ComposeResult:
        yield TextArea.code_editor(
            self._initial_text,
            language=_language_for(self.file_path),
            soft_wrap=False,
            classes="editor-area",
        )

    @property
    def text_area(self) -> TextArea:
        return self.query_one(TextArea)

    @property
    def tab_label(self) -> str:
        """`● name ✕` when dirty, `  name ✕` when clean.

        The marker slot is always one cell wide so tabs don't jump around as
        files go in and out of the unsaved state.
        """
        mark = DIRTY_MARK if self.dirty else CLEAN_MARK
        return f"{mark} {self.file_path.name} {CLOSE_MARK}"

    @property
    def status_text(self) -> str:
        # Relative to the workspace, which the CLI can point somewhere other
        # than the current directory.
        root = getattr(self.app, "workspace", None) or Path.cwd()
        try:
            shown = self.file_path.relative_to(root)
        except ValueError:
            shown = self.file_path
        return f"{shown}{' *' if self.dirty else ''}"

    def needs_close_confirmation(self) -> bool:
        """True the first time a dirty tab is asked to close; False thereafter.

        Arms the tab so a second close goes through, and any further edit or
        save disarms it again (see `_mark_dirty`).
        """
        if not self.dirty or self._close_armed:
            return False
        self._close_armed = True
        return True

    def unsaved_summary(self) -> str:
        """Describe the unsaved edits, e.g. `+4 -1 lines`.

        The dirty flag itself is an exact text comparison; `difflib` is used
        here only to say *how much* changed, which the comparison can't.
        """
        saved = self._saved_text.splitlines()
        current = self.text_area.text.splitlines()
        matcher = difflib.SequenceMatcher(None, saved, current, autojunk=False)
        added = removed = 0
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op in ("replace", "delete"):
                removed += i2 - i1
            if op in ("replace", "insert"):
                added += j2 - j1
        parts = []
        if added:
            parts.append(f"+{added}")
        if removed:
            parts.append(f"-{removed}")
        return f"{' '.join(parts)} lines" if parts else "unsaved changes"

    def goto_line(self, line: int) -> None:
        """Put the cursor on `line` (1-based) and scroll it into view."""
        area = self.text_area
        row = max(0, min(line - 1, area.document.line_count - 1))
        area.cursor_location = (row, 0)
        area.scroll_cursor_visible(center=True)

    def save(self) -> bool:
        """Write the buffer back to disk. Returns True on success."""
        try:
            self.file_path.write_text(self.text_area.text, encoding="utf-8")
        except OSError as error:
            self.notify(f"Save failed: {error}", severity="error")
            return False
        self._saved_text = self.text_area.text
        self._mark_dirty(False)
        return True

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Track unsaved edits."""
        event.stop()
        self._mark_dirty(event.text_area.text != self._saved_text)

    def _mark_dirty(self, dirty: bool) -> None:
        if dirty == self.dirty:
            return
        self.dirty = dirty
        # Editing (or saving) after a refused close means the next ✕ must warn again.
        self._close_armed = False
        self.query_ancestor(CLIEditor).refresh_tab(self)


class CLIEditor(Vertical):
    """A tabbed text editor: one tab per open file, plus a status bar."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._tab_counter = 0

    def compose(self) -> ComposeResult:
        yield Label(
            "No file open — pick one in the explorer.",
            classes="editor-placeholder",
            id="editor-placeholder",
        )
        yield EditorTabs(id="editor-tabs")
        yield Label("No file open", classes="editor-status", id="editor-status")

    def on_mount(self) -> None:
        self._sync_chrome()

    @property
    def tabs(self) -> EditorTabs:
        return self.query_one("#editor-tabs", EditorTabs)

    @property
    def active_tab(self) -> EditorTab | None:
        pane = self.tabs.active_pane
        return pane if isinstance(pane, EditorTab) else None

    def open_file(self, path: str | Path, line: int | None = None) -> None:
        """Open `path` in a new tab, or focus its existing tab."""
        path = Path(path).resolve()

        existing = self._tab_for(path)
        if existing is not None:
            self._activate(existing, line)
            return

        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            self.notify(f"Cannot open {path.name}: {error}", severity="error")
            return

        self._tab_counter += 1
        tab = EditorTab(path, text, id=f"file-tab-{self._tab_counter}")
        # `call_next` keeps mounts serialized, so tabs appear in the order asked for.
        self.call_next(self._mount_tab, tab, line)

    async def _mount_tab(self, tab: EditorTab, line: int | None) -> None:
        await self.tabs.add_pane(tab)
        self._activate(tab, line)
        self._sync_chrome()

    def _tab_for(self, path: Path) -> EditorTab | None:
        for tab in self.query(EditorTab):
            if tab.file_path == path:
                return tab
        return None

    def _activate(self, tab: EditorTab, line: int | None = None) -> None:
        self.tabs.active = tab.id or ""
        if line is not None:
            tab.goto_line(line)
        tab.text_area.focus()
        self._sync_chrome()

    def refresh_tab(self, tab: EditorTab) -> None:
        """Refresh a tab's label (dirty marker) and the status bar."""
        try:
            self.tabs.get_tab(tab).label = tab.tab_label
        except Exception:
            pass
        self._sync_chrome()

    def action_save(self) -> None:
        """Save the file in the active tab."""
        tab = self.active_tab
        if tab is None:
            self.notify("No file open.", severity="warning")
            return
        if tab.save():
            self.notify(f"Saved {tab.file_path.name}")

    def action_close_tab(self) -> None:
        """Close the active tab."""
        tab = self.active_tab
        if tab is None:
            self.notify("No file open.", severity="warning")
            return
        self.close_tab(tab)

    def on_file_tab_close_requested(self, event: FileTab.CloseRequested) -> None:
        """The ✕ on a tab was clicked."""
        event.stop()
        try:
            pane = self.tabs.get_pane(event.tab.pane_id)
        except Exception:
            return
        if isinstance(pane, EditorTab):
            self.close_tab(pane)

    def close_tab(self, tab: EditorTab) -> None:
        """Close `tab`, warning once first if it has unsaved changes."""
        if tab.needs_close_confirmation():
            self.notify(
                f"{tab.file_path.name} has unsaved changes ({tab.unsaved_summary()}) — "
                "ctrl+s to save, or close again to discard.",
                severity="warning",
            )
            return
        self.call_next(self._close, tab)

    async def _close(self, tab: EditorTab) -> None:
        await self.tabs.remove_pane(tab.id or "")
        self._sync_chrome()
        remaining = self.active_tab
        if remaining is not None:
            remaining.text_area.focus()

    def action_next_tab(self) -> None:
        self._cycle(1)

    def action_previous_tab(self) -> None:
        self._cycle(-1)

    def _cycle(self, step: int) -> None:
        tabs = list(self.query(EditorTab))
        current = self.active_tab
        if len(tabs) < 2 or current is None:
            return
        self._activate(tabs[(tabs.index(current) + step) % len(tabs)])

    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        event.stop()
        self._sync_chrome()

    def on_tabbed_content_cleared(self, event: TabbedContent.Cleared) -> None:
        event.stop()
        self._sync_chrome()

    def _sync_chrome(self) -> None:
        """Keep the placeholder and status bar in step with the open tabs."""
        tab = self.active_tab
        has_tabs = self.tabs.tab_count > 0
        self.query_one("#editor-placeholder", Label).display = not has_tabs
        self.tabs.display = has_tabs
        self.query_one("#editor-status", Label).update(
            tab.status_text if tab is not None else "No file open"
        )
