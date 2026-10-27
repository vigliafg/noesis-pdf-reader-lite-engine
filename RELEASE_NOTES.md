# Noesis PDF Reader Lite Engine 0.30.0

Edizione **CLI + TUI** del motore di [Noesis PDF Reader Lite](https://github.com/vigliafg/noesis-pdf-reader-lite) **0.30.0**.
Il motore è sincronizzato dal desktop (commit `68365fa`) e verificato dal test di
parità (`tests/test_sync_parity.py`).

## Novità

- **Wizard TUI (`-gui`)** più solido: destinazione sempre visibile, selezione
  pagine implicita digitando nei campi, nome output che segue il PDF finché non
  viene modificato a mano.
- **Test end-to-end della TUI**: l'app Textual reale viene pilotata con click,
  tasti e digitazione; si verificano anche i file esportati (merged, ZIP,
  cartella, vault, formati, annullamento).
- **Release multipiattaforma** con installer Windows, AppImage Linux e DMG macOS.
- **Dipendenze riproducibili**: PyMuPDF/PyMuPDF4LLM restano sulla serie **1.x**,
  quella su cui è tarato il motore layout.

## Asset

| Piattaforma | File |
| --- | --- |
| Windows x64 | `noesis-pdf-reader-lite-engine-windows-x64.exe` |
| Windows x64 (installer) | `noesis-pdf-reader-lite-engine-windows-x64-setup.exe` |
| Linux x86_64 | `noesis-pdf-reader-lite-engine-x86_64.AppImage` |
| macOS x86_64 | `noesis-pdf-reader-lite-engine-macos-x64.dmg` |
| macOS arm64 | `noesis-pdf-reader-lite-engine-macos-arm64.dmg` |
| Integrità | `SHA256SUMS.txt` |

## Verifica

```bash
sha256sum -c SHA256SUMS.txt
./noesis-pdf-reader-lite-engine --version   # 0.30.0
./noesis-pdf-reader-lite-engine --help
```

Il wizard TUI richiede un terminale interattivo: `-gui` ripiega su un wizard a
righe se Textual non è disponibile. I PDF scansionati richiedono Tesseract.

## Requisiti

- Windows 10+, macOS 12+, oppure Linux x86_64.
- PyMuPDF/PyMuPDF4LLM 1.x (inclusi nei bundle).
- Tesseract OCR opzionale per i PDF scansionati.

Vedi il [README](https://github.com/vigliafg/noesis-pdf-reader-lite-engine#readme)
per opzioni, formati e differenze rispetto all'app desktop.
