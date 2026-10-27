"""Strings and terminal-capability helpers for the TUI wizard.

``i18n.py`` is copied **verbatim** from the desktop repository, so the strings
that only exist in the terminal wizard live here instead of being appended to
it. :func:`T` first looks in this module's table and otherwise delegates to the
shared :func:`i18n.T`, so the wizard reuses every existing ``export.*`` key.

The module also probes the terminal (:func:`probe_terminal`) so the UI can
degrade gracefully: ASCII instead of box-drawing/emoji, no color when
``NO_COLOR`` is set, and the simple line wizard when the terminal cannot host
Textual.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import i18n

__all__ = [
    "T",
    "language",
    "set_language",
    "ascii_mode",
    "set_ascii",
    "strip_non_ascii",
    "page_error",
    "TerminalProfile",
    "probe_terminal",
]

#: TUI-only strings (shared strings are served by ``i18n.T``).
_STRINGS: dict[str, dict[str, str]] = {
    "tui.pages.all": {
        "it": "Tutte le pagine", "en": "All pages"},
    "tui.pick_pdf": {
        "it": "Scegli PDF…", "en": "Choose PDF…"},
    "tui.pick_folder": {
        "it": "Scegli cartella…", "en": "Choose folder…"},
    "tui.err.no_pdf": {
        "it": "Seleziona un file PDF di input.",
        "en": "Select an input PDF file."},
    "tui.err.bad_packaging": {
        "it": "L'impacchettamento «{packaging}» non può contenere il formato «{format}».",
        "en": "Packaging “{packaging}” cannot carry format “{format}”."},
    "tui.err.need_pandoc": {
        "it": "Serve pandoc per il formato «{format}» (installalo o indica il percorso).",
        "en": "pandoc is required for “{format}” (install it or set the path)."},
    "tui.err.no_page_count": {
        "it": "PDF illeggibile o senza pagine.",
        "en": "Unreadable PDF or no pages."},
    "tui.field.pdf": {
        "it": "File PDF", "en": "PDF file"},
    "tui.field.range": {
        "it": "Intervallo", "en": "Range"},
    "tui.field.free": {
        "it": "Pagine", "en": "Pages"},
    "tui.field.ocr": {
        "it": "Lingua OCR", "en": "OCR language"},
    "tui.field.tessdata": {
        "it": "Cartella tessdata", "en": "tessdata folder"},
    "tui.field.pandoc": {
        "it": "Eseguibile pandoc", "en": "pandoc executable"},
    "tui.optional": {
        "it": "opzionale", "en": "optional"},
    "tui.filepicker.title": {
        "it": "Seleziona un file", "en": "Select a file"},
    "tui.filepicker.folder_title": {
        "it": "Seleziona una cartella", "en": "Select a folder"},
    "tui.filepicker.path": {
        "it": "Percorso", "en": "Path"},
    "tui.filepicker.up": {
        "it": "Su", "en": "Up"},
    "tui.filepicker.home": {
        "it": "Home", "en": "Home"},
    "tui.filepicker.cwd": {
        "it": "Cartella corrente", "en": "Current folder"},
    "tui.filepicker.hidden": {
        "it": "Nascosti", "en": "Hidden"},
    "tui.filepicker.open": {
        "it": "Apri", "en": "Open"},
    "tui.filepicker.select": {
        "it": "Seleziona", "en": "Select"},
    "tui.filepicker.cancel": {
        "it": "Annulla", "en": "Cancel"},
    "tui.filepicker.empty": {
        "it": "Nessun elemento qui.", "en": "Nothing here."},
    "tui.filepicker.hint": {
        "it": "Doppio clic o Invio per aprire · Backspace per risalire",
        "en": "Double-click or Enter to open · Backspace to go up"},
    "tui.run.title": {
        "it": "Esportazione in corso", "en": "Export in progress"},
    "tui.run.progress": {
        "it": "Pagina {done}/{total}", "en": "Page {done}/{total}"},
    "tui.run.page_ok": {
        "it": "✓ pagina {page}", "en": "✓ page {page}"},
    "tui.run.page_err": {
        "it": "✗ pagina {page}: {err}", "en": "✗ page {page}: {err}"},
    "tui.run.cancel": {
        "it": "Interrompi", "en": "Cancel"},
    "tui.run.cancelled": {
        "it": "Esportazione annullata.", "en": "Export cancelled."},
    "tui.run.done": {
        "it": "Esportazione completata", "en": "Export completed"},
    "tui.run.failed": {
        "it": "Completata con errori", "en": "Completed with errors"},
    "tui.run.saved": {
        "it": "Salvato in: {path}", "en": "Saved to: {path}"},
    "tui.run.in_folder": {
        "it": "Cartella: {path}", "en": "Folder: {path}"},
    "tui.run.elapsed": {
        "it": "Tempo: {s:.1f}s", "en": "Time: {s:.1f}s"},
    "tui.run.summary": {
        "it": "{ok} pagine ok · {errors} errori",
        "en": "{ok} pages ok · {errors} errors"},
    "tui.destbar": {
        "it": "Destinazione: {folder}  ·  {name}",
        "en": "Destination: {folder}  ·  {name}"},
    "tui.destbar.none": {
        "it": "Destinazione: scegli un PDF per iniziare",
        "en": "Destination: choose a PDF to begin"},
    "tui.summary.planned": {
        "it": "File che verranno creati", "en": "Files that will be created"},
    "tui.summary.nofiles": {
        "it": "Nessun file (selezione vuota).", "en": "No files (empty selection)."},
    "tui.close": {
        "it": "Chiudi", "en": "Close"},
    "tui.open_folder": {
        "it": "Apri cartella", "en": "Open folder"},
    "tui.help.title": {
        "it": "Aiuto e scorciatoie", "en": "Help and shortcuts"},
    "tui.help.body": {
        "it": "Tab/frecce: sposta il focus · Invio: attiva · Spazio: seleziona\n"
              "1-5: vai al passo · b/n: indietro/avanti · Ctrl+R: esegui\n"
              "a: ASCII · l: lingua · t: tema · ?: aiuto · q: esci\n"
              "Il mouse è attivo quando il terminale lo supporta (clic, rotella, doppio clic).",
        "en": "Tab/arrows: move focus · Enter: activate · Space: select\n"
              "1-5: go to step · b/n: back/next · Ctrl+R: run\n"
              "a: ASCII · l: language · t: theme · ?: help · q: quit\n"
              "Mouse is active whenever the terminal supports it (click, wheel, double-click)."},
    "tui.ascii_on": {
        "it": "ASCII: attivo", "en": "ASCII: on"},
    "tui.ascii_off": {
        "it": "ASCII: disattivo", "en": "ASCII: off"},
    "tui.term.too_small": {
        "it": "Terminale troppo piccolo: allarga la finestra.",
        "en": "Terminal too small: enlarge the window."},
    "tui.fallback.title": {
        "it": "Wizard di esportazione (modalità semplice)",
        "en": "Export wizard (simple mode)"},
    "tui.fallback.hint": {
        "it": "Invio accetta il valore tra parentesi quadre.",
        "en": "Press Enter to accept the value in brackets."},
    "tui.fallback.run": {
        "it": "Avvio esportazione…", "en": "Starting export…"},
    "tui.lang": {
        "it": "Lingua", "en": "Language"},
    "tui.theme": {
        "it": "Tema", "en": "Theme"},
    "tui.step": {
        "it": "Passo {n}/{total}", "en": "Step {n}/{total}"},
}

_lang: str = "it"
_ascii: bool = False

# Languages the TUI can display (must exist for every key above).
_TUI_LANGS = ("it", "en")


def language() -> str:
    return _lang


def set_language(code: str) -> None:
    """Switch the TUI language (``it``/``en``; ignored if unknown)."""
    global _lang
    if code in _TUI_LANGS:
        _lang = code


def ascii_mode() -> bool:
    return _ascii


def set_ascii(enabled: bool) -> None:
    """Toggle ASCII rendering (drops emoji/flags and box-drawing glyphs)."""
    global _ascii
    _ascii = bool(enabled)


def strip_non_ascii(text: str) -> str:
    """Remove non-ASCII glyphs and squeeze the leftover double spaces."""
    out = "".join(ch if ord(ch) < 128 else "" for ch in text)
    return " ".join(out.split()) if "\n" not in out else out


def T(key: str, **fmt) -> str:
    """Translate ``key``: TUI table first, then the shared ``i18n.T``."""
    table = _STRINGS.get(key)
    if table is None:
        text = i18n.T(key, **fmt)
    else:
        text = table.get(_lang) or table.get("it") or key
        if fmt:
            try:
                text = text.format(**fmt)
            except (KeyError, IndexError, ValueError):
                pass
    return strip_non_ascii(text) if _ascii else text


def page_error(error) -> str:
    """Render a ``(key, params)`` page error tuple as a localized string."""
    if not error:
        return ""
    key, params = error
    return T(key, **params)


# ── terminal capability probe ────────────────────────────────────────────────


@dataclass
class TerminalProfile:
    """What the current terminal can do (drives the fallback + ASCII mode)."""

    isatty: bool
    dumb: bool
    utf8: bool
    no_color: bool
    color_system: str  # truecolor | 256 | 16 | none
    columns: int
    lines: int
    supports_textual: bool

    @property
    def minimal(self) -> bool:
        """True for terminals that should use the line fallback."""
        return not self.supports_textual


def probe_terminal() -> TerminalProfile:
    """Best-effort detection of the terminal capabilities."""
    try:
        isatty = bool(sys.stdin.isatty() and sys.stdout.isatty())
    except Exception:  # noqa: BLE001 — detached/closed streams
        isatty = False

    term = os.environ.get("TERM", "")
    dumb = term.strip().lower() in ("dumb",) or (
        not term and os.name != "nt")

    encoding = (getattr(sys.stdout, "encoding", "") or "").lower()
    utf8 = "utf" in encoding or (
        "utf" in os.environ.get("LC_ALL", "").lower()) or (
        "utf" in os.environ.get("LC_CTYPE", "").lower()) or (
        "utf" in os.environ.get("LANG", "").lower())
    # Python 3.15+'s UTF-8 mode / PEP 540 makes stdout utf-8 regardless.
    if getattr(sys.flags, "utf8_mode", 0):
        utf8 = True

    no_color = "NO_COLOR" in os.environ
    colorterm = os.environ.get("COLORTERM", "").lower()
    if no_color:
        color_system = "none"
    elif "truecolor" in colorterm or "24bit" in colorterm:
        color_system = "truecolor"
    elif "256" in term or "truecolor" in term:
        color_system = "256"
    elif term or os.name == "nt":
        color_system = "16"
    else:
        color_system = "none"

    try:
        size = os.get_terminal_size()
        columns, lines = size.columns, size.lines
    except OSError:
        columns, lines = 80, 24

    supports_textual = isatty and not dumb
    return TerminalProfile(
        isatty=isatty, dumb=dumb, utf8=utf8, no_color=no_color,
        color_system=color_system, columns=columns, lines=lines,
        supports_textual=supports_textual)
