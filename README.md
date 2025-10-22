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
   pip install -r requirements.txt
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

## Dati e privacy
La repo elabora i file inclusi nella cartella `fluency_data/`. Assicurati di avere i diritti per trattare i dati.

***
Per dubbi o problemi, apri una issue o contatta il maintainer.
***
