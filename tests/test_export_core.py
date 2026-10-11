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


    def test_output_units(self):
        self.assertEqual(export_core.output_units("original"), [("", "original")])
        self.assertEqual(
            export_core.output_units("translated"), [("-translated", "translated")])
        self.assertEqual(
            export_core.output_units("both"),
            [("", "original"), ("-translated", "translated")])

    def test_page_filename(self):
        self.assertEqual(export_core.page_filename("doc", 0, ""), "doc_pag0001.md")
        self.assertEqual(
            export_core.page_filename("doc", 11, "-translated"),
            "doc_pag0012-translated.md")

    def test_write_output_merged_translated_suffix(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.md"
            result = export_core.write_output(
                {0: {"translated": _HDR + "B"}}, [0], content="translated",
                include_images=True, fmt="merged", out_path=out,
                out_folder=None, stem="doc")
            self.assertEqual(result, Path(d) / "o-translated.md")
            self.assertEqual(result.read_text(encoding="utf-8"),
                             "<!-- pagina 1 -->\n\nB")

    def test_write_output_merged_both_two_files(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.md"
            export_core.write_output(
                {0: {"original": _HDR + "A", "translated": _HDR + "B"}},
                [0], content="both", include_images=True, fmt="merged",
                out_path=out, out_folder=None, stem="doc")
            self.assertEqual((Path(d) / "o.md").read_text(encoding="utf-8"),
                             "<!-- pagina 1 -->\n\nA")
            self.assertEqual(
                (Path(d) / "o-translated.md").read_text(encoding="utf-8"),
                "<!-- pagina 1 -->\n\nB")

    def test_write_output_zip_both(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.zip"
            export_core.write_output(
                {0: {"original": _HDR + "A", "translated": _HDR + "B"}},
                [0], content="both", include_images=True, fmt="zip",
                out_path=out, out_folder=None, stem="doc")
            with zipfile.ZipFile(out) as zf:
                self.assertEqual(
                    zf.namelist(),
                    ["doc_pag0001.md", "doc_pag0001-translated.md"])
                self.assertEqual(zf.read("doc_pag0001.md").decode(), "A")
                self.assertEqual(
                    zf.read("doc_pag0001-translated.md").decode(), "B")

    def test_planned_outputs_folder(self):
        files = export_core.planned_outputs(
            [0, 1], content="both", fmt="folder", out_path=None,
            out_folder="/tmp/x", stem="doc")
        self.assertEqual(
            [f.name for f in files],
            ["doc_pag0001.md", "doc_pag0001-translated.md",
             "doc_pag0002.md", "doc_pag0002-translated.md"])


if __name__ == "__main__":
    unittest.main()
