"""Unit tests for the pure TUI state layer (no Textual required)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import tui_state  # noqa: E402
from _fixtures import make_text_pdf  # noqa: E402


class OptionsTests(unittest.TestCase):
    def test_from_dict_normalizes(self):
        opts = tui_state.ExportOptions.from_dict({
            "pages_mode": "bogus", "content": "nope", "engine": "yandex",
            "content_format": "pdf", "packaging": "tar", "src": "xx",
            "dst": "auto", "pipeline": "zzz",
        })
        self.assertEqual(opts.pages_mode, "all")
        self.assertEqual(opts.content, "original")
        self.assertEqual(opts.engine, "google")
        self.assertEqual(opts.content_format, "markdown")
        self.assertEqual(opts.packaging, "merged")
        self.assertEqual(opts.src, "auto")
        self.assertEqual(opts.dst, "it")
        self.assertEqual(opts.pipeline, "ir")

    def test_from_dict_roundtrip(self):
        opts = tui_state.ExportOptions(pdf="/a/b.pdf", content="both",
                                       dst="en", include_images=False)
        again = tui_state.ExportOptions.from_dict(opts.as_dict())
        self.assertEqual(again, opts)

    def test_from_dict_tolerates_garbage(self):
        self.assertEqual(tui_state.ExportOptions.from_dict(None),
                         tui_state.ExportOptions())
        self.assertEqual(tui_state.ExportOptions.from_dict("nope"),
                         tui_state.ExportOptions())


class PagesTests(unittest.TestCase):
    def test_all(self):
        pages, err = tui_state.select_pages(
            tui_state.ExportOptions(pages_mode="all"), 4)
        self.assertEqual(pages, [0, 1, 2, 3])
        self.assertIsNone(err)

    def test_range_swaps_bounds(self):
        pages, err = tui_state.select_pages(
            tui_state.ExportOptions(pages_mode="range", range_from=3,
                                    range_to=1), 5)
        self.assertEqual(pages, [0, 1, 2])
        self.assertIsNone(err)

    def test_free_invalid(self):
        pages, err = tui_state.select_pages(
            tui_state.ExportOptions(pages_mode="free", free_pages="99"), 3)
        self.assertIsNone(pages)
        self.assertEqual(err[0], "export.free.err.bounds")

    def test_no_pages(self):
        pages, err = tui_state.select_pages(
            tui_state.ExportOptions(pages_mode="all"), 0)
        self.assertIsNone(pages)
        self.assertEqual(err[0], "export.free.err.no_pages")


class OutputTests(unittest.TestCase):
    def test_allowed_packagings(self):
        self.assertEqual(
            tui_state.allowed_packagings("epub"), ["merged"])
        self.assertIn("vault", tui_state.allowed_packagings("markdown"))

    def test_resolve_merged(self):
        out, folder, name = tui_state.resolve_outputs(
            tui_state.ExportOptions(pdf="/x/doc.pdf", out_folder="/tmp",
                                    name="doc_estratto"))
        self.assertIsNone(folder)
        self.assertEqual(out, Path("/tmp/doc_estratto.md"))
        self.assertEqual(name, "doc_estratto")

    def test_resolve_zip_adds_ext(self):
        out, _folder, _name = tui_state.resolve_outputs(
            tui_state.ExportOptions(pdf="/x/doc.pdf", out_folder="/tmp",
                                    name="doc", packaging="zip"))
        self.assertEqual(out, Path("/tmp/doc.zip"))

    def test_resolve_folder(self):
        out, folder, _name = tui_state.resolve_outputs(
            tui_state.ExportOptions(pdf="/x/doc.pdf", out_folder="/tmp",
                                    name="doc", packaging="vault"))
        self.assertIsNone(out)
        self.assertEqual(folder, Path("/tmp/doc"))

    def test_ocr_lang_derived(self):
        self.assertEqual(
            tui_state.ocr_lang_for(tui_state.ExportOptions(src="en")),
            "eng")
        self.assertEqual(
            tui_state.ocr_lang_for(
                tui_state.ExportOptions(src="en", ocr_lang="ita")),
            "ita")

    def test_summary_rows(self):
        rows = tui_state.summary_rows(
            tui_state.ExportOptions(pdf="/x/doc.pdf", out_folder="/tmp",
                                    name="doc_estratto"), [0, 1, 2])
        keys = [k for k, _ in rows]
        self.assertIn("export.sum.pages", keys)
        self.assertIn("export.sum.output", keys)


class ValidateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.pdf = make_text_pdf(self.dir / "s.pdf", pages=3)

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_pdf(self):
        pages, errors = tui_state.validate(tui_state.ExportOptions())
        self.assertIsNone(pages)
        self.assertEqual(errors[0][0], "tui.err.no_pdf")

    def test_bad_packaging(self):
        _pages, errors = tui_state.validate(tui_state.ExportOptions(
            pdf=str(self.pdf), content_format="epub", packaging="folder"))
        self.assertTrue(any(k == "tui.err.bad_packaging" for k, _ in errors))

    def test_ok(self):
        pages, errors = tui_state.validate(tui_state.ExportOptions(
            pdf=str(self.pdf)))
        self.assertEqual(pages, [0, 1, 2])
        self.assertEqual(errors, [])

    def test_planned_files_both_merged(self):
        opts = tui_state.ExportOptions(
            pdf=str(self.pdf), content="both", out_folder=str(self.dir),
            name="doc", packaging="merged")
        files = tui_state.planned_files(opts, [0, 1])
        self.assertEqual(len(files), 2)
        self.assertTrue(str(files[0]).endswith("doc.md"))
        self.assertTrue(str(files[1]).endswith("doc-translated.md"))


class ExecuteTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.pdf = make_text_pdf(self.dir / "s.pdf", pages=2)

    def tearDown(self):
        self._tmp.cleanup()

    def test_execute_merged(self):
        opts = tui_state.ExportOptions(
            pdf=str(self.pdf), out_folder=str(self.dir), name="out",
            pages_mode="range", range_from=1, range_to=1)
        result = tui_state.execute(opts)
        self.assertFalse(result.cancelled)
        self.assertEqual(result.ok, 1)
        self.assertEqual(result.errors, {})
        self.assertTrue(result.output_path.is_file())

    def test_execute_cancel(self):
        opts = tui_state.ExportOptions(
            pdf=str(self.pdf), out_folder=str(self.dir), name="out")
        result = tui_state.execute(opts, should_cancel=lambda: True)
        self.assertTrue(result.cancelled)
        self.assertIsNone(result.output_path)


class PrefsTests(unittest.TestCase):
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp}):
                opts = tui_state.ExportOptions(pdf="/a/b.pdf", dst="fr",
                                               content="both")
                tui_state.save_prefs(opts)
                self.assertTrue(tui_state.prefs_path().is_file())
                self.assertEqual(tui_state.load_prefs(), opts)

    def test_load_missing_is_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp}):
                self.assertEqual(tui_state.load_prefs(),
                                 tui_state.ExportOptions())


if __name__ == "__main__":
    unittest.main()
