"""Smoke tests for the headless engine core (``main``)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import main  # noqa: E402
from _fixtures import make_text_pdf  # noqa: E402


class EngineSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.pdf = make_text_pdf(Path(cls._tmp.name) / "s.pdf", pages=1)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_select_page_output(self):
        text, engine, raw = main._select_page_output(str(self.pdf), 0)
        self.assertTrue(text.strip())
        self.assertIn(engine, ("ir", "current"))
        self.assertIsInstance(raw, str)

    def test_batch_extract_page(self):
        text, label, raw, engine = main._batch_extract_page(
            str(self.pdf), 0, "eng", None)
        self.assertTrue(text.strip())
        self.assertIn(engine, ("ir", "current"))
        self.assertIn(label, ("auto", "manual"))

    def test_tess_lang_code(self):
        self.assertEqual(main._tess_lang_code("it"), "ita")
        self.assertEqual(main._tess_lang_code("en"), "eng")
        self.assertEqual(main._tess_lang_code(None), main._AUTO_TESS_LANGS)

    def test_strip_header(self):
        body = "── pagina 1 │ auto ──\n\nHello"
        self.assertEqual(main._strip_header(body), "Hello")
        self.assertEqual(main._strip_header("Hello"), "Hello")

    def test_norm_text(self):
        self.assertEqual(main._norm_text("Hello,  World!"), "hello world")

    def test_pipeline_mode_default_ir(self):
        self.assertEqual(main._pipeline_mode(), "ir")


if __name__ == "__main__":
    unittest.main()
