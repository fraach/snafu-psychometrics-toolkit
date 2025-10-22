"""
Analisi dei dati SNAFU per prove di fluenza semantica.

Questo script:
- prepara e filtra i dati grezzi di fluenza;
- calcola metriche psicometriche per soggetto e categoria;
- ricostruisce diverse reti semantiche di gruppo e ne estrae metriche
  strutturali (es. densità, clustering, diametro del componente maggiore);
- esporta tabelle e liste di archi nei file di output.

Le funzioni sono corredate da docstring e commenti descrittivi in italiano per
facilitare la lettura e la manutenzione del codice.
"""

import csv
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()


def _extend_sys_path() -> list[str]:
    """Aggiunge ai `sys.path` le cartelle di site-packages dell'ambiente locale.

    Questo consente di importare dipendenze installate nell'`env/` locale anche
    quando lo script viene eseguito fuori da quell'ambiente.
    Restituisce la lista dei percorsi effettivamente aggiunti.
    """
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
import snafu

from filter import merge_and_validate_rows

BASE_DIR = Path(__file__).parent.resolve()
# Percorsi e risorse principali del progetto.
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
def sanitize_scheme_file(original: Path) -> Path:
    """Crea una versione sanificata del file di schema.

    - Rimuove BOM e commenti/righe vuote
    - Tronca spazi superflui
    - Salva il risultato in `results/scheme_cache/` per velocizzare run successivi

    Se la cache è più recente dell'originale, la riutilizza.
    """
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
    """Restituisce il percorso dello schema per una categoria validata."""
    if category not in SCHEMES:
        raise KeyError(f"Categoria sconosciuta: {category}")
    return sanitize_scheme_file(SCHEMES[category])




def ensure_filtered_dataset() -> None:
    """Rigenera il dataset filtrato se mancante o obsoleto.

    Usa `merge_and_validate_rows` per unire/validare i dati grezzi rispetto agli
    schemi di categoria, producendo `filtered_snafu.csv`.
    """
    needs_refresh = not FILTERED_FILE.exists()
    if not needs_refresh:
        needs_refresh = RAW_FILE.stat().st_mtime > FILTERED_FILE.stat().st_mtime
    if needs_refresh:
        merge_and_validate_rows(str(RAW_FILE), str(SCHEME_DIR), str(FILTERED_FILE))


def serialize_nested(value) -> str:
    """Serializza (come JSON) una struttura annidata o vuota in stringa.

    Utile per salvare elenchi di parole (es. perseverazioni/intrusioni) per
    soggetto in colonne CSV.
    """
    if not value:
        return "[]"
    return json.dumps(value, ensure_ascii=True)



def prepare_first_edge_sequences(sequences):
    """Seleziona solo le liste con almeno due elementi (per First Edge)."""
    return [seq for seq in sequences if isinstance(seq, (list, tuple)) and len(seq) >= 2]

def flatten_unique_strings(value) -> str:
    """Appiattisce una struttura annidata in stringhe uniche ordinate (JSON).

    Esempio: set/list/tuple annidati vengono esplosi in una lista piatta di
    stringhe, deduplicate e ordinate alfabeticamente, poi serializzate in JSON.
    """
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


def compute_psychometric_table() -> pd.DataFrame:
    """Calcola le metriche psicometriche per soggetto e categoria.

    Per ogni categoria (es. animali, frutta, verdura) ottiene:
    - cluster switch (static/fluid) e switch rate
    - dimensione media dei cluster (static/fluid)
    - perseverazioni (conteggi ed elenco parole)
    - intrusioni (conteggi ed elenco parole)
    - frequenza media delle parole (SUBTLEX) e voci mancanti
    - età di acquisizione media (AoA) e voci mancanti
    """
    rows: list[dict[str, object]] = []
    for category in SCHEMES:
        scheme_path = get_scheme_path(category)
        data = snafu.load_fluency_data(
            str(FILTERED_FILE),
            category=category,
            removeNonAlphaChars=True,
            hierarchical=True,
        )
        labeled_lists = data.labeledlists
        subject_ids = data.subs

        # Cambi di cluster stimati con definizione "statica" (confini fissi)
        cluster_switch_static = snafu.clusterSwitch(
            labeled_lists,
            str(scheme_path),
            clustertype="static",
        )
        # Cambi di cluster con definizione "fluida" (confini data-driven)
        cluster_switch_fluid = snafu.clusterSwitch(
            labeled_lists,
            str(scheme_path),
            clustertype="fluid",
        )
        # Tasso di switch (normalizzato) in modalità statica
        switch_rate_static = snafu.clusterSwitch(
            labeled_lists,
            str(scheme_path),
            clustertype="static",
            switchrate=True,
        )
        # Dimensione dei cluster (media) con definizione fluida
        cluster_size_fluid = snafu.clusterSize(
            labeled_lists,
            str(scheme_path),
            clustertype="fluid",
        )
        # Dimensione dei cluster (media) con definizione statica
        cluster_size_static = snafu.clusterSize(
            labeled_lists,
            str(scheme_path),
            clustertype="static",
        )
        # Errori di produzione: ripetizioni (perseverazioni) e parole fuori schema (intrusioni)
        perseveration_counts = snafu.perseverations(labeled_lists)
        perseveration_words = snafu.perseverationsList(labeled_lists)
        intrusion_counts = snafu.intrusions(labeled_lists, str(scheme_path))
        intrusion_words = snafu.intrusionsList(labeled_lists, str(scheme_path))
        # Indicatori lessicali: frequenza e AoA (con tracciamento degli item mancanti)
        word_freq, missing_word_freq = snafu.wordFrequency(
            labeled_lists,
            data=str(FREQUENCY_FILE),
            missing=0.5,
        )
        aoa, missing_aoa = snafu.ageOfAcquisition(
            labeled_lists,
            data=str(AOA_FILE),
            missing=None,
        )

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
    """Converte l'output dei costruttori SNAFU in `networkx.Graph`.

    Supporta sia grafi già `networkx`, sia matrici/tuple restituite dalle
    funzioni di inferenza di SNAFU.
    """
    if isinstance(graph, nx.Graph):
        return graph.copy()
    if isinstance(graph, tuple):
        graph = graph[0]
    array = np.asarray(graph)
    return nx.from_numpy_array(array)


def compute_graph_metrics(graph: nx.Graph) -> dict[str, object]:
    """Estrae metriche strutturali dalla rete.

    Valuta dimensioni, densità, clustering medio, grado medio dei vicini e
    statistiche del componente connesso più grande (ASP e diametro).
    """
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


def infer_semantic_networks() -> pd.DataFrame:
    """Ricostruisce diverse reti semantiche di gruppo e calcola metriche.

    Metodi inclusi:
    - naive_random_walk: co-occorrenza per passeggiata casuale
    - conceptual_network: rete concettuale (usa parametri `fitinfo`)
    - pathfinder: backbone tipo Pathfinder
    - correlation_based: rete basata su correlazioni
    - first_edge: collega solo la prima transizione di ogni lista (richiede ≥2 item)
    """
    NETWORK_DIR.mkdir(parents=True, exist_ok=True)
    # Parametri di adattamento per la rete concettuale
    fitinfo = snafu.Fitinfo(
        {
            "cn_alpha": 0.05,
            "cn_windowsize": 2,
            "cn_threshold": 2,
        }
    )

    network_rows: list[dict[str, object]] = []

    for category in SCHEMES:
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
        # Per First Edge servono liste con almeno due parole prodotte
        first_edge_sequences = prepare_first_edge_sequences(sequences)

        def build_first_edge():
            if not first_edge_sequences:
                raise ValueError("No fluency lists with at least two items after preprocessing")
            return snafu.firstEdge(
                first_edge_sequences,
                numnodes=data.groupnumnodes,
            )

        # Collezione di costruttori di grafi, tutti con etichetta metodo
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
                # In caso di errore sul metodo, registriamo l'eccezione e continuiamo
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
            # Esporta la lista archi con etichette leggibili
            snafu.write_graph(
                raw_graph,
                str(output_path),
                labels=data.groupitems,
                subj=category.upper(),
            )

    return pd.DataFrame(network_rows)

def main() -> None:
    """Punto di ingresso: prepara dati, calcola tabelle e salva output."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ensure_filtered_dataset()

    psychometrics = compute_psychometric_table()
    psychometrics.to_csv(RESULTS_DIR / "psychometrics.csv", index=False)

    network_metrics = infer_semantic_networks()
    network_metrics.to_csv(RESULTS_DIR / "network_metrics.csv", index=False)

    print("Psychometrics saved to", RESULTS_DIR / "psychometrics.csv")
    print("Network metrics saved to", RESULTS_DIR / "network_metrics.csv")
    print("Network edge lists in", NETWORK_DIR)


if __name__ == "__main__":
    main()














