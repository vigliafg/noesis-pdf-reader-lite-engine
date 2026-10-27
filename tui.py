"""Modern Textual front-end for the ``-gui`` export wizard.

Five steps mirroring the desktop ``ExportWizardDialog`` (pages → content →
languages/engine → output → summary) plus a live progress screen and a result
screen. It is mouse-aware (click, wheel, double-click) and keyboard-driven,
uses a **file picker** for the input PDF and the destination folder, and
degrades gracefully: :func:`launch` falls back to the line wizard
(:mod:`tui_fallback`) when the terminal cannot host Textual.

All the engine work is delegated to :mod:`tui_state`; this module only renders
and collects input.
"""
from __future__ import annotations

from pathlib import Path

import theme as theme_mod

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button, Checkbox, ContentSwitcher, DirectoryTree, Input, Label, ProgressBar,
    RadioButton, RadioSet, RichLog, Select, Static,
)

import main as engine
from i18n import TRANSLATION_ENGINES, TRANSLATION_LANGUAGES, flag_endonym

import tui_i18n as ti
import tui_state
from tui_state import ExportOptions

__all__ = ["ExportWizardApp", "FilePicker"]

#: Wizard steps, in the order shown by the step bar.
STEPS = ("pages", "content", "langs", "output", "summary")


# ── helpers ──────────────────────────────────────────────────────────────────


def _lang_label(code: str) -> str:
    text = flag_endonym(code)
    return ti.strip_non_ascii(text) if ti.ascii_mode() else text


def _int_or(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ── file picker ──────────────────────────────────────────────────────────────


class _FilteredTree(DirectoryTree):
    """DirectoryTree with the wizard's filters (hidden files, extensions)."""

    def __init__(self, path, *, dirs_only: bool, hidden: bool,
                 suffixes: tuple[str, ...], **kwargs):
        self._dirs_only = dirs_only
        self._hidden = hidden
        self._suffixes = tuple(s.lower() for s in suffixes)
        super().__init__(path, **kwargs)

    def set_hidden(self, hidden: bool) -> None:
        self._hidden = hidden
        self.reload()

    def filter_paths(self, paths):
        out = []
        for path in paths:
            try:
                is_dir = path.is_dir()
            except OSError:
                continue
            if path.name.startswith(".") and not self._hidden:
                continue
            if is_dir:
                out.append(path)
                continue
            if self._dirs_only:
                continue
            if self._suffixes and path.suffix.lower() not in self._suffixes:
                continue
            out.append(path)
        return out


class FilePicker(ModalScreen):
    """A mouse-friendly file/directory picker (returns a ``Path`` or ``None``)."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("backspace", "up", "Up", show=False),
    ]

    def __init__(self, start, *, mode: str = "open",
                 suffixes=(".pdf",)):
        super().__init__()
        self._mode = mode
        self._suffixes = tuple(suffixes)
        start = Path(start).expanduser() if start else Path.home()
        self._root = start if start.is_dir() else start.parent
        if not self._root.is_dir():
            self._root = Path.home()
        self._hidden = False
        self._chosen: Path | None = None

    # ── layout ─────────────────────────────────────────────────────────
    def compose(self) -> ComposeResult:
        title = (ti.T("tui.filepicker.folder_title") if self._mode == "dir"
                 else ti.T("tui.filepicker.title"))
        with VerticalScroll(id="picker"):
            yield Static(title, id="picker-title")
            yield Input(value=str(self._root), id="picker-path")
            yield _FilteredTree(
                self._root, dirs_only=(self._mode == "dir"),
                hidden=self._hidden, suffixes=self._suffixes, id="picker-tree")
            with Horizontal(id="picker-buttons"):
                yield Button(ti.T("tui.filepicker.up"), id="picker-up")
                yield Button(ti.T("tui.filepicker.home"), id="picker-home")
                yield Button(ti.T("tui.filepicker.cwd"), id="picker-cwd")
                yield Button(ti.T("tui.filepicker.hidden"),
                             id="picker-hidden")
                yield Button(ti.T("tui.filepicker.cancel"),
                             id="picker-cancel")
                yield Button(ti.T("tui.filepicker.select"),
                             id="picker-select", variant="primary")
            yield Static(ti.T("tui.filepicker.hint"), id="picker-hint")

    # ── navigation ─────────────────────────────────────────────────────
    def _go(self, path: Path) -> None:
        path = Path(path).expanduser()
        if not path.is_dir():
            return
        self._root = path
        self.query_one("#picker-path", Input).value = str(path)
        tree = self.query_one("#picker-tree", _FilteredTree)
        tree.path = path

    def _tree(self) -> _FilteredTree:
        return self.query_one("#picker-tree", _FilteredTree)

    def _accept(self, path: Path) -> None:
        if self._mode == "dir":
            if path.is_dir():
                self.dismiss(path)
            else:
                self.notify(ti.T("tui.filepicker.folder_title"),
                            severity="warning")
            return
        if path.is_dir():
            self._go(path)
            return
        if path.is_file():
            self.dismiss(path)
        else:
            self.notify(ti.T("tui.filepicker.title"), severity="warning")

    # ── events ─────────────────────────────────────────────────────────
    def on_directory_tree_directory_selected(
            self, event: DirectoryTree.DirectorySelected) -> None:
        self._go(event.path)

    def on_directory_tree_file_selected(
            self, event: DirectoryTree.FileSelected) -> None:
        self._chosen = event.path
        self.query_one("#picker-path", Input).value = str(event.path)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "picker-path":
            return
        self._accept(Path(event.value.strip() or self._root))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button.id
        if button == "picker-cancel":
            self.dismiss(None)
        elif button == "picker-select":
            raw = self.query_one("#picker-path", Input).value.strip()
            self._accept(Path(raw) if raw else self._root)
        elif button == "picker-up":
            self._go(self._tree().path.parent)
        elif button == "picker-home":
            self._go(Path.home())
        elif button == "picker-cwd":
            self._go(Path.cwd())
        elif button == "picker-hidden":
            self._hidden = not self._hidden
            self._tree().set_hidden(self._hidden)

    def action_up(self) -> None:
        self._go(self._tree().path.parent)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── CSS ──────────────────────────────────────────────────────────────────────

CSS = """
Screen { background: $background; color: $foreground; }

#topbar {
    dock: top;
    height: 3;
    background: $panel;
    color: $foreground;
    padding: 1 2;
    text-style: bold;
}
#stepbar {
    height: 3;
    background: $surface;
    color: $text-muted;
    padding: 1 2;
}
#panes { height: 1fr; }
VerticalScroll { padding: 1 3; }
.h3 { text-style: bold; color: $primary; margin-top: 1; }
.hint { color: $text-muted; }
.label { color: $text-muted; }
.row { height: auto; }
.row Input { width: 1fr; }
Input { background: $surface; border: tall $border-blurred; }
Input:focus { border: tall $primary; }
Button { margin: 0 1 0 0; }
RadioSet { height: auto; width: 1fr; margin: 1 0; }
Select { width: 1fr; margin-bottom: 1; }
#footerbar {
    dock: bottom;
    height: 3;
    background: $panel;
    align-horizontal: right;
    padding: 0 2;
}
#destbar {
    height: auto;
    max-height: 4;
    background: $surface;
    color: $text-muted;
    border-top: solid $border-blurred;
    padding: 0 2;
}
#destbar.-unset { color: $text-disabled; }
#footerbar Button { margin-left: 1; }
#pages-preview { margin-top: 1; }
#out-preview { margin-top: 1; }
#sum-body { padding: 1 0; }
#run-progress { margin: 1 0; }
#run-log { height: 1fr; background: $surface; border: tall $border-blurred; }
#result-body { padding: 1 0; }

FilePicker { align: center middle; }
#picker {
    width: 80%;
    height: 80%;
    background: $surface;
    border: thick $primary;
    padding: 1 2;
}
#picker-title { text-style: bold; color: $primary; }
#picker #picker-tree { height: 1fr; background: $background; }
#picker-buttons { height: auto; align-horizontal: right; margin-top: 1; }
#picker-hint { color: $text-muted; margin-top: 1; }
"""


# ── the app ──────────────────────────────────────────────────────────────────


class ExportWizardApp(App):
    """The five-step export wizard, rendered with Textual."""

    TITLE = "noesis-pdf-reader-lite-engine"
    SUB_TITLE = "-gui"
    CSS = CSS

    BINDINGS = [
        Binding("q", "request_quit", "Quit", show=False),
        Binding("escape", "request_quit", "Quit", show=False),
        Binding("question_mark", "help", "Help", show=False),
        Binding("b", "back", "Back", show=False),
        Binding("n", "next", "Next", show=False),
        Binding("ctrl+r", "run", "Run", show=False),
        Binding("1", "goto(0)", "Step 1", show=False),
        Binding("2", "goto(1)", "Step 2", show=False),
        Binding("3", "goto(2)", "Step 3", show=False),
        Binding("4", "goto(3)", "Step 4", show=False),
        Binding("5", "goto(4)", "Step 5", show=False),
        Binding("a", "toggle_ascii", "ASCII", show=False),
        Binding("l", "toggle_language", "Language", show=False),
        Binding("t", "toggle_theme", "Theme", show=False),
    ]

    def __init__(self, options: ExportOptions, *, dark: bool = True,
                 ansi: bool = False):
        super().__init__()
        self.opts = options
        self._dark = dark
        self._ansi = ansi
        self._view = "pages"
        self._pages: list[int] = []
        self._page_count: int | None = None
        self._cancel = False
        self._done = 0
        self._worker = None
        self._result = None
        # Track whether the user edited the output *Name* field by hand: until
        # then it follows the chosen PDF (``{stem}_estratto``). A name coming
        # from prefs/CLI is explicit and must not be overwritten.
        self._name_touched = bool(options.name and options.name.strip())
        self._last_name_value = ""

        if ansi:
            self.theme = "ansi-dark" if dark else "ansi-light"
        else:
            self.register_theme(_build_theme(True))
            self.register_theme(_build_theme(False))
            self.theme = "noesis-dark" if dark else "noesis-light"

    # ── composition ────────────────────────────────────────────────────
    def on_mount(self) -> None:
        self._goto(self._view)

    def compose(self) -> ComposeResult:
        self._normalize()
        yield Static(self._topbar_text(), id="topbar")
        yield Static(self._stepbar_text(), id="stepbar")
        with ContentSwitcher(initial=f"pane-{self._view}", id="panes"):
            yield from self._pane_pages()
            yield from self._pane_content()
            yield from self._pane_langs()
            yield from self._pane_output()
            yield from self._pane_summary()
            yield from self._pane_run()
            yield from self._pane_result()
        yield Static("", id="destbar")
        with Horizontal(id="footerbar"):
            yield Button(ti.T("export.wizard.back"), id="btn-back")
            yield Button(ti.T("settings.cancel"), id="btn-cancel")
            yield Button(ti.T("export.wizard.next"), id="btn-next",
                         variant="primary")

    # ── panes ──────────────────────────────────────────────────────────
    def _pane_pages(self) -> ComposeResult:
        o = self.opts
        with VerticalScroll(id="pane-pages"):
            yield Static(ti.T("export.wizard.pages.title"), classes="h3")
            yield Static(ti.T("export.wizard.pages.hint"), classes="hint")
            yield Static(ti.T("tui.field.pdf"), classes="label")
            with Horizontal(classes="row"):
                yield Input(value=o.pdf, placeholder="/percorso/file.pdf",
                            id="in-pdf")
                yield Button(ti.T("tui.pick_pdf"), id="btn-pick-pdf")
            yield RadioSet(
                RadioButton(ti.T("tui.pages.all"), id="pm-all",
                            value=(o.pages_mode == "all")),
                RadioButton(ti.T("export.mode.range"), id="pm-range",
                            value=(o.pages_mode == "range")),
                RadioButton(ti.T("export.mode.free"), id="pm-free",
                            value=(o.pages_mode == "free")),
                id="rs-pages")
            with Horizontal(classes="row"):
                yield Label(ti.T("export.range.from.short"))
                yield Input(value=str(o.range_from), id="in-from",
                            type="integer")
                yield Label(ti.T("export.range.to.short"))
                yield Input(value=str(o.range_to), id="in-to", type="integer")
            yield Input(value=o.free_pages,
                        placeholder=ti.T("export.free.placeholder"), id="in-free")
            yield Static(ti.T("export.free.hint"), classes="hint")
            yield Static("", id="pages-preview", classes="hint")

    def _pane_content(self) -> ComposeResult:
        o = self.opts
        with VerticalScroll(id="pane-content"):
            yield Static(ti.T("export.wizard.content.title"), classes="h3")
            yield Static(ti.T("export.wizard.content.hint"), classes="hint")
            yield RadioSet(
                RadioButton(ti.T("export.mode.original"), id="cm-original",
                            value=(o.content == "original")),
                RadioButton(ti.T("export.mode.translated"), id="cm-translated",
                            value=(o.content == "translated")),
                RadioButton(ti.T("export.mode.both"), id="cm-both",
                            value=(o.content == "both")),
                id="rs-content")
            yield Checkbox(ti.T("export.include_images"),
                           value=o.include_images, id="chk-images")
            yield Checkbox(ti.T("export.translate_missing"),
                           value=o.translate_missing, id="chk-missing")

    def _pane_langs(self) -> ComposeResult:
        o = self.opts
        with VerticalScroll(id="pane-langs"):
            yield Static(ti.T("export.wizard.langs.title"), classes="h3")
            yield Static(ti.T("export.wizard.langs.hint"), classes="hint")
            yield Label(ti.T("settings.lang.source"), classes="label")
            yield Select(
                [( _lang_label(code), code) for code in TRANSLATION_LANGUAGES],
                value=o.src, allow_blank=False, id="sel-src")
            yield Label(ti.T("settings.lang.target"), classes="label")
            yield Select(
                [(_lang_label(code), code)
                 for code in TRANSLATION_LANGUAGES if code != "auto"],
                value=o.dst, allow_blank=False, id="sel-dst")
            yield Static(ti.T("export.wizard.step.langs"), classes="h3")
            yield RadioSet(
                *[RadioButton(ti.T(f"engine.option.{code}"), id=f"eng-{code}",
                              value=(o.engine == code))
                  for code in TRANSLATION_ENGINES],
                id="rs-engine")
            yield Label(ti.T("tui.field.ocr"), classes="label")
            yield Input(value=o.ocr_lang,
                        placeholder=ti.T("tui.optional"), id="in-ocr")
            yield Label(ti.T("tui.field.tessdata"), classes="label")
            yield Input(value=o.tessdata,
                        placeholder=ti.T("tui.optional"), id="in-tessdata")

    def _pane_output(self) -> ComposeResult:
        o = self.opts
        with VerticalScroll(id="pane-output"):
            yield Static(ti.T("export.wizard.output.title"), classes="h3")
            # Destination folder + name first: they must be reachable without
            # scrolling past the (long) format/packaging lists.
            yield Label(ti.T("export.wizard.output.folder"), classes="label")
            with Horizontal(classes="row"):
                yield Input(value=o.out_folder or str(tui_state.default_folder()),
                            id="in-folder")
                yield Button(ti.T("tui.pick_folder"), id="btn-pick-folder")
            yield Label(ti.T("export.wizard.output.filename"), classes="label")
            name_value = o.name or tui_state.default_name(o)
            self._last_name_value = name_value
            yield Input(value=name_value, id="in-name")
            yield Static(ti.T("export.output.content_format"), classes="h3")
            buttons = []
            for code in engine._CONTENT_FORMAT_ORDER:
                disabled = (engine.content_format_kind(code) == "pandoc"
                            and not self._pandoc_ready())
                buttons.append(RadioButton(
                    ti.T(f"export.contentfmt.{code}"), id=f"cf-{code}",
                    value=(o.content_format == code), disabled=disabled))
            yield RadioSet(*buttons, id="rs-format")
            yield Static(ti.T("export.output.packaging"), classes="h3")
            allowed = tui_state.allowed_packagings(o.content_format)
            yield RadioSet(
                *[RadioButton(ti.T(f"export.format.{code}"), id=f"pk-{code}",
                              value=(o.packaging == code),
                              disabled=(code not in allowed))
                  for code in engine._PACKAGING_ORDER],
                id="rs-packaging")
            yield Label(ti.T("tui.field.pandoc"), classes="label")
            yield Input(value=o.pandoc, placeholder=ti.T("tui.optional"),
                        id="in-pandoc")
            yield Static("", id="out-preview", classes="hint")

    def _pane_summary(self) -> ComposeResult:
        with VerticalScroll(id="pane-summary"):
            yield Static(ti.T("export.wizard.summary.title"), classes="h3")
            yield Static("", id="sum-body")

    def _pane_run(self) -> ComposeResult:
        with VerticalScroll(id="pane-run"):
            yield Static(ti.T("tui.run.title"), classes="h3")
            yield Static("", id="run-status", classes="hint")
            yield ProgressBar(total=100, show_eta=False, id="run-progress")
            yield RichLog(id="run-log", wrap=True, markup=False)
            yield Button(ti.T("tui.run.cancel"), id="btn-run-cancel",
                         variant="error")

    def _pane_result(self) -> ComposeResult:
        with VerticalScroll(id="pane-result"):
            yield Static(ti.T("tui.run.done"), classes="h3")
            yield Static("", id="result-body")
            with Horizontal(id="result-buttons"):
                yield Button(ti.T("tui.close"), id="btn-close",
                             variant="primary")

    # ── step bar / sync ────────────────────────────────────────────────
    def _topbar_text(self) -> str:
        return "noesis-pdf-reader-lite-engine  ·  " + ti.T("export.wizard.title")

    def _step_index(self) -> int:
        return STEPS.index(self._view) if self._view in STEPS else len(STEPS)

    def _stepbar_text(self) -> str:
        step = self._step_index()
        parts = []
        for i, name in enumerate(STEPS):
            label = f"{i + 1} {ti.T(f'export.wizard.step.{name}')}"
            if i < step:
                parts.append(f"[dim]{label}[/dim]")
            elif i == step:
                parts.append(f"[b]{label}[/b]")
            else:
                parts.append(f"[dim]{label}[/dim]")
        return "   ".join(parts)

    def _goto(self, view: str) -> None:
        self._view = view
        try:
            self.query_one("#panes", ContentSwitcher).current = f"pane-{view}"
            self.query_one("#stepbar", Static).update(self._stepbar_text())
        except Exception:  # noqa: BLE001 — during teardown
            return
        wizard = view in STEPS
        self.query_one("#btn-back").display = wizard and self._step_index() > 0
        self.query_one("#btn-next").display = wizard
        self.query_one("#btn-cancel").display = wizard
        if wizard:
            last = self._step_index() == len(STEPS) - 1
            self.query_one("#btn-next", Button).label = (
                ti.T("export.wizard.start") if last
                else ti.T("export.wizard.next"))
            if view == "pages":
                self._refresh_pages_preview()
            elif view == "output":
                self._refresh_output_preview()
            elif view == "summary":
                self._render_summary()

    # ── state collection ───────────────────────────────────────────────
    def _normalize(self) -> None:
        o = self.opts
        allowed = tui_state.allowed_packagings(o.content_format)
        if o.packaging not in allowed:
            o.packaging = "merged"
        if (engine.content_format_kind(o.content_format) == "pandoc"
                and not self._pandoc_ready()):
            o.content_format = "markdown"

    def _pandoc_ready(self) -> bool:
        return bool(self.opts.pandoc.strip()) or engine.pandoc_path() is not None

    def _set_pages_mode(self, code: str) -> None:
        """Apply a page-selection mode and reflect it on the radio set.

        Called when the user types in the *from/to* or *free* fields so that
        entering a selection implicitly selects the matching mode (otherwise
        the text would be silently ignored while the mode stayed on *all*).
        """
        if self.opts.pages_mode == code:
            return
        self.opts.pages_mode = code
        try:
            self.query_one(f"#pm-{code}", RadioButton).value = True
        except Exception:  # noqa: BLE001 — during teardown / not mounted
            pass

    def _sync_packaging_enabled(self) -> None:
        allowed = tui_state.allowed_packagings(self.opts.content_format)
        for code in engine._PACKAGING_ORDER:
            try:
                self.query_one(f"#pk-{code}", RadioButton).disabled = (
                    code not in allowed)
            except Exception:  # noqa: BLE001
                pass
        if self.opts.packaging not in allowed:
            self.opts.packaging = "merged"
            try:
                self.query_one("#pk-merged", RadioButton).value = True
            except Exception:  # noqa: BLE001
                pass

    def _resolved_name(self) -> str:
        """Output name actually used: the field, or ``{stem}_estratto``."""
        return self.opts.name.strip() or tui_state.default_name(self.opts)

    def _apply_name_default(self) -> None:
        """Keep the *Name* field following the chosen PDF until edited by hand."""
        if self._name_touched:
            return
        try:
            field = self.query_one("#in-name", Input)
        except Exception:  # noqa: BLE001 — not mounted
            return
        default = tui_state.default_name(self.opts)
        if field.value != default:
            self.opts.name = ""
            self._last_name_value = default
            field.value = default

    def _refresh_destbar(self) -> None:
        """Update the always-visible destination bar (folder + name)."""
        try:
            bar = self.query_one("#destbar", Static)
        except Exception:  # noqa: BLE001 — during teardown
            return
        if not self.opts.pdf:
            bar.update(ti.T("tui.destbar.none"))
            bar.add_class("-unset")
            return
        bar.remove_class("-unset")
        folder = self.opts.out_folder.strip() or str(tui_state.default_folder())
        bar.update(ti.T("tui.destbar", folder=folder, name=self._resolved_name()))

    def _refresh_pages_preview(self) -> None:
        self._refresh_destbar()
        if not self.opts.pdf:
            self._page_count = None
        elif self._page_count is None:
            self._page_count = tui_state.read_page_count(self.opts.pdf)
        count = self._page_count
        widget = self.query_one("#pages-preview", Static)
        if not self.opts.pdf or count is None:
            widget.update(ti.T("tui.err.no_pdf"))
            return
        pages, err = tui_state.select_pages(self.opts, count)
        if err is not None:
            widget.update(ti.page_error(err))
            return
        from pages import format_pages_label
        widget.update(ti.T("export.wizard.preview.count", n=len(pages),
                           label=format_pages_label(pages)))

    def _refresh_output_preview(self) -> None:
        self._refresh_destbar()
        if not self.opts.pdf:
            self.query_one("#out-preview", Static).update("")
            return
        count = self._page_count or tui_state.read_page_count(self.opts.pdf) or 0
        pages, _err = tui_state.select_pages(self.opts, count)
        if not pages:
            self.query_one("#out-preview", Static).update("")
            return
        files = tui_state.planned_files(self.opts, pages)
        text = ti.T("tui.summary.planned") + ":\n" + "\n".join(
            f"  {p}" for p in files[:20])
        if len(files) > 20:
            text += f"\n  … (+{len(files) - 20})"
        self.query_one("#out-preview", Static).update(text)

    def _render_summary(self) -> None:
        pages, errors = tui_state.validate(self.opts, self._page_count)
        lines: list[str] = []
        if pages is not None:
            for key, value in tui_state.summary_rows(self.opts, pages):
                lines.append(f"[b]{ti.T(key)}[/b]: {value}")
            lines.append("")
            lines.append(f"[b]{ti.T('tui.summary.planned')}[/b]")
            files = tui_state.planned_files(self.opts, pages)
            if files:
                lines.extend(f"  {p}" for p in files[:50])
                if len(files) > 50:
                    lines.append(f"  … (+{len(files) - 50})")
            else:
                lines.append(f"  {ti.T('tui.summary.nofiles')}")
        for key, params in errors:
            lines.append(f"[red]! {ti.T(key, **params)}[/red]")
        self.query_one("#sum-body", Static).update("\n".join(lines))

    # ── input events ───────────────────────────────────────────────────
    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        pressed = event.pressed.id or ""
        rs_id = event.radio_set.id
        if rs_id == "rs-pages":
            for code in tui_state.PAGES_MODES:
                if pressed == f"pm-{code}":
                    self.opts.pages_mode = code
            self._refresh_pages_preview()
        elif rs_id == "rs-content":
            for code in tui_state.CONTENTS:
                if pressed == f"cm-{code}":
                    self.opts.content = code
        elif rs_id == "rs-engine":
            for code in TRANSLATION_ENGINES:
                if pressed == f"eng-{code}":
                    self.opts.engine = code
        elif rs_id == "rs-format":
            for code in engine._CONTENT_FORMAT_ORDER:
                if pressed == f"cf-{code}":
                    self.opts.content_format = code
            self._sync_packaging_enabled()
            self._refresh_output_preview()
        elif rs_id == "rs-packaging":
            for code in engine._PACKAGING_ORDER:
                if pressed == f"pk-{code}":
                    self.opts.packaging = code
            self._refresh_output_preview()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "chk-images":
            self.opts.include_images = event.value
        elif event.checkbox.id == "chk-missing":
            self.opts.translate_missing = event.value

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "sel-src" and event.value != Select.BLANK:
            self.opts.src = str(event.value)
        elif event.select.id == "sel-dst" and event.value != Select.BLANK:
            self.opts.dst = str(event.value)

    def on_input_changed(self, event: Input.Changed) -> None:
        ident = event.input.id
        value = event.value
        if ident == "in-pdf":
            self.opts.pdf = value.strip()
            self._page_count = None
            self._apply_name_default()
            self._refresh_pages_preview()
        elif ident == "in-from":
            new = _int_or(value, self.opts.range_from)
            if new != self.opts.range_from:
                self.opts.range_from = new
                self._set_pages_mode("range")
            self._refresh_pages_preview()
        elif ident == "in-to":
            new = _int_or(value, self.opts.range_to)
            if new != self.opts.range_to:
                self.opts.range_to = new
                self._set_pages_mode("range")
            self._refresh_pages_preview()
        elif ident == "in-free":
            new = value or "all"
            if new != self.opts.free_pages:
                self.opts.free_pages = new
                self._set_pages_mode("free")
            self._refresh_pages_preview()
        elif ident == "in-folder":
            self.opts.out_folder = value.strip()
            self._refresh_output_preview()
        elif ident == "in-name":
            if value != self._last_name_value:
                self._name_touched = True
            self._last_name_value = value
            self.opts.name = value.strip()
            self._refresh_output_preview()
        elif ident == "in-ocr":
            self.opts.ocr_lang = value.strip()
        elif ident == "in-tessdata":
            self.opts.tessdata = value.strip()
        elif ident == "in-pandoc":
            self.opts.pandoc = value.strip()
            ready = self._pandoc_ready()
            for code in engine._CONTENT_FORMAT_ORDER:
                if engine.content_format_kind(code) == "pandoc":
                    try:
                        self.query_one(f"#cf-{code}", RadioButton).disabled = (
                            not ready)
                    except Exception:  # noqa: BLE001
                        pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        ident = event.button.id
        if ident == "btn-pick-pdf":
            self._pick_file()
        elif ident == "btn-pick-folder":
            self._pick_folder()
        elif ident == "btn-back":
            self.action_back()
        elif ident == "btn-next":
            self.action_next()
        elif ident == "btn-cancel":
            self.action_request_quit()
        elif ident == "btn-run-cancel":
            self._cancel = True
            self.notify(ti.T("tui.run.cancelled"), severity="warning")
        elif ident == "btn-close":
            self.exit(self._exit_code())

    # ── file pickers ───────────────────────────────────────────────────
    def _pick_file(self) -> None:
        start = self.opts.pdf or str(Path.home())
        self.push_screen(FilePicker(start, mode="open", suffixes=(".pdf",)),
                         self._on_picked_pdf)

    def _on_picked_pdf(self, path) -> None:
        if path is None:
            return
        self.opts.pdf = str(path)
        self._page_count = None
        try:
            self.query_one("#in-pdf", Input).value = str(path)
        except Exception:  # noqa: BLE001
            pass
        self._apply_name_default()
        self._refresh_pages_preview()

    def _pick_folder(self) -> None:
        start = self.opts.out_folder or str(tui_state.default_folder())
        self.push_screen(FilePicker(start, mode="dir"), self._on_picked_folder)

    def _on_picked_folder(self, path) -> None:
        if path is None:
            return
        self.opts.out_folder = str(path)
        try:
            self.query_one("#in-folder", Input).value = str(path)
        except Exception:  # noqa: BLE001
            pass
        self._refresh_output_preview()

    # ── navigation actions ─────────────────────────────────────────────
    def action_goto(self, index: int) -> None:
        if self._view in ("run", "result"):
            return
        index = max(0, min(int(index), len(STEPS) - 1))
        if index > self._step_index() and not self._can_leave_pages():
            return
        self._goto(STEPS[index])

    def _can_leave_pages(self) -> bool:
        """Validate the pages step before moving past it."""
        if self._step_index() != 0:
            return True
        message = self._pages_error()
        if message:
            self.notify(message, severity="error")
            return False
        return True

    def action_next(self) -> None:
        if self._view not in STEPS:
            return
        step = self._step_index()
        if step == 0 and not self._can_leave_pages():
            return
        if step == len(STEPS) - 1:
            self.action_run()
            return
        self._goto(STEPS[step + 1])

    def action_back(self) -> None:
        if self._view not in STEPS:
            return
        step = self._step_index()
        if step > 0:
            self._goto(STEPS[step - 1])

    def _pages_error(self) -> str:
        if not self.opts.pdf:
            return ti.T("tui.err.no_pdf")
        if self._page_count is None:
            self._page_count = tui_state.read_page_count(self.opts.pdf)
        if not self._page_count:
            return ti.T("tui.err.no_pdf")
        _pages, err = tui_state.select_pages(self.opts, self._page_count)
        return ti.page_error(err)

    # ── toggles ────────────────────────────────────────────────────────
    def action_toggle_language(self) -> None:
        ti.set_language("en" if ti.language() == "it" else "it")
        self.refresh(recompose=True)
        self.call_after_refresh(lambda: self._goto(self._view))

    def action_toggle_ascii(self) -> None:
        ti.set_ascii(not ti.ascii_mode())
        self.refresh(recompose=True)
        self.call_after_refresh(
            lambda: self._goto(self._view) if self._view in STEPS
            else None)

    def action_toggle_theme(self) -> None:
        self._dark = not self._dark
        if self._ansi:
            self.theme = "ansi-dark" if self._dark else "ansi-light"
        else:
            self.theme = "noesis-dark" if self._dark else "noesis-light"

    def action_help(self) -> None:
        self.notify(ti.T("tui.help.body"), title=ti.T("tui.help.title"),
                    timeout=0)

    def action_request_quit(self) -> None:
        if self._view == "run":
            self._cancel = True
            return
        self.exit(self._exit_code())

    def action_run(self) -> None:
        pages, errors = tui_state.validate(self.opts, self._page_count)
        if pages is None or errors:
            for key, params in errors:
                self.notify(ti.T(key, **params), severity="error")
            return
        self._pages = list(pages)
        self._cancel = False
        self._done = 0
        tui_state.save_prefs(self.opts)
        self._goto("run")
        self.query_one("#run-status", Static).update(
            ti.T("tui.run.progress", done=0, total=len(pages)))
        self.query_one("#run-progress", ProgressBar).update(
            total=max(1, len(pages)), progress=0)
        self.query_one("#run-log", RichLog).clear()
        self._run_export()

    # ── the background export ──────────────────────────────────────────
    @work(thread=True, exclusive=True)
    def _run_export(self) -> None:
        options = self.opts

        def on_page(page, entry, err):
            self.call_from_thread(self._on_page, page, err)

        try:
            result = tui_state.execute(
                options, on_page=on_page,
                should_cancel=lambda: self._cancel)
        except Exception as exc:  # noqa: BLE001 — surface any fatal error
            self.call_from_thread(self._on_fatal, str(exc))
            return
        self.call_from_thread(self._on_done, result)

    def _on_page(self, page: int, err) -> None:
        self._done += 1
        try:
            self.query_one("#run-progress", ProgressBar).update(
                progress=self._done)
            self.query_one("#run-status", Static).update(
                ti.T("tui.run.progress", done=self._done,
                     total=len(self._pages)))
            log = self.query_one("#run-log", RichLog)
            if err:
                log.write(ti.T("tui.run.page_err", page=page + 1, err=err))
            else:
                log.write(ti.T("tui.run.page_ok", page=page + 1))
        except Exception:  # noqa: BLE001
            pass

    def _on_fatal(self, message: str) -> None:
        try:
            self.notify(message, severity="error", timeout=0)
        except Exception:  # noqa: BLE001
            pass
        self._goto("pages")

    def _on_done(self, result) -> None:
        self._result = result
        if result.cancelled:
            title = ti.T("tui.run.cancelled")
        elif result.errors:
            title = ti.T("tui.run.failed")
        else:
            title = ti.T("tui.run.done")
        lines = [
            f"[b]{title}[/b]",
            ti.T("tui.run.summary", ok=result.ok, errors=len(result.errors)),
            ti.T("tui.run.elapsed", s=result.elapsed),
        ]
        if result.output_path is not None:
            lines.append(ti.T("tui.run.saved", path=result.output_path))
        for page, err in sorted(result.errors.items()):
            lines.append(f"  [red]![/red] page {page + 1}: {err}")
        try:
            self.query_one("#result-body", Static).update("\n".join(lines))
        except Exception:  # noqa: BLE001
            pass
        self._goto("result")

    def _exit_code(self) -> int:
        if self._result is not None:
            if self._result.cancelled or self._result.errors:
                return 1
            return 0
        return 2


def _build_theme(dark: bool) -> "object":
    """Build a Textual theme from the shared ``theme.py`` wizard palette."""
    from textual.theme import Theme

    theme_mod.set_mode("dark" if dark else "light")
    theme_mod.set_resolved("dark" if dark else "light")
    return Theme(
        name="noesis-dark" if dark else "noesis-light",
        primary=str(theme_mod.color("wiz_accent")),
        secondary=str(theme_mod.color("wiz_ind_border")),
        accent=str(theme_mod.color("wiz_ok")),
        success=str(theme_mod.color("wiz_ok")),
        error=str(theme_mod.color("wiz_err")),
        warning=str(theme_mod.color("warn")),
        foreground=str(theme_mod.color("wiz_title")),
        background=str(theme_mod.color("wiz_bg")),
        surface=str(theme_mod.color("wiz_panel")),
        panel=str(theme_mod.color("wiz_header")),
        dark=dark,
    )


# ── entry point ──────────────────────────────────────────────────────────────
#
# The ``launch()`` dispatcher lives in ``tui_launch.py`` on purpose: this module
# imports Textual at the top, so it must only be imported when Textual is
# actually available (the line fallback does not need it).

