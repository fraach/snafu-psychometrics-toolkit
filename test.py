r"""
Esecuzione pipeline PNRR tramite import dei moduli locali.

Passi:
  1) keep_columns.keep_only_allowed_columns -> standardizza colonne e (opzionale) filtri ID/study/split genere
  2) filter.merge_and_validate_rows -> merge token + filtro OT consecutivo
  3) analyze_snafu -> psicometria e reti (API chiamate direttamente senza CLI)
  4) plot_snafu_results -> grafici riepilogativi e reti

Esempio rapido (PowerShell):
  py test.py --raw "fluency_data\snafu_downloaded.csv" --patients "fluency_data\patients.csv" --study-id 19
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

# Supporta moduli spostati in ./functions mantenendo test.py nel root.
BASE_DIR = Path(__file__).resolve().parent
FUNCTIONS_DIR = BASE_DIR / "functions"
if FUNCTIONS_DIR.exists():
    functions_path = str(FUNCTIONS_DIR)
    if functions_path not in sys.path:
        sys.path.insert(0, functions_path)

import keep_columns as kc
import filter as flt
import analyze_snafu as an
import plot_snafu_results as psr


def run_pipeline(
    *,
    raw_file: Path,
    output_csv: Path,
    scheme_dir: Path,
    results_dir: Path,
    # keep_columns options
    id_prefix: Optional[str] = None,
    id_suffix: Optional[str] = None,
    patient_csv: Optional[Path] = None,
    study_ids: Optional[Iterable[str]] = None,
    invert: bool = False,
    sep_data: Optional[str] = None,
    sep_pat: Optional[str] = None,
    output_male: Optional[Path] = None,
    output_female: Optional[Path] = None,
    no_gender_splits: bool = False,
    # filter options
    min_ot_run: int = 3,
    # analyze options
    categories: Optional[list[str]] = None,
    cn_alpha: float = 0.05,
    cn_window: int = 2,
    cn_threshold: int = 2,
) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)

    # 1) keep_columns
    print("[1/4] keep_columns: standardizzazione + filtri opzionali…")
    kc.keep_only_allowed_columns(
        input_csv=raw_file,
        output_csv=output_csv,
        sep=sep_data,
        id_suffix=id_suffix,
        id_prefix=id_prefix,
        patient_csv=patient_csv,
        study_ids=study_ids,
        invert=invert,
        sep_pat=sep_pat,
        output_male=output_male,
        output_female=output_female,
        no_gender_splits=no_gender_splits,
    )

    # 2) filter (merge + OT)
    print("[2/4] filter: merge + filtro OT…")
    filtered_file = output_csv.parent / "filtered_snafu.csv"
    flt.merge_and_validate_rows(str(output_csv), str(scheme_dir), str(filtered_file), min_ot_run=min_ot_run, apply_ot_filter=True)

    # 3) analyze (usa API interne impostando i percorsi)
    print("[3/4] analyze_snafu: calcolo psicometria e reti…")
    an.RAW_FILE = raw_file
    an.FILTERED_FILE = filtered_file
    an.SCHEME_DIR = scheme_dir
    an.RESULTS_DIR = results_dir
    an.NETWORK_DIR = results_dir / "networks"
    an.SCHEME_CACHE_DIR = results_dir / "scheme_cache"

    if categories is None:
        categories = sorted([p.stem for p in scheme_dir.glob("*.csv")]) or ["animali", "frutta", "verdura"]
    an.SCHEMES = {c: scheme_dir / f"{c}.csv" for c in categories}

    # Applica sempre la sanificazione del filtrato (rimuove item che diventerebbero vuoti dopo removeNonAlphaChars)
    an.ensure_filtered_dataset(force=False)

    psychometrics = an.compute_psychometric_table(categories)
    psych_path = results_dir / "psychometrics.csv"
    psychometrics.to_csv(psych_path, index=False)

    network_metrics = an.infer_semantic_networks(categories, cn_alpha=cn_alpha, cn_windowsize=cn_window, cn_threshold=cn_threshold)
    netm_path = results_dir / "network_metrics.csv"
    network_metrics.to_csv(netm_path, index=False)

    # 4) plot
    print("[4/4] plot_snafu_results: grafici…")
    psr.RESULTS_DIR = results_dir
    psr.NETWORK_DIR = results_dir / "networks"
    psr.FIGURES_DIR = results_dir / "figures"
    psr.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    psr.SCHEME_CACHE_DIR = results_dir / "scheme_cache"
    psr.SCHEMES = {c: scheme_dir / f"{c}.csv" for c in categories}

    psych_df = pd.read_csv(psych_path)
    netm_df = pd.read_csv(netm_path)
    psr.plot_psychometric_summary(psych_df)
    psr.plot_network_metrics_summary(netm_df)
    for cat in categories:
        for method in psr.NETWORK_METHODS:
            psr.plot_network(cat, method, netm_df)
        # Anche la distribuzione dei gradi per categoria
        psr.plot_degree_distribution(cat)

    print(f"\nCompletato. Risultati in: {results_dir}")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Esempi PNRR: pipeline end-to-end")
    p.add_argument("--raw", type=Path, required=True, help="CSV grezzo di partenza")
    p.add_argument("--output", type=Path, default=Path("fluency_data/snafu.csv"), help="CSV standardizzato in uscita")
    p.add_argument("--scheme-dir", type=Path, default=Path("schemes"))
    p.add_argument("--results-dir", type=Path, default=Path("results"))
    p.add_argument("--id-prefix", type=str, default=None)
    p.add_argument("--id-suffix", type=str, default=None)
    p.add_argument("--patients", type=Path, default=None, help="CSV pazienti per filtro study_id")
    p.add_argument("--study-id", nargs="+", default=None)
    p.add_argument("--invert", action="store_true")
    p.add_argument("--sep-data", type=str, default=None)
    p.add_argument("--sep-pat", type=str, default=None)
    p.add_argument("--min-ot-run", type=int, default=3)
    p.add_argument("--categories", nargs="+", default=None)
    p.add_argument("--cn-alpha", type=float, default=0.05)
    p.add_argument("--cn-window", type=int, default=2)
    p.add_argument("--cn-threshold", type=int, default=2)
    p.add_argument("--no-gender-splits", action="store_true")
    return p.parse_args()


def main() -> None:
    a = _parse_args()
    run_pipeline(
        raw_file=a.raw,
        output_csv=a.output,
        scheme_dir=a.scheme_dir,
        results_dir=a.results_dir,
        id_prefix=a.id_prefix,
        id_suffix=a.id_suffix,
        patient_csv=a.patients,
        study_ids=a.study_id,
        invert=a.invert,
        sep_data=a.sep_data,
        sep_pat=a.sep_pat,
        no_gender_splits=a.no_gender_splits,
        min_ot_run=a.min_ot_run,
        categories=a.categories,
        cn_alpha=a.cn_alpha,
        cn_window=a.cn_window,
        cn_threshold=a.cn_threshold,
    )


if __name__ == "__main__":
    main()
