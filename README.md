# Noesis PDF Reader Lite — Engine (CLI)

**`noesis-pdf-reader-lite-engine`** è l'edizione **da riga di comando** del motore di
[Noesis PDF Reader Lite](https://github.com/vigliafg/noesis-pdf-reader-lite):
estrae le pagine di un PDF in **Markdown** con lo stesso *engine adattativo*
dell'app desktop (ricostruzione dell'ordine di lettura, tabelle, figure,
header/footer, titoli…) e, se vuoi, le **traduce**. Espone le **stesse opzioni
di esportazione** della procedura guidata dell'app: selezione pagine, contenuto
(originale / traduzione / entrambi), motore e lingue di traduzione, figure,
**formato del contenuto** (`markdown` / `html` / `text` / `epub` / `docx` /
`odt` / `rtf` / `latex`) e **impacchettamento** (*Markdown unico* / *ZIP* /
*cartella di pagine* / *vault con indice*).

Nessuna dipendenza da Qt: solo il motore, il traduttore e l'esportatore.
In più, con `-gui`, un **wizard TUI** opzionale (Textual) per chi vuole
l'interfaccia guidata senza la GUI desktop.

---

## Indice

- [A cosa serve](#a-cosa-serve)
- [Cosa fa il motore](#cosa-fa-il-motore)
- [Requisiti](#requisiti)
- [Installazione](#installazione)
- [Avvio rapido](#avvio-rapido)
- [Esempi d'uso](#esempi-duso)
- [Riferimento delle opzioni](#riferimento-delle-opzioni)
- [Wizard interattivo (`-gui`)](#wizard-interattivo---gui)
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
noesis-pdf-reader-lite-engine libro.pdf
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
noesis-pdf-reader-lite-engine --version
```

Dopo l'installazione il comando `noesis-pdf-reader-lite-engine` è disponibile ovunque.

### C) Senza installare nulla (uso dal checkout)

```bash
python cli.py libro.pdf --pages 1-10
```

---

## Avvio rapido

```bash
# 1) Tutte le pagine → un file Markdown nella cartella corrente
noesis-pdf-reader-lite-engine libro.pdf
# → libro.md

# 2) Solo alcune pagine
noesis-pdf-reader-lite-engine libro.pdf --pages 1-10 -o estratto.md

# 3) Una pagina per file, in una cartella
noesis-pdf-reader-lite-engine libro.pdf --format folder --out out/

# 4) Estratto + traduzione in inglese
noesis-pdf-reader-lite-engine libro.pdf --content both --dst en -o libro_en.md
```

> **Nota sul default:** la CLI parte da `--content original` (solo estrazione,
> nessuna rete). L'app desktop parte da "traduzione". Per tradurre usa
> `--content translated` oppure `--content both`.

---

## Esempi d'uso

### Estrarre un capitolo

```bash
noesis-pdf-reader-lite-engine manuale.pdf --pages 12-45 --content original -o cap3.md
```

### Tradurre una pagina in francese (solo traduzione)

```bash
noesis-pdf-reader-lite-engine articolo.pdf --pages 1 --content translated --src en --dst fr
```

### Originale e traduzione affiancati (nello stesso file)

```bash
noesis-pdf-reader-lite-engine articolo.pdf --content both --dst de -o articolo_de.md
```

### Un file per pagina, numerato

```bash
noesis-pdf-reader-lite-engine tesi.pdf --format folder --out pagine/
# → pagine/tesi_pag0001.md, pagine/tesi_pag0002.md, …
```

### Un archivio ZIP con una pagina per file

```bash
noesis-pdf-reader-lite-engine tesi.pdf --format zip -o tesi.zip
```

### Selezione mista di pagine

```bash
noesis-pdf-reader-lite-engine libro.pdf --pages "1,3,7-9,15"
```

### PDF scansionato (OCR)

```bash
noesis-pdf-reader-lite-engine scansione.pdf --content original --ocr-lang eng+ita
```

### Solo testo, senza immagini incorporate

```bash
noesis-pdf-reader-lite-engine libro.pdf --no-images -o libro_solo_testo.md
```

### Forzare la pipeline classica (debug/confronto)

```bash
noesis-pdf-reader-lite-engine libro.pdf --pipeline current -o confronto.md
```

### Riepilogo leggibile da un altro programma (JSON)

```bash
noesis-pdf-reader-lite-engine libro.pdf --pages 1-5 --json -o out.md
```

---

## Riferimento delle opzioni

| Opzione | Valori | Default | Descrizione |
|---|---|---|---|
| `pdf` *(posizionale)* | percorso | — | Il PDF di input (obbligatorio, **opzionale con `-gui`**). |
| `--pages SPEC` | `all`, `7`, `100-103`, `1,3,5-7` | `all` | Pagine da elaborare (1-based). Gli spazi sono ignorati; gli estremi invertiti sono accettati. |
| `--content` | `original` · `translated` · `both` | `original` | Cosa esportare. |
| `--engine` | `google` · `microsoft` | `google` | Motore di traduzione. |
| `--src LANG` | codice lingua o `auto` | `auto` | Lingua di origine. |
| `--dst LANG` | codice lingua | `it` | Lingua di destinazione. |
| `--translate-missing` / `--no-translate-missing` | flag | attivo | Traduce le pagine senza traduzione in cache. |
| `--images` / `--no-images` | flag | attivo | Mantiene (o rimuove) le immagini incorporate nel Markdown. |
| `--format` | `merged` · `zip` · `folder` · `vault` | `merged` | Impacchettamento dell'output. |
| `--content-format` | `markdown` · `html` · `text` · `epub` · `docx` · `odt` · `rtf` · `latex` | `markdown` | Formato del contenuto (conversione del Markdown). |
| `--pandoc PATH` | percorso | `$PATH` | Eseguibile pandoc per `docx`/`odt`/`rtf`/`latex`. |
| `-o`, `--out PATH` | percorso | cartella corrente | File (merged/zip) o cartella (folder/vault). |
| `--name NAME` | nome | nome del PDF | Nome del contenitore di output. |
| `--ocr-lang LANG` | es. `eng+ita` | derivato da `--src` | Lingua/e Tesseract per l'OCR. |
| `--tessdata DIR` | percorso | — | Cartella `tessdata` per l'OCR (imposta `TESSDATA_PREFIX`). |
| `--pipeline` | `ir` · `current` | `ir` | Pipeline di estrazione (`current` è la classica/di confronto). |
| `-gui`, `--gui` | flag | off | Apre il **wizard TUI** interattivo (file picker, mouse). |
| `--tui-theme` | `auto` · `dark` · `light` | `auto` | Tema della TUI. |
| `--tui-lang` | `it` · `en` | dal config | Lingua dell'interfaccia TUI. |
| `--ascii` | flag | off | Forza ASCII nella TUI (niente emoji / box drawing). |
| `--json` | flag | off | Stampa un riepilogo JSON su stdout. |
| `--dry-run` | flag | off | **Simulazione**: mostra i file che verrebbero creati, senza estrarre né tradurre. |
| `-q`, `--quiet` | flag | off | Nessun progresso. |
| `-v`, `--verbose` | flag | off | Output più dettagliato. |
| `--version` | flag | — | Stampa la versione. |

**Codici di uscita:** `0` = tutto ok · `1` = almeno una pagina è fallita ·
`2` = errore di input (file mancante, `--pages` non valido, PDF illeggibile).

---

## Wizard interattivo (`-gui`)

Se preferisci un'interfaccia guidata alla riga di comando, lancia la **TUI**:

```bash
noesis-pdf-reader-lite-engine -gui
```

Si apre un wizard a **5 passi** identico per opzioni a quello dell'app desktop:

1. **File e pagine** — *file picker* per il PDF (con filtro `*.pdf`) e scelta
   pagine: *tutte* / *intervallo* / *libera* (`1,3,7-9`).
2. **Contenuto** — originale / traduzione / entrambi, figure incluse, traduci-mancanti.
3. **Lingue e motore** — origine (`Auto`), destinazione, Google/Microsoft e
   (novità della CLI) lingua OCR e cartella `tessdata`.
4. **Output** — *formato contenuto* × *impacchettamento* (le combinazioni non
   valide sono disattivate), cartella di destinazione col *file picker* e nome file.
5. **Riepilogo** — tutte le scelte e **l'elenco dei file che verranno creati**;
   poi parte l'esportazione con barra di avanzamento e log per pagina.

**Mouse e tastiera.** Clic, rotella e doppio clic funzionano quando il terminale
li supporta; da tastiera: `Tab`/frecce per il focus, `Invio`/`Spazio` per
attivare, `1-5` per saltare a un passo, `b`/`n` indietro/avanti, `Ctrl+R` per
eseguire, `a` per ASCII, `l` per la lingua, `t` per il tema, `?` per l'aiuto,
`q`/`Esc` per uscire.

**Compatibilità.** Se il terminale non può ospitare la TUI (`TERM=dumb`, nessun
TTY, Textual non installato) il comando **non fallisce**: ripiega su un wizard a
righe che usa solo `input()`. Per la TUI moderna installa l'extra:

```bash
pip install -r requirements-tui.txt     # oppure: pip install .[tui]
```

Esempi:

```bash
noesis-pdf-reader-lite-engine -gui                              # parte dal file picker
noesis-pdf-reader-lite-engine -gui libro.pdf --dst en           # precompila il wizard
noesis-pdf-reader-lite-engine -gui libro.pdf -o out/ --format zip
noesis-pdf-reader-lite-engine -gui --ascii                      # terminali senza UTF-8
```

> Le scelte dell'ultima sessione vengono ricordate in
> `~/.config/noesis-pdf-reader-lite-engine/tui.json`.

---

## Formati di output

Il **nome dei file di contenuto** segue una regola precisa: i file tradotti
portano il suffisso **`-translated`**.

| `--content` | File per pagina |
|---|---|
| `original` | `{nome-pdf}_pagNNNN.md` |
| `translated` | `{nome-pdf}_pagNNNN-translated.md` |
| `both` | **due** file per pagina: `{nome-pdf}_pagNNNN.md` **+** `{nome-pdf}_pagNNNN-translated.md` |

`NNNN` è il numero di pagina **1-based** su 4 cifre (es. `harrison2025_pag0007-translated.md`).

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

Il file è `<name>.md`; con `--content translated` diventa
`<name>-translated.md` (anche se hai scelto un `--name` esplicito). Con
`--content both` si producono **due** file: `<name>.md` (originale) e
`<name>-translated.md` (traduzione).

### `zip` — un file per pagina, dentro uno ZIP

```bash
noesis-pdf-reader-lite-engine tesi.pdf --format zip -o tesi.zip
# tesi.zip contiene: tesi_pag0001.md, tesi_pag0002.md, …
# con --content translated: tesi_pag0001-translated.md, …
```

### `folder` — un file per pagina, in una cartella

```bash
noesis-pdf-reader-lite-engine tesi.pdf --format folder --out pagine/
# pagine/tesi_pag0001.md, pagine/tesi_pag0002.md, …
```

### `vault` — cartella con indice e front-matter

Come `folder`, ma aggiunge un **`index.md`** (TOC con i link alle pagine) e, per
il formato Markdown, un **front-matter YAML** in ogni pagina (compatibile
Obsidian/LogSeq):

```bash
noesis-pdf-reader-lite-engine tesi.pdf --format vault --out tesi/
# tesi/index.md, tesi/tesi_pag0001.md, tesi/tesi_pag0002.md, …
```

### Formato del contenuto (`--content-format`)

Il Markdown estratto può essere convertito al volo:

| `--content-format` | Estensione | Motore |
|---|---|---|
| `markdown` (default) | `.md` | — (identità) |
| `html` | `.html` | HTML autonomo (figure in base64) |
| `text` | `.txt` | testo semplice (markdown rimosso) |
| `epub` | `.epub` | EPUB 3 nativo (solo `merged`) |
| `docx` · `odt` · `rtf` · `latex` | `.docx` · `.odt` · `.rtf` · `.tex` | **pandoc** (richiesto) |

```bash
noesis-pdf-reader-lite-engine libro.pdf --content-format html -o libro.html
noesis-pdf-reader-lite-engine libro.pdf --content-format epub -o libro.epub
noesis-pdf-reader-lite-engine libro.pdf --content-format docx -o libro.docx   # richiede pandoc
```

> Le combinazioni valide: `epub` solo con `--format merged`; i formati pandoc
> (`docx`/`odt`/`rtf`/`latex`) con `merged`/`zip`/`folder`; `markdown`/`html`/
> `text` con tutti. Una combinazione non valida esce con codice `2`.

> L'archivio ZIP e la cartella mantengono il **nome scelto** (`--name`): il
> suffisso `-translated` è solo sui **file di contenuto**. I file interni si
> chiamano sempre `<nome-pdf>_pagNNNN[-translated].<ext>`.

**Dettaglio importante:** in ogni corpo il *header di estrazione* viene rimosso
(come nell'export dell'app desktop), quindi il Markdown esportato è "pulito".
Con `--no-images` i riferimenti immagine Markdown vengono eliminati.

### Simulare prima di esportare

Con `--dry-run` vedi **esattamente** quali file verrebbero creati, senza
estrarre né tradurre (nessuna rete):

```bash
noesis-pdf-reader-lite-engine libro.pdf --pages 1-3 --content both --format folder --dry-run
```

```text
noesis-pdf-reader-lite-engine — dry run (nessuna estrazione)
  input    : /percorso/libro.pdf
  pages    : 1-3  (3)
  content  : both
  format   : folder
  cartella : /percorso/out
    - libro_pag0001.md   [original]
    - libro_pag0001-translated.md   [translated]
    - libro_pag0002.md   [original]
    - libro_pag0002-translated.md   [translated]
    - libro_pag0003.md   [original]
    - libro_pag0003-translated.md   [translated]
```

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
noesis-pdf-reader-lite-engine doc.pdf --content translated

# da inglese a tedesco con Microsoft
noesis-pdf-reader-lite-engine doc.pdf --content translated --src en --dst de --engine microsoft
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
noesis-pdf-reader-lite-engine scansione.pdf --content original --ocr-lang eng+ita

# cartella tessdata personalizzata
noesis-pdf-reader-lite-engine scansione.pdf --ocr-lang eng --tessdata /percorso/tessdata
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

| Aspetto | App desktop | CLI `noesis-pdf-reader-lite-engine` |
|---|---|---|
| Interfaccia | GUI (PyQt6) | Riga di comando · wizard TUI opzionale (`-gui`) |
| Contenuto di default | `translated` | `original` (nessuna rete) |
| Pagine di default | pagina corrente | `all` |
| Zone manuali (escludi/includi) | sì, disegnate a mano | **no** (solo pipeline automatica) |
| Cattura oggetti / reader / tema | sì | no |
| Cache di traduzione su disco | sì | no |
| Opzioni di esportazione | selezione pagine, contenuto, lingue/motore, traduci-mancanti, figure, merged/zip/cartella | **le stesse** |
| Composizione dell'output | header rimosso, `<!-- pagina N -->`, `---`, nomi `*_pagNNNN[-translated].md`, split di `both` | **identica** |

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

Il wizard `-gui` è composto da moduli **solo front-end** (non rigenerati, non
verbatim), che si limitano a comporre le stesse chiamate della CLI:

```
tui.py          · app Textual (passi, file picker, progress)
tui_launch.py   · scelta fra TUI moderna e fallback a righe
tui_state.py    · stato/validazione puri + esecuzione (riusa export_core)
tui_i18n.py     · stringhe della TUI + probe del terminale
tui_fallback.py · wizard a righe per terminali senza Textual
```

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
- **test del wizard `-gui`**: logica pura (`tests/test_tui_state.py`), fallback a
  righe, wiring della CLI e widget Textual (`tests/test_tui_gui.py`; i test dei
  widget si saltano da soli se Textual non è installato);
- **parità di sorgente** con il checkout desktop (`tests/test_sync_parity.py`,
  si salta se il repo desktop non è presente);
- i **test del motore** portati dal repository desktop (i casi che richiedono il
  corpus reale si saltano da soli se i PDF non ci sono).

La CI (`.github/workflows/tests.yml`) gira **headless, senza Qt e senza TTY**, su
ogni push e PR: installa PyMuPDF, PyMuPDF4LLM, Tesseract e Textual ed esegue
l'intera suite.

---

## Licenza

Nessuna licenza esplicita (come il repository desktop di riferimento). Contatta
l'autore per l'uso.
