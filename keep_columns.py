"""
Script per filtrare un file CSV mantenendo solo le colonne desiderate.

Conserva esclusivamente le colonne: id, listnum, category, item, rt.
Tutte le altre colonne vengono rimosse. Se una o più colonne tra le 5
non sono presenti nel CSV di ingresso, vengono create vuote per avere
sempre lo stesso schema in uscita.

Filtri opzionali:
- `--id-suffix`: mantieni solo le righe con id che termina con il suffisso
- `--id-prefix`: mantieni solo le righe con id che inizia con il prefisso
- `--patient-csv` + `--study-id [...]`: mantieni solo le righe dei pazienti
  presenti nel file pazienti con uno degli study_id indicati (o esclusi con
  `--invert`). Se disponibile/indicato il genere, genera due dataset
  aggiuntivi con soli maschi e sole femmine.

Uso (PowerShell / cmd):
  python keep_columns.py input.csv -o output.csv --patient-csv patients.csv --study-id A B

Opzioni principali:
  -o, --output   Percorso del file CSV di output. Se non fornito,
                 il file viene salvato accanto all'input con suffisso
                 ".columns.csv".
  --sep          Separatore (default: auto-rilevamento). Esempi: "," oppure ";".
  --encoding     Encoding (default: utf-8-sig).
  --inplace      Sovrascrive il file di ingresso (usa con cautela).
  --id-suffix    Mantiene solo le righe con `id` che termina con il suffisso indicato.
  --id-prefix    Mantiene solo le righe con `id` che inizia con il prefisso indicato.
  --patient-csv  File pazienti per filtrare per study_id.
  --study-id     Uno o più valori di study_id/studio_id da includere (o escludere con --invert).
  --invert       Esclude gli study-id forniti invece di includerli.
  --patient-id-col  Colonna ID nel file pazienti (default: auto id/patient_id/...)
  --study-col       Colonna studio nel file pazienti (default: auto studio_id/study_id)
  --gender-col      Colonna genere nel file pazienti (default: auto gender/sex/sesso/genere)
  --sep-pat         Separatore del file pazienti (default: auto)
  --output-male / --output-female  Output opzionali per dataset maschi/femmine.
  --no-gender-splits  Non generare i dataset per genere.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional, Iterable
import csv

import pandas as pd


ALLOWED_COLUMNS: List[str] = ["id", "listnum", "category", "item", "rt"]


def infer_engine(sep: str | None) -> str:
    # Se non specifichiamo il separatore, usiamo l'engine 'python' che supporta
    # l'auto-detection (sep=None). Altrimenti, restiamo sul default.
    return "python" if sep is None else "c"


def _read_csv_robust(path: Path, sep: Optional[str] = None, prefer_enc: str = "utf-8-sig") -> pd.DataFrame:
    encodings = [prefer_enc, "utf-8", "cp1252", "latin1"]
    for enc in encodings:
        try:
            return pd.read_csv(path, sep=sep, engine=infer_engine(sep), encoding=enc, dtype=str)
        except Exception:
            continue
    return pd.read_csv(path, sep=sep, engine=infer_engine(sep), dtype=str)


def _normcols(df: pd.DataFrame) -> dict:
    return {str(c).strip().lower().lstrip("\ufeff"): c for c in df.columns}


def _norm_gender(v: str) -> Optional[str]:
    s = str(v).strip().lower()
    male_tokens = {"m", "male", "man", "uomo", "maschio", "maschi"}
    female_tokens = {"f", "female", "woman", "donna", "femmina", "femmine"}
    if s in male_tokens:
        return "male"
    if s in female_tokens:
        return "female"
    if s.startswith("m"):
        return "male"
    if s.startswith("f"):
        return "female"
    return None


def keep_only_allowed_columns(
    input_csv: Path,
    output_csv: Path,
    *,
    sep: str | None = None,
    encoding: str = "utf-8-sig",
    id_suffix: str | None = None,
    id_prefix: str | None = None,
    # Filtro per study_id via file pazienti
    patient_csv: Optional[Path] = None,
    study_ids: Optional[Iterable[str]] = None,
    invert: bool = False,
    patient_id_col: Optional[str] = None,
    study_col: Optional[str] = None,
    gender_col: Optional[str] = None,
    sep_pat: Optional[str] = None,
    output_male: Optional[Path] = None,
    output_female: Optional[Path] = None,
    no_gender_splits: bool = False,
) -> None:
    df = pd.read_csv(input_csv, sep=sep, engine=infer_engine(sep), encoding=encoding)

    removed = [c for c in df.columns if c not in ALLOWED_COLUMNS]
    missing = [c for c in ALLOWED_COLUMNS if c not in df.columns]

    # Filtri opzionali su colonna id (se presenti)
    if id_suffix:
        if "id" in df.columns:
            before_rows = len(df)
            df = df[df["id"].astype(str).str.endswith(id_suffix, na=False)].copy()
            print(f"Righe mantenute per suffisso id='{id_suffix}': {len(df)} (filtrate {before_rows - len(df)})")
        else:
            print("[WARN] Filtro --id-suffix ignorato: colonna 'id' assente nel CSV di ingresso")
    if id_prefix:
        if "id" in df.columns:
            before_rows = len(df)
            df = df[df["id"].astype(str).str.startswith(id_prefix, na=False)].copy()
            print(f"Righe mantenute per prefisso id='{id_prefix}': {len(df)} (filtrate {before_rows - len(df)})")
        else:
            print("[WARN] Filtro --id-prefix ignorato: colonna 'id' assente nel CSV di ingresso")

    # Filtro opzionale via file pazienti + study_id
    kept_gender_map = None  # dict id -> gender "male"/"female"
    if patient_csv is not None and study_ids:
        pdf = _read_csv_robust(patient_csv, sep=sep_pat)
        cmap = _normcols(pdf)
        if study_col is None:
            for key in ("studio_id", "study_id"):
                if key in cmap:
                    study_col = cmap[key]
                    break
        else:
            study_col = cmap.get(study_col.lower(), study_col)
        if patient_id_col is None:
            for key in ("id", "patient_id", "subject_id", "participant_id"):
                if key in cmap:
                    patient_id_col = cmap[key]
                    break
        else:
            patient_id_col = cmap.get(patient_id_col.lower(), patient_id_col)
        if gender_col is None:
            for key in ("gender", "sex", "sesso", "genere"):
                if key in cmap:
                    gender_col = cmap[key]
                    break
        else:
            gender_col = cmap.get(gender_col.lower(), gender_col)

        if study_col is None or patient_id_col is None:
            print("[WARN] Colonne study/id non trovate nel file pazienti: filtro study_id ignorato")
        else:
            study_ids = [str(s) for s in study_ids]
            mask = pdf[study_col].astype(str).isin(study_ids)
            if invert:
                mask = ~mask
            kept_pdf = pdf.loc[mask, :].copy()
            kept_ids = set(kept_pdf[patient_id_col].astype(str).tolist())
            before_rows = len(df)
            if "id" in df.columns:
                df = df[df["id"].astype(str).isin(kept_ids)].copy()
                print(f"Righe mantenute per study_id: {len(df)} (filtrate {before_rows - len(df)})")
            else:
                print("[WARN] Colonna 'id' mancante: impossibile filtrare per study_id")

            # Prepara mappa genere (se disponibile) per eventuali split
            if gender_col and gender_col in kept_pdf.columns:
                kept_pdf["__gender__"] = kept_pdf[gender_col].map(_norm_gender)
                kept_gender_map = {
                    str(row[patient_id_col]): row["__gender__"]
                    for _, row in kept_pdf.iterrows()
                    if row.get("__gender__") in ("male", "female")
                }

    # Aggiunge le colonne mancanti come vuote (NaN) per avere lo schema completo
    for col in missing:
        df[col] = pd.NA

    # Seleziona e ordina le colonne finali secondo ALLOWED_COLUMNS
    df_out = df[ALLOWED_COLUMNS]
    # Scrive il CSV quotando SEMPRE sia header che dati, così rimangono le ""
    # attorno a colonne e valori indipendentemente dal contenuto.
    df_out.to_csv(
        output_csv,
        index=False,
        encoding=encoding,
        sep=("," if sep is None else sep),
        quoting=csv.QUOTE_ALL,
        quotechar='"',
    )

    # Messaggi riassuntivi
    print(f"Salvato: {output_csv}")
    if removed:
        print(f"Colonne rimosse ({len(removed)}): {', '.join(removed)}")
    if missing:
        print(f"Colonne aggiunte come vuote ({len(missing)}): {', '.join(missing)}")

    # Split per genere (opzionale)
    if (not no_gender_splits) and kept_gender_map and "id" in df_out.columns:
        male_ids = {pid for pid, g in kept_gender_map.items() if g == "male"}
        female_ids = {pid for pid, g in kept_gender_map.items() if g == "female"}
        if output_male is None:
            output_male = output_csv.with_name(output_csv.stem + "_male" + output_csv.suffix)
        if output_female is None:
            output_female = output_csv.with_name(output_csv.stem + "_female" + output_csv.suffix)

        if male_ids:
            d_m = df_out[df_out["id"].astype(str).isin(male_ids)].copy()
            d_m.to_csv(
                output_male,
                index=False,
                encoding=encoding,
                sep=("," if sep is None else sep),
                quoting=csv.QUOTE_ALL,
                quotechar='"',
            )
            print(f"[gender] Salvato dataset maschi: {output_male} (righe={len(d_m)})")
        if female_ids:
            d_f = df_out[df_out["id"].astype(str).isin(female_ids)].copy()
            d_f.to_csv(
                output_female,
                index=False,
                encoding=encoding,
                sep=("," if sep is None else sep),
                quoting=csv.QUOTE_ALL,
                quotechar='"',
            )
            print(f"[gender] Salvato dataset femmine: {output_female} (righe={len(d_f)})")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Mantieni solo le colonne id,listnum,category,item,rt in un CSV")
    p.add_argument("input", type=Path, help="CSV di ingresso")
    p.add_argument("-o", "--output", type=Path, default=None, help="CSV di uscita (default: <input>.columns.csv)")
    p.add_argument("--sep", type=str, default=None, help="Separatore (es. ',' oppure ';'). Se assente: auto-rilevamento")
    p.add_argument("--encoding", type=str, default="utf-8-sig", help="Encoding (default: utf-8-sig)")
    p.add_argument("--inplace", action="store_true", help="Sovrascrive il file di ingresso")
    p.add_argument("--id-suffix", dest="id_suffix", type=str, default=None, help="Mantiene solo righe con id che termina con questo suffisso")
    p.add_argument("--id-prefix", dest="id_prefix", type=str, default=None, help="Mantiene solo righe con id che inizia con questo prefisso")
    # Opzioni filtro pazienti/studio
    p.add_argument("--patient-csv", type=Path, default=None, help="CSV dei pazienti per filtro study_id")
    p.add_argument("--study-id", nargs="+", default=None, help="Uno o più valori di studio_id/study_id da includere")
    p.add_argument("--invert", action="store_true", help="Esclude gli study-id specificati")
    p.add_argument("--patient-id-col", type=str, default=None, help="Colonna ID nel CSV pazienti (default: auto)")
    p.add_argument("--study-col", type=str, default=None, help="Colonna study nel CSV pazienti (default: auto)")
    p.add_argument("--gender-col", type=str, default=None, help="Colonna genere nel CSV pazienti (default: auto)")
    p.add_argument("--sep-pat", dest="sep_pat", type=str, default=None, help="Separatore del CSV pazienti (default: auto)")
    p.add_argument("--output-male", type=Path, default=None, help="Percorso CSV solo maschi")
    p.add_argument("--output-female", type=Path, default=None, help="Percorso CSV solo femmine")
    p.add_argument("--no-gender-splits", action="store_true", help="Non generare dataset per genere")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    input_csv: Path = args.input
    if not input_csv.exists():
        raise SystemExit(f"File non trovato: {input_csv}")

    if args.inplace and args.output is not None:
        raise SystemExit("Specifica solo --inplace oppure -o/--output, non entrambi.")

    if args.inplace:
        output_csv = input_csv
    else:
        output_csv = args.output or input_csv.with_suffix(input_csv.suffix + ".columns.csv")

    keep_only_allowed_columns(
        input_csv,
        output_csv,
        sep=args.sep,
        encoding=args.encoding,
        id_suffix=args.id_suffix,
        id_prefix=args.id_prefix,
        patient_csv=args.patient_csv,
        study_ids=args.study_id,
        invert=args.invert,
        patient_id_col=args.patient_id_col,
        study_col=args.study_col,
        gender_col=args.gender_col,
        sep_pat=args.sep_pat,
        output_male=args.output_male,
        output_female=args.output_female,
        no_gender_splits=args.no_gender_splits,
    )


if __name__ == "__main__":
    main()
