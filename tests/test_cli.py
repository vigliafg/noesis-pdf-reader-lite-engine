"""End-to-end tests for the ``noesis-pdf-engine`` CLI.

Runs the real engine on a small synthetic PDF (no corpus, no network: only
``--content original``).
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import cli  # noqa: E402
from _fixtures import make_text_pdf  # noqa: E402


class CliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.pdf = make_text_pdf(self.dir / "sample.pdf", pages=2)

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cli.main(argv)
        return rc, out.getvalue(), err.getvalue()

    # ── formats ────────────────────────────────────────────────────────

    def test_merged_original(self):
        out = self.dir / "out.md"
        rc, _stdout, _err = self._run([
            str(self.pdf), "--pages", "all", "--content", "original",
            "--format", "merged", "-o", str(out), "--quiet",
        ])
        self.assertEqual(rc, 0)
        self.assertTrue(out.is_file())
        text = out.read_text(encoding="utf-8")
        self.assertIn("<!-- pagina 1 -->", text)
        self.assertIn("<!-- pagina 2 -->", text)
        self.assertIn("quick brown fox", text)

    def test_zip_format_and_names(self):
        out = self.dir / "bundle.zip"
        rc, _stdout, _err = self._run([
            str(self.pdf), "--pages", "1", "--content", "original",
            "--format", "zip", "-o", str(out), "--quiet",
        ])
        self.assertEqual(rc, 0)
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
            self.assertEqual(names, ["sample_pag0001.md"])
            self.assertIn("quick brown fox", zf.read(names[0]).decode("utf-8"))

    def test_folder_format(self):
        folder = self.dir / "outdir"
        rc, _stdout, _err = self._run([
            str(self.pdf), "--pages", "1-2", "--content", "original",
            "--format", "folder", "-o", str(folder), "--quiet",
        ])
        self.assertEqual(rc, 0)
        self.assertTrue((folder / "sample_pag0001.md").is_file())
        self.assertTrue((folder / "sample_pag0002.md").is_file())

    def test_default_out_name_adds_suffix(self):
        rc, _stdout, _err = self._run([
            str(self.pdf), "--pages", "1", "--content", "original",
            "--out", str(self.dir / "named"), "--quiet",
        ])
        self.assertEqual(rc, 0)
        self.assertTrue((self.dir / "named.md").is_file())

    # ── new content formats + vault ────────────────────────────────────

    def test_html_merged(self):
        out = self.dir / "o.html"
        rc, _stdout, _err = self._run([
            str(self.pdf), "--pages", "all", "--content", "original",
            "--content-format", "html", "-o", str(out), "--quiet",
        ])
        self.assertEqual(rc, 0)
        text = out.read_text(encoding="utf-8")
        self.assertIn("<!DOCTYPE html>", text)
        self.assertIn("quick brown fox", text)

    def test_text_zip(self):
        out = self.dir / "o.zip"
        rc, _stdout, _err = self._run([
            str(self.pdf), "--pages", "1", "--content", "original",
            "--content-format", "text", "--format", "zip", "-o", str(out),
            "--quiet",
        ])
        self.assertEqual(rc, 0)
        with zipfile.ZipFile(out) as zf:
            self.assertEqual(zf.namelist(), ["sample_pag0001.txt"])

    def test_epub_merged(self):
        out = self.dir / "o.epub"
        rc, _stdout, _err = self._run([
            str(self.pdf), "--pages", "1-2", "--content", "original",
            "--content-format", "epub", "-o", str(out), "--quiet",
        ])
        self.assertEqual(rc, 0)
        with zipfile.ZipFile(out) as zf:
            self.assertEqual(zf.namelist()[0], "mimetype")
            self.assertIn("OEBPS/content.opf", zf.namelist())

    def test_vault_format(self):
        folder = self.dir / "vault"
        rc, _stdout, _err = self._run([
            str(self.pdf), "--pages", "1-2", "--content", "original",
            "--format", "vault", "--out", str(folder), "--quiet",
        ])
        self.assertEqual(rc, 0)
        self.assertTrue((folder / "index.md").is_file())
        page = (folder / "sample_pag0001.md").read_text(encoding="utf-8")
        self.assertTrue(page.startswith("---\n"))

    def test_invalid_packaging_content_combo(self):
        rc, _stdout, err = self._run([
            str(self.pdf), "--pages", "1", "--content", "original",
            "--content-format", "epub", "--format", "folder", "--quiet",
        ])
        self.assertEqual(rc, 2)
        self.assertIn("cannot carry", err)

    @unittest.skipUnless(shutil.which("pandoc"), "pandoc non installato")
    def test_docx_merged(self):
        out = self.dir / "o.docx"
        rc, _stdout, _err = self._run([
            str(self.pdf), "--pages", "1", "--content", "original",
            "--content-format", "docx", "-o", str(out), "--quiet",
        ])
        self.assertEqual(rc, 0)
        with zipfile.ZipFile(out) as zf:
            self.assertIn("word/document.xml", zf.namelist())

    def test_dry_run_html_lists_html_files(self):
        rc, stdout, _err = self._run([
            str(self.pdf), "--pages", "1", "--content", "original",
            "--content-format", "html", "--dry-run",
        ])
        self.assertEqual(rc, 0)
        self.assertIn(".html", stdout)

    # ── options ────────────────────────────────────────────────────────

    def test_json_summary(self):
        rc, stdout, _err = self._run([
            str(self.pdf), "--pages", "1", "--content", "original",
            "--format", "merged", "-o", str(self.dir / "o.md"),
            "--json", "--quiet",
        ])
        self.assertEqual(rc, 0)
        data = json.loads(stdout)
        self.assertEqual(data["pages"], [1])
        self.assertEqual(data["ok"], 1)
        self.assertEqual(data["errors"], {})
        self.assertEqual(data["content"], "original")

    def test_default_content_is_original(self):
        # Headless default is extraction only (no network); the GUI starts from
        # "translated". Overridable with --content.
        rc, stdout, _err = self._run([
            str(self.pdf), "--pages", "1", "--json",
            "-o", str(self.dir / "default.md"), "--quiet",
        ])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(stdout)["content"], "original")

    def test_no_images_flag(self):
        out = self.dir / "noimg.md"
        rc, _stdout, _err = self._run([
            str(self.pdf), "--pages", "1", "--content", "original",
            "--no-images", "-o", str(out), "--quiet",
        ])
        self.assertEqual(rc, 0)
        self.assertNotIn("data:image", out.read_text(encoding="utf-8"))

    def test_pipeline_current(self):
        out = self.dir / "cur.md"
        rc, _stdout, _err = self._run([
            str(self.pdf), "--pages", "1", "--content", "original",
            "--pipeline", "current", "-o", str(out), "--quiet",
        ])
        self.assertEqual(rc, 0)
        self.assertTrue(out.read_text(encoding="utf-8").strip())

    # ── errors ─────────────────────────────────────────────────────────

    def test_invalid_pages(self):
        rc, _stdout, err = self._run([
            str(self.pdf), "--pages", "99", "--content", "original", "--quiet",
        ])
        self.assertEqual(rc, 2)
        self.assertIn("invalid --pages", err)

    def test_missing_file(self):
        rc, _stdout, err = self._run([str(self.dir / "nope.pdf"), "--quiet"])
        self.assertEqual(rc, 2)
        self.assertIn("not found", err)

    def test_translated_without_translate_missing_errors(self):
        # No cache in the CLI: translated + --no-translate-missing must fail
        # per page (mirrors the desktop "not ready" behaviour).
        rc, stdout, _err = self._run([
            str(self.pdf), "--pages", "1", "--content", "translated",
            "--no-translate-missing", "--json", "--quiet",
        ])
        self.assertEqual(rc, 1)
        data = json.loads(stdout)
        self.assertEqual(data["ok"], 0)
        self.assertIn("1", data["errors"])

    def test_dry_run_lists_translated_files(self):
        rc, stdout, _err = self._run([
            str(self.pdf), "--pages", "1-2", "--content", "both",
            "--format", "folder", "--out", str(self.dir / "out"),
            "--dry-run",
        ])
        self.assertEqual(rc, 0)
        self.assertIn("sample_pag0001.md", stdout)
        self.assertIn("sample_pag0001-translated.md", stdout)
        self.assertIn("sample_pag0002-translated.md", stdout)
        self.assertFalse((self.dir / "out").exists())  # nessuna estrazione

    # ── console entrypoint ─────────────────────────────────────────────

    def test_console_entrypoint_subprocess(self):
        env = dict(os.environ, PYTHONPATH=str(_ROOT))
        out = self.dir / "sub.md"
        proc = subprocess.run(
            [sys.executable, str(_ROOT / "cli.py"), str(self.pdf),
             "--pages", "1", "--content", "original", "-o", str(out),
             "--quiet"],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(out.is_file())


if __name__ == "__main__":
    unittest.main()
