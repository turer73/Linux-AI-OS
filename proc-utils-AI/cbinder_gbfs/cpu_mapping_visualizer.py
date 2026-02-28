"""
cpu_mapping_visualizer.py - CPU core usage heatmap

Auto-detects CPU core count from system (no hard-coded 32 cores).
Supports headless mode (ASCII output) when matplotlib is not available.
"""

import csv
import numpy as np
import os
import json
from collections import defaultdict
import psutil

DATASET_FILE = "/var/AI-stump/ai_dataset.csv"


def get_cpu_count():
    """Detect actual CPU core count from system."""
    return psutil.cpu_count(logical=True)


def parse_cpu_data():
    core_usage_map = defaultdict(list)

    if not os.path.exists(DATASET_FILE):
        raise FileNotFoundError("Veri dosyasi bulunamadi: " + DATASET_FILE)

    with open(DATASET_FILE, "r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                cores = json.loads(row["assigned_cores"])
                usage = float(row["cpu_usage"])
                for core in cores:
                    core_usage_map[core].append(usage)
            except (ValueError, KeyError, json.JSONDecodeError):
                continue
    return core_usage_map


def generate_ascii_heatmap(core_usage_map, cpu_count):
    """ASCII heatmap for headless / low-resource systems."""
    print(f"\n=== AI-CPU Kullanim Haritasi ({cpu_count} thread) ===\n")
    for i in range(cpu_count):
        values = core_usage_map.get(i, [])
        avg = round(np.mean(values), 1) if values else 0.0

        # Simple bar chart
        bar_len = int(avg / 2)  # 50 chars = 100%
        bar = "#" * bar_len + "." * (50 - bar_len)
        print(f"  CPU{i:<2d} [{bar}] {avg:5.1f}%")
    print()


def generate_heatmap(core_usage_map, cpu_count):
    """Graphical heatmap (requires matplotlib + seaborn)."""
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        print("[CPU Visualizer] matplotlib/seaborn yuklu degil, ASCII mod kullaniliyor.")
        generate_ascii_heatmap(core_usage_map, cpu_count)
        return

    core_values = []
    for i in range(cpu_count):
        values = core_usage_map.get(i, [])
        core_values.append(round(np.mean(values), 2) if values else 0.0)

    # Auto grid: prefer 2 columns for small CPUs, 4/8 for larger
    if cpu_count <= 4:
        cols = 2
    elif cpu_count <= 16:
        cols = 4
    else:
        cols = 8

    rows = (cpu_count + cols - 1) // cols
    padded = core_values + [0.0] * (rows * cols - len(core_values))
    matrix = np.array(padded).reshape((rows, cols))

    fig_width = max(4, cols * 1.5)
    fig_height = max(3, rows * 1.2)
    plt.figure(figsize=(fig_width, fig_height))
    sns.heatmap(matrix, annot=True, cmap="YlOrRd", cbar=True, linewidths=0.5,
                vmin=0, vmax=100)
    plt.title(f"AI-CPU Kullanim Isi Haritasi ({cpu_count} thread)")
    plt.xlabel("Core Bloklari")
    plt.ylabel("CPU Satirlari")
    plt.tight_layout()
    plt.show()


def main():
    cpu_count = get_cpu_count()
    print(f"[CPU Visualizer] Sistem: {cpu_count} logical CPU tespit edildi")
    print("[CPU Visualizer] CPU kullanim verileri okunuyor...")

    core_usage = parse_cpu_data()
    generate_heatmap(core_usage, cpu_count)


if __name__ == "__main__":
    main()
