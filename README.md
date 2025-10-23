# SNAFU Test — Guida Rapida (Windows)

Questa repo analizza liste di fluenza semantica con la libreria SNAFU e genera:
- metriche psicometriche per soggetto e categoria
- reti semantiche di gruppo con relative metriche
- grafici riassuntivi delle reti e delle metriche

Tutte le istruzioni sono pensate per chi non ha mai usato Python o Visual Studio/VS Code.

## Requisiti
- Windows 10/11
- Connessione Internet (per installare Python e i pacchetti)
- PowerShell (preinstallato in Windows)
- Facoltativo: winget (di solito preinstallato in Windows 11)

## Installazione AUTOMATICA (consigliata)
1) Apri PowerShell nella cartella del progetto (Shift + tasto destro → "Apri PowerShell qui").
2) Consenti l'esecuzione temporanea degli script solo per questa sessione:
   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
   ```
3) Esegui lo script di setup:
   ```powershell
   .\SETUP_WINDOWS.ps1
   ```
   Opzioni utili (facoltative):
   - Installa Visual Studio Code: ` .\SETUP_WINDOWS.ps1 -InstallVSCode `
   - Installa Visual Studio 2022 Community: ` .\SETUP_WINDOWS.ps1 -InstallVisualStudio `
   - Installa snafu da GitHub (se non è su PyPI): ` .\SETUP_WINDOWS.ps1 -SnafuGitUrl "git+https://github.com/<organizzazione>/<repo-snafu>.git" `

Cosa fa lo script:
- verifica/installa Python (via winget se necessario)
- crea l'ambiente virtuale `.venv`
- installa i pacchetti da `requirements.txt`
- esegue l'analisi (`analyze_snafu.py`) e genera i grafici (`plot_snafu_results.py`)
- salva gli output nella cartella `results/`

## Ri-esecuzione (dopo il primo setup)
Se hai già eseguito il setup una volta e vuoi rigenerare i risultati:
```powershell
.\.venv\Scripts\Activate.ps1
python analyze_snafu.py
python plot_snafu_results.py
```

## Installazione MANUALE (alternativa)
Se `winget` non è disponibile o preferisci i passaggi manuali:
1) Installa Python 3.x da https://www.python.org/downloads/ e attiva la casella "Add Python to PATH".
2) In PowerShell, dentro la cartella del progetto:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip setuptools wheel
   # Tentativo 1: tutti i requisiti
   pip install -r requirements.txt
   # Se fallisce su "snafu", alternativa:
   pip install numpy pandas networkx matplotlib
   pip install snafu
   ```
3) Lancia gli script:
   ```powershell
   python analyze_snafu.py
   python plot_snafu_results.py
   ```

## Output generati (cartella `results/`)
- `psychometrics.csv` — metriche per soggetto e categoria:
  - cluster_switch_* (static/fluid), switch_rate_static
  - cluster_size_* (static/fluid)
  - perseverations/intrusions (conteggi) e relative liste di parole
  - avg_word_frequency (SUBTLEX) e avg_aoa (età di acquisizione)
- `network_metrics.csv` — metriche della rete per categoria e metodo:
  - nodes, edges, density, average_clustering, average_neighbor_degree
  - largest_component_density, largest_component_average_shortest_path, largest_component_diameter
- `networks/*.csv` — liste di archi per ciascuna combinazione categoria/metodo
- `figures/*.png` — grafici riassuntivi e visualizzazioni delle reti
  - Nuovi grafici ispirati al paper SNAFU:
    - `degree_dist_<categoria>.png` — distribuzione dei gradi per metodo
    - `smallworld_summary.png` — coefficiente small‑world per metodo/categoria
    - `irt_hist_<categoria>.png` e `irt_position_<categoria>.png` — distribuzione IRT e IRT medio per posizione

## Novità principali (tooling e CLI)
- `keep_columns.py`: filtra per `--id-prefix`/`--id-suffix`; integrazione filtro pazienti `--patient-csv` + `--study-id`; genera dataset aggiuntivi maschi/femmine; output sempre quotato.
- `filter.py`: ora ha CLI; rimuove run OT con `--min-ot-run` (o disattiva con `--no-ot-filter`).
- `analyze_snafu.py`: CLI completa (percorsi, categorie, parametri Conceptual Network, `--force-merge`, `--skip-*`).
- `plot_snafu_results.py`: figure più ampie e layout meno denso; opzioni `PLOT_CFG` per GCC/k‑core/etichette; nuovi grafici (gradi, small‑world, IRT) e lettura CSV robusta a encoding.
- Pipeline esempi: `pnrr_test.py` (Python) e `pnrr_test.ps1` (PowerShell). Guida: `PNRR_TEST.md`.

## Pipeline PNRR (consigliata)
- Opzione Python (import diretto dei moduli):
  - `py pnrr_test.py --raw "fluency_data\Snafu_2025-10-22_10-02-58.csv" --patients "fluency_data\patients.csv" --study-id PNRR --id-prefix PNRR --categories animali frutta verdura`
- Opzione PowerShell (script):
  - `.\pnrr_test.ps1 -Raw "fluency_data\Snafu_2025-10-22_10-02-58.csv" -Patients "fluency_data\patients.csv" -StudyId PNRR -IdPrefix PNRR -MinOTRun 3 -Categories animali,frutta,verdura`

## Esempi CLI per singolo step
- `keep_columns.py` (standardizza e filtra):
  - `python keep_columns.py input.csv -o fluency_data\snafu.csv --id-prefix PNRR --patient-csv fluency_data\patients.csv --study-id PNRR`
  - Aggiungi `--output-male ... --output-female ...` per gli split di genere; `--sep ";"` se usa `;`.
- `filter.py` (merge + OT):
  - `py filter.py --input fluency_data\snafu.csv --schemes schemes --output fluency_data\filtered_snafu.csv --min-ot-run 3`
- `analyze_snafu.py` (analisi):
  - `py analyze_snafu.py --filtered-file fluency_data\filtered_snafu.csv --scheme-dir schemes --results-dir results`
  - Con categorie: `--categories animali frutta verdura`
  - Parametri CN: `--cn-alpha 0.01 --cn-window 3 --cn-threshold 3`
- `plot_snafu_results.py` (grafici):
  - `py plot_snafu_results.py` (usa `PLOT_CFG` interno per ridurre l’affollamento)

## Note utili
- Encoding: i CSV delle reti sono letti in modo robusto (utf‑8‑sig/utf‑8/cp1252/latin1). Se un grafico resta vuoto, rigenera le reti con `analyze_snafu.py` e riprova.
- SNAFU opzionale nei grafici: small‑world e IRT vengono saltati se `snafu` non è disponibile; gli altri grafici si generano comunque.

## Uso con Visual Studio Code (facoltativo)
- Installa VS Code (puoi usare `-InstallVSCode` nello script o scaricarlo dal sito).
- Apri la cartella del progetto in VS Code (File → Apri cartella).
- In basso a destra seleziona l'interprete Python della cartella `.venv`.
- Terminale → Nuovo terminale, poi:
  ```powershell
  .\.venv\Scripts\Activate.ps1
  python analyze_snafu.py
  python plot_snafu_results.py
  ```

## Risoluzione problemi
- Errore di esecuzione script (ExecutionPolicy): usa il comando indicato sopra per la sola sessione.
- `winget` non trovato: installa Python manualmente (sezione precedente).
- Errore durante `pip install` su `snafu`: verifica la connessione Internet e riprova. Se persiste, apri un issue con il log dell'errore.
- `python` non riconosciuto: chiudi e riapri PowerShell dopo l'installazione, oppure usa `py` al posto di `python`.

### Se `snafu` non è disponibile
- Lo script di setup prova ad installarlo automaticamente; se fallisce, lo segnala ma completa l'installazione dei pacchetti base. Puoi passare direttamente l'URL git: `-SnafuGitUrl "git+https://github.com/<organizzazione>/<repo-snafu>.git"`.
- Per usare tutte le funzionalità devi installare `snafu`. Opzioni:
  - Se è su PyPI: `pip install snafu`
  - Se è solo su GitHub: `pip install git+https://github.com/<organizzazione>/<repo-snafu>.git`
  - Con conda (se disponibile in un canale): `conda install -c conda-forge snafu`
- Senza `snafu` non puoi generare i CSV in `results/`. Se possiedi già `results/psychometrics.csv` e `results/network_metrics.csv`, puoi comunque eseguire:
  ```powershell
  .\.venv\Scripts\Activate.ps1
  python plot_snafu_results.py
  ```

## Dati e privacy
La repo elabora i file inclusi nella cartella `fluency_data/`. Assicurati di avere i diritti per trattare i dati.

***
Per dubbi o problemi, apri una issue o contatta il maintainer.
***
