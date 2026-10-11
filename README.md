# Noesis PDF Reader Lite — Engine (CLI)

**`noesis-pdf-engine`** è l'edizione **da riga di comando** del motore di
[Noesis PDF Reader Lite](https://github.com/vigliafg/noesis-pdf-reader-lite):
estrae le pagine di un PDF in **Markdown** con lo stesso *engine adattativo*
dell'app desktop (ricostruzione dell'ordine di lettura, tabelle, figure,
header/footer, titoli…) e, se vuoi, le **traduce**. Espone le **stesse opzioni
di esportazione** della procedura guidata dell'app: selezione pagine, contenuto
(originale / traduzione / entrambi), motore e lingue di traduzione, figure, e i
formati *Markdown unico* / *ZIP* / *cartella di pagine*.

Nessuna interfaccia grafica, nessuna dipendenza da Qt: solo il motore,
il traduttore e l'esportatore.

---

## Indice

- [A cosa serve](#a-cosa-serve)
- [Cosa fa il motore](#cosa-fa-il-motore)
- [Requisiti](#requisiti)
- [Installazione](#installazione)
- [Avvio rapido](#avvio-rapido)
- [Esempi d'uso](#esempi-duso)
- [Riferimento delle opzioni](#riferimento-delle-opzioni)
- [Formati di output](#formati-di-output)
- [Lingue e traduzione](#lingue-e-traduzione)
- [OCR (PDF scansionati)](#ocr-pdf-scansionati)
- [Differenze rispetto all'app desktop](#differenze-rispetto-allapp-desktop)
- [Risoluzione dei problemi](#risoluzione-dei-problemi)
- [Come è costruito](#come-è-costruito)
- [Test e CI](#test-e-ci)
- [Licenza](#licenza)

---

## A cosa serve

Hai un PDF e vuoi **testo Markdown pulito**, pronto per l'archivio, la ricerca
o un'altra pipeline. Con un solo comando ottieni il contenuto della pagina
ricostruito nell'ordine di lettura corretto — anche su layout difficili
(due/tre colonne, tabelle, box, didascalie) — senza aprire nessuna finestra.

```bash
noesis-pdf-engine libro.pdf
```

Genera `libro.md` con **tutte** le pagine estratte.

---

## Cosa fa il motore

L'engine adattativo analizza **ogni pagina** e applica automaticamente il piano
di correzioni giusto:

- **Ordine di lettura** — riordina le colonne (due, tre, quattro…), ricuce i
  paragrafi spezzati e rimette i titoli al posto giusto.
- **Tabelle** — ricostruisce la griglia, riallinea le colonne numeriche,
  sistema le celle vuote e mette le didascalie `TABLE n` su riga propria.
- **Figure** — quando trova una didascalia `FIG n`, la figura diventa un corpo
  unico + didascalia, con l'immagine **incorporata** nel Markdown (data URI), così
  il file resta autocontenuto.
- **Header / footer / numeri di pagina** — riconosciuti per frequenza tra le
  pagine e rimossi (anche quando il Markdown li "traveste" da titolo o elenco).
- **Titoli e leggibilità** — ricompone i titoli spezzati su più righe, separa i
  titoletti MAIUSCOLI fusi col testo, normalizza i glifi mancanti (`\ufffd`),
  raddrizza le pagine a 90°, sistema spaziature e liste.
- **Fallback sicuro** — se una pagina è problematica, il motore **non peggiora
  mai** l'output: ricade sulla pipeline classica solo per quella pagina.

Puoi confrontare il comportamento con l'app desktop: è **lo stesso motore**,
copiato verbatim (vedi [Come è costruito](#come-è-costruito)).

---

## Requisiti

- **Python 3.10+**
- **pip**
- *(opzionale)* **Tesseract OCR** — serve solo per i PDF **scansionati** (immagini).
  Senza Tesseract l'estrazione funziona comunque sui PDF con testo nativo.

---

## Installazione

### A) Con un ambiente virtuale (consigliato)

```bash
python3 -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python cli.py --help          # oppure: python cli.py libro.pdf
```

### B) Come comando installato

```bash
pip install .
noesis-pdf-engine --version
```

Dopo l'installazione il comando `noesis-pdf-engine` è disponibile ovunque.

### C) Senza installare nulla (uso dal checkout)

```bash
python cli.py libro.pdf --pages 1-10
```

---

## Avvio rapido

```bash
# 1) Tutte le pagine → un file Markdown nella cartella corrente
noesis-pdf-engine libro.pdf
# → libro.md

# 2) Solo alcune pagine
noesis-pdf-engine libro.pdf --pages 1-10 -o estratto.md

# 3) Una pagina per file, in una cartella
noesis-pdf-engine libro.pdf --format folder --out out/

# 4) Estratto + traduzione in inglese
noesis-pdf-engine libro.pdf --content both --dst en -o libro_en.md
```

> **Nota sul default:** la CLI parte da `--content original` (solo estrazione,
> nessuna rete). L'app desktop parte da "traduzione". Per tradurre usa
> `--content translated` oppure `--content both`.

---

## Esempi d'uso

### Estrarre un capitolo

```bash
noesis-pdf-engine manuale.pdf --pages 12-45 --content original -o cap3.md
```

### Tradurre una pagina in francese (solo traduzione)

```bash
noesis-pdf-engine articolo.pdf --pages 1 --content translated --src en --dst fr
```

### Originale e traduzione affiancati (nello stesso file)

```bash
noesis-pdf-engine articolo.pdf --content both --dst de -o articolo_de.md
```

### Un file per pagina, numerato

```bash
noesis-pdf-engine tesi.pdf --format folder --out pagine/
# → pagine/tesi_pag0001.md, pagine/tesi_pag0002.md, …
```

### Un archivio ZIP con una pagina per file

```bash
noesis-pdf-engine tesi.pdf --format zip -o tesi.zip
```

### Selezione mista di pagine

```bash
noesis-pdf-engine libro.pdf --pages "1,3,7-9,15"
```

### PDF scansionato (OCR)

```bash
noesis-pdf-engine scansione.pdf --content original --ocr-lang eng+ita
```

### Solo testo, senza immagini incorporate

```bash
noesis-pdf-engine libro.pdf --no-images -o libro_solo_testo.md
```

### Forzare la pipeline classica (debug/confronto)

```bash
noesis-pdf-engine libro.pdf --pipeline current -o confronto.md
```

### Riepilogo leggibile da un altro programma (JSON)

```bash
noesis-pdf-engine libro.pdf --pages 1-5 --json -o out.md
```

---

## Riferimento delle opzioni

| Opzione | Valori | Default | Descrizione |
|---|---|---|---|
| `pdf` *(posizionale)* | percorso | — | Il PDF di input (obbligatorio). |
| `--pages SPEC` | `all`, `7`, `100-103`, `1,3,5-7` | `all` | Pagine da elaborare (1-based). Gli spazi sono ignorati; gli estremi invertiti sono accettati. |
| `--content` | `original` · `translated` · `both` | `original` | Cosa esportare. |
| `--engine` | `google` · `microsoft` | `google` | Motore di traduzione. |
| `--src LANG` | codice lingua o `auto` | `auto` | Lingua di origine. |
| `--dst LANG` | codice lingua | `it` | Lingua di destinazione. |
| `--translate-missing` / `--no-translate-missing` | flag | attivo | Traduce le pagine senza traduzione in cache. |
| `--images` / `--no-images` | flag | attivo | Mantiene (o rimuove) le immagini incorporate nel Markdown. |
| `--format` | `merged` · `zip` · `folder` | `merged` | Formato di output. |
| `-o`, `--out PATH` | percorso | cartella corrente | File (merged/zip) o cartella (folder). |
| `--name NAME` | nome | nome del PDF | Nome del contenitore di output. |
| `--ocr-lang LANG` | es. `eng+ita` | derivato da `--src` | Lingua/e Tesseract per l'OCR. |
| `--tessdata DIR` | percorso | — | Cartella `tessdata` per l'OCR (imposta `TESSDATA_PREFIX`). |
| `--pipeline` | `ir` · `current` | `ir` | Pipeline di estrazione (`current` è la classica/di confronto). |
| `--json` | flag | off | Stampa un riepilogo JSON su stdout. |
| `-q`, `--quiet` | flag | off | Nessun progresso. |
| `-v`, `--verbose` | flag | off | Output più dettagliato. |
| `--version` | flag | — | Stampa la versione. |

**Codici di uscita:** `0` = tutto ok · `1` = almeno una pagina è fallita ·
`2` = errore di input (file mancante, `--pages` non valido, PDF illeggibile).

---

## Formati di output

### `merged` (default) — un unico Markdown

Le pagine sono separate da `---` e precedute da un commento `<!-- pagina N -->`:

```markdown
<!-- pagina 1 -->

# Introduzione

Il testo della prima pagina, con l'ordine di lettura ricostruito.

---

<!-- pagina 2 -->

## Metodo

Il testo della seconda pagina.
```

Il file è nominato `<name>.md` (default: il nome del PDF).

### `zip` — un file per pagina, dentro uno ZIP

```bash
noesis-pdf-engine tesi.pdf --format zip -o tesi.zip
# tesi.zip contiene: tesi_pag0001.md, tesi_pag0002.md, …
```

### `folder` — un file per pagina, in una cartella

```bash
noesis-pdf-engine tesi.pdf --format folder --out pagine/
# pagine/tesi_pag0001.md, pagine/tesi_pag0002.md, …
```

> In `zip` e `folder` i file interni si chiamano sempre
> `<nome-pdf>_pagNNNN.md`; `--name` cambia solo il nome del contenitore
> (file `.zip` o cartella).

**Dettaglio importante:** in ogni corpo il *header di estrazione* viene rimosso
(come nell'export dell'app desktop), quindi il Markdown esportato è "pulito".
Con `--no-images` i riferimenti immagine Markdown vengono eliminati.

---

## Lingue e traduzione

La traduzione usa gli **stessi endpoint pubblici** dell'app desktop
(**Google** o **Microsoft**), quindi richiede **accesso a Internet**.

| Codice | Lingua | Codice | Lingua |
|---|---|---|---|
| `en` | English | `ru` | Русский |
| `it` | Italiano | `zh` | 中文 |
| `fr` | Français | `ja` | 日本語 |
| `de` | Deutsch | `ko` | 한국어 |
| `es` | Español | `ar` | العربية |
| `pt` | Português | `tr` | Türkçe |
| `nl` | Nederlands | `pl` | Polski |
| `auto` | rilevamento automatico *(solo `--src`)* | | |

Esempi:

```bash
# rileva la lingua e traduce in italiano (default)
noesis-pdf-engine doc.pdf --content translated

# da inglese a tedesco con Microsoft
noesis-pdf-engine doc.pdf --content translated --src en --dst de --engine microsoft
```

> **Cache:** a differenza dell'app, la CLI **non ha cache su disco**: le pagine
> vengono sempre tradotte al volo. Per questo `--no-translate-missing` esiste
> solo per parità con l'app: con `--content translated` farebbe fallire ogni
> pagina (non c'è una traduzione salvata a cui ricadere).

---

## OCR (PDF scansionati)

Se il PDF è una **scansione** (pagine come immagini), il testo va riconosciuto
con **Tesseract** tramite PyMuPDF. Serve il binario `tesseract` con i dati
della lingua desiderata.

```bash
# lingua esplicita
noesis-pdf-engine scansione.pdf --content original --ocr-lang eng+ita

# cartella tessdata personalizzata
noesis-pdf-engine scansione.pdf --ocr-lang eng --tessdata /percorso/tessdata
```

Se `--ocr-lang` non è indicato, la lingua OCR deriva da `--src`; con `--src auto`
la CLI usa una combinazione di lingue latine/cirilliche (come l'app desktop).
Se una lingua richiesta non è disponibile, l'estrazione ripiega su `eng` invece
di fallire.

Installazione di Tesseract (esempi):

```bash
# Debian/Ubuntu
sudo apt-get install tesseract-ocr tesseract-ocr-ita tesseract-ocr-eng
# macOS (Homebrew)
brew install tesseract tesseract-lang
# Windows: scarica l'installer da https://github.com/UB-Mannheim/tesseract/wiki
```

---

## Differenze rispetto all'app desktop

| Aspetto | App desktop | CLI `noesis-pdf-engine` |
|---|---|---|
| Interfaccia | GUI (PyQt6) | Riga di comando |
| Contenuto di default | `translated` | `original` (nessuna rete) |
| Pagine di default | pagina corrente | `all` |
| Zone manuali (escludi/includi) | sì, disegnate a mano | **no** (solo pipeline automatica) |
| Cattura oggetti / reader / tema | sì | no |
| Cache di traduzione su disco | sì | no |
| Opzioni di esportazione | selezione pagine, contenuto, lingue/motore, traduci-mancanti, figure, merged/zip/cartella | **le stesse** |
| Composizione dell'output | header rimosso, `<!-- pagina N -->`, `---`, nomi `*_pagNNNN.md` | **identica** |

---

## Risoluzione dei problemi

**`error: input PDF not found`**
Controlla il percorso del file. La CLI esce con codice `2`.

**`error: invalid --pages`**
La specifica è fuori intervallo o malformata. Usa `all`, un numero, un
intervallo (`10-20`) o una lista (`1,3,7-9`). Le pagine partono da `1`.

**Il testo esce vuoto o con errori su una pagina**
È probabile una pagina scansionata senza Tesseract: installalo e indica
`--ocr-lang`. Se una sola pagina fallisce, le altre vengono comunque esportate
e il codice di uscita è `1` (vedi `--json` per l'elenco degli errori).

**La traduzione fallisce**
Serve Internet; l'endpoint può essere temporaneamente bloccato. Prova l'altro
motore con `--engine microsoft`. Con `--json` vedi quali pagine hanno fallito.

**Voglio l'output identico all'app desktop**
Lascia `--pipeline ir` (default) e usa `--content original` (o `translated`
dopo aver impostato le lingue). L'app e la CLI condividono lo stesso motore.

**Le immagini appesantiscono il file**
Sono incorporate come data URI (file autocontenuto). Usa `--no-images` per
rimuoverle.

---

## Come è costruito

I moduli del motore sono **copiati verbatim** dal repository desktop:

```
ir_layout.py · layout_engine.py · page_model.py · layout_proxies.py
pages.py · i18n.py · theme.py
```

`main.py` è il **core Qt-free** rigenerato dallo `main.py` desktop: lo script
`tools/sync_from_desktop.py` ritaglia il blocco senza Qt, lo incapsula con un
header/footer headless e registra la provenienza in `ENGINE_SOURCE.json`.

```bash
python tools/sync_from_desktop.py
python tools/sync_from_desktop.py --desktop /percorso/noesis-pdf-reader-lite
```

`export_core.py` riproduce **byte per byte** la composizione dell'export batch
dell'app (header rimosso, blocchi `<!-- pagina N -->`, ZIP/cartella, rimozione
immagini). Il repository desktop resta la **fonte di verità**: per aggiornare
il motore si lancia lo script di sync.

---

## Test e CI

```bash
pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

La suite include:

- **end-to-end della CLI** su PDF sintetici (merged / zip / cartella, opzioni,
  errori, entrypoint);
- **unit test** della composizione di export;
- **smoke test** del motore headless;
- **parità di sorgente** con il checkout desktop (`tests/test_sync_parity.py`,
  si salta se il repo desktop non è presente);
- i **test del motore** portati dal repository desktop (i casi che richiedono il
  corpus reale si saltano da soli se i PDF non ci sono).

La CI (`.github/workflows/tests.yml`) gira **headless, senza Qt**, su ogni push
e PR: installa PyMuPDF, PyMuPDF4LLM e Tesseract ed esegue l'intera suite.

---

## Licenza

Nessuna licenza esplicita (come il repository desktop di riferimento). Contatta
l'autore per l'uso.
