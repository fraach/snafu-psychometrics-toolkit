import csv
from pathlib import Path
from typing import Dict, Iterable

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).parent.resolve()
RESULTS_DIR = BASE_DIR / "results"
NETWORK_DIR = RESULTS_DIR / "networks"
FIGURES_DIR = RESULTS_DIR / "figures"
SCHEME_CACHE_DIR = RESULTS_DIR / "scheme_cache"
SCHEME_DIR = BASE_DIR / "schemes"

SCHEMES: Dict[str, Path] = {
    "animali": SCHEME_DIR / "animali.csv",
    "frutta": SCHEME_DIR / "frutta.csv",
    "verdura": SCHEME_DIR / "verdura.csv",
}
NETWORK_METHODS: Iterable[str] = (
    "naive_random_walk",
    "conceptual_network",
    "pathfinder",
    "first_edge",
)


FIGURES_DIR.mkdir(parents=True, exist_ok=True)


def load_scheme_labels(category: str) -> Dict[str, str]:
    """Return a mapping item -> semantic cluster label for a category."""
    if category not in SCHEMES:
        raise KeyError(f"Categoria sconosciuta: {category}")

    sanitized = SCHEME_CACHE_DIR / f"{category}.csv"
    scheme_path = sanitized if sanitized.exists() else SCHEMES[category]

    labels: Dict[str, str] = {}
    with scheme_path.open("r", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if len(row) < 2:
                continue
            family = row[0].strip()
            item = row[1].strip().lower().replace(" ", "")
            if not item:
                continue
            labels[item] = family
    return labels


def load_network(category: str, method: str) -> nx.Graph:
    """Load an inferred semantic network as a NetworkX graph."""
    path = NETWORK_DIR / f"{category}_{method}.csv"
    if not path.exists():
        raise FileNotFoundError(f"File mancante: {path}")

    df = pd.read_csv(path)
    if "edge" not in df.columns:
        raise ValueError(f"Colonna 'edge' mancante in {path}")

    edges = df[df["edge"] == 1][["item1", "item2"]].dropna()
    g = nx.Graph()
    for _, row in edges.iterrows():
        item1 = str(row["item1"]).strip()
        item2 = str(row["item2"]).strip()
        if item1 and item2:
            g.add_edge(item1, item2)
    # assicurati di includere eventuali nodi isolati citati nel file
    isolated = set(df["item1"].dropna().unique()).union(df["item2"].dropna().unique())
    g.add_nodes_from(isolated)
    return g


def _color_palette(n: int) -> Dict[str, tuple]:
    cmap = plt.get_cmap("tab20")
    return {idx: cmap(idx % cmap.N) for idx in range(n)}


def plot_network(category: str, method: str, metrics_df: pd.DataFrame) -> None:
    try:
        graph = load_network(category, method)
    except (FileNotFoundError, ValueError) as err:
        print(f"[WARN] {err}")
        return

    if graph.number_of_nodes() == 0 or graph.number_of_edges() == 0:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, f"Nessun arco stimato\n({category}, {method})", ha="center", va="center")
        ax.axis("off")
        output = FIGURES_DIR / f"network_{category}_{method}.png"
        fig.tight_layout()
        fig.savefig(output, dpi=200)
        plt.close(fig)
        return

    labels = load_scheme_labels(category)
    node_clusters = [labels.get(node.lower().replace(" ", ""), "intrusion") for node in graph.nodes()]
    unique_clusters = sorted(set(node_clusters))
    palette = _color_palette(len(unique_clusters))
    color_map = {cluster: palette[idx] for idx, cluster in enumerate(unique_clusters)}
    node_colors = [color_map[cluster] for cluster in node_clusters]

    degrees = dict(graph.degree())
    node_sizes = np.array([degrees[node] for node in graph.nodes()], dtype=float)
    node_sizes = 400 * (node_sizes / node_sizes.max()) + 200 if node_sizes.max() > 0 else np.full_like(node_sizes, 300)

    pos = nx.spring_layout(graph, seed=42, k=0.4)

    fig, ax = plt.subplots(figsize=(7, 6))
    nx.draw_networkx_edges(graph, pos, ax=ax, alpha=0.4, width=1.5)
    nx.draw_networkx_nodes(graph, pos, ax=ax, node_color=node_colors, node_size=node_sizes, linewidths=0.8, edgecolors="white")
    nx.draw_networkx_labels(graph, pos, ax=ax, font_size=7)

    handles = [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=color_map[c], label=c, markersize=6) for c in unique_clusters[:10]]
    if handles:
        ax.legend(handles=handles, title="Cluster", loc="upper right", frameon=False, fontsize=8)

    ax.set_title(f"{category.title()} - {method.replace('_', ' ').title()}")
    ax.axis("off")

    metric_row = metrics_df[(metrics_df["category"] == category) & (metrics_df["method"] == method)]
    if not metric_row.empty:
        info = metric_row.iloc[0]
        if isinstance(info.get("error"), str) and info["error"]:
            ax.annotate(f"Errore: {info['error']}", xy=(0.02, 0.02), xycoords="axes fraction", fontsize=8, ha="left")
        else:
            summary = (
                f"nodi={int(info['nodes'])} | archi={int(info['edges'])}\n"
                f"densita={info['density']:.3f} | clustering={info['average_clustering']:.3f}"
            )
            ax.annotate(summary, xy=(0.02, 0.02), xycoords="axes fraction", fontsize=8, ha="left")

    output = FIGURES_DIR / f"network_{category}_{method}.png"
    fig.tight_layout()
    fig.savefig(output, dpi=300)
    plt.close(fig)


def plot_psychometric_summary(psychometrics_df: pd.DataFrame) -> None:
    numeric_cols = [
        "cluster_switch_static",
        "cluster_switch_fluid",
        "switch_rate_static",
        "cluster_size_static",
        "cluster_size_fluid",
        "perseverations",
        "intrusions",
        "avg_word_frequency",
        "avg_aoa",
    ]
    summary = psychometrics_df.groupby("category")[numeric_cols].mean(numeric_only=True)
    categories = summary.index.tolist()
    x = np.arange(len(categories))

    metric_groups = [
        ("Cluster dynamics", ["cluster_switch_static", "cluster_switch_fluid", "switch_rate_static", "cluster_size_static", "cluster_size_fluid"]),
        ("Error patterns", ["perseverations", "intrusions"]),
        ("Lexical properties", ["avg_word_frequency", "avg_aoa"]),
    ]

    fig, axes = plt.subplots(len(metric_groups), 1, figsize=(10, 12))
    for ax, (title, cols) in zip(axes, metric_groups):
        width = 0.8 / len(cols)
        for idx, col in enumerate(cols):
            values = summary[col]
            ax.bar(x + idx * width, values, width=width, label=col.replace("_", " ").title())
        ax.set_xticks(x + width * (len(cols) - 1) / 2)
        ax.set_xticklabels([c.title() for c in categories], rotation=0)
        ax.set_title(title)
        ax.grid(axis="y", linestyle="--", linewidth=0.5, alpha=0.6)
        ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "psychometrics_summary.png", dpi=300)
    plt.close(fig)


def plot_network_metrics_summary(metrics_df: pd.DataFrame) -> None:
    metrics_df = metrics_df.copy()
    metrics_df["error"] = metrics_df["error"].fillna("")
    valid = metrics_df[metrics_df["error"] == ""]
    if valid.empty:
        print("[WARN] Nessuna rete valida per il riepilogo delle metriche")
        return

    metric_names = [
        "density",
        "average_clustering",
        "average_neighbor_degree",
        "largest_component_density",
        "largest_component_average_shortest_path",
    ]

    fig, axes = plt.subplots(len(metric_names), 1, figsize=(9, 14), sharex=True)
    methods = list(NETWORK_METHODS)
    x = np.arange(len(methods))
    categories = sorted(valid["category"].unique())
    colors = plt.cm.Set2(np.linspace(0, 1, len(categories)))

    for ax, metric in zip(axes, metric_names):
        for color, category in zip(colors, categories):
            subset = valid[valid["category"] == category]
            values = [subset.loc[subset["method"] == method, metric].mean() for method in methods]
            ax.plot(x, values, marker="o", label=category.title(), color=color)
        ax.set_title(metric.replace("_", " ").title())
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.6)
    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels([m.replace("_", " ").title() for m in methods], rotation=15)
    axes[0].legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "network_metrics_summary.png", dpi=300)
    plt.close(fig)


def main() -> None:
    psychometrics_path = RESULTS_DIR / "psychometrics.csv"
    network_metrics_path = RESULTS_DIR / "network_metrics.csv"

    if not psychometrics_path.exists() or not network_metrics_path.exists():
        raise FileNotFoundError("Assicurati di aver eseguito analyze_snafu.py prima di generare i grafici.")

    psychometrics_df = pd.read_csv(psychometrics_path)
    network_metrics_df = pd.read_csv(network_metrics_path)

    plot_psychometric_summary(psychometrics_df)
    plot_network_metrics_summary(network_metrics_df)

    for category in SCHEMES:
        for method in NETWORK_METHODS:
            plot_network(category, method, network_metrics_df)

    print(f"Grafici salvati in: {FIGURES_DIR}")


if __name__ == "__main__":
    main()

