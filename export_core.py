"""Export composition for the CLI — mirrors the desktop batch export.

The desktop composes the batch output inside ``MainWindow`` methods
(``_write_batch_output`` / ``_batch_page_content`` / ``_batch_strip_images``).
A CLI has no saved text edits, so the edit-cache lookup reduces to the
identity and the composition is: strip the extraction header, join the
original and/or the translation, optionally drop the Markdown image embeds,
then write merged / zip / per-page folder.

This module reproduces that logic so the CLI output is byte-identical to the
desktop export for the same engine options.

Naming rules (desktop parity):

* ``original``   → one file per page, ``{stem}_pag{NNNN}.md``;
* ``translated`` → one file per page, ``{stem}_pag{NNNN}-translated.md``;
* ``both``       → **two** files per page (original + translation).

In the ``merged`` format the single output file carries the same
``-translated`` suffix (``both`` emits two merged files). Zip archives and
per-page folders keep the user-chosen container name; only the content files
get the suffix.
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

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


def page_filename(stem: str, page: int, suffix: str) -> str:
    """Per-page file name: ``{stem}_pag{NNNN}{suffix}.md`` (1-based page)."""
    return f"{stem}_pag{page + 1:04d}{suffix}.md"


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


def planned_outputs(pages, *, content, fmt, out_path, out_folder, stem):
    """Return the list of paths a run would create (for ``--dry-run``)."""
    units = output_units(content)
    if fmt == "merged":
        base = Path(out_path)
        return [base.with_name(base.stem + suffix + base.suffix)
                for suffix, _sub in units]
    names = [page_filename(stem, p, suffix)
             for p in pages for suffix, _sub in units]
    if fmt == "zip":
        return [Path(out_path)]  # archive; entries listed separately
    return [Path(out_folder) / n for n in names]


def write_output(
    results, pages, *, content, include_images, fmt, out_path, out_folder, stem
):
    """Write the batch output; return the created path.

    Mirrors ``MainWindow._write_batch_output`` exactly, including the
    ``-translated`` suffix and the ``both`` split.
    """
    units = output_units(content)
    if fmt == "merged":
        created: Path | None = None
        for suffix, sub in units:
            chunks = []
            for p in pages:
                body = page_content(results.get(p, {}), sub, include_images)
                chunks.append(f"<!-- pagina {p + 1} -->\n\n{body}")
            text = "\n\n---\n\n".join(chunks)
            base = Path(out_path)
            path = base.with_name(base.stem + suffix + base.suffix)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            created = path
        return created if created is not None else Path(out_path)
    files: dict[str, str] = {}
    for p in pages:
        for suffix, sub in units:
            body = page_content(results.get(p, {}), sub, include_images)
            files[page_filename(stem, p, suffix)] = body
    if fmt == "zip":
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, body in files.items():
                zf.writestr(name, body)
        return out_path
    out_folder = Path(out_folder)
    out_folder.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (out_folder / name).write_text(body, encoding="utf-8")
    return out_folder
