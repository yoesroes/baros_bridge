# plot_mapping.py
"""
Visualisasi mapping penampang sepanjang jembatan Baros.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle
from section_mapping import SECTION_MAP
from support_data import SUPPORTS

# Warna per tipe penampang
COLORS = {
    "tumpuan":  "#d62728",   # merah
    "hollow":   "#2ca02c",   # hijau
    "blockout": "#ff7f0e",   # oranye
    "tipikal":  "#1f77b4",   # biru
}

# ============================================================
# FIGURE
# ============================================================
fig, ax = plt.subplots(figsize=(18, 6))

# ============================================================
# PLOT SEGMEN PENAMPANG
# ============================================================
for x1, x2, tipe in SECTION_MAP:
    ax.add_patch(Rectangle(
        (x1, 0), x2 - x1, 0.5,
        facecolor=COLORS.get(tipe, "grey"),
        edgecolor="black", linewidth=0.5,
    ))

# ============================================================
# PLOT SUPPORT
# ============================================================
for name, data in SUPPORTS.items():
    x = data["x"]
    # Garis vertikal
    ax.axvline(x=x, color="black", linestyle="--", linewidth=1, alpha=0.7)
    # Label
    ax.text(x, 0.7, name, ha="center", va="bottom",
            fontsize=10, fontweight="bold")

# ============================================================
# PLOT EXPANSION JOINT
# ============================================================
from support_data import EXPANSION_JOINTS
for ej, support in EXPANSION_JOINTS.items():
    x = SUPPORTS[support]["x"]
    ax.axvline(x=x, color="blue", linestyle="-", linewidth=2, alpha=0.5)
    ax.text(x, -0.15, ej, ha="center", va="top",
            fontsize=8, color="blue", rotation=90)

# ============================================================
# LABEL SUMBU
# ============================================================
ax.set_xlim(-2, 207)
ax.set_ylim(-0.3, 1.0)
ax.set_xlabel("Posisi x (m)", fontsize=12)
ax.set_title("Mapping Penampang Jembatan Baros (A1 → A2)",
             fontsize=14, fontweight="bold")

# Sembunyikan sumbu y
ax.set_yticks([])

# Grid
ax.grid(True, axis="x", linestyle=":", alpha=0.5)

# ============================================================
# LEGENDA
# ============================================================
legend_patches = [
    mpatches.Patch(color=COLORS["tumpuan"], label="Tumpuan (diafragma)"),
    mpatches.Patch(color=COLORS["hollow"], label="Hollow"),
    mpatches.Patch(color=COLORS["blockout"], label="Blockout"),
    mpatches.Patch(color=COLORS["tipikal"], label="Tipikal"),
    plt.Line2D([0], [0], color="blue", linewidth=2,
               label="Expansion Joint"),
]
ax.legend(handles=legend_patches, loc="upper right",
          fontsize=10, framealpha=0.9)

plt.tight_layout()
plt.savefig("mapping_penampang.png", dpi=150)
plt.show()

print("Visualisasi disimpan: mapping_penampang.png")