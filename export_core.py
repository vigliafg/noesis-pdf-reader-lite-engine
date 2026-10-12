"""Export composition for the CLI — mirrors the desktop batch export.

The desktop composes the batch output inside ``MainWindow._write_batch_output``,
which now delegates to the shared, pure ``main.write_export``. This module does
the same, so the CLI output is byte-identical to the desktop export for the same
engine options: strip the extraction header, join the original and/or the
translation, optionally drop the Markdown image embeds, convert to the chosen
content format, then write merged / zip / per-page folder / vault.

Content formats (``content_fmt``): ``markdown`` (identity), ``html``, ``text``,
``epub`` (native, merged only), and the pandoc writers ``docx``/``odt``/``rtf``/
``latex``. Packagings (``fmt``): ``merged``, ``zip``, ``folder``, ``vault``.

Naming rules (desktop parity):

* ``original``   → one file per page, ``{stem}_pag{NNNN}.md``;
* ``translated`` → one file per page, ``{stem}_pag{NNNN}-translated.md``;
* ``both``       → **two** files per page (original + translation).

The extension follows the content format (``.md``/``.html``/``.txt``/…). In the
``merged`` format the single output file carries the same ``-translated`` suffix
(``both`` emits two merged files). Zip archives and per-page folders keep the
user-chosen container name; only the content files get the suffix.
"""
from __future__ import annotations

import re

import main

#: Markdown image embeds, stripped when figures are excluded (desktop regex).
_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")


def strip_images(text: str) -> str:
    """Remove Markdown image embeds when figures are excluded."""
    return _MD_IMAGE_RE.sub("", text)


def output_units(content: str) -> list[tuple[str, str]]:
    """Return the ``(filename suffix, content key)`` pairs to emit.

    Mirrors the desktop ``_batch_output_units``.
    """
    if content == "original":
        return [("", "original")]
    if content == "translated":
        return [("-translated", "translated")]
    return [("", "original"), ("-translated", "translated")]


def page_filename(stem: str, page: int, suffix: str, ext: str = ".md") -> str:
    """Per-page file name: ``{stem}_pag{NNNN}{suffix}{ext}`` (1-based page)."""
    return f"{stem}_pag{page + 1:04d}{suffix}{ext}"


def page_content(entry: dict, content: str, include_images: bool) -> str:
    """Compose one page's body (mirrors ``MainWindow._batch_page_content``).

    The extraction header is stripped from each window body, exactly like the
    desktop (``_batch_apply_edits`` → ``_strip_header``); with no saved edits
    the lookup is the identity.
    """
    parts: list[str] = []
    if content in ("original", "both") and "original" in entry:
        parts.append(main._strip_header(entry["original"]))
    if content in ("translated", "both") and "translated" in entry:
        parts.append(main._strip_header(entry["translated"]))
    text = "\n\n".join(p for p in parts if p.strip())
    if not include_images:
        text = strip_images(text)
    return text


def extract_and_translate(
    pdf_path,
    pages,
    *,
    content: str,
    translate_missing: bool,
    engine: str,
    src: str,
    target: str,
    ocr_lang: str,
    figures_dir,
    on_page=None,
):
    """Extract (+ optionally translate) the selected pages.

    Mirrors ``BatchExportThread.run`` without the GUI caches: returns
    ``(results, errors)`` keyed by 0-based page index. One failing page does
    not stop the batch (same as the desktop).
    """
    results: dict[int, dict] = {}
    errors: dict[int, str] = {}
    for page in pages:
        entry: dict = {}
        try:
            if content in ("original", "both"):
                text, _label, _raw, _eng = main._batch_extract_page(
                    str(pdf_path), page, ocr_lang, figures_dir)
                entry["original"] = text
            if content in ("translated", "both"):
                if "original" not in entry:
                    text, _label, _raw, _eng = main._batch_extract_page(
                        str(pdf_path), page, ocr_lang, figures_dir)
                    entry["original"] = text
                if not translate_missing:
                    raise RuntimeError(
                        "no cached translation for this page and "
                        "--no-translate-missing was given")
                body = main._strip_header(entry["original"])
                entry["translated"] = main.translate_text(
                    body, source=src, target=target, engine=engine)
            results[page] = entry
        except Exception as exc:  # noqa: BLE001 — una pagina non ferma il batch
            errors[page] = str(exc)
        if on_page is not None:
            on_page(page, entry, errors.get(page))
    return results, errors


def planned_outputs(pages, *, content, fmt, out_path, out_folder, stem,
                    content_fmt="markdown"):
    """Return the list of paths a run would create (for ``--dry-run``)."""
    units = output_units(content)
    return main.planned_export_paths(
        list(pages), units, fmt, content_fmt, out_path, out_folder, stem)


def write_output(
    results, pages, *, content, include_images, fmt, out_path, out_folder, stem,
    content_fmt="markdown", pandoc=None, lang="",
):
    """Write the batch output; return the created path.

    Delegates to the shared ``main.write_export`` so the CLI stays byte-identical
    to the desktop export (including the ``-translated`` suffix, the ``both``
    split and the content-format conversion).

    ``fmt`` is the packaging (``merged``/``zip``/``folder``/``vault``);
    ``content_fmt`` the content format (markdown/html/text/epub/docx/…).
    """
    units = output_units(content)
    return main.write_export(
        results, list(pages), units=units,
        body_for=lambda entry, sub: page_content(entry, sub, include_images),
        packaging=fmt, content_fmt=content_fmt,
        out_path=out_path, out_folder=out_folder, stem=stem,
        pandoc=pandoc, lang=lang, title=stem)
