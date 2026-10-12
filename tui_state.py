"""Pure state + orchestration for the ``-gui`` export wizard.

This module is the **headless, terminal-free core** of the TUI wizard: it holds
the user's choices (:class:`ExportOptions`), validates them, resolves the output
paths and runs the batch export. It is shared verbatim by the modern Textual
front-end (:mod:`tui`) and by the line-oriented fallback
(:mod:`tui_fallback`), and it is fully unit-testable without any TUI library.

Design rule (same as the rest of the CLI repo): **never reimplement the
engine**. Everything here composes the shared helpers already used by
``cli.py`` — :mod:`export_core`, ``main`` (the Qt-free engine core), ``pages``
and ``i18n``. The desktop app stays the source of truth.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import export_core
import main as engine
from i18n import TRANSLATION_ENGINES, TRANSLATION_LANGUAGES
from pages import PageSpecError, format_pages_label, parse_pages

__all__ = [
    "PAGES_MODES",
    "CONTENTS",
    "ExportOptions",
    "ExportResult",
    "ExportError",
    "ExportCancelled",
    "read_page_count",
    "stem_of",
    "select_pages",
    "allowed_packagings",
    "ocr_lang_for",
    "resolve_outputs",
    "planned_files",
    "summary_rows",
    "validate",
    "execute",
    "load_prefs",
    "save_prefs",
    "prefs_path",
]

#: Page-selection modes offered by the wizard (the desktop's "current page"
#: has no meaning in a headless batch, so the CLI wizard starts from "all").
PAGES_MODES = ("all", "range", "free")

#: What to export (mirrors ``--content``).
CONTENTS = ("original", "translated", "both")

#: Wizard steps, in order (labels live in ``i18n`` / ``tui_i18n``).
PIPELINES = ("ir", "current")


# ── options ──────────────────────────────────────────────────────────────────


@dataclass
class ExportOptions:
    """All wizard choices, mirroring the CLI flags one-to-one."""

    pdf: str = ""
    pages_mode: str = "all"
    range_from: int = 1
    range_to: int = 1
    free_pages: str = "all"
    content: str = "original"
    include_images: bool = True
    translate_missing: bool = True
    engine: str = "google"
    src: str = "auto"
    dst: str = "it"
    ocr_lang: str = ""
    tessdata: str = ""
    content_format: str = "markdown"
    packaging: str = "merged"
    out_folder: str = ""
    name: str = ""
    pandoc: str = ""
    pipeline: str = "ir"

    # ── serialization (prefs file) ─────────────────────────────────────
    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> "ExportOptions":
        """Build options from a (possibly partial/invalid) mapping.

        Unknown fields are ignored and wrong types fall back to the dataclass
        default, so an old or corrupted prefs file never crashes the wizard.
        """
        defaults = cls()
        if not isinstance(raw, dict):
            return defaults
        out = cls()
        for key, default in defaults.as_dict().items():
            if key not in raw:
                continue
            value = raw[key]
            if isinstance(default, bool):
                out.__dict__[key] = _to_bool(value, default)
            elif isinstance(default, int):
                try:
                    out.__dict__[key] = int(value)
                except (TypeError, ValueError):
                    pass
            elif isinstance(default, str):
                out.__dict__[key] = value if isinstance(value, str) else default
        # Normalize enumerated fields.
        if out.pages_mode not in PAGES_MODES:
            out.pages_mode = "all"
        if out.content not in CONTENTS:
            out.content = "original"
        if out.engine not in TRANSLATION_ENGINES:
            out.engine = "google"
        if out.pipeline not in PIPELINES:
            out.pipeline = "ir"
        if out.src not in TRANSLATION_LANGUAGES:
            out.src = "auto"
        if out.dst not in TRANSLATION_LANGUAGES or out.dst == "auto":
            out.dst = "it"
        if out.content_format not in engine._CONTENT_FORMAT_ORDER:
            out.content_format = "markdown"
        if out.packaging not in engine._PACKAGING_ORDER:
            out.packaging = "merged"
        return out


def _to_bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("1", "true", "yes", "on"):
            return True
        if low in ("0", "false", "no", "off"):
            return False
    return default


@dataclass
class ExportResult:
    """Outcome of one batch run (mirrors the CLI summary fields)."""

    output_path: Path | None
    ok: int
    errors: dict
    elapsed: float
    pages: list
    cancelled: bool = False


class ExportError(RuntimeError):
    """Fatal input error (bad PDF, invalid pages, impossible packaging)."""


class ExportCancelled(Exception):
    """Raised from the progress callback when the user cancels the batch."""


# ── basic introspection ──────────────────────────────────────────────────────


def read_page_count(pdf) -> int | None:
    """Page count of ``pdf`` via PyMuPDF, or ``None`` when unreadable."""
    try:
        import pymupdf  # local import: keeps the module importable without it

        with pymupdf.open(str(pdf)) as doc:
            return int(doc.page_count)
    except Exception:  # noqa: BLE001
        return None


def stem_of(options: ExportOptions) -> str:
    """Base stem for the output names (the PDF file name)."""
    return Path(options.pdf).stem if options.pdf else "documento"


def default_name(options: ExportOptions) -> str:
    """Default container name, mirroring the desktop's ``{stem}_estratto``."""
    return f"{stem_of(options)}_estratto"


def default_folder() -> Path:
    """Default destination folder (the current working directory)."""
    return Path.cwd()


# ── pages ────────────────────────────────────────────────────────────────────


def select_pages(options: ExportOptions, page_count: int):
    """Resolve the page selection.

    Returns ``(pages, error)`` where ``error`` is ``None`` on success or a
    ``(i18n_key, params)`` tuple the UI translates via ``i18n.T`` (the same
    ``export.free.err.*`` keys the desktop wizard uses).
    """
    if page_count <= 0:
        return None, ("export.free.err.no_pages", {})
    if options.pages_mode == "all":
        return list(range(page_count)), None
    if options.pages_mode == "range":
        lo = max(1, min(options.range_from, options.range_to))
        hi = min(page_count, max(options.range_from, options.range_to))
        if hi < lo:
            return None, ("export.free.err.range", {"token": f"{lo}-{hi}"})
        return list(range(lo - 1, hi)), None
    try:
        pages = parse_pages(options.free_pages, page_count)
    except PageSpecError as exc:
        return None, (f"export.free.err.{exc.code}", dict(exc.params))
    if not pages:
        return None, ("export.free.err.none", {})
    return pages, None


# ── output / packaging ───────────────────────────────────────────────────────


def allowed_packagings(content_format: str) -> list[str]:
    """Packagings that can carry ``content_format`` (desktop parity)."""
    return [p for p in engine._PACKAGING_ORDER
            if engine.packaging_allows(content_format, p)]


def ocr_lang_for(options: ExportOptions) -> str:
    """OCR language: explicit when given, else derived from ``--src``."""
    if options.ocr_lang.strip():
        return options.ocr_lang.strip()
    return engine._tess_lang_code(None if options.src == "auto" else options.src)


def resolve_outputs(options: ExportOptions, stem: str | None = None):
    """Return ``(out_path, out_folder, name)`` like ``cli._resolve_outputs``.

    ``out_path`` is set for ``merged``/``zip``; ``out_folder`` for
    ``folder``/``vault``.
    """
    stem = stem or stem_of(options)
    name = options.name.strip() or f"{stem}_estratto"
    folder = (Path(options.out_folder).expanduser()
              if options.out_folder.strip() else default_folder())
    if options.packaging in ("folder", "vault"):
        return None, folder / name, name
    ext = (".zip" if options.packaging == "zip"
           else engine.content_format_ext(options.content_format))
    out = folder / name
    if out.suffix.lower() != ext:
        out = out.with_suffix(ext)
    return out, None, name


def planned_files(options: ExportOptions, pages, stem: str | None = None):
    """Paths a run would create (same as ``--dry-run``)."""
    stem = stem or stem_of(options)
    out_path, out_folder, _name = resolve_outputs(options, stem)
    return export_core.planned_outputs(
        pages, content=options.content, fmt=options.packaging,
        out_path=out_path, out_folder=out_folder, stem=stem,
        content_fmt=options.content_format)


def needs_pandoc(options: ExportOptions) -> bool:
    return engine.content_format_kind(options.content_format) == "pandoc"


def pandoc_ready(options: ExportOptions) -> bool:
    return bool(options.pandoc.strip()) or engine.pandoc_path() is not None


# ── summary ──────────────────────────────────────────────────────────────────


def summary_rows(options: ExportOptions, pages, stem: str | None = None):
    """``(i18n_key, value)`` rows for the summary panel (desktop parity)."""
    stem = stem or stem_of(options)
    pages = list(pages or [])
    label = format_pages_label(pages)
    out_path, out_folder, name = resolve_outputs(options, stem)
    if options.packaging in ("folder", "vault"):
        out = str(out_folder)
    else:
        out = str(out_path)
    return [
        ("export.sum.file", name),
        ("export.sum.pages", f"{label}  ({len(pages)})"),
        ("export.sum.content", _content_label(options)),
        ("export.sum.langs",
         f"{options.src} → {options.dst} · {options.engine}"),
        ("export.sum.output", out),
    ]


def _content_label(options: ExportOptions) -> str:
    parts = [options.content]
    if options.include_images:
        parts.append("images")
    parts.append(options.content_format)
    return " · ".join(parts)


# ── validation ───────────────────────────────────────────────────────────────


def validate(options: ExportOptions, page_count: int | None = None):
    """Validate the whole plan.

    Returns ``(pages, errors)``: ``pages`` is the resolved page list (or
    ``None``) and ``errors`` a list of ``(i18n_key, params)`` tuples.
    """
    errors: list[tuple[str, dict]] = []
    pdf = Path(options.pdf) if options.pdf else None
    if not pdf or not pdf.is_file():
        errors.append(("tui.err.no_pdf", {}))
        return None, errors

    if page_count is None:
        page_count = read_page_count(pdf) or 0
    pages, page_err = select_pages(options, page_count)
    if page_err is not None:
        errors.append(page_err)

    if not engine.packaging_allows(options.content_format, options.packaging):
        errors.append(("tui.err.bad_packaging", {
            "format": options.content_format,
            "packaging": options.packaging,
        }))

    if needs_pandoc(options) and not pandoc_ready(options):
        errors.append(("tui.err.need_pandoc", {
            "format": options.content_format}))

    return pages, errors


# ── execution ────────────────────────────────────────────────────────────────


def execute(options: ExportOptions, *, on_page=None, should_cancel=None):
    """Run the batch export described by ``options``.

    Mirrors :func:`cli.main`'s orchestration exactly (same engine calls, same
    figures temp dir, same pipeline switch). ``on_page(page, entry, error)``
    is called after each page; ``should_cancel()`` is polled before every page
    and, when true, aborts with :class:`ExportCancelled` (no output written).
    """
    pdf = Path(options.pdf)
    page_count = read_page_count(pdf) or 0
    pages, page_err = select_pages(options, page_count)
    if page_err is not None:
        raise ExportError(page_err[0])
    if not engine.packaging_allows(options.content_format, options.packaging):
        raise ExportError("tui.err.bad_packaging")
    if needs_pandoc(options) and not pandoc_ready(options):
        raise ExportError("tui.err.need_pandoc")

    if options.tessdata.strip():
        os.environ["TESSDATA_PREFIX"] = options.tessdata.strip()
    engine.set_setting("pipeline", options.pipeline)
    os.environ["NOESIS_PIPELINE"] = options.pipeline

    ocr_lang = ocr_lang_for(options)
    pandoc = options.pandoc.strip() or engine.pandoc_path()
    out_path, out_folder, _name = resolve_outputs(options, pdf.stem)

    figures_dir = tempfile.mkdtemp(prefix="noesis-fig-")

    def _progress(page, entry, err):
        if should_cancel is not None and should_cancel():
            raise ExportCancelled()
        if on_page is not None:
            on_page(page, entry, err)

    t0 = time.time()
    try:
        results, errors = export_core.extract_and_translate(
            pdf, pages,
            content=options.content,
            translate_missing=options.translate_missing,
            engine=options.engine,
            src=options.src,
            target=options.dst,
            ocr_lang=ocr_lang,
            figures_dir=figures_dir,
            on_page=_progress,
        )
    except ExportCancelled:
        return ExportResult(None, 0, {}, time.time() - t0, list(pages),
                            cancelled=True)
    finally:
        shutil.rmtree(figures_dir, ignore_errors=True)

    result_path = None
    if results:
        result_path = export_core.write_output(
            results, pages,
            content=options.content,
            include_images=options.include_images,
            fmt=options.packaging,
            out_path=out_path,
            out_folder=out_folder,
            stem=pdf.stem,
            content_fmt=options.content_format,
            pandoc=pandoc,
            lang=options.dst,
        )
    return ExportResult(
        Path(result_path) if result_path else None,
        len(results), errors, time.time() - t0, list(pages))


# ── preferences ──────────────────────────────────────────────────────────────


def prefs_path() -> Path:
    """Per-user prefs file for the wizard (kept separate from the app config)."""
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "noesis-pdf-reader-lite-engine" / "tui.json"


def load_prefs() -> ExportOptions:
    """Load the last-used options; fall back to defaults on any problem."""
    try:
        data = json.loads(prefs_path().read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return ExportOptions()
    return ExportOptions.from_dict(data)


def save_prefs(options: ExportOptions) -> None:
    """Persist ``options`` (best effort: never raise from the UI)."""
    try:
        path = prefs_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(options.as_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
