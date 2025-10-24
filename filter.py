import pandas as pd
import os
import argparse

def _letters_only(s: str) -> str:
    try:
        return "".join(ch for ch in str(s) if str(ch).isalpha())
    except Exception:
        return ""

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

    df = df.copy()
    df['_orig_idx'] = df.index

    group_cols = [c for c in ['id', 'listnum', 'category'] if c in df.columns]
    for _, g in df.groupby(group_cols, sort=False):
        category = str(g['category'].iloc[0]) if 'category' in g.columns else ''
        allowed = allowed_map.get(category, set())
        if not allowed:
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

def merge_and_validate_rows(input_file, category_dir, output_file, *, min_ot_run: int = 3, apply_ot_filter: bool = True):

    data = pd.read_csv(input_file)
    initial_unique_ids = None
    if 'id' in data.columns:
        try:
            initial_unique_ids = data['id'].astype(str).nunique(dropna=True)
        except Exception:
            initial_unique_ids = None
    merged_data = []

    i = 0
    while i < len(data):
        row = data.iloc[i].copy()

        if i + 1 < len(data):
            merged_item_2 = (
                str(data.iloc[i]['item']) +
                str(data.iloc[i + 1]['item'])
            ).replace("'", "").replace(" ", "")

            category_file = os.path.join(category_dir, f"{row['category']}.csv")
            if os.path.exists(category_file):
                try:
                    category_data = pd.read_csv(category_file, header=None, usecols=[1])
                except Exception as e:
                    print(f"Errore durante il caricamento di {category_file}: {e}")
                    continue

                if merged_item_2 in category_data.iloc[:, 0].values:
                    row['item'] = merged_item_2
                    merged_data.append(row)
                    i += 2  
                    continue

        if i + 2 < len(data):
            merged_item_3 = (
                str(data.iloc[i]['item']) +
                str(data.iloc[i + 1]['item']) +
                str(data.iloc[i + 2]['item'])
            ).replace("'", "").replace(" ", "")

            if os.path.exists(category_file):
                try:
                    category_data = pd.read_csv(category_file, header=None, usecols=[1])
                except Exception as e:
                    print(f"Errore durante il caricamento di {category_file}: {e}")
                    continue

                if merged_item_3 in category_data.iloc[:, 0].values:
                    row['item'] = merged_item_3
                    merged_data.append(row)
                    i += 3  
                    continue

        merged_data.append(row)
        i += 1

    merged_df = pd.DataFrame(merged_data)

    if apply_ot_filter:
        try:
            merged_df = _remove_consecutive_ot_runs(merged_df, category_dir, min_run=min_ot_run)
        except Exception as e:
            print(f"[WARN] Filtraggio OT non applicato per errore: {e}")

    # Normalizza item: rimuove apici/spazi, tiene solo caratteri alfabetici
    # e rimuove le righe con item vuoto/non alfabetico
    if not merged_df.empty and 'item' in merged_df.columns:
        before_rows = len(merged_df)
        items = (
            merged_df['item']
            .fillna('')
            .astype(str)
            .str.strip()
            .str.replace("'", "", regex=False)
        )
        letters = items.map(_letters_only)
        mask_nonempty = letters.str.len() > 0
        removed = int((~mask_nonempty).sum())
        merged_df = merged_df.loc[mask_nonempty, :].copy()
        merged_df.loc[:, 'item'] = letters[mask_nonempty].values
        if removed > 0:
            print(f"[sanitize] Rimosse {removed} righe con item vuoto/non alfabetico")

    merged_df.to_csv(output_file, index=False)
    print(f"File salvato con successo in: {output_file}")
    if 'id' in merged_df.columns:
        try:
            n_ids = merged_df['id'].astype(str).nunique(dropna=True)
            if initial_unique_ids is not None:
                print(f"ID unici iniziali: {initial_unique_ids}")
            print(f"ID unici nel file finale: {n_ids}")
        except Exception:
            pass


def _parse_args():
    p = argparse.ArgumentParser(description="Unisci/valida dati SNAFU e applica filtro OT opzionale")
    p.add_argument("--input", "-i", default="fluency_data/snafu.csv", help="CSV di input con colonne id,listnum,category,item,rt")
    p.add_argument("--schemes", "-s", default="schemes/", help="Directory degli schemi di categoria (file <categoria>.csv)")
    p.add_argument("--output", "-o", default="fluency_data/filtered_snafu.csv", help="CSV di output filtrato")
    p.add_argument("--min-ot-run", type=int, default=3, help="Lunghezza minima della sequenza OT consecutiva da rimuovere")
    p.add_argument("--no-ot-filter", action="store_true", help="Disattiva il filtro OT")
    return p.parse_args()


def main():
    args = _parse_args()
    merge_and_validate_rows(
        args.input,
        args.schemes,
        args.output,
        min_ot_run=max(1, args.min_ot_run),
        apply_ot_filter=(not args.no_ot_filter),
    )


if __name__ == "__main__":
    main()
