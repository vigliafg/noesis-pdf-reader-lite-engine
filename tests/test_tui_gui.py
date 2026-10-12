"""Tests for the ``-gui`` wiring, the line fallback and the Textual UI.

The Textual tests are skipped when Textual is not installed, so the headless
CI (which does not install the ``tui`` extra) still runs the rest.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import itertools
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

import cli  # noqa: E402
import tui_i18n as ti  # noqa: E402
import tui_launch  # noqa: E402
import tui_state  # noqa: E402
from _fixtures import make_text_pdf  # noqa: E402

try:
    import importlib.util

    _HAS_TEXTUAL = importlib.util.find_spec("textual") is not None
except Exception:  # pragma: no cover
    _HAS_TEXTUAL = False


def _drive_fallback(opts):
    """Run the line wizard accepting every default; return (rc, lines)."""
    lines = itertools.chain([""], [""] * 60)
    output: list[str] = []

    def input_fn(_prompt=""):
        try:
            return next(lines)
        except StopIteration:  # pragma: no cover - plenty of lines
            raise EOFError

    import tui_fallback

    saved = (ti.language(), ti.ascii_mode())
    try:
        rc = tui_fallback.run(
            opts, input_fn=input_fn,
            print_fn=lambda *a: output.append(" ".join(str(x) for x in a)))
    finally:
        ti.set_language(saved[0])
        ti.set_ascii(saved[1])
    return rc, output


class CliWiringTests(unittest.TestCase):
    def _run(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cli.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_gui_flag_calls_launcher(self):
        with mock.patch("tui_launch.launch", return_value=7) as launch:
            rc = cli.main(["-gui", "book.pdf"])
        self.assertEqual(rc, 7)
        args = launch.call_args[0][0]
        self.assertTrue(args.gui)
        self.assertEqual(args.pdf, "book.pdf")

    def test_long_gui_flag(self):
        with mock.patch("tui_launch.launch", return_value=0):
            rc = cli.main(["--gui"])
        self.assertEqual(rc, 0)

    def test_gui_prefills_wizard_options(self):
        captured = {}

        def fake_launch(args):
            captured["args"] = args
            return 0

        with mock.patch("tui_launch.launch", side_effect=fake_launch):
            cli.main(["-gui", "book.pdf", "--dst", "en", "--content-format",
                      "html"])
        self.assertEqual(captured["args"].dst, "en")
        self.assertEqual(captured["args"].content_format, "html")

    def test_help_mentions_gui(self):
        out = io.StringIO()
        with self.assertRaises(SystemExit), contextlib.redirect_stdout(out):
            cli.build_parser().parse_args(["--help"])
        self.assertIn("-gui", out.getvalue())

    def test_missing_pdf_without_gui(self):
        rc, _out, err = self._run([])
        self.assertEqual(rc, 2)
        self.assertIn("missing input PDF", err)


class I18nTests(unittest.TestCase):
    def tearDown(self):
        ti.set_language("it")
        ti.set_ascii(False)

    def test_tui_key(self):
        ti.set_language("it")
        self.assertEqual(ti.T("tui.field.pdf"), "File PDF")
        ti.set_language("en")
        self.assertEqual(ti.T("tui.field.pdf"), "PDF file")

    def test_falls_back_to_shared_i18n(self):
        ti.set_language("it")
        self.assertEqual(ti.T("export.wizard.step.pages"), "Pagine")

    def test_ascii_strips_glyphs(self):
        ti.set_language("it")
        ti.set_ascii(False)
        self.assertIn("✓", ti.T("tui.run.page_ok", page=1))
        ti.set_ascii(True)
        self.assertNotIn("✓", ti.T("tui.run.page_ok", page=1))

    def test_probe_terminal(self):
        profile = ti.probe_terminal()
        self.assertIn(profile.color_system,
                      ("truecolor", "256", "16", "none"))
        self.assertIsInstance(profile.minimal, bool)


class FallbackTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.pdf = make_text_pdf(self.dir / "s.pdf", pages=2)

    def tearDown(self):
        self._tmp.cleanup()

    def test_fallback_runs_export(self):
        opts = tui_state.ExportOptions(
            pdf=str(self.pdf), out_folder=str(self.dir), name="fb",
            pages_mode="range", range_from=1, range_to=2)
        rc, output = _drive_fallback(opts)
        self.assertEqual(rc, 0)
        self.assertTrue((self.dir / "fb.md").is_file())
        self.assertTrue(any("pagina 1" in line for line in output))

    def test_fallback_aborts_on_eof(self):
        opts = tui_state.ExportOptions(pdf=str(self.pdf),
                                       out_folder=str(self.dir))

        def input_fn(_prompt=""):
            raise EOFError

        import tui_fallback

        rc = tui_fallback.run(opts, input_fn=input_fn,
                              print_fn=lambda *a: None)
        self.assertEqual(rc, 2)


class LaunchTests(unittest.TestCase):
    """The ``launch`` dispatcher picks the right front-end."""

    def _args(self, **kw):
        base = dict(pdf=None, gui=True, content="original", engine="google",
                    src="auto", dst="it", pages="all", format="merged",
                    content_format="markdown", name=None, out=None,
                    ocr_lang=None, tessdata=None, pandoc=None, pipeline="ir",
                    include_images=True, translate_missing=True,
                    tui_theme="dark", tui_lang="it", ascii=False)
        base.update(kw)
        return argparse.Namespace(**base)

    def _full_profile(self):
        return ti.TerminalProfile(
            isatty=True, dumb=False, utf8=True, no_color=False,
            color_system="truecolor", columns=100, lines=30,
            supports_textual=True)

    def test_falls_back_without_textual(self):
        with mock.patch.object(ti, "probe_terminal", self._full_profile), \
             mock.patch.dict(sys.modules, {"textual": None}), \
             mock.patch.object(tui_launch, "tui_fallback_run",
                               return_value=5) as fallback:
            rc = tui_launch.launch(self._args())
        self.assertEqual(rc, 5)
        fallback.assert_called_once()

    def test_minimal_terminal_uses_fallback(self):
        profile = ti.TerminalProfile(
            isatty=False, dumb=True, utf8=False, no_color=True,
            color_system="none", columns=80, lines=24, supports_textual=False)
        with mock.patch.object(ti, "probe_terminal", return_value=profile), \
             mock.patch.object(tui_launch, "tui_fallback_run",
                               return_value=0) as fallback:
            rc = tui_launch.launch(self._args())
        self.assertEqual(rc, 0)
        fallback.assert_called_once()

    @unittest.skipUnless(_HAS_TEXTUAL, "textual non installato")
    def test_uses_textual_when_available(self):
        fake_app = mock.MagicMock()
        fake_app.run.return_value = 0
        with mock.patch.object(ti, "probe_terminal", self._full_profile), \
             mock.patch("tui.ExportWizardApp", return_value=fake_app) as cls:
            rc = tui_launch.launch(self._args())
        self.assertEqual(rc, 0)
        fake_app.run.assert_called_once()
        cls.assert_called_once()


@unittest.skipUnless(_HAS_TEXTUAL, "textual non installato")
class TextualAppTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.pdf = make_text_pdf(self.dir / "s.pdf", pages=3)

    def tearDown(self):
        self._tmp.cleanup()

    def _app(self, **kw):
        from tui import ExportWizardApp

        opts = tui_state.ExportOptions(
            pdf=str(self.pdf), out_folder=str(self.dir), name="app_out")
        return ExportWizardApp(opts, **kw)

    async def test_wizard_navigates_and_exports(self):
        app = self._app(dark=True)
        async with app.run_test(size=(100, 34)) as pilot:
            await pilot.pause()
            self.assertEqual(app._view, "pages")
            for expected in ("content", "langs", "output", "summary"):
                app.action_next()
                await pilot.pause()
                self.assertEqual(app._view, expected)
            app.action_run()
            for _ in range(100):
                await pilot.pause(0.1)
                if app._view == "result":
                    break
            self.assertEqual(app._view, "result")
            self.assertIsNotNone(app._result)
            self.assertEqual(app._result.errors, {})
            self.assertTrue((self.dir / "app_out.md").is_file())

    async def test_toggles_and_picker(self):
        app = self._app(dark=True)
        async with app.run_test(size=(100, 34)) as pilot:
            await pilot.pause()
            app.action_toggle_language()
            await pilot.pause(0.2)
            self.assertEqual(ti.language(), "en")
            ti.set_language("it")
            app.action_toggle_theme()
            await pilot.pause()
            self.assertEqual(app.theme, "noesis-light")

            app._pick_file()
            await pilot.pause(0.3)
            self.assertEqual(type(app.screen).__name__, "FilePicker")
            app.screen.dismiss(str(self.pdf))
            await pilot.pause(0.2)
            self.assertEqual(app.opts.pdf, str(self.pdf))

    async def test_ansi_theme(self):
        app = self._app(dark=True, ansi=True)
        self.assertEqual(app.theme, "ansi-dark")

    async def test_invalid_packaging_notifies(self):
        app = self._app(dark=True)
        async with app.run_test(size=(100, 34)) as pilot:
            await pilot.pause()
            app.opts.content_format = "epub"
            app.opts.packaging = "folder"
            app.action_run()
            await pilot.pause()
            # stays on the wizard, does not start a run
            self.assertNotEqual(app._view, "run")


if __name__ == "__main__":
    unittest.main()
