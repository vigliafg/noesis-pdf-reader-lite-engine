#!/usr/bin/env python3
"""``noesis-pdf-reader-lite-engine`` — headless CLI for the Noesis PDF Reader Lite engine.

Extracts PDF pages to Markdown with the same adaptive layout engine as the
desktop app and exposes the *same export options* as its batch-export wizard:
page selection, content (original / translated / both), translation engine and
languages, translate-missing, image embeds, the **content format** (markdown /
html / text / epub / docx / odt / rtf / latex) and the **packaging** (merged /
zip / per-page folder / vault with index).

Examples::

    noesis-pdf-reader-lite-engine book.pdf --pages 1-10 --format merged -o book.md
    noesis-pdf-reader-lite-engine book.pdf --pages 3,5,10-12 --content both --dst en
    noesis-pdf-reader-lite-engine scan.pdf --content original --ocr-lang eng+ita
    noesis-pdf-reader-lite-engine book.pdf --format folder --out out/ --name capitolo
    noesis-pdf-reader-lite-engine book.pdf --content-format html -o book.html
    noesis-pdf-reader-lite-engine book.pdf --content-format epub -o book.epub
    noesis-pdf-reader-lite-engine book.pdf --format vault --out vault/
    noesis-pdf-reader-lite-engine book.pdf --content-format docx -o book.docx  # richiede pandoc
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import export_core
import main as engine
from i18n import TRANSLATION_ENGINES, TRANSLATION_LANGUAGES
from pages import PageSpecError, describe_pages, format_pages_label, parse_pages

__version__ = "0.1.0"


def _lang_choices(include_auto: bool) -> list[str]:
    codes = set(TRANSLATION_LANGUAGES.keys())
    if include_auto:
        return sorted(codes | {"auto"})
    return sorted(codes - {"auto"})


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="noesis-pdf-reader-lite-engine",
        description=(
            "Extract (and optionally translate) PDF pages to Markdown with the "
            "Noesis adaptive layout engine. Export options mirror the desktop "
            "batch-export wizard."
        ),
    )
    p.add_argument(
        "pdf", nargs="?", help="input PDF file (optional with -gui)")
    p.add_argument(
        "-gui", "--gui", dest="gui", action="store_true",
        help="open the interactive TUI wizard (file picker, mouse; falls back "
             "to a simple line wizard on terminals without Textual support)")
    p.add_argument(
        "--pages", default="all", metavar="SPEC",
        help="page spec: all | 7 | 100-103 | 1,3,5-7 (default: all)",
    )
    p.add_argument(
        "--content", choices=["original", "translated", "both"],
        default="original",
        help="what to export (default: original)",
    )
    p.add_argument(
        "--engine", choices=list(TRANSLATION_ENGINES), default="google",
        help="translation engine (default: google)",
    )
    p.add_argument(
        "--src", choices=_lang_choices(True), default="auto",
        help="source language (default: auto)",
    )
    p.add_argument(
        "--dst", choices=_lang_choices(False), default="it",
        help="target language (default: it)",
    )
    p.add_argument(
        "--translate-missing", dest="translate_missing",
        action=argparse.BooleanOptionalAction, default=True,
        help="translate pages with no cached translation (default: on)",
    )
    p.add_argument(
        "--images", dest="include_images",
        action=argparse.BooleanOptionalAction, default=True,
        help="keep Markdown image embeds (default: on)",
    )
    p.add_argument(
        "--format", dest="format", choices=list(engine._PACKAGING_ORDER),
        default="merged",
        help="packaging: merged | zip | folder | vault (default: merged)",
    )
    p.add_argument(
        "--content-format", dest="content_format",
        choices=list(engine._CONTENT_FORMAT_ORDER), default="markdown",
        help="content format: markdown | html | text | epub | docx | odt | "
             "rtf | latex (default: markdown)",
    )
    p.add_argument(
        "--pandoc", default=None, metavar="PATH",
        help="pandoc executable for docx/odt/rtf/latex (default: $PATH)",
    )
    p.add_argument(
        "-o", "--out", default=None, metavar="PATH",
        help="output file (merged/zip) or folder (folder)",
    )
    p.add_argument(
        "--name", default=None, metavar="NAME",
        help="base name for the output (default: the PDF file name)",
    )
    p.add_argument(
        "--ocr-lang", default=None, metavar="LANG",
        help="Tesseract language(s) for OCR, e.g. eng+ita (default: from --src)",
    )
    p.add_argument(
        "--tessdata", default=None, metavar="DIR",
        help="TESSDATA_PREFIX directory for OCR",
    )
    p.add_argument(
        "--pipeline", choices=["ir", "current"], default="ir",
        help="extraction pipeline (default: ir)",
    )
    p.add_argument(
        "--tui-theme", dest="tui_theme", choices=["auto", "dark", "light"],
        default="auto", help="theme for -gui (default: auto/dark)")
    p.add_argument(
        "--tui-lang", dest="tui_lang", choices=["it", "en"], default=None,
        help="language for the -gui wizard (default: from the app config)")
    p.add_argument(
        "--ascii", dest="ascii", action="store_true",
        help="force ASCII rendering in -gui (no emoji/box drawing)")
    p.add_argument("--json", action="store_true", help="print a JSON summary")
    p.add_argument(
        "--dry-run", action="store_true",
        help="show the output files that would be created, without extracting",
    )
    p.add_argument("-q", "--quiet", action="store_true", help="suppress progress")
    p.add_argument("-v", "--verbose", action="store_true", help="verbose output")
    p.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _resolve_outputs(args, stem: str):
    """Return ``(out_path, out_folder, name)`` from the CLI options."""
    name = args.name or stem
    cwd = Path.cwd()
    if args.format in ("folder", "vault"):
        folder = Path(args.out) if args.out else (cwd / name)
        return None, folder, name
    ext = (".zip" if args.format == "zip"
           else engine.content_format_ext(args.content_format))
    out = Path(args.out) if args.out else (cwd / f"{name}{ext}")
    if out.suffix.lower() != ext:
        out = out.with_suffix(ext)
    return out, None, name


def _print_summary(args, pages, ocr_lang, result_path, results, errors, elapsed):
    label = format_pages_label(pages)
    if args.json:
        print(json.dumps({
            "input": str(Path(args.pdf).resolve()),
            "pages": [p + 1 for p in pages],
            "pages_label": label,
            "content": args.content,
            "content_format": args.content_format,
            "packaging": args.format,
            "engine": args.engine,
            "src": args.src,
            "dst": args.dst,
            "pipeline": args.pipeline,
            "include_images": args.include_images,
            "translate_missing": args.translate_missing,
            "ocr_lang": ocr_lang,
            "output": str(result_path) if result_path else None,
            "ok": len(results),
            "errors": {str(p + 1): e for p, e in errors.items()},
            "elapsed_s": round(elapsed, 2),
            "version": __version__,
        }, ensure_ascii=False, indent=2))
        return
    print("Noesis PDF engine — extract")
    print(f"  input    : {Path(args.pdf).resolve()}")
    print(f"  pages    : {label}  ({len(pages)})")
    content = args.content + (" · images" if args.include_images else " · no-images")
    print(f"  content  : {content}")
    print(f"  engine   : {args.engine} · {args.src} → {args.dst}")
    print(f"  pipeline : {args.pipeline}  (OCR: {ocr_lang})")
    if result_path is not None:
        print(f"  output   : {result_path}")
    print(f"  result   : {len(results)} ok, {len(errors)} errors  ({elapsed:.1f}s)")
    for p, err in sorted(errors.items()):
        print(f"    ! page {p + 1}: {err}")


def _print_dry_run(args, pages, out_path, out_folder, stem):
    """Simulate a run: print the files that would be created (no extraction)."""
    units = export_core.output_units(args.content)
    ext = engine.content_format_ext(args.content_format)
    print("noesis-pdf-reader-lite-engine — dry run (nessuna estrazione)")
    print(f"  input    : {Path(args.pdf).resolve()}")
    print(f"  pages    : {format_pages_label(pages)}  ({len(pages)})")
    print(f"  content  : {args.content}")
    print(f"  format   : {args.content_format} · {args.format}")
    if args.format == "merged":
        base = Path(out_path)
        for suffix, sub in units:
            path = base.with_name(base.stem + suffix + ext)
            print(f"  file     : {path}   [{sub}]")
    elif args.format == "zip":
        print(f"  archivio : {out_path}")
        for page in pages:
            for suffix, sub in units:
                print(f"    - {export_core.page_filename(stem, page, suffix, ext)}"
                      f"   [{sub}]")
    else:
        print(f"  cartella : {out_folder}")
        for page in pages:
            for suffix, sub in units:
                print(f"    - {export_core.page_filename(stem, page, suffix, ext)}"
                      f"   [{sub}]")
        if args.format == "vault":
            print("    - index.md")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.gui:
        import tui_launch
        return tui_launch.launch(args)

    if not args.pdf:
        print("error: missing input PDF (or use -gui for the wizard)",
              file=sys.stderr)
        return 2

    pdf = Path(args.pdf)
    if not pdf.is_file():
        print(f"error: input PDF not found: {pdf}", file=sys.stderr)
        return 2

    if args.tessdata:
        os.environ["TESSDATA_PREFIX"] = args.tessdata
    # Same pipeline switch as the desktop app (setting + env var).
    engine.set_setting("pipeline", args.pipeline)
    os.environ["NOESIS_PIPELINE"] = args.pipeline

    try:
        import pymupdf
    except ImportError:
        print("error: PyMuPDF is required (pip install pymupdf)", file=sys.stderr)
        return 2
    try:
        with pymupdf.open(pdf) as doc:
            page_count = doc.page_count
    except Exception as exc:  # noqa: BLE001
        print(f"error: cannot open PDF: {exc}", file=sys.stderr)
        return 2

    try:
        pages = parse_pages(args.pages, page_count)
    except PageSpecError as exc:
        print(f"error: invalid --pages: {exc}", file=sys.stderr)
        return 2

    if not engine.packaging_allows(args.content_format, args.format):
        print(
            f"error: packaging '{args.format}' cannot carry content format "
            f"'{args.content_format}'", file=sys.stderr)
        return 2

    pandoc = args.pandoc
    if engine.content_format_kind(args.content_format) == "pandoc":
        pandoc = pandoc or engine.pandoc_path()
        if not pandoc:
            print(
                f"error: pandoc is required for --content-format "
                f"{args.content_format} (install pandoc or pass --pandoc)",
                file=sys.stderr)
            return 2

    ocr_lang = args.ocr_lang or engine._tess_lang_code(
        None if args.src == "auto" else args.src)

    out_path, out_folder, name = _resolve_outputs(args, pdf.stem)

    if args.dry_run:
        _print_dry_run(args, pages, out_path, out_folder, pdf.stem)
        return 0

    if args.verbose and not args.quiet:
        print(f"pages: {describe_pages(pages)}  ocr-lang: {ocr_lang}",
              file=sys.stderr)

    figures_dir = tempfile.mkdtemp(prefix="noesis-fig-")

    def _progress(page, entry, err):
        if args.quiet:
            return
        mark = "ERR" if err else "ok "
        print(f"  [{page + 1}] {mark}", file=sys.stderr, flush=True)

    t0 = time.time()
    try:
        results, errors = export_core.extract_and_translate(
            pdf, pages,
            content=args.content,
            translate_missing=args.translate_missing,
            engine=args.engine,
            src=args.src,
            target=args.dst,
            ocr_lang=ocr_lang,
            figures_dir=figures_dir,
            on_page=_progress,
        )
    finally:
        try:
            import shutil
            shutil.rmtree(figures_dir, ignore_errors=True)
        except Exception:  # noqa: BLE001
            pass

    result_path = None
    if results:
        result_path = export_core.write_output(
            results, pages,
            content=args.content,
            include_images=args.include_images,
            fmt=args.format,
            out_path=out_path,
            out_folder=out_folder,
            stem=pdf.stem,
            content_fmt=args.content_format,
            pandoc=pandoc,
            lang=args.dst,
        )

    _print_summary(args, pages, ocr_lang, result_path, results, errors,
                   time.time() - t0)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
