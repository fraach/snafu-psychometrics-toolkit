"""
Filtra il dataset principale in base agli ID paziente selezionati da un file pazienti,
filtrati a loro volta per `studio_id` (o `study_id`).

Uso (esempi PowerShell / cmd):
  # Filtra tenendo solo i pazienti con studio_id A o B e salva un nuovo CSV
  python filter_by_study_id.py \
      --patient-csv fluency_data/patients.csv \
      --study-id A B \
      --data-csv fluency_data/snafu.csv \
      -o fluency_data/snafu_studioAB.csv

  # Stessa cosa ma escludendo A e B
  python filter_by_study_id.py --patient-csv ... --study-id A B --invert -o out.csv

Opzioni principali:
  --patient-csv   CSV con i pazienti (deve contenere colonne id paziente e studio_id/study_id)
  --study-id      Uno o più valori di studio_id da includere (o escludere con --invert)
  --data-csv      CSV completo con tutte le risposte (default: fluency_data/snafu.csv)
  --output / -o   CSV filtrato in output
  --patient-id-col  Nome colonna ID paziente nel file pazienti (default: autodetect/id)
  --study-col       Nome colonna studio (default: autodetect tra studio_id/study_id)
  --data-id-col     Nome colonna ID nel CSV dei dati (default: id)
  --sep-pat / --sep-data  Separatore; se non indicato: auto-rilevamento
  --encoding       Encoding in output (default: utf-8-sig)
  --gender-col     Nome colonna genere nel file pazienti (default: autodetect tra gender/sex/sesso)
  --output-male / --output-female  Percorsi opzionali per dataset solo maschi/femmine.
  --no-gender-splits  Non generare i dataset per genere (per default li genera se la colonna è disponibile).
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Set

import pandas as pd


def _read_csv_robust(path: Path, sep: Optional[str] = None, prefer_enc: str = "utf-8-sig") -> pd.DataFrame:
    encodings = [prefer_enc, "utf-8", "cp1252", "latin1"]
    for enc in encodings:
        try:
            return pd.read_csv(path, sep=sep, engine=("python" if sep is None else "c"), encoding=enc, dtype=str)
        except Exception:
            continue
    # estremo fallback
    return pd.read_csv(path, sep=sep, engine=("python" if sep is None else "c"), dtype=str)


def _norm_cols(df: pd.DataFrame) -> dict:
    return {str(c).strip().lower().lstrip("\ufeff"): c for c in df.columns}


def filter_by_study(
    patient_csv: Path,
    study_ids: Iterable[str],
    *,
    data_csv: Path,
    output_csv: Path,
    patient_id_col: Optional[str] = None,
    study_col: Optional[str] = None,
    data_id_col: str = "id",
    sep_pat: Optional[str] = None,
    sep_data: Optional[str] = None,
    encoding: str = "utf-8-sig",
    invert: bool = False,
    gender_col: Optional[str] = None,
    output_male: Optional[Path] = None,
    output_female: Optional[Path] = None,
    no_gender_splits: bool = False,
) -> None:
    # Carica file pazienti e individua colonne
    pdf = _read_csv_robust(patient_csv, sep=sep_pat)
    cmap = _norm_cols(pdf)
    # Autodetect colonne
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
    # Prova a rilevare la colonna genere
    if gender_col is None:
        for key in ("gender", "sex", "sesso", "genere"):
            if key in cmap:
                gender_col = cmap[key]
                break
    else:
        gender_col = cmap.get(gender_col.lower(), gender_col)

    if study_col is None or patient_id_col is None:
        raise SystemExit("Impossibile determinare le colonne study/id nel file pazienti. Usa --study-col e/o --patient-id-col.")

    study_ids = [str(s) for s in study_ids]
    if not study_ids:
        raise SystemExit("Specifica almeno uno --study-id")

    mask = pdf[study_col].astype(str).isin(study_ids)
    if invert:
        mask = ~mask
    kept_pdf = pdf.loc[mask, :].copy()
    kept_ids = kept_pdf[patient_id_col].astype(str).tolist()
    kept_set: Set[str] = set(kept_ids)
    print(f"[patients] Selezionati {len(kept_set)} pazienti da {patient_csv} (invert={invert})")

    # Carica CSV completo dei dati
    ddf = _read_csv_robust(data_csv, sep=sep_data)
    dmap = _norm_cols(ddf)
    data_id_col = dmap.get(data_id_col.lower(), data_id_col)
    if data_id_col not in ddf.columns:
        raise SystemExit(f"Colonna id '{data_id_col}' non trovata in {data_csv}")

    before = len(ddf)
    ddf = ddf[ddf[data_id_col].astype(str).isin(kept_set)].copy()
    print(f"[data] Righe mantenute: {len(ddf)} (filtrate {before - len(ddf)}) in base agli ID selezionati")

    # Salva mantenendo le virgolette
    ddf.to_csv(
        output_csv,
        index=False,
        encoding=encoding,
        sep=("," if sep_data is None else sep_data),
        quoting=csv.QUOTE_ALL,
        quotechar='"',
    )
    print(f"Salvato: {output_csv}")

    # Suddivisione per genere (se possibile)
    if not no_gender_splits and gender_col and gender_col in kept_pdf.columns:
        def norm_gender(v: str) -> Optional[str]:
            s = str(v).strip().lower()
            # mapping robusto
            male_tokens = {"m", "male", "man", "uomo", "maschio", "maschi"}
            female_tokens = {"f", "female", "woman", "donna", "femmina", "femmine"}
            if s in male_tokens:
                return "male"
            if s in female_tokens:
                return "female"
            # anche valori tipo M/F misti (es. 'M.'), numerici, ecc.
            if s.startswith("m"):
                return "male"
            if s.startswith("f"):
                return "female"
            return None

        kept_pdf["__gender__"] = kept_pdf[gender_col].map(norm_gender)
        male_ids = set(kept_pdf.loc[kept_pdf["__gender__"] == "male", patient_id_col].astype(str).tolist())
        female_ids = set(kept_pdf.loc[kept_pdf["__gender__"] == "female", patient_id_col].astype(str).tolist())

        # Prepara percorsi output
        if output_male is None:
            output_male = output_csv.with_name(output_csv.stem + "_male" + output_csv.suffix)
        if output_female is None:
            output_female = output_csv.with_name(output_csv.stem + "_female" + output_csv.suffix)

        if male_ids:
            d_m = ddf[ddf[data_id_col].astype(str).isin(male_ids)].copy()
            d_m.to_csv(output_male, index=False, encoding=encoding, sep=("," if sep_data is None else sep_data), quoting=csv.QUOTE_ALL, quotechar='"')
            print(f"[gender] Salvato dataset maschi: {output_male} (righe={len(d_m)})")
        else:
            print("[gender] Nessun paziente maschio trovato dopo il filtro studi.")

        if female_ids:
            d_f = ddf[ddf[data_id_col].astype(str).isin(female_ids)].copy()
            d_f.to_csv(output_female, index=False, encoding=encoding, sep=("," if sep_data is None else sep_data), quoting=csv.QUOTE_ALL, quotechar='"')
            print(f"[gender] Salvato dataset femmine: {output_female} (righe={len(d_f)})")
        else:
            print("[gender] Nessun paziente femmina trovato dopo il filtro studi.")
    else:
        if no_gender_splits:
            print("[gender] Split per genere disattivato (--no-gender-splits)")
        else:
            print("[gender] Colonna genere non trovata o non specificata; split non generati.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Filtra il dataset per studio_id partendo dal file pazienti e (opzionale) genera split per genere")
    p.add_argument("--patient-csv", type=Path, required=True, help="CSV dei pazienti")
    p.add_argument("--study-id", nargs="+", required=True, help="Uno o più valori di studio_id/study_id da includere")
    p.add_argument("--data-csv", type=Path, default=Path("fluency_data/snafu.csv"), help="CSV completo dei dati")
    p.add_argument("-o", "--output", type=Path, required=True, help="CSV filtrato in output")
    p.add_argument("--patient-id-col", type=str, default=None, help="Colonna ID paziente nel file pazienti (default: autodetect)")
    p.add_argument("--study-col", type=str, default=None, help="Colonna studio nel file pazienti (default: studio_id/study_id)")
    p.add_argument("--data-id-col", type=str, default="id", help="Colonna ID nel CSV dati (default: id)")
    p.add_argument("--sep-pat", dest="sep_pat", type=str, default=None, help="Separatore file pazienti (default: auto)")
    p.add_argument("--sep-data", dest="sep_data", type=str, default=None, help="Separatore file dati (default: auto)")
    p.add_argument("--encoding", type=str, default="utf-8-sig", help="Encoding in output")
    p.add_argument("--invert", action="store_true", help="Esclude gli study-id forniti invece di includerli")
    p.add_argument("--gender-col", type=str, default=None, help="Colonna genere nel file pazienti (default: autodetect)")
    p.add_argument("--output-male", type=Path, default=None, help="Percorso output dataset solo maschi")
    p.add_argument("--output-female", type=Path, default=None, help="Percorso output dataset solo femmine")
    p.add_argument("--no-gender-splits", action="store_true", help="Non generare dataset per genere")
    return p.parse_args()


def main() -> None:
    a = parse_args()
    filter_by_study(
        patient_csv=a.patient_csv,
        study_ids=a.study_id,
        data_csv=a.data_csv,
        output_csv=a.output,
        patient_id_col=a.patient_id_col,
        study_col=a.study_col,
        data_id_col=a.data_id_col,
        sep_pat=a.sep_pat,
        sep_data=a.sep_data,
        encoding=a.encoding,
        invert=a.invert,
        gender_col=a.gender_col,
        output_male=a.output_male,
        output_female=a.output_female,
        no_gender_splits=a.no_gender_splits,
    )


if __name__ == "__main__":
    main()
