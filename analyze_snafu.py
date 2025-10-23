import csv
import json
import sys
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()


def _extend_sys_path() -> list[str]:
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    candidates = [
        BASE_DIR / "env" / "lib" / version / "site-packages",
        BASE_DIR / "env" / "Lib" / "site-packages",
    ]
    added: list[str] = []
    for candidate in candidates:
        if candidate.exists():
            path_str = str(candidate)
            if path_str not in sys.path:
                sys.path.append(path_str)
                added.append(path_str)
    return added


SITE_PACKAGES_ADDED = _extend_sys_path()

import numpy as np
import pandas as pd
import networkx as nx
try:
    import snafu #type:ignore
except ImportError as exc:
    raise SystemExit(
        "Modulo 'snafu' non trovato. Installa con 'pip install snafu' o usa SETUP_WINDOWS.ps1."
    ) from exc

from filter import merge_and_validate_rows

# Default
RAW_FILE = BASE_DIR / "fluency_data" / "snafu.csv"
FILTERED_FILE = BASE_DIR / "fluency_data" / "filtered_snafu.csv"
SCHEME_DIR = BASE_DIR / "schemes"
SCHEMES = {
    "animali": SCHEME_DIR / "animali.csv",
    "frutta": SCHEME_DIR / "frutta.csv",
    "verdura": SCHEME_DIR / "verdura.csv",
}
FREQUENCY_FILE = BASE_DIR / "frequency" / "subtlex-us.csv"
AOA_FILE = BASE_DIR / "aoa" / "kuperman.csv"
RESULTS_DIR = BASE_DIR / "results"
NETWORK_DIR = RESULTS_DIR / "networks"
SCHEME_CACHE_DIR = RESULTS_DIR / "scheme_cache"

def _discover_categories(scheme_dir: Path) -> list[str]:
    cats: list[str] = []
    if scheme_dir.exists():
        for p in scheme_dir.glob("*.csv"):
            cats.append(p.stem)
    return sorted(cats) or ["animali", "frutta", "verdura"]
def sanitize_scheme_file(original: Path) -> Path:
    SCHEME_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    sanitized_path = SCHEME_CACHE_DIR / original.name
    if sanitized_path.exists() and sanitized_path.stat().st_mtime >= original.stat().st_mtime:
        return sanitized_path

    with original.open('r', encoding='utf-8-sig') as src, sanitized_path.open('w', newline='', encoding='utf-8') as dest:
        reader = csv.reader(src)
        writer = csv.writer(dest)
        for row in reader:
            if not row:
                continue
            first_cell = row[0].strip()
            if not first_cell or first_cell.startswith('#'):
                continue
            if len(row) < 2:
                continue
            writer.writerow([first_cell, row[1].strip()])
    return sanitized_path


def get_scheme_path(category: str) -> Path:
    if category not in SCHEMES:
        raise KeyError(f"Categoria sconosciuta: {category}")
    return sanitize_scheme_file(SCHEMES[category])




def ensure_filtered_dataset(*, force: bool = False) -> None:
    needs_refresh = not FILTERED_FILE.exists()
    if not needs_refresh:
        needs_refresh = RAW_FILE.stat().st_mtime > FILTERED_FILE.stat().st_mtime
    if force:
        needs_refresh = True
    if needs_refresh:
        merge_and_validate_rows(str(RAW_FILE), str(SCHEME_DIR), str(FILTERED_FILE))
    try:
        df = pd.read_csv(FILTERED_FILE, dtype=str)
        before = len(df)
        if "item" in df.columns:
            df["item"] = df["item"].fillna("").astype(str)
            df.loc[:, "item"] = df["item"].str.strip().str.replace("'", "", regex=False)

            def _letters_only(s: str) -> str:
                return "".join(ch for ch in s if ch.isalpha())

            letters = df["item"].map(_letters_only)

            mask_nonempty = letters.str.len() > 0
            removed_empty = int((~mask_nonempty).sum())
            df = df[mask_nonempty].copy()

            df.loc[:, "item"] = letters[mask_nonempty].values

        df.to_csv(FILTERED_FILE, index=False)
        if before - len(df) > 0:
            print(
                f"[sanitize] Rimosse {before - len(df)} righe con item vuoto/non alfabetico da {FILTERED_FILE}"
            )
    except Exception:
        pass


def serialize_nested(value) -> str:
    if not value:
        return "[]"
    return json.dumps(value, ensure_ascii=True)



def prepare_first_edge_sequences(sequences):
    """Keep only fluency lists with at least two items for First Edge."""
    return [seq for seq in sequences if isinstance(seq, (list, tuple)) and len(seq) >= 2]

def flatten_unique_strings(value) -> str:
    if not value:
        return "[]"
    flat: list[str] = []
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, (list, tuple, set)):
            stack.extend(current)
        elif current is None:
            continue
        else:
            flat.append(str(current))
    unique_sorted = sorted(set(flat))
    return json.dumps(unique_sorted, ensure_ascii=True)


def compute_psychometric_table(categories: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for category in categories:
        scheme_path = get_scheme_path(category)
        data = snafu.load_fluency_data(
            str(FILTERED_FILE),
            category=category,
            removeNonAlphaChars=True,
            hierarchical=True,
        )
        labeled_lists = data.labeledlists
        subject_ids = data.subs

        n = len(subject_ids)
        if n == 0 or not labeled_lists:
            continue

        def _safe(default_list, fn, *args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception:
                return default_list

        zeros = [0.0] * n
        empties = [[] for _ in range(n)]
        nones = [None] * n

        cluster_switch_static = _safe(zeros, snafu.clusterSwitch, labeled_lists, str(scheme_path), clustertype="static")
        cluster_switch_fluid = _safe(zeros, snafu.clusterSwitch, labeled_lists, str(scheme_path), clustertype="fluid")
        switch_rate_static = _safe(zeros, snafu.clusterSwitch, labeled_lists, str(scheme_path), clustertype="static", switchrate=True)
        cluster_size_fluid = _safe(zeros, snafu.clusterSize, labeled_lists, str(scheme_path), clustertype="fluid")
        cluster_size_static = _safe(zeros, snafu.clusterSize, labeled_lists, str(scheme_path), clustertype="static")
        perseveration_counts = _safe(zeros, snafu.perseverations, labeled_lists)
        perseveration_words = _safe(empties, snafu.perseverationsList, labeled_lists)
        intrusion_counts = _safe(zeros, snafu.intrusions, labeled_lists, str(scheme_path))
        intrusion_words = _safe(empties, snafu.intrusionsList, labeled_lists, str(scheme_path))
        try:
            word_freq, missing_word_freq = snafu.wordFrequency(labeled_lists, data=str(FREQUENCY_FILE), missing=0.5)
        except Exception:
            word_freq, missing_word_freq = nones, empties
        try:
            aoa, missing_aoa = snafu.ageOfAcquisition(labeled_lists, data=str(AOA_FILE), missing=None)
        except Exception:
            aoa, missing_aoa = nones, empties

        for idx, subject in enumerate(subject_ids):
            rows.append(
                {
                    "id": subject,
                    "category": category,
                    "cluster_switch_static": float(cluster_switch_static[idx]),
                    "cluster_switch_fluid": float(cluster_switch_fluid[idx]),
                    "switch_rate_static": float(switch_rate_static[idx]),
                    "cluster_size_static": float(cluster_size_static[idx]),
                    "cluster_size_fluid": float(cluster_size_fluid[idx]),
                    "perseverations": float(perseveration_counts[idx]),
                    "perseveration_words": serialize_nested(perseveration_words[idx]),
                    "intrusions": float(intrusion_counts[idx]),
                    "intrusion_words": serialize_nested(intrusion_words[idx]),
                    "avg_word_frequency": float(word_freq[idx]) if word_freq[idx] is not None else None,
                    "missing_word_freq_items": flatten_unique_strings(missing_word_freq[idx]),
                    "avg_aoa": float(aoa[idx]) if aoa[idx] is not None else None,
                    "missing_aoa_items": flatten_unique_strings(missing_aoa[idx]),
                }
            )
    return pd.DataFrame(rows)

def to_networkx_graph(graph) -> nx.Graph:
    if isinstance(graph, nx.Graph):
        return graph.copy()
    if isinstance(graph, tuple):
        graph = graph[0]
    array = np.asarray(graph)
    return nx.from_numpy_array(array)


def compute_graph_metrics(graph: nx.Graph) -> dict[str, object]:
    metrics: dict[str, object] = {}
    num_nodes = graph.number_of_nodes()
    num_edges = graph.number_of_edges()
    metrics["nodes"] = num_nodes
    metrics["edges"] = num_edges
    metrics["density"] = float(nx.density(graph)) if num_nodes > 1 else 0.0
    metrics["average_clustering"] = float(nx.average_clustering(graph)) if num_nodes > 2 else 0.0

    if num_nodes > 0:
        neighbor_degrees = nx.average_neighbor_degree(graph)
        if neighbor_degrees:
            metrics["average_neighbor_degree"] = float(np.mean(list(neighbor_degrees.values())))
        else:
            metrics["average_neighbor_degree"] = 0.0
    else:
        metrics["average_neighbor_degree"] = 0.0

    if num_nodes == 0 or num_edges == 0:
        metrics["largest_component_nodes"] = 0
        metrics["largest_component_density"] = 0.0
        metrics["largest_component_average_shortest_path"] = None
        metrics["largest_component_diameter"] = None
        return metrics

    largest_component_nodes = max(nx.connected_components(graph), key=len)
    largest = graph.subgraph(largest_component_nodes)
    metrics["largest_component_nodes"] = largest.number_of_nodes()
    metrics["largest_component_density"] = float(nx.density(largest)) if largest.number_of_nodes() > 1 else 0.0

    if largest.number_of_nodes() > 1:
        metrics["largest_component_average_shortest_path"] = float(nx.average_shortest_path_length(largest))
        try:
            metrics["largest_component_diameter"] = int(nx.diameter(largest))
        except nx.NetworkXError:
            metrics["largest_component_diameter"] = None
    else:
        metrics["largest_component_average_shortest_path"] = None
        metrics["largest_component_diameter"] = None

    return metrics


def infer_semantic_networks(categories: list[str], *, cn_alpha: float = 0.05, cn_windowsize: int = 2, cn_threshold: int = 2) -> pd.DataFrame:
    NETWORK_DIR.mkdir(parents=True, exist_ok=True)
    fitinfo = snafu.Fitinfo(
        {
            "cn_alpha": cn_alpha,
            "cn_windowsize": cn_windowsize,
            "cn_threshold": cn_threshold,
        }
    )

    network_rows: list[dict[str, object]] = []

    for category in categories:
        scheme_path = get_scheme_path(category)
        data = snafu.load_fluency_data(
            str(FILTERED_FILE),
            category=category,
            removePerseverations=True,
            removeIntrusions=True,
            scheme=str(scheme_path),
            removeNonAlphaChars=True,
            hierarchical=False,
        )

        sequences = data.Xs
        first_edge_sequences = prepare_first_edge_sequences(sequences)

        def build_first_edge():
            if not first_edge_sequences:
                raise ValueError("No fluency lists with at least two items after preprocessing")
            return snafu.firstEdge(
                first_edge_sequences,
                numnodes=data.groupnumnodes,
            )

        builders = {
            "naive_random_walk": lambda: snafu.naiveRandomWalk(
                sequences,
                numnodes=data.groupnumnodes,
            ),
            "conceptual_network": lambda: snafu.conceptualNetwork(
                sequences,
                numnodes=data.groupnumnodes,
                fitinfo=fitinfo,
            ),
            "pathfinder": lambda: snafu.pathfinder(
                sequences,
                numnodes=data.groupnumnodes,
            ),
            "correlation_based": lambda: snafu.correlationBasedNetwork(
                sequences,
                numnodes=data.groupnumnodes,
            ),
            "first_edge": build_first_edge,
        }

        for method, builder in builders.items():
            try:
                raw_graph = builder()
            except Exception as exc:
                network_rows.append(
                    {
                        "category": category,
                        "method": method,
                        "error": str(exc),
                    }
                )
                continue

            nx_graph = to_networkx_graph(raw_graph)
            metrics = compute_graph_metrics(nx_graph)
            metrics.update(
                {
                    "category": category,
                    "method": method,
                }
            )
            network_rows.append(metrics)

            output_path = NETWORK_DIR / f"{category}_{method}.csv"
            snafu.write_graph(
                raw_graph,
                str(output_path),
                labels=data.groupitems,
                subj=category.upper(),
            )

    return pd.DataFrame(network_rows)

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Analisi SNAFU: psicometria e reti semantiche")
    p.add_argument("--raw-file", type=Path, default=RAW_FILE, help="CSV grezzo (input)")
    p.add_argument("--filtered-file", type=Path, default=FILTERED_FILE, help="CSV filtrato (output di filter.py)")
    p.add_argument("--scheme-dir", type=Path, default=SCHEME_DIR, help="Directory degli schemi")
    p.add_argument("--results-dir", type=Path, default=RESULTS_DIR, help="Directory risultati")
    p.add_argument("--categories", nargs="+", default=None, help="Categorie da analizzare (default: tutti gli schemi trovati)")
    p.add_argument("--force-merge", action="store_true", help="Rigenera sempre il filtrato")
    p.add_argument("--skip-psychometrics", action="store_true")
    p.add_argument("--skip-networks", action="store_true")
    p.add_argument("--cn-alpha", type=float, default=0.05)
    p.add_argument("--cn-window", type=int, default=2)
    p.add_argument("--cn-threshold", type=int, default=2)
    return p.parse_args()


def main() -> None:
    global RAW_FILE, FILTERED_FILE, SCHEME_DIR, SCHEMES, RESULTS_DIR, NETWORK_DIR, SCHEME_CACHE_DIR

    args = _parse_args()

    RAW_FILE = args.raw_file if isinstance(args.raw_file, Path) else Path(args.raw_file)
    FILTERED_FILE = args.filtered_file if isinstance(args.filtered_file, Path) else Path(args.filtered_file)
    SCHEME_DIR = args.scheme_dir if isinstance(args.scheme_dir, Path) else Path(args.scheme_dir)
    RESULTS_DIR = args.results_dir if isinstance(args.results_dir, Path) else Path(args.results_dir)
    NETWORK_DIR = RESULTS_DIR / "networks"
    SCHEME_CACHE_DIR = RESULTS_DIR / "scheme_cache"

    discovered = _discover_categories(SCHEME_DIR)
    cats = args.categories or discovered
    SCHEMES = {c: SCHEME_DIR / f"{c}.csv" for c in cats}

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ensure_filtered_dataset(force=args.force_merge)

    if not args.skip_psychometrics:
        psychometrics = compute_psychometric_table(cats)
        psychometrics.to_csv(RESULTS_DIR / "psychometrics.csv", index=False)

    if not args.skip_networks:
        network_metrics = infer_semantic_networks(cats, cn_alpha=args.cn_alpha, cn_windowsize=args.cn_window, cn_threshold=args.cn_threshold)
        network_metrics.to_csv(RESULTS_DIR / "network_metrics.csv", index=False)

    print("Psychometrics saved to", RESULTS_DIR / "psychometrics.csv")
    print("Network metrics saved to", RESULTS_DIR / "network_metrics.csv")
    print("Network edge lists in", NETWORK_DIR)


if __name__ == "__main__":
    main()










