import pandas as pd
import os

def _load_allowed_items(category_dir: str) -> dict:
    """Carica per ciascuna categoria l'insieme di item validi dallo schema.

    Legge i file `<categoria>.csv` presenti in `category_dir` assumendo
    due colonne (cluster, item). Gli item vengono normalizzati in
    minuscolo senza spazi né apostrofi per un confronto robusto.
    """
    allowed: dict[str, set[str]] = {}
    for fname in os.listdir(category_dir):
        if not fname.endswith('.csv'):
            continue
        category = os.path.splitext(fname)[0]
        path = os.path.join(category_dir, fname)
        try:
            data = pd.read_csv(path, header=None, usecols=[1], encoding='utf-8-sig')
            items = (
                data.iloc[:, 0]
                .astype(str)
                .str.lower()
                .str.replace(" ", "", regex=False)
                .str.replace("'", "", regex=False)
            )
            allowed[category] = set(items.tolist())
        except Exception:
            # Se uno schema non è leggibile, proseguiamo senza bloccare l'intero processo
            continue
    return allowed


def _normalize_item(val: str) -> str:
    return str(val).lower().replace(" ", "").replace("'", "")


def _remove_consecutive_ot_runs(df: pd.DataFrame, category_dir: str, min_run: int = 3) -> pd.DataFrame:
    """Rimuove sequenze consecutive (lunghezza >= min_run) di item fuori categoria.

    Per ogni gruppo (id, listnum, category), se esiste una sottosequenza di
    item non presenti nello schema della categoria di lunghezza almeno `min_run`,
    quelle righe vengono eliminate dal DataFrame.
    """
    if df.empty or 'category' not in df.columns or 'item' not in df.columns:
        return df

    allowed_map = _load_allowed_items(category_dir)
    to_drop: list[int] = []

    # Mantieni l'ordine originale per ogni gruppo usando l'indice
    df = df.copy()
    df['_orig_idx'] = df.index

    group_cols = [c for c in ['id', 'listnum', 'category'] if c in df.columns]
    for _, g in df.groupby(group_cols, sort=False):
        category = str(g['category'].iloc[0]) if 'category' in g.columns else ''
        allowed = allowed_map.get(category, set())
        if not allowed:
            # Se non abbiamo lo schema, non applichiamo il filtro a questo gruppo
            continue
        items = g['item'].astype(str).map(_normalize_item).tolist()
        idxs = g['_orig_idx'].tolist()

        run_start = None
        for i, it in enumerate(items + ['__END__']):
            is_ot = (i < len(items)) and (it not in allowed)
            if is_ot:
                if run_start is None:
                    run_start = i
            if (not is_ot) or i == len(items):
                if run_start is not None:
                    run_len = i - run_start
                    if run_len >= min_run:
                        to_drop.extend(idxs[run_start:i])
                    run_start = None

    if to_drop:
        df = df[~df['_orig_idx'].isin(to_drop)].copy()
        print(f"[ot-filter] Rimosse {len(to_drop)} righe con sequenze OT (>= {min_run})")
    df.drop(columns=['_orig_idx'], inplace=True, errors='ignore')
    return df

def merge_and_validate_rows(input_file, category_dir, output_file):
    # Caricare il file principale
    data = pd.read_csv(input_file)

    # Preparare un nuovo DataFrame per il risultato
    merged_data = []

    i = 0
    while i < len(data):
        row = data.iloc[i]

        # Unire l'item corrente con l'item successivo
        if i + 1 < len(data):
            merged_item_2 = (
                str(data.iloc[i]['item']) +
                str(data.iloc[i + 1]['item'])
            ).replace("'", "").replace(" ", "")

            # Controllare il file della categoria corrispondente
            category_file = os.path.join(category_dir, f"{row['category']}.csv")
            if os.path.exists(category_file):
                try:
                    # Caricare solo la seconda colonna
                    category_data = pd.read_csv(category_file, header=None, usecols=[1])
                except Exception as e:
                    print(f"Errore durante il caricamento di {category_file}: {e}")
                    continue

                # Controllare se l'item unito esiste nella seconda colonna
                if merged_item_2 in category_data.iloc[:, 0].values:
                    # Sostituire i due item con l'unione
                    row['item'] = merged_item_2
                    merged_data.append(row)
                    i += 2  # Saltare la riga successiva
                    continue

        # Unire l'item corrente con i due successivi
        if i + 2 < len(data):
            merged_item_3 = (
                str(data.iloc[i]['item']) +
                str(data.iloc[i + 1]['item']) +
                str(data.iloc[i + 2]['item'])
            ).replace("'", "").replace(" ", "")

            # Controllare il file della categoria corrispondente
            if os.path.exists(category_file):
                try:
                    # Caricare solo la seconda colonna
                    category_data = pd.read_csv(category_file, header=None, usecols=[1])
                except Exception as e:
                    print(f"Errore durante il caricamento di {category_file}: {e}")
                    continue

                # Controllare se l'item unito esiste nella seconda colonna
                if merged_item_3 in category_data.iloc[:, 0].values:
                    # Sostituire i tre item con l'unione
                    row['item'] = merged_item_3
                    merged_data.append(row)
                    i += 3  # Saltare le due righe successive
                    continue

        # Aggiungere la riga corrente senza modifiche
        merged_data.append(row)
        i += 1

    # Creare un nuovo DataFrame con i dati uniti
    merged_df = pd.DataFrame(merged_data)

    # Applicare il filtro OT: rimuove sequenze di 3+ item fuori categoria consecutivi
    try:
        merged_df = _remove_consecutive_ot_runs(merged_df, category_dir, min_run=3)
    except Exception as e:
        print(f"[WARN] Filtraggio OT non applicato per errore: {e}")

    # Salvare il risultato in un file CSV
    merged_df.to_csv(output_file, index=False)
    print(f"File salvato con successo in: {output_file}")

# Percorsi

def main():
    input_file = 'fluency_data/snafu_study_male.csv'
    category_dir = 'schemes/'  
    output_file = 'fluency_data/filtered_snafu.csv'

    merge_and_validate_rows(input_file, category_dir, output_file)


if __name__ == "__main__":
    main()


