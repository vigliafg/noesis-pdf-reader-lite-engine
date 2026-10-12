"""Dispatcher for the ``-gui`` wizard.

Decides between the modern Textual UI (:mod:`tui`) and the line fallback
(:mod:`tui_fallback`). It lives in its own module so that importing the CLI
never pulls in Textual: :mod:`tui` imports Textual at the top, this module only
imports it after checking that it is available and the terminal supports it.
"""
from __future__ import annotations

from pathlib import Path

import tui_i18n as ti
import tui_state
from tui_state import ExportOptions

__all__ = ["launch"]


def _apply_args(options: ExportOptions, args) -> None:
    """Overlay explicit CLI values on the loaded preferences.

    Only values that differ from the parser defaults are applied, so
    ``noesis-pdf-reader-lite-engine -gui`` keeps the last-used options while
    ``noesis-pdf-reader-lite-engine -gui libro.pdf --dst en`` prefills them.
    """
    if args is None:
        return
    if getattr(args, "pdf", None):
        options.pdf = str(args.pdf)
    if getattr(args, "content", "original") != "original":
        options.content = args.content
    if getattr(args, "engine", "google") != "google":
        options.engine = args.engine
    if getattr(args, "src", "auto") != "auto":
        options.src = args.src
    if getattr(args, "dst", "it") != "it":
        options.dst = args.dst
    if getattr(args, "pages", "all") != "all":
        options.pages_mode = "free"
        options.free_pages = args.pages
    if getattr(args, "format", "merged") != "merged":
        options.packaging = args.format
    if getattr(args, "content_format", "markdown") != "markdown":
        options.content_format = args.content_format
    if getattr(args, "name", None):
        options.name = args.name
    if getattr(args, "ocr_lang", None):
        options.ocr_lang = args.ocr_lang
    if getattr(args, "tessdata", None):
        options.tessdata = args.tessdata
    if getattr(args, "pandoc", None):
        options.pandoc = args.pandoc
    if getattr(args, "pipeline", "ir") != "ir":
        options.pipeline = args.pipeline
    if getattr(args, "include_images", True) is False:
        options.include_images = False
    if getattr(args, "translate_missing", True) is False:
        options.translate_missing = False
    out = getattr(args, "out", None)
    if out:
        path = Path(out).expanduser()
        if path.suffix or path.is_file():
            options.out_folder = str(path.parent)
            options.name = path.stem
        else:
            options.out_folder = str(path)


def launch(args=None) -> int:
    """Launch the ``-gui`` wizard; returns the process exit code.

    Uses the modern Textual UI when the terminal supports it, otherwise the
    line fallback — so ``-gui`` works everywhere.
    """
    import i18n

    profile = ti.probe_terminal()
    options = tui_state.load_prefs()
    _apply_args(options, args)

    lang = getattr(args, "tui_lang", None)
    if lang not in ("it", "en"):
        lang = i18n.get_language() if i18n.get_language() in ("it", "en") else "it"
    ti.set_language(lang)
    if getattr(args, "ascii", False) or not profile.utf8:
        ti.set_ascii(True)

    theme_choice = getattr(args, "tui_theme", None) or "auto"
    dark = theme_choice != "light"

    if profile.minimal:
        return tui_fallback_run(options)
    try:
        import textual  # noqa: F401
    except ImportError:
        return tui_fallback_run(options)

    from tui import ExportWizardApp

    app = ExportWizardApp(options, dark=dark,
                          ansi=(ti.ascii_mode() or profile.no_color))
    result = app.run()
    return int(result) if isinstance(result, int) else 0


def tui_fallback_run(options: ExportOptions) -> int:
    """Import the fallback lazily and run it (keeps the module import light)."""
    import tui_fallback

    return tui_fallback.run(options)
