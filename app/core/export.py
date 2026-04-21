"""
Export module — save processing results to disk.
"""

import os
import json
import datetime
import numpy as np
import matplotlib
matplotlib.use("Agg")  # non-interactive backend for saving
import matplotlib.pyplot as plt


def save_results(
    output_dir: str,
    sample_name: str,
    concentrations: np.ndarray,
    chromophore_names: list,
    derived: dict,
    rmse_map: np.ndarray,
    diagnostics: dict,
    chrom_scales: dict = None,
    derived_scales: dict = None,
):
    """
    Save all results for one sample.

    Creates:
        <output_dir>/<sample_name>/
            maps/          – PNG images with colorbars
            arrays/        – .npy files
            metadata.json  – processing metadata
    """
    sample_dir = os.path.join(output_dir, sample_name)
    maps_dir = os.path.join(sample_dir, "maps")
    arrays_dir = os.path.join(sample_dir, "arrays")
    os.makedirs(maps_dir, exist_ok=True)
    os.makedirs(arrays_dir, exist_ok=True)

    # --- Save chromophore maps ---
    n_chrom = len(chromophore_names)
    all_names = chromophore_names.copy()
    if concentrations.shape[2] > n_chrom:
        all_names.append("background")

    for i, name in enumerate(all_names):
        data = concentrations[:, :, i]
        vmin, vmax = chrom_scales.get(name, (None, None)) if chrom_scales else (None, None)
        finite = data[np.isfinite(data)]
        if finite.size > 0:
            mean_val = finite.mean()
            median_val = float(np.median(finite))
            display_title = f"{name}\nμ={mean_val:.3e}, med={median_val:.3e}"
        else:
            display_title = name
        _save_map_png(data, display_title, name, maps_dir, vmin=vmin, vmax=vmax)
        np.save(os.path.join(arrays_dir, f"{name}.npy"), data)

    # --- Save derived maps ---
    for name, data in derived.items():
        vmin, vmax = derived_scales.get(name, (None, None)) if derived_scales else (None, None)
        _save_map_png(data, _format_map_title(name, data), name, maps_dir, vmin=vmin, vmax=vmax)
        np.save(os.path.join(arrays_dir, f"{name}.npy"), data)

    # --- Save RMSE map ---
    vmin, vmax = derived_scales.get("RMSE", (None, None)) if derived_scales else (None, None)
    _save_map_png(rmse_map, _format_map_title("RMSE", rmse_map), "RMSE", maps_dir, cmap="hot", vmin=vmin, vmax=vmax)
    np.save(os.path.join(arrays_dir, "RMSE.npy"), rmse_map)

    # --- Save metadata ---
    meta = {
        "sample_name": sample_name,
        "timestamp": datetime.datetime.now().isoformat(),
        "chromophores": chromophore_names,
        "include_background": "background" in all_names,
        "image_shape": list(concentrations.shape[:2]),
        "diagnostics": {
            k: v for k, v in diagnostics.items() if k != "warnings"
        },
        "warnings": diagnostics.get("warnings", []),
    }
    with open(os.path.join(sample_dir, "metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)


def _save_map_png(
    data: np.ndarray,
    title: str,
    filename: str,
    output_dir: str,
    cmap: str = "viridis",
    vmin: float = None,
    vmax: float = None,
):
    """Save a 2D array as a PNG image with colorbar."""
    fig, ax = plt.subplots(1, 1, figsize=(5, 4))
    im = ax.imshow(data, cmap=cmap, aspect="equal", vmin=vmin, vmax=vmax)
    ax.set_title(title, fontsize=12)
    ax.set_xticks([])
    ax.set_yticks([])
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(
        os.path.join(output_dir, f"{filename}.png"),
        dpi=150, bbox_inches="tight",
    )
    plt.close(fig)


def _format_map_title(name: str, data: np.ndarray) -> str:
    """Format map title with finite-value mean and median statistics."""
    finite = data[np.isfinite(data)]
    if finite.size == 0:
        return name

    mean_val = float(finite.mean())
    median_val = float(np.median(finite))
    return f"{name}\nμ={mean_val:.3e}, med={median_val:.3e}"
