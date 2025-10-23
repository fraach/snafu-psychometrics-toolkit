# PNRR Test — Esecuzione passo‑passo (Windows)

Questa guida mostra esempi concreti per usare gli strumenti della repo su un dataset PNRR: `keep_columns.py`, `filter.py`, `analyze_snafu.py` e `plot_snafu_results.py`.

## Prerequisiti
- Python 3 installato e raggiungibile da terminale (`py` oppure `python`).
- Ambiente consigliato: esegui una volta `./SETUP_WINDOWS.ps1` per creare `.venv` e installare le dipendenze.

## 1) Standardizza il CSV di partenza (keep_columns)
Mantiene solo le 5 colonne richieste e può filtrare per prefisso/suffisso dell’id, studio_id dal file pazienti, e generare split per genere.

Esempio completo (con file pazienti e split per genere):
```powershell
python keep_columns.py "fluency_data\Snafu_2025-10-22_10-02-58.csv" `
  -o fluency_data\snafu_pnrr.csv `
  --sep ";" `                          # usa se il tuo CSV usa ; come separatore
  --id-prefix PNRR `                    # opzionale: tieni solo id che iniziano con PNRR
  --patient-csv fluency_data\patients.csv `
  --study-id PNRR `                     # uno o più valori; ripeti o separa con spazi
  --output-male  fluency_data\snafu_pnrr_male.csv `
  --output-female fluency_data\snafu_pnrr_female.csv
```
Note:
- Se non vuoi gli split per genere, ometti `--output-male/--output-female` o usa `--no-gender-splits`.
- Se non hai il file pazienti, rimuovi le opzioni `--patient-csv` e `--study-id`.

## 2) Merge + filtro OT (filter.py)
Unisce eventuali token contigui e rimuove sequenze di item fuori categoria (OT) di lunghezza ≥ N.

- Dataset combinato:
```powershell
py filter.py --input fluency_data\snafu_pnrr.csv --schemes schemes `
  --output fluency_data\filtered_snafu.csv --min-ot-run 3
```
- (Opzionale) Solo maschi/femmine (se creati al passo 1):
```powershell
py filter.py -i fluency_data\snafu_pnrr_male.csv   -s schemes -o fluency_data\filtered_snafu_male.csv   --min-ot-run 3
py filter.py -i fluency_data\snafu_pnrr_female.csv -s schemes -o fluency_data\filtered_snafu_female.csv --min-ot-run 3
```

## 3) Analisi (analyze_snafu.py)
Calcola la tabella psicometrica e le reti semantiche. Ora accetta percorsi e categorie da CLI.

- Eseguire analisi standard sui dati filtrati: 
```powershell
py analyze_snafu.py `
  --filtered-file fluency_data\filtered_snafu.csv `
  --scheme-dir schemes `
  --results-dir results
```
- Specificare categorie (altrimenti usa tutti gli schemi trovati in `schemes/`):
```powershell
py analyze_snafu.py --filtered-file fluency_data\filtered_snafu.csv --categories animali frutta verdura
```
- Parametri del metodo Conceptual Network (facoltativo):
```powershell
py analyze_snafu.py --filtered-file fluency_data\filtered_snafu.csv --cn-alpha 0.01 --cn-window 3 --cn-threshold 3
```

(Per ripetere il merge automatico dal raw usa `--force-merge` e imposta `--raw-file`.)

## 4) Grafici (plot_snafu_results.py)
Genera i grafici delle reti e i riassunti. Il layout è già più “spazioso” e le figure si scalano con il numero di nodi.
```powershell
py plot_snafu_results.py
```
Output in `results/figures/`:
- `network_<categoria>_<metodo>.png` (reti)
- `psychometrics_summary.png`, `network_metrics_summary.png`
- `degree_dist_<categoria>.png`, `smallworld_summary.png`
- `irt_hist_<categoria>.png`, `irt_position_<categoria>.png` (se `snafu` disponibile)

## Script rapido (opzionale)
Puoi anche usare lo script `pnrr_test.ps1` per eseguire in un colpo solo i passi 1→4 con i parametri più comuni.

## Troubleshooting
- Errori di encoding su CSV reti: il loader è “robusto” (utf‑8‑sig/utf‑8/cp1252/latin1). Se persiste, rigenera le reti con `analyze_snafu.py`.
- `snafu` mancante: esegui `SETUP_WINDOWS.ps1` oppure `pip install snafu` (o dal repo Git se non su PyPI).
- Grafici densi: in `plot_snafu_results.py` modifica `PLOT_CFG` (k‑core, layout="kamada", max_labels più basso).
