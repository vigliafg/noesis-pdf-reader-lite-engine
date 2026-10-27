"""End-to-end harness for the Textual wizard (``-gui``).

This module drives the **real** :class:`tui.ExportWizardApp` through the same
interactions a user performs — clicking the footer buttons and the option
widgets, pressing navigation keys, typing into the fields — using Textual's
``Pilot``. It then exposes the app state, the rendered screen and the files the
wizard wrote, so the scenarios in ``tests/test_tui_e2e.py`` can assert on the
whole flow instead of on isolated widgets.

Design notes:

* **Offline and deterministic.** The engine runs on generated PDFs and the
  translation is stubbed by the scenarios that need it, so nothing here touches
  the network.
* **Isolated preferences.** ``XDG_CONFIG_HOME`` is redirected to a temp folder
  for the whole session, so running the wizard never writes the user's real
  ``tui.json``.
* Not a test module (the file name does not start with ``test_``), so
  ``unittest discover`` treats it as a plain helper importable by the test
  module. It stays importable — and reports :data:`HAS_TEXTUAL` — even when the
  optional ``textual`` extra is missing, so the headless CI can skip cleanly.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for _path in (str(_ROOT), str(_HERE)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

#: Wizard steps, in the order the step bar shows them (mirrors ``tui.STEPS``).
STEPS = ("pages", "content", "langs", "output", "summary")

try:  # the harness only works with the optional ``tui`` extra installed
    from textual.pilot import Pilot
    from textual.widgets import Button, Checkbox, Input, Select

    import tui_i18n as ti
    import tui_state
    from tui import STEPS as _REAL_STEPS
    from tui import ExportWizardApp
    from tui_state import ExportOptions

    STEPS = _REAL_STEPS
    HAS_TEXTUAL = True
except ImportError:  # pragma: no cover - exercised only on the headless CI
    HAS_TEXTUAL = False
    ti = None  # type: ignore[assignment]
    tui_state = None  # type: ignore[assignment]
    ExportOptions = None  # type: ignore[assignment]
    ExportWizardApp = None  # type: ignore[assignment]
    Button = Checkbox = Input = Select = None  # type: ignore[assignment]
    Pilot = None  # type: ignore[assignment]


async def _fast_pause(self, delay=None) -> None:
    """A ``Pilot.pause`` replacement that does not wait for CPU idle.

    ``Pilot.pause`` normally calls Textual's ``wait_for_idle``, which compares
    process vs wall time. The engine pulls in native MuPDF/OCR threads that
    keep the process "busy" for a second at a time, so every click/press would
    cost ~1s. A plain short sleep is enough here because the scenarios poll for
    the state they expect (see :meth:`Wizard.wait_until`).
    """
    await asyncio.sleep(0.05 if delay is None else delay)
    try:
        self.app.screen._on_timer_update()
    except Exception:  # noqa: BLE001 — keep the harness version-tolerant
        pass


def reset_i18n() -> None:
    """Restore the TUI language/ASCII globals (they are module state)."""
    if ti is None:
        return
    ti.set_language("it")
    ti.set_ascii(False)


class Wizard:
    """A user-facing driver for a running :class:`ExportWizardApp`.

    Every ``choose_*`` / ``set_*`` helper navigates to the step that owns the
    widget before touching it, exactly like a person clicking through the
    wizard — clicking a control on a hidden pane would otherwise do nothing.
    """

    def __init__(self, app, pilot):
        self.app = app
        self.pilot = pilot

    # ── observation ────────────────────────────────────────────────────
    @property
    def opts(self):
        """The live :class:`ExportOptions` the app is editing."""
        return self.app.opts

    def step(self) -> str:
        """Current wizard step (``pages`` … ``summary``, ``run``, ``result``)."""
        return self.app._view

    def rendered(self, selector: str) -> str:
        """Plain text of a widget: an input's value or its rendered label."""
        widget = self.app.query_one(selector)
        if isinstance(widget, Input):
            return widget.value
        if isinstance(widget, Button):
            return str(widget.label)
        try:
            return str(widget.render())
        except Exception:  # noqa: BLE001 — containers render nothing useful
            return ""

    def screen_text(self) -> str:
        """The whole visible screen as text (for smoke assertions)."""
        try:
            strips = self.app.screen._compositor.render_strips()
            return "\n".join(strip.text.rstrip() for strip in strips)
        except Exception:  # noqa: BLE001 — private API changed
            return ""

    def is_visible(self, selector: str) -> bool:
        widget = self.app.query_one(selector)
        return bool(widget.display) and bool(widget.visible)

    def is_disabled(self, selector: str) -> bool:
        return bool(self.app.query_one(selector).disabled)

    def exit_code(self) -> int:
        """What the app would return to the shell right now."""
        return self.app._exit_code()

    # ── waiting ────────────────────────────────────────────────────────
    async def pause(self, seconds: float = 0.02) -> None:
        """Yield to the event loop so queued messages are delivered."""
        await self.pilot.pause(seconds)

    async def settle(self, rounds: int = 2) -> None:
        """Let pending messages and refreshes settle."""
        for _ in range(rounds):
            await self.pilot.pause(0.02)

    async def wait_until(self, predicate, timeout: float = 1.5,
                         poll: float = 0.02) -> bool:
        """Poll ``predicate`` until it is true or ``timeout`` elapses.

        Used after a click so a slow message pump can never make a scenario
        flaky: the test asserts on the state, not on a fixed sleep.
        """
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while True:
            if predicate():
                return True
            if loop.time() > deadline:
                return False
            await asyncio.sleep(poll)

    # ── raw interactions ───────────────────────────────────────────────
    async def press(self, *keys: str) -> None:
        if keys:
            await self.pilot.press(*keys)
        await self.pause()

    async def click(self, selector: str) -> None:
        await self.pilot.click(selector)
        await self.pause()

    async def click_until(self, selector: str, predicate, *, tries: int = 3,
                          timeout: float = 0.5) -> bool:
        """Click ``selector`` until ``predicate`` holds (options are idempotent)."""
        for _ in range(tries):
            await self.pilot.click(selector)
            if await self.wait_until(predicate, timeout=timeout):
                return True
        return False

    async def type_into(self, selector: str, text: str) -> None:
        """Focus a field, select-all and type ``text`` as real key presses."""
        await self.pilot.click(selector)
        await self.pause()
        await self.pilot.press("ctrl+shift+a")
        if text:
            await self.pilot.press(*text)
        await self.pause()

    # ── navigation ─────────────────────────────────────────────────────
    async def click_next(self) -> str:
        before = self.step()
        # A valid step change is what a person would see; retry and wait for it
        # instead of racing the message pump.
        await self.click_until("#btn-next",
                               lambda: self.step() != before, tries=3)
        return self.step()

    async def next(self) -> str:
        return await self.click_next()

    async def back(self) -> str:
        before = self.step()
        await self.click_until("#btn-back",
                               lambda: self.step() != before, tries=3)
        return self.step()

    async def goto(self, step) -> str:
        """Jump to a step with the ``1``-``5`` shortcut, like the wizard."""
        index = STEPS.index(step) if isinstance(step, str) else int(step)
        target = STEPS[index]
        try:
            self.app.set_focus(None)
        except Exception:  # noqa: BLE001 — older Textual
            pass
        await self.pilot.press(str(index + 1))
        if not await self.wait_until(lambda: self.step() == target, timeout=0.5):
            # The digit may have been swallowed (e.g. focus on a field): fall
            # back to the action the binding itself dispatches.
            self.app.action_goto(index)
            await self.wait_until(lambda: self.step() == target, timeout=0.5)
        return self.step()

    async def start(self) -> str:
        """Confirm on the summary: fires the run (clicks the *Start* button)."""
        await self.click_until(
            "#btn-next", lambda: self.step() in ("run", "result"),
            tries=3, timeout=1.0)
        return self.step()

    async def wait_result(self, timeout: float = 60.0,
                          poll: float = 0.02):
        """Wait for the export worker to reach the result screen.

        Polls with a plain sleep (not ``Pilot.pause``) so the background
        worker — which runs on a thread — cannot keep the event loop "busy"
        and starve the idle wait.
        """
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while self.app._view != "result":
            if loop.time() > deadline:
                raise AssertionError(
                    f"export did not finish in {timeout}s "
                    f"(view={self.app._view!r})")
            await asyncio.sleep(poll)
        await self.pause()
        return self.app._result

    # ── pages step ─────────────────────────────────────────────────────
    async def set_pdf(self, path) -> None:
        await self.goto("pages")
        await self.type_into("#in-pdf", str(path))
        await self.wait_until(lambda: self.opts.pdf == str(path))

    async def choose_all_pages(self) -> None:
        await self.goto("pages")
        await self.click_until("#pm-all", lambda: self.opts.pages_mode == "all")

    async def choose_range(self, lo: int, hi: int) -> None:
        await self.goto("pages")
        await self.type_into("#in-from", str(lo))
        await self.type_into("#in-to", str(hi))
        await self.wait_until(lambda: self.opts.pages_mode == "range")

    async def choose_free(self, spec: str) -> None:
        await self.goto("pages")
        await self.type_into("#in-free", spec)
        await self.wait_until(lambda: self.opts.pages_mode == "free")

    # ── content step ───────────────────────────────────────────────────
    async def choose_content(self, code: str) -> None:
        await self.goto("content")
        await self.click_until(f"#cm-{code}",
                               lambda: self.opts.content == code)

    async def set_images(self, value: bool) -> None:
        await self.goto("content")
        box = self.app.query_one("#chk-images", Checkbox)
        if box.value != value:
            await self.click_until("#chk-images",
                                   lambda: self.opts.include_images == value)

    async def set_translate_missing(self, value: bool) -> None:
        await self.goto("content")
        box = self.app.query_one("#chk-missing", Checkbox)
        if box.value != value:
            await self.click_until(
                "#chk-missing", lambda: self.opts.translate_missing == value)

    # ── languages step ─────────────────────────────────────────────────
    async def choose_src(self, code: str) -> None:
        await self.goto("langs")
        self.app.query_one("#sel-src", Select).value = code
        await self.wait_until(lambda: self.opts.src == code)

    async def choose_dst(self, code: str) -> None:
        await self.goto("langs")
        self.app.query_one("#sel-dst", Select).value = code
        await self.wait_until(lambda: self.opts.dst == code)

    async def choose_engine(self, code: str) -> None:
        await self.goto("langs")
        await self.click_until(f"#eng-{code}", lambda: self.opts.engine == code)

    # ── output step ────────────────────────────────────────────────────
    async def choose_content_format(self, code: str) -> None:
        await self.goto("output")
        await self.click_until(f"#cf-{code}",
                               lambda: self.opts.content_format == code)

    async def choose_packaging(self, code: str) -> None:
        await self.goto("output")
        await self.click_until(f"#pk-{code}",
                               lambda: self.opts.packaging == code)

    async def set_folder(self, path) -> None:
        await self.goto("output")
        await self.type_into("#in-folder", str(path))
        await self.wait_until(lambda: self.opts.out_folder == str(path))

    async def set_name(self, name: str) -> None:
        await self.goto("output")
        await self.type_into("#in-name", name)
        await self.wait_until(lambda: self.opts.name == name)


@asynccontextmanager
async def open_wizard(options=None, *, dark: bool = True, ansi: bool = False,
                      size=(120, 48), config_home=None):
    """Mount a :class:`Wizard` on a real app and yield the driver.

    ``options`` defaults to a blank :class:`ExportOptions`. The caller owns any
    fixture files; this helper only isolates the preferences folder.
    """
    if not HAS_TEXTUAL:  # pragma: no cover - guarded by the test module
        raise RuntimeError("Textual non installato")

    opts = options if options is not None else ExportOptions()
    app = ExportWizardApp(opts, dark=dark, ansi=ansi)
    # Disable animations: they make ``Pilot``'s idle waits up to ~4s each,
    # while changing nothing the scenarios assert on.
    try:
        app.animation_level = "none"
    except Exception:  # noqa: BLE001 — attribute renamed in other versions
        pass
    owned_config = config_home is None
    cfg = config_home or tempfile.mkdtemp(prefix="noesis-tui-cfg-")
    try:
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": cfg}), \
                mock.patch.object(Pilot, "pause", _fast_pause):
            async with app.run_test(size=size) as pilot:
                wizard = Wizard(app, pilot)
                # One short settle so the initial compose/mount is complete;
                # the individual interactions then poll for their state.
                await pilot.pause()
                await wizard.settle()
                yield wizard
    finally:
        if owned_config:
            shutil.rmtree(cfg, ignore_errors=True)
