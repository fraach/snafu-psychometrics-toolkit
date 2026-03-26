import csv
import sys
from pathlib import Path
from typing import Dict, Iterable, List

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

# Rende disponibili le dipendenze installate in env/ o .venv/
_BASE_DIR = Path(__file__).parent.resolve()
def _extend_sys_path() -> None:
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    candidates = [
        _BASE_DIR / "env" / "lib" / version / "site-packages",
        _BASE_DIR / "env" / "Lib" / "site-packages",
        _BASE_DIR / ".venv" / "lib" / version / "site-packages",
        _BASE_DIR / ".venv" / "Lib" / "site-packages",
    ]
    for c in candidates:
        p = str(c)
        if c.exists() and p not in sys.path:
            sys.path.append(p)

_extend_sys_path()

try:
    import snafu  # type: ignore
    _SNAFU_AVAILABLE = True
except Exception:
    snafu = None  # type: ignore
    _SNAFU_AVAILABLE = False

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
    "uinvite",
)


FIGURES_DIR.mkdir(parents=True, exist_ok=True)

PLOT_CFG = {
    "filter_to_gcc": True,
    "use_k_core": False,
    "k_core_min_degree": 2,
    "label_strategy": "top_degree",
    "max_labels": 80,
    "layout": "auto",
    "spring_k_factor": 2.2,
    "fig_base_w": 8.0,
    "fig_base_h": 6.5,
    "fig_scale_per_node": 0.05,  
    "fig_max_w": 28.0,
    "fig_max_h": 22.0,
    "edge_alpha": 0.2,
    "edge_width": 0.9,
    "node_edgecolor": "white",
    "node_linewidth": 0.6,
    "node_size_min": 120.0,
    "node_size_max": 900.0,
    "label_fontsize": 7,
}


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

    def _read_csv_robust(p: Path) -> pd.DataFrame:
        encodings = ["utf-8-sig", "utf-8", "cp1252", "latin1"]
        last_exc = None
        for enc in encodings:
            try:
                return pd.read_csv(p, encoding=enc)
            except Exception as e1:
                last_exc = e1
                try:
                    text = p.read_bytes().decode(enc, errors="replace")
                    import io as _io
                    return pd.read_csv(_io.StringIO(text))
                except Exception as e2:
                    last_exc = e2
                    continue
        if last_exc is not None:
            raise last_exc
        return pd.read_csv(p)

    df = _read_csv_robust(path)
    df.columns = [str(c).strip().lstrip("\ufeff") for c in df.columns]
    lower_map = {c.lower(): c for c in df.columns}
    if "edge" not in lower_map:
        raise ValueError(f"Colonna 'edge' mancante in {path}")
    edge_col = lower_map["edge"]
    i1 = lower_map.get("item1", "item1")
    i2 = lower_map.get("item2", "item2")
    if i1 not in df.columns or i2 not in df.columns:
        raise ValueError(f"Colonne 'item1'/'item2' mancanti in {path}")
    df[edge_col] = pd.to_numeric(df[edge_col], errors="coerce").fillna(0).astype(int)
    edges = df[df[edge_col] == 1][[i1, i2]].dropna()
    g = nx.Graph()
    for _, row in edges.iterrows():
        item1 = str(row[i1]).strip()
        item2 = str(row[i2]).strip()
        if item1 and item2:
            g.add_edge(item1, item2)
    isolated = set(df[i1].dropna().astype(str).str.strip().unique()).union(
        df[i2].dropna().astype(str).str.strip().unique()
    )
    g.add_nodes_from(isolated)
    return g


def _color_palette(n: int) -> Dict[str, tuple]:
    cmap = plt.get_cmap("tab20")
    return {idx: cmap(idx % cmap.N) for idx in range(n)}


def _ensure_intervals(rts: List[int]) -> List[float]:
    """Converte una sequenza di time-stamp in intervalli tra risposte.

    Se i valori non sono strettamente non decrescenti, assume che siano già IRT.
    """
    if len(rts) <= 1:
        return rts
    nondecreasing = all(rts[i] <= rts[i + 1] for i in range(len(rts) - 1))
    if nondecreasing:
        prev = 0
        out: List[float] = []
        for v in rts:
            out.append(max(0, v - prev))
            prev = v
        return out
    return rts


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

    G = graph
    if PLOT_CFG["filter_to_gcc"] and graph.number_of_nodes() > 0 and graph.number_of_edges() > 0:
        gcc_nodes = max(nx.connected_components(graph), key=len)
        G = graph.subgraph(gcc_nodes).copy()
    if PLOT_CFG["use_k_core"] and G.number_of_nodes() > 0:
        try:
            G = nx.k_core(G, k=PLOT_CFG["k_core_min_degree"])
        except nx.NetworkXError:
            pass

    labels = load_scheme_labels(category)
    node_clusters = [labels.get(node.lower().replace(" ", ""), "intrusion") for node in G.nodes()]
    unique_clusters = sorted(set(node_clusters))
    palette = _color_palette(len(unique_clusters))
    color_map = {cluster: palette[idx] for idx, cluster in enumerate(unique_clusters)}
    node_colors = [color_map[cluster] for cluster in node_clusters]

    degrees = dict(G.degree())
    deg_vals = np.array([degrees[node] for node in G.nodes()], dtype=float)
    if deg_vals.size == 0:
        deg_vals = np.array([0.0])
    if deg_vals.max() > 0:
        scale = (deg_vals - deg_vals.min()) / (deg_vals.max() - deg_vals.min() + 1e-9)
        node_sizes = PLOT_CFG["node_size_min"] + scale * (PLOT_CFG["node_size_max"] - PLOT_CFG["node_size_min"])
    else:
        node_sizes = np.full_like(deg_vals, (PLOT_CFG["node_size_min"] + PLOT_CFG["node_size_max"]) / 2)

    n_nodes = G.number_of_nodes()
    layout_mode = PLOT_CFG["layout"]
    if layout_mode == "auto":
        layout_mode = "kamada" if n_nodes >= 250 else "spring"
    if layout_mode == "kamada":
        pos = nx.kamada_kawai_layout(G)
    else:
        k = PLOT_CFG["spring_k_factor"] / np.sqrt(max(n_nodes, 1))
        pos = nx.spring_layout(G, seed=42, k=k, iterations=200, scale=2.0)

    w = min(PLOT_CFG["fig_max_w"], PLOT_CFG["fig_base_w"] + PLOT_CFG["fig_scale_per_node"] * n_nodes)
    h = min(PLOT_CFG["fig_max_h"], PLOT_CFG["fig_base_h"] + PLOT_CFG["fig_scale_per_node"] * n_nodes)
    fig, ax = plt.subplots(figsize=(w, h))

    nx.draw_networkx_edges(G, pos, ax=ax, alpha=PLOT_CFG["edge_alpha"], width=PLOT_CFG["edge_width"])
    nx.draw_networkx_nodes(
        G,
        pos,
        ax=ax,
        node_color=node_colors,
        node_size=node_sizes,
        linewidths=PLOT_CFG["node_linewidth"],
        edgecolors=PLOT_CFG["node_edgecolor"],
    )

    label_strategy = PLOT_CFG["label_strategy"]
    if label_strategy == "all":
        nx.draw_networkx_labels(G, pos, ax=ax, font_size=PLOT_CFG["label_fontsize"])
    elif label_strategy == "top_degree":
        top = sorted(degrees.items(), key=lambda kv: kv[1], reverse=True)[: PLOT_CFG["max_labels"]]
        top_nodes = [name for name, _ in top if name in pos]
        if top_nodes:
            labels_dict = {n: n for n in top_nodes}
            nx.draw_networkx_labels(G, pos, labels=labels_dict, ax=ax, font_size=PLOT_CFG["label_fontsize"])

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


def plot_degree_distribution(category: str) -> None:
    """Plot della distribuzione dei gradi per tutti i metodi di una categoria."""
    methods = list(NETWORK_METHODS)
    if not methods:
        return
    cols = 2 if len(methods) <= 4 else 3
    rows = int(np.ceil(len(methods) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 4.5 * rows))
    axes = np.atleast_1d(axes).ravel()
    for idx, method in enumerate(methods):
        ax = axes[idx]
        try:
            G = load_network(category, method)
        except Exception as err:
            ax.text(0.5, 0.5, str(err), ha="center", va="center")
            ax.axis("off")
            continue
        deg = np.array([d for _, d in G.degree()])
        if deg.size == 0:
            ax.text(0.5, 0.5, "Rete vuota", ha="center", va="center")
            ax.axis("off")
            continue
        vals, counts = np.unique(deg, return_counts=True)
        ax.bar(vals, counts, alpha=0.8, color="#4C72B0")
        ax.set_title(method.replace("_", " ").title())
        ax.set_xlabel("Grado")
        ax.set_ylabel("Frequenza")
        ax.grid(axis="y", linestyle="--", linewidth=0.5, alpha=0.6)
    for ax in axes[len(methods):]:
        ax.axis("off")
    fig.suptitle(f"Distribuzione dei gradi — {category.title()}")
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig.savefig(FIGURES_DIR / f"degree_dist_{category}.png", dpi=300)
    plt.close(fig)


def plot_smallworld_summary() -> None:
    """Barplot del coefficiente small-world s per categoria e metodo.

    s = (C/C_rand) / (L/L_rand) calcolato da `snafu.smallworld`.
    """
    if not _SNAFU_AVAILABLE:
        return
    methods = list(NETWORK_METHODS)
    categories = list(SCHEMES.keys())
    s_vals = {cat: [] for cat in categories}
    for cat in categories:
        for method in methods:
            try:
                G = load_network(cat, method)
                a = nx.to_numpy_array(G)
                s = snafu.smallworld(a)
            except Exception:
                s = np.nan
            s_vals[cat].append(s)

    x = np.arange(len(methods))
    width = 0.8 / len(categories)
    fig, ax = plt.subplots(figsize=(10, 6))
    for idx, cat in enumerate(categories):
        vals = np.array(s_vals[cat], dtype=float)
        ax.bar(x + idx * width, vals, width=width, label=cat.title())
    ax.set_xticks(x + width * (len(categories) - 1) / 2)
    ax.set_xticklabels([m.replace("_", " ").title() for m in methods])
    ax.set_ylabel("Small-world s")
    ax.set_title("Coefficiente small-world per metodo e categoria")
    ax.legend(loc="upper right")
    ax.grid(axis="y", linestyle="--", linewidth=0.5, alpha=0.6)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "smallworld_summary.png", dpi=300)
    plt.close(fig)


def plot_irt_figures() -> None:
    """Grafici di IRT aggregati per categoria usando i dati filtrati.

    Genera due figure:
    - istogramma degli IRT aggregati per categoria
    - profilo della media degli IRT vs posizione seriale
    """
    if not _SNAFU_AVAILABLE:
        return
    try:
        data = snafu.load_fluency_data(
            str(RESULTS_DIR.parent / "fluency_data" / "filtered_snafu.csv"),
            removePerseverations=True,
            removeIntrusions=True,
            removeNonAlphaChars=True,
            hierarchical=True,
        )
    except Exception:
        return

    for cat in SCHEMES.keys():
        irts_all: List[float] = []
        pos_vals: Dict[int, List[float]] = {}
        for sid in data.subs:
            for listnum, catname in data.categories.get(sid, {}).items():
                if catname != cat:
                    continue
                rts = data.irts.get(sid, {}).get(listnum, [])
                irts = _ensure_intervals(rts)
                irts_all.extend(irts)
                for idx, val in enumerate(irts):
                    pos_vals.setdefault(idx + 1, []).append(val)

        if not irts_all:
            continue

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.hist(irts_all, bins=30, color="#4C72B0", alpha=0.85)
        ax.set_title(f"Distribuzione IRT — {cat.title()}")
        ax.set_xlabel("Inter-response time (ms)")
        ax.set_ylabel("Frequenza")
        ax.grid(axis="y", linestyle="--", linewidth=0.5, alpha=0.6)
        fig.tight_layout()
        fig.savefig(FIGURES_DIR / f"irt_hist_{cat}.png", dpi=300)
        plt.close(fig)

        positions = sorted(pos_vals.keys())
        means = [np.mean(pos_vals[p]) for p in positions]
        stds = [np.std(pos_vals[p]) for p in positions]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.errorbar(positions, means, yerr=stds, fmt="-o", color="#55A868")
        ax.set_title(f"IRT medio per posizione — {cat.title()}")
        ax.set_xlabel("Posizione seriale")
        ax.set_ylabel("IRT (ms)")
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.6)
        fig.tight_layout()
        fig.savefig(FIGURES_DIR / f"irt_position_{cat}.png", dpi=300)
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
        plot_degree_distribution(category)

    plot_smallworld_summary()
    plot_irt_figures()

    print(f"Grafici salvati in: {FIGURES_DIR}")


if __name__ == "__main__":
    main()
