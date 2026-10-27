"""End-to-end scenarios for the ``-gui`` Textual wizard.

Each test drives the real :class:`tui.ExportWizardApp` through the harness in
:mod:`tests.tui_e2e` — clicking, typing and pressing keys as a user would — and
then checks both the on-screen state and the files the wizard produced. They
run offline (generated PDFs, stubbed translation) and skip when Textual is not
installed, so the headless CI stays green.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import main as engine  # noqa: E402
import tui_i18n as ti  # noqa: E402
import tui_state  # noqa: E402
import tui_e2e  # noqa: E402
from _fixtures import make_text_pdf  # noqa: E402
from tui_e2e import open_wizard  # noqa: E402


@unittest.skipUnless(tui_e2e.HAS_TEXTUAL, "textual non installato")
class WizardE2EBase(unittest.IsolatedAsyncioTestCase):
    """Shared fixtures: a temp workspace and a 3-page generated PDF."""

    async def asyncSetUp(self):
        tui_e2e.reset_i18n()
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.pdf = make_text_pdf(self.dir / "libro.pdf", pages=3)

    async def asyncTearDown(self):
        tui_e2e.reset_i18n()
        self._tmp.cleanup()

    def options(self, **overrides):
        values = dict(pdf=str(self.pdf), out_folder=str(self.dir))
        values.update(overrides)
        return tui_state.ExportOptions(**values)

    @staticmethod
    def outputs(wizard):
        """``(out_path, out_folder, name)`` the wizard would write."""
        return tui_state.resolve_outputs(wizard.opts)

    async def export(self, wizard):
        """Go to the summary (triggering validation) and run the export."""
        await wizard.goto("summary")
        await wizard.start()
        return await wizard.wait_result()


# ── full flows + artifacts ───────────────────────────────────────────────────


class ExportScenarioTests(WizardE2EBase):
    async def test_full_flow_merged_original(self):
        async with open_wizard(self.options()) as w:
            self.assertEqual(w.step(), "pages")
            # the visible screen shows the step bar and the destination bar
            screen = w.screen_text()
            self.assertIn("Pagine", screen)
            self.assertIn("Destinazione", screen)
            for expected in ("content", "langs", "output", "summary"):
                self.assertEqual(await w.next(), expected)
            result = await self.export(w)

            self.assertFalse(result.cancelled)
            self.assertEqual(result.errors, {})
            self.assertEqual(result.ok, 3)
            self.assertEqual(w.exit_code(), 0)

            out, folder, name = self.outputs(w)
            self.assertIsNone(folder)
            self.assertEqual(name, "libro_estratto")
            self.assertTrue(out.is_file())
            text = out.read_text(encoding="utf-8")
            self.assertIn("<!-- pagina 1 -->", text)
            self.assertIn("<!-- pagina 3 -->", text)
            self.assertIn("quick brown fox", text)
            # the result screen summarizes the run
            self.assertIn("3", w.rendered("#result-body"))

    async def test_range_selection_exports_selected_pages(self):
        async with open_wizard(self.options()) as w:
            await w.choose_range(2, 3)
            self.assertEqual(w.opts.pages_mode, "range")
            result = await self.export(w)

            self.assertEqual(result.ok, 2)
            out, _folder, _name = self.outputs(w)
            text = out.read_text(encoding="utf-8")
            self.assertIn("<!-- pagina 2 -->", text)
            self.assertIn("<!-- pagina 3 -->", text)
            self.assertNotIn("<!-- pagina 1 -->", text)

    async def test_free_selection_exports_selected_pages(self):
        async with open_wizard(self.options()) as w:
            await w.choose_free("1,3")
            self.assertEqual(w.opts.pages_mode, "free")
            result = await self.export(w)

            self.assertEqual(result.ok, 2)
            out, _folder, _name = self.outputs(w)
            text = out.read_text(encoding="utf-8")
            self.assertIn("<!-- pagina 1 -->", text)
            self.assertIn("<!-- pagina 3 -->", text)
            self.assertNotIn("<!-- pagina 2 -->", text)

    async def test_content_both_offline_writes_original_and_translation(self):
        # Stub the translator so "both" stays offline and deterministic.
        with mock.patch.object(engine, "translate_text",
                               side_effect=lambda body, **kw: "TR:" + body):
            async with open_wizard(self.options()) as w:
                await w.choose_content("both")
                result = await self.export(w)

        self.assertEqual(result.ok, 3)
        out, _folder, _name = self.outputs(w)
        translated = out.with_name(out.stem + "-translated" + out.suffix)
        self.assertTrue(out.is_file())
        self.assertTrue(translated.is_file())
        self.assertIn("TR:", translated.read_text(encoding="utf-8"))

    async def test_zip_packaging(self):
        async with open_wizard(self.options()) as w:
            await w.choose_packaging("zip")
            result = await self.export(w)
            self.assertEqual(result.ok, 3)
            out, folder, _name = self.outputs(w)
            self.assertIsNone(folder)
            self.assertEqual(out.suffix, ".zip")
            with zipfile.ZipFile(out) as zf:
                names = set(zf.namelist())
            self.assertEqual(
                names,
                {"libro_pag0001.md", "libro_pag0002.md", "libro_pag0003.md"})

    async def test_folder_packaging(self):
        async with open_wizard(self.options()) as w:
            await w.choose_packaging("folder")
            result = await self.export(w)
            self.assertEqual(result.ok, 3)
            _out, folder, _name = self.outputs(w)
            self.assertTrue((folder / "libro_pag0001.md").is_file())
            self.assertTrue((folder / "libro_pag0003.md").is_file())

    async def test_vault_packaging(self):
        async with open_wizard(self.options()) as w:
            await w.choose_packaging("vault")
            result = await self.export(w)
            self.assertEqual(result.ok, 3)
            _out, folder, _name = self.outputs(w)
            self.assertTrue((folder / "index.md").is_file())
            page = (folder / "libro_pag0001.md").read_text(encoding="utf-8")
            self.assertTrue(page.startswith("---\n"))

    async def test_content_format_html(self):
        async with open_wizard(self.options()) as w:
            await w.choose_content_format("html")
            result = await self.export(w)
            self.assertEqual(result.ok, 3)
            out, _folder, _name = self.outputs(w)
            self.assertEqual(out.suffix, ".html")
            text = out.read_text(encoding="utf-8")
            self.assertIn("<!DOCTYPE html>", text)

    async def test_content_format_text(self):
        async with open_wizard(self.options()) as w:
            await w.choose_content_format("text")
            result = await self.export(w)
            self.assertEqual(result.ok, 3)
            out, _folder, _name = self.outputs(w)
            self.assertEqual(out.suffix, ".txt")
            self.assertIn("quick brown fox", out.read_text(encoding="utf-8"))

    async def test_content_format_epub(self):
        async with open_wizard(self.options()) as w:
            await w.choose_content_format("epub")
            result = await self.export(w)
            self.assertEqual(result.ok, 3)
            out, _folder, _name = self.outputs(w)
            self.assertEqual(out.suffix, ".epub")
            with zipfile.ZipFile(out) as zf:
                self.assertEqual(zf.namelist()[0], "mimetype")


# ── validation / state ───────────────────────────────────────────────────────


class ValidationScenarioTests(WizardE2EBase):
    async def test_pdf_required_before_leaving_pages(self):
        async with open_wizard(tui_state.ExportOptions(
                out_folder=str(self.dir))) as w:
            self.assertEqual(w.step(), "pages")
            await w.click_next()
            # no PDF: the wizard must stay on step 1
            self.assertEqual(w.step(), "pages")
            self.assertEqual(w.exit_code(), 2)
            # once a PDF is chosen, Next works
            await w.set_pdf(self.pdf)
            self.assertEqual(await w.next(), "content")

    async def test_invalid_packaging_is_disabled_and_run_blocked(self):
        async with open_wizard(self.options()) as w:
            await w.choose_content_format("epub")  # merged-only format
            self.assertTrue(w.is_disabled("#pk-folder"))
            self.assertFalse(w.is_disabled("#pk-merged"))
            # force an impossible combination and try to run: it must not start
            w.opts.packaging = "folder"
            w.app.action_run()
            await w.settle()
            self.assertNotEqual(w.step(), "run")
            self.assertIsNone(w.app._result)

    async def test_pandoc_formats_disabled_without_pandoc(self):
        with mock.patch.object(engine, "pandoc_path", return_value=None):
            async with open_wizard(self.options()) as w:
                await w.goto("output")
                self.assertTrue(w.is_disabled("#cf-docx"))
                self.assertTrue(w.is_disabled("#cf-latex"))
                self.assertFalse(w.is_disabled("#cf-markdown"))

    async def test_name_default_follows_pdf_and_manual_edit(self):
        async with open_wizard(self.options()) as w:
            self.assertEqual(w.rendered("#in-name"), "libro_estratto")
            other = make_text_pdf(self.dir / "altro.pdf", pages=2)
            await w.set_pdf(other)
            self.assertEqual(w.rendered("#in-name"), "altro_estratto")
            # a manual edit must survive later PDF changes
            await w.set_name("mio_nome")
            await w.set_pdf(self.pdf)
            self.assertEqual(w.rendered("#in-name"), "mio_nome")
            self.assertEqual(w.opts.name, "mio_nome")

    async def test_destbar_and_previews_update_live(self):
        async with open_wizard(self.options()) as w:
            bar = w.rendered("#destbar")
            self.assertIn("libro_estratto", bar)
            self.assertIn(str(self.dir), bar)
            self.assertIn("3", w.rendered("#pages-preview"))

            await w.choose_packaging("folder")
            preview = w.rendered("#out-preview")
            self.assertIn("libro_pag0001.md", preview)

            await w.choose_free("1")
            self.assertIn("libro_pag0001.md", w.rendered("#out-preview"))


# ── navigation / presentation ────────────────────────────────────────────────


class NavigationScenarioTests(WizardE2EBase):
    async def test_footer_back_visibility_and_back_navigation(self):
        async with open_wizard(self.options()) as w:
            self.assertFalse(w.is_visible("#btn-back"))
            await w.next()
            self.assertTrue(w.is_visible("#btn-back"))
            self.assertEqual(await w.back(), "pages")
            self.assertFalse(w.is_visible("#btn-back"))

    async def test_numeric_shortcuts_and_key_navigation(self):
        async with open_wizard(self.options()) as w:
            for step in tui_e2e.STEPS:
                self.assertEqual(await w.goto(step), step)
            # keyboard back/next with no field focused
            w.app.set_focus(None)
            await w.press("b")
            self.assertEqual(w.step(), "output")
            await w.press("n")
            self.assertEqual(w.step(), "summary")
            # the last step turns Next into the start button
            self.assertIn("i", w.rendered("#btn-next").lower())

    async def test_language_toggle_updates_labels(self):
        async with open_wizard(self.options()) as w:
            # The TUI owns its own strings (``tui.*``); a shared ``export.*``
            # label follows the app language instead (see ``tui_i18n``).
            self.assertEqual(ti.language(), "it")
            self.assertEqual(w.rendered("#btn-pick-pdf"), "Scegli PDF…")
            w.app.set_focus(None)
            await w.press("l")
            self.assertTrue(
                await w.wait_until(lambda: ti.language() == "en", timeout=2.0))
            self.assertTrue(await w.wait_until(
                lambda: w.rendered("#btn-pick-pdf") == "Choose PDF…",
                timeout=2.0))
            self.assertTrue(w.rendered("#destbar").startswith("Destination:"))
            w.app.set_focus(None)
            await w.press("l")
            self.assertTrue(
                await w.wait_until(lambda: ti.language() == "it", timeout=2.0))

    async def test_ascii_and_theme_toggles(self):
        async with open_wizard(self.options()) as w:
            self.assertEqual(w.app.theme, "noesis-dark")
            w.app.set_focus(None)
            await w.press("t")
            await w.settle()
            self.assertEqual(w.app.theme, "noesis-light")
            self.assertFalse(ti.ascii_mode())
            await w.press("a")
            await w.settle()
            self.assertTrue(ti.ascii_mode())

    async def test_help_shortcut_keeps_the_wizard(self):
        async with open_wizard(self.options()) as w:
            w.app.set_focus(None)
            await w.press("question_mark")
            await w.settle()
            self.assertEqual(w.step(), "pages")


# ── file pickers ─────────────────────────────────────────────────────────────


class FilePickerScenarioTests(WizardE2EBase):
    async def test_file_picker_selects_pdf(self):
        async with open_wizard(self.options(pdf="")) as w:
            await w.click("#btn-pick-pdf")
            await w.settle()
            self.assertEqual(type(w.app.screen).__name__, "FilePicker")
            await w.type_into("#picker-path", str(self.pdf))
            await w.press("enter")
            await w.settle()
            self.assertNotEqual(type(w.app.screen).__name__, "FilePicker")
            self.assertEqual(w.opts.pdf, str(self.pdf))
            self.assertEqual(w.rendered("#in-name"), "libro_estratto")

    async def test_file_picker_selects_output_folder(self):
        dest = self.dir / "scelti"
        dest.mkdir()
        async with open_wizard(self.options()) as w:
            await w.goto("output")
            await w.click("#btn-pick-folder")
            await w.settle()
            self.assertEqual(type(w.app.screen).__name__, "FilePicker")
            await w.type_into("#picker-path", str(dest))
            await w.press("enter")
            await w.settle()
            self.assertEqual(w.opts.out_folder, str(dest))


# ── run control / exit codes ─────────────────────────────────────────────────


class RunControlScenarioTests(WizardE2EBase):
    async def test_cancel_during_run_keeps_no_output(self):
        big = make_text_pdf(self.dir / "lungo.pdf", pages=12)
        async with open_wizard(self.options(pdf=str(big))) as w:
            await w.goto("summary")
            # start the (real) worker and cancel before it finishes
            w.app.action_run()
            w.app._cancel = True
            result = await w.wait_result()
            self.assertTrue(result.cancelled)
            self.assertIsNone(result.output_path)
            self.assertEqual(w.exit_code(), 1)
            out, _folder, _name = self.outputs(w)
            self.assertFalse(out.exists())

    async def test_exit_codes(self):
        async with open_wizard(self.options()) as w:
            # nothing run yet: "cancelled / not confirmed"
            self.assertEqual(w.exit_code(), 2)
            result = await self.export(w)
            self.assertFalse(result.errors)
            self.assertEqual(w.exit_code(), 0)


if __name__ == "__main__":
    unittest.main()
