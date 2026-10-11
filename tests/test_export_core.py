"""Unit tests for ``export_core`` (desktop-parity composition)."""
from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import export_core  # noqa: E402

_HDR = "── pagina 1 │ auto ──\n\n"


class ExportCoreTests(unittest.TestCase):
    def test_strip_images(self):
        text = "before ![fig](file:///tmp/a.png) after"
        self.assertEqual(export_core.strip_images(text), "before  after")

    def test_page_content_strips_header(self):
        entry = {"original": _HDR + "Body text"}
        self.assertEqual(export_core.page_content(entry, "original", True), "Body text")

    def test_page_content_both_joins(self):
        entry = {"original": _HDR + "A", "translated": _HDR + "B"}
        self.assertEqual(export_core.page_content(entry, "both", True), "A\n\nB")

    def test_page_content_translated_only(self):
        entry = {"original": _HDR + "A", "translated": _HDR + "B"}
        self.assertEqual(export_core.page_content(entry, "translated", True), "B")

    def test_page_content_no_images(self):
        entry = {"original": _HDR + "A ![f](x.png)"}
        out = export_core.page_content(entry, "original", False)
        self.assertNotIn("![", out)

    def test_write_output_merged(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.md"
            result = export_core.write_output(
                {0: {"original": _HDR + "A"}, 1: {"original": _HDR + "B"}},
                [0, 1], content="original", include_images=True,
                fmt="merged", out_path=out, out_folder=None, stem="doc",
            )
            self.assertEqual(result, out)
            text = out.read_text(encoding="utf-8")
            self.assertEqual(
                text, "<!-- pagina 1 -->\n\nA\n\n---\n\n<!-- pagina 2 -->\n\nB")

    def test_write_output_zip(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.zip"
            export_core.write_output(
                {0: {"original": _HDR + "A"}}, [0], content="original",
                include_images=True, fmt="zip", out_path=out,
                out_folder=None, stem="doc",
            )
            with zipfile.ZipFile(out) as zf:
                self.assertEqual(zf.namelist(), ["doc_pag0001.md"])
                self.assertEqual(zf.read("doc_pag0001.md").decode(), "A")

    def test_write_output_folder(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / "pages"
            export_core.write_output(
                {0: {"original": _HDR + "A"}}, [0], content="original",
                include_images=True, fmt="folder", out_path=None,
                out_folder=folder, stem="doc",
            )
            self.assertEqual((folder / "doc_pag0001.md").read_text(), "A")


if __name__ == "__main__":
    unittest.main()
