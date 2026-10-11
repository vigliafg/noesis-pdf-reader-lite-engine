"""Source-parity with the desktop repository.

The CLI engine must stay *identical* to the desktop engine. When a sibling
checkout of the desktop repo is present (``../noesis-pdf-reader-lite``), this
test asserts that:

* every verbatim engine module is byte-identical;
* the generated headless ``main.py`` equals what the sync script would produce
  from the desktop ``main.py`` right now.

In CI (no desktop checkout) the whole class is skipped.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_DESKTOP = _ROOT.parent / "noesis-pdf-reader-lite"

sys.path.insert(0, str(_ROOT / "tools"))
try:
    import sync_from_desktop as sync  # noqa: E402
except Exception:  # noqa: BLE001
    sync = None


@unittest.skipUnless(
    _DESKTOP.is_dir() and (_DESKTOP / "main.py").is_file() and sync is not None,
    "desktop repo checkout not present",
)
class SyncParityTests(unittest.TestCase):
    def test_engine_modules_are_verbatim(self):
        for name in sync.VERBATIM:
            local = _ROOT / name
            upstream = _DESKTOP / name
            self.assertTrue(local.is_file(), f"missing {name}")
            self.assertEqual(
                local.read_bytes(), upstream.read_bytes(),
                f"{name} differs from the desktop copy — run "
                "tools/sync_from_desktop.py",
            )

    def test_generated_main_matches_desktop(self):
        desktop_text = (_DESKTOP / "main.py").read_text(encoding="utf-8")
        expected = sync.build_main_text(desktop_text)
        actual = (_ROOT / "main.py").read_text(encoding="utf-8")
        self.assertEqual(
            actual, expected,
            "headless main.py is stale — run tools/sync_from_desktop.py",
        )


if __name__ == "__main__":
    unittest.main()
