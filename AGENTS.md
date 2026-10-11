# Istruzioni per l'agente — noesis-pdf-reader-lite-engine (CLI)

## Relazione con il repository desktop

Questo repository è l'edizione **headless / CLI** di
`../noesis-pdf-reader-lite` (app desktop con GUI). **Non possiede un motore
proprio**: usa lo **stesso engine** del desktop, copiato **verbatim**.

Il repository desktop è la **fonte di verità**. Qui:

- `ir_layout.py`, `layout_engine.py`, `page_model.py`, `layout_proxies.py`,
  `pages.py`, `i18n.py`, `theme.py` sono **copie verbatim** dal desktop;
- `main.py` è il **core Qt-free** rigenerato dal `main.py` desktop;
- `export_core.py` riproduce la composizione dell'export batch del desktop
  (merged / zip / cartella, header rimosso, rimozione immagini);
- `cli.py` è il front-end del comando `noesis-pdf-engine`;
- `tools/measure_page_model.py` è copiato dal desktop (test del page model).

## Non modificare a mano il motore

**Non** editare a mano i moduli verbatim né `main.py`: sono **artefatti
rigenerati**. Dopo un cambiamento del motore nel repo desktop:

```bash
python tools/sync_from_desktop.py
python -m unittest discover -s tests
```

`ENGINE_SOURCE.json` registra il commit desktop di provenienza.

## Accoppiamento da ricordare

`ir_layout.py` fa `import main` **lazy** per alcuni helper puri
(`_detect_column_splits`, `_figure_jpeg`, `_word_recall`,
`_rotated_table_rects`, `_norm_text`). Il core headless **deve restare
importabile come modulo `main`**: è il motivo per cui `main.py` non si rinomina.
I marker di ritaglio sono `CORE_START` / `CORE_END` in
`tools/sync_from_desktop.py`.

## Contratto di parità

`tests/test_sync_parity.py` verifica che le copie verbatim e `main.py` siano
**byte-identici** al checkout desktop (si salta in CI, dove il desktop non c'è).
Non aggirarlo: è il contratto "stesso engine".

## Convenzioni del repo

- La CLI parte da `--content original` (nessuna rete di default); l'app desktop
  parte da "translated".
- Comandi utili: `python cli.py --help`, `python -m unittest discover -s tests`,
  `python tools/sync_from_desktop.py`.
- CI headless (senza Qt) in `.github/workflows/tests.yml`.
