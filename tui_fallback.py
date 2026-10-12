"""Line-oriented fallback wizard for ``-gui``.

Used when the terminal cannot host the modern Textual UI (``TERM=dumb``, not a
TTY, no support) so ``-gui`` never crashes: the same steps, driven by plain
``input()``. It shares :mod:`tui_state` with the Textual front-end, so the
export behaves identically.
"""
from __future__ import annotations

from pathlib import Path

import main as engine
from i18n import TRANSLATION_ENGINES, TRANSLATION_LANGUAGES, flag_endonym

import tui_i18n as ti
import tui_state
from tui_state import ExportOptions

__all__ = ["run"]


def _read(input_fn, print_fn, label: str, default: str = "") -> str | None:
    """Prompt for a text value; ``None`` means the user aborted (EOF)."""
    hint = f" [{default}]" if default else ""
    try:
        raw = input_fn(f"{label}{hint}: ")
    except EOFError:
        return None
    raw = (raw or "").strip()
    return raw or default


def _choose(input_fn, print_fn, label: str, choices, default_index=0):
    """Prompt for one of ``choices`` (list of labels); return the index."""
    print_fn(f"\n{label}")
    for i, text in enumerate(choices, 1):
        mark = "•" if (i - 1) == default_index else " "
        print_fn(f"  {mark} {i}) {text}")
    raw = _read(input_fn, print_fn, ">", str(default_index + 1))
    if raw is None:
        return None
    try:
        idx = int(raw) - 1
    except ValueError:
        idx = default_index
    if not 0 <= idx < len(choices):
        idx = default_index
    return idx


def _yes_no(input_fn, print_fn, label: str, default: bool) -> bool | None:
    d = "S/n" if default else "s/N"
    raw = _read(input_fn, print_fn, f"{label} [{d}]", "")
    if raw is None:
        return None
    raw = raw.strip().lower()
    if not raw:
        return default
    return raw[0] in ("s", "y", "1")


def run(options: ExportOptions | None = None, *,
        input_fn=input, print_fn=print) -> int:
    """Run the fallback wizard; return the process exit code (0/1/2)."""
    opts = options or tui_state.load_prefs()

    print_fn("=" * 60)
    print_fn(ti.T("tui.fallback.title"))
    print_fn(ti.T("tui.fallback.hint"))
    print_fn("=" * 60)

    # ① PDF + pages
    pdf = _read(input_fn, print_fn, ti.T("tui.field.pdf"), opts.pdf)
    if pdf is None:
        print_fn(ti.T("export.cancelled"))
        return 2
    if not Path(pdf).is_file():
        print_fn(ti.T("tui.err.no_pdf"))
        return 2
    opts.pdf = pdf
    page_count = tui_state.read_page_count(pdf) or 0
    if page_count <= 0:
        print_fn(ti.T("tui.err.no_page_count"))
        return 2

    modes = [ti.T("tui.pages.all"), ti.T("export.mode.range"),
             ti.T("export.mode.free")]
    idx = _choose(input_fn, print_fn, ti.T("export.wizard.pages.title"), modes,
                  tui_state.PAGES_MODES.index(opts.pages_mode)
                  if opts.pages_mode in tui_state.PAGES_MODES else 0)
    if idx is None:
        return 2
    opts.pages_mode = tui_state.PAGES_MODES[idx]
    if opts.pages_mode == "range":
        raw = _read(input_fn, print_fn,
                    f"{ti.T('export.range.from.short')} (1-{page_count})",
                    str(opts.range_from))
        if raw is None:
            return 2
        opts.range_from = _as_int(raw, 1)
        raw = _read(input_fn, print_fn,
                    f"{ti.T('export.range.to.short')} (1-{page_count})",
                    str(opts.range_to))
        if raw is None:
            return 2
        opts.range_to = _as_int(raw, page_count)
    elif opts.pages_mode == "free":
        raw = _read(input_fn, print_fn, ti.T("export.free.hint"),
                    opts.free_pages)
        if raw is None:
            return 2
        opts.free_pages = raw

    # ② content
    contents = [ti.T("export.mode.original"), ti.T("export.mode.translated"),
                ti.T("export.mode.both")]
    idx = _choose(input_fn, print_fn, ti.T("export.wizard.content.title"),
                  contents, tui_state.CONTENTS.index(opts.content)
                  if opts.content in tui_state.CONTENTS else 0)
    if idx is None:
        return 2
    opts.content = tui_state.CONTENTS[idx]
    opts.include_images = _yes_no(
        input_fn, print_fn, ti.T("export.include_images"),
        opts.include_images) is not False
    opts.translate_missing = _yes_no(
        input_fn, print_fn, ti.T("export.translate_missing"),
        opts.translate_missing) is not False

    # ③ languages / engine
    src_codes = list(TRANSLATION_LANGUAGES)
    labels = [flag_endonym(c) for c in src_codes]
    idx = _choose(input_fn, print_fn, ti.T("settings.lang.source"), labels,
                  src_codes.index(opts.src) if opts.src in src_codes else 0)
    if idx is None:
        return 2
    opts.src = src_codes[idx]

    dst_codes = [c for c in TRANSLATION_LANGUAGES if c != "auto"]
    labels = [flag_endonym(c) for c in dst_codes]
    idx = _choose(input_fn, print_fn, ti.T("settings.lang.target"), labels,
                  dst_codes.index(opts.dst) if opts.dst in dst_codes else 0)
    if idx is None:
        return 2
    opts.dst = dst_codes[idx]

    engines = list(TRANSLATION_ENGINES)
    labels = [ti.T(f"engine.option.{c}") for c in engines]
    idx = _choose(input_fn, print_fn, ti.T("export.wizard.langs.title"), labels,
                  engines.index(opts.engine) if opts.engine in engines else 0)
    if idx is None:
        return 2
    opts.engine = engines[idx]

    ocr = _read(input_fn, print_fn, ti.T("tui.field.ocr"),
                opts.ocr_lang)
    if ocr is None:
        return 2
    opts.ocr_lang = ocr

    # ④ output
    formats = list(engine._CONTENT_FORMAT_ORDER)
    labels = [ti.T(f"export.contentfmt.{c}") for c in formats]
    idx = _choose(input_fn, print_fn, ti.T("export.output.content_format"),
                  labels, formats.index(opts.content_format)
                  if opts.content_format in formats else 0)
    if idx is None:
        return 2
    opts.content_format = formats[idx]

    allowed = tui_state.allowed_packagings(opts.content_format)
    labels = [ti.T(f"export.format.{c}") for c in allowed]
    idx = _choose(input_fn, print_fn, ti.T("export.output.packaging"), labels,
                  allowed.index(opts.packaging)
                  if opts.packaging in allowed else 0)
    if idx is None:
        return 2
    opts.packaging = allowed[idx]

    folder = _read(input_fn, print_fn, ti.T("export.wizard.output.folder"),
                   opts.out_folder or str(tui_state.default_folder()))
    if folder is None:
        return 2
    opts.out_folder = folder
    name = _read(input_fn, print_fn, ti.T("export.wizard.output.filename"),
                 opts.name or tui_state.default_name(opts))
    if name is None:
        return 2
    opts.name = name

    if tui_state.needs_pandoc(opts):
        path = _read(input_fn, print_fn, ti.T("tui.field.pandoc"), opts.pandoc)
        if path is None:
            return 2
        opts.pandoc = path

    # ⑤ summary
    pages, errors = tui_state.validate(opts, page_count)
    print_fn("")
    print_fn(ti.T("export.wizard.summary.title"))
    if pages is not None:
        for key, value in tui_state.summary_rows(opts, pages):
            print_fn(f"  {ti.T(key)}: {value}")
        print_fn(f"  {ti.T('tui.summary.planned')}:")
        for path in tui_state.planned_files(opts, pages):
            print_fn(f"    - {path}")
    for key, params in errors:
        print_fn(f"  ! {ti.T(key, **params)}")
    if pages is None or errors:
        return 2

    go = _yes_no(input_fn, print_fn, ti.T("export.wizard.start"), True)
    if not go:
        print_fn(ti.T("export.cancelled"))
        return 2

    tui_state.save_prefs(opts)
    print_fn(ti.T("tui.fallback.run"))

    def _on_page(page, entry, err):
        if err:
            print_fn(f"  {ti.T('tui.run.page_err', page=page + 1, err=err)}")
        else:
            print_fn(f"  {ti.T('tui.run.page_ok', page=page + 1)}")

    result = tui_state.execute(opts, on_page=_on_page)
    if result.cancelled:
        print_fn(ti.T("tui.run.cancelled"))
        return 1
    if result.output_path is not None:
        print_fn(ti.T("tui.run.saved", path=result.output_path))
    print_fn(ti.T("tui.run.summary", ok=result.ok, errors=len(result.errors)))
    return 1 if result.errors else 0


def _as_int(raw: str, default: int) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default
