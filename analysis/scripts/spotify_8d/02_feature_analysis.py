"""
Feature Analysis
=========================
Analyses all 12 numeric Spotify features (8 current + 4 dropped) plus the
6 one-hot genre columns to inform feature selection before reduction.

Steps:
  2a. Distribution plots  -- histogram + KDE for all 12 audio features
  2b. Correlation matrix  -- Pearson heatmap: 12 audio + 6 genre cols; flag |r| > 0.4
  2c. Variance ranking    -- MinMax-scaled audio features + genre cols
  2d. PCA scree plot      -- explained variance per PC, two curves:
                               (i)  12 audio features only
                               (ii) 12 audio + 6 genre cols (weight=GENRE_WEIGHT)
                             shows effective dimensionality of each feature space

Outputs:
  figures/02_feature_analysis/distributions.png
  figures/02_feature_analysis/correlation.png
  figures/02_feature_analysis/variance.png
  figures/02_feature_analysis/pca_scree.png

Run from analysis/:
  python 02_feature_analysis.py
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.decomposition import PCA
from sklearn.preprocessing import MinMaxScaler

# ---------------------------------------------------------------------------
# Paths & config
# ---------------------------------------------------------------------------

ANALYSIS_DIR = Path(__file__).parent.parent.parent
DATA_DIR     = ANALYSIS_DIR / "data"
FIG_DIR      = ANALYSIS_DIR / "figures" / "02_feature_analysis"
CSV_PATH     = ANALYSIS_DIR / "../backend/data/spotify_songs.csv"

CURRENT_FEATURE_COLS = [
    "danceability", "energy", "loudness", "speechiness",
    "instrumentalness", "liveness", "valence", "tempo",
]
DROPPED_FEATURE_COLS = ["acousticness", "key", "mode", "duration_ms"]
ALL_AUDIO_COLS       = CURRENT_FEATURE_COLS + DROPPED_FEATURE_COLS

HIGH_CORR_THRESHOLD  = 0.4   # flag pairs with |r| above this
GENRE_WEIGHT         = 0.3   # fixed weight applied to genre cols in scree plot

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_data() -> tuple[pd.DataFrame, np.ndarray, np.ndarray, list[str]]:
    """
    Returns
    -------
    df_all       : DataFrame with ALL_AUDIO_COLS + playlist_genre, deduplicated
    minmax_all   : (N, 12) MinMax-scaled array -- 8 current (from ingest) +
                   4 dropped (scaled here); same row order as df_all
    genre_onehot : (N, 6) unweighted one-hot genre matrix
    genre_labels : list of genre column names matching genre_onehot columns
    """
    for p in [DATA_DIR / "features_minmax.npz", DATA_DIR / "genres_onehot.npz"]:
        if not p.exists():
            print(f"ERROR: {p} not found -- run 01_ingest.py first.", file=sys.stderr)
            sys.exit(1)

    # 8 current features, already MinMax-scaled by ingest
    minmax_8 = np.load(DATA_DIR / "features_minmax.npz", allow_pickle=True)["features"]

    # Genre one-hot
    genre_npz    = np.load(DATA_DIR / "genres_onehot.npz", allow_pickle=True)
    genre_onehot = genre_npz["features"]
    genre_labels = genre_npz["cols"].tolist()

    # Full CSV -- for dropped features + genre string label
    csv_df = pd.read_csv(CSV_PATH)
    keep   = ["track_id", "playlist_genre"] + [c for c in ALL_AUDIO_COLS if c in csv_df.columns]
    csv_df = (csv_df[keep]
              .dropna(subset=CURRENT_FEATURE_COLS)
              .drop_duplicates("track_id")
              .reset_index(drop=True))

    # MinMax-scale the 4 dropped features independently
    dropped_present = [c for c in DROPPED_FEATURE_COLS if c in csv_df.columns]
    dropped_raw     = csv_df[dropped_present].fillna(csv_df[dropped_present].median()).to_numpy(dtype=np.float32)
    dropped_mm      = MinMaxScaler().fit_transform(dropped_raw).astype(np.float32)

    # Combine into (N, 12) in ALL_AUDIO_COLS order
    minmax_all = np.concatenate([minmax_8, dropped_mm], axis=1)

    print(f"Loaded {len(csv_df)} tracks")
    print(f"  Audio features : {len(ALL_AUDIO_COLS)} ({len(CURRENT_FEATURE_COLS)} current + {len(dropped_present)} dropped)")
    print(f"  Genre columns  : {len(genre_labels)} {genre_labels}")
    return csv_df, minmax_all, genre_onehot, genre_labels


# ---------------------------------------------------------------------------
# 2a. Distribution plots (audio features only)
# ---------------------------------------------------------------------------

def plot_distributions(df: pd.DataFrame) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    present = [c for c in ALL_AUDIO_COLS if c in df.columns]
    n_cols  = 4
    n_rows  = int(np.ceil(len(present) / n_cols))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(18, n_rows * 3.2))
    axes = axes.flatten()

    for i, col in enumerate(present):
        ax    = axes[i]
        data  = df[col].dropna()
        color = "steelblue" if col in CURRENT_FEATURE_COLS else "lightcoral"
        ax.hist(data, bins=60, density=True, alpha=0.5, color=color, edgecolor="none")
        data.plot.kde(ax=ax, color=color, linewidth=1.5)
        tag = "(current)" if col in CURRENT_FEATURE_COLS else "(dropped)"
        ax.set_title(f"{col} {tag}", fontsize=10)
        ax.tick_params(labelsize=8)

    for j in range(i + 1, len(axes)):
        axes[j].set_visible(False)

    fig.suptitle("Audio Feature Distributions (raw values)\nblue = current  |  red = dropped", fontsize=12, y=1.01)
    fig.tight_layout()
    out = FIG_DIR / "distributions.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out}")


# ---------------------------------------------------------------------------
# 2b. Correlation matrix (12 audio + 6 genre cols)
# ---------------------------------------------------------------------------

def plot_correlation(df: pd.DataFrame, genre_onehot: np.ndarray, genre_labels: list[str]) -> None:
    present_audio = [c for c in ALL_AUDIO_COLS if c in df.columns]

    # Build combined DataFrame for correlation
    genre_df  = pd.DataFrame(genre_onehot, columns=genre_labels, index=df.index)
    combined  = pd.concat([df[present_audio], genre_df], axis=1)
    all_cols  = present_audio + genre_labels
    corr      = combined[all_cols].corr()

    fig, ax = plt.subplots(figsize=(14, 11))
    mask = np.zeros_like(corr, dtype=bool)
    mask[np.triu_indices_from(mask, k=1)] = True
    sns.heatmap(
        corr, mask=mask, annot=True, fmt=".2f", cmap="coolwarm",
        center=0, vmin=-1, vmax=1, linewidths=0.3,
        annot_kws={"size": 7}, ax=ax,
    )
    ax.set_title("Pearson Correlation — 12 audio features + 6 genre cols\n"
                 "grey italic = dropped audio  |  plain = current audio  |  bold = genre", fontsize=11)

    for label in ax.get_xticklabels() + ax.get_yticklabels():
        col = label.get_text()
        label.set_fontsize(8)
        if col in DROPPED_FEATURE_COLS:
            label.set_style("italic")
            label.set_color("grey")
        elif col in genre_labels:
            label.set_weight("bold")
            label.set_color("darkgreen")

    fig.tight_layout()
    out = FIG_DIR / "correlation.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out}")

    # Print high-correlation pairs (audio ↔ audio and audio ↔ genre)
    print(f"\n--- Pairs with |r| > {HIGH_CORR_THRESHOLD} ---")
    pairs = []
    for i in range(len(all_cols)):
        for j in range(i + 1, len(all_cols)):
            r = corr.iloc[i, j]
            if abs(r) > HIGH_CORR_THRESHOLD:
                pairs.append((all_cols[i], all_cols[j], r))
    pairs.sort(key=lambda x: abs(x[2]), reverse=True)
    if pairs:
        for a, b, r in pairs:
            def tag(c):
                if c in DROPPED_FEATURE_COLS: return "(dropped)"
                if c in genre_labels:         return "(genre)"
                return ""
            print(f"  {a}{tag(a):9s}  ↔  {b}{tag(b):9s}   r = {r:+.3f}")
    else:
        print("  None found.")


# ---------------------------------------------------------------------------
# 2c. Variance ranking (12 audio + 6 genre cols)
# ---------------------------------------------------------------------------

def plot_variance(minmax_all: np.ndarray, genre_onehot: np.ndarray, genre_labels: list[str]) -> None:
    audio_vars = minmax_all.var(axis=0)          # (12,)
    genre_vars = genre_onehot.var(axis=0)        # (6,) -- natural variance from genre balance

    all_cols = ALL_AUDIO_COLS + genre_labels
    all_vars = np.concatenate([audio_vars, genre_vars])
    colors   = (["steelblue"] * len(CURRENT_FEATURE_COLS) +
                ["lightcoral"] * len(DROPPED_FEATURE_COLS) +
                ["mediumseagreen"] * len(genre_labels))

    order       = np.argsort(all_vars)           # ascending for barh (bottom = lowest)
    sorted_cols = [all_cols[i] for i in order]
    sorted_vars = all_vars[order]
    sorted_cols_colors = [colors[i] for i in order]

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(sorted_cols, sorted_vars, color=sorted_cols_colors)
    ax.set_xlabel("Variance (MinMax-scaled)")
    ax.set_title("Feature Variance Ranking\nblue = current audio  |  red = dropped audio  |  green = genre")
    ax.axvline(0.02, color="black", linestyle="--", linewidth=0.8, alpha=0.6, label="low-var threshold (0.02)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    out = FIG_DIR / "variance.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out}")

    print("\n--- Variance ranking (MinMax-scaled) ---")
    for col, var in sorted(zip(all_cols, all_vars), key=lambda x: -x[1]):
        if col in DROPPED_FEATURE_COLS: tag = " (dropped)"
        elif col in genre_labels:       tag = " (genre)"
        else:                           tag = ""
        flag = " ← LOW" if var < 0.02 else ""
        print(f"  {col:<20}{tag:<10} {var:.4f}{flag}")


# ---------------------------------------------------------------------------
# 2d. PCA scree -- audio-only vs. audio+genre
# ---------------------------------------------------------------------------

def plot_pca_scree(minmax_all: np.ndarray, genre_onehot: np.ndarray) -> None:
    # (i) 12 audio features only
    pca_audio = PCA().fit(minmax_all)
    ev_audio  = np.cumsum(pca_audio.explained_variance_ratio_) * 100

    # (ii) 12 audio + 6 genre cols weighted at GENRE_WEIGHT, then re-scale rows
    combined     = np.concatenate([minmax_all, genre_onehot * GENRE_WEIGHT], axis=1)
    pca_combined = PCA().fit(combined)
    ev_combined  = np.cumsum(pca_combined.explained_variance_ratio_) * 100

    fig, ax = plt.subplots(figsize=(9, 5))

    x_audio    = np.arange(1, len(ev_audio)    + 1)
    x_combined = np.arange(1, len(ev_combined) + 1)

    ax.plot(x_audio,    ev_audio,    "o-", color="steelblue",    label=f"12 audio features only",          linewidth=1.8, markersize=5)
    ax.plot(x_combined, ev_combined, "s-", color="mediumseagreen", label=f"12 audio + 6 genre (w={GENRE_WEIGHT})", linewidth=1.8, markersize=5)

    # Mark 90% threshold
    ax.axhline(90, color="black", linestyle="--", linewidth=0.8, alpha=0.7, label="90% variance")
    ax.axhline(95, color="grey",  linestyle=":",  linewidth=0.8, alpha=0.7, label="95% variance")

    # Annotate number of PCs needed to hit 90% for each curve
    for ev, color, label in [(ev_audio, "steelblue", "audio"), (ev_combined, "mediumseagreen", "audio+genre")]:
        n90 = int(np.searchsorted(ev, 90)) + 1
        ax.axvline(n90, color=color, linestyle="--", linewidth=0.8, alpha=0.5)
        ax.text(n90 + 0.1, 5, f"{label}: {n90} PCs\n@ 90%", color=color, fontsize=8, va="bottom")

    ax.set_xlabel("Number of principal components")
    ax.set_ylabel("Cumulative explained variance (%)")
    ax.set_title("PCA Scree — Effective Dimensionality of Feature Space")
    ax.set_xlim(1, max(len(ev_audio), len(ev_combined)))
    ax.set_ylim(0, 102)
    ax.legend(fontsize=9)
    fig.tight_layout()
    out = FIG_DIR / "pca_scree.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out}")

    print(f"\n--- PCA: components needed for 90% / 95% variance ---")
    for ev, label in [(ev_audio, "12 audio only"), (ev_combined, f"12 audio + 6 genre (w={GENRE_WEIGHT})")]:
        n90 = int(np.searchsorted(ev, 90)) + 1
        n95 = int(np.searchsorted(ev, 95)) + 1
        print(f"  {label:<40}  90% → {n90} PCs   95% → {n95} PCs")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    df_all, minmax_all, genre_onehot, genre_labels = load_data()

    print("\n[2a] Distribution plots ...")
    plot_distributions(df_all)

    print("\n[2b] Correlation matrix ...")
    plot_correlation(df_all, genre_onehot, genre_labels)

    print("\n[2c] Variance ranking ...")
    plot_variance(minmax_all, genre_onehot, genre_labels)

    print("\n[2d] PCA scree ...")
    plot_pca_scree(minmax_all, genre_onehot)

    print("\nDone. Check figures/02_feature_analysis/ for plots.")
    print("Review high-correlation pairs and scree before running 03_reduction_comparison.py.")


if __name__ == "__main__":
    main()
