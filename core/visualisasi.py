# core/visualisasi.py
"""
Visualisasi model grillage Baros (matplotlib, tanpa dependensi lain).

Isi
---
1. peta_koordinat           koordinat (x, y, z) semua node, termasuk node bearing
2. plot_model_denah         denah node dan elemen per unit (+ bearing, lengan kaku)
3. plot_model_detail        zoom satu tumpuan dengan nomor node/elemen/bearing
4. beban_ekuivalen_nodal    beban nodal ekuivalen konsisten (Fy, Mz) per kasus
5. simpan_beban_ekuivalen   CSV semua kasus x semua node
6. plot_beban_nodal_denah   peta gelembung beban nodal per unit
7. plot_beban_nodal_profil  Fy nodal sepanjang x per garis
8. plot_gaya_total          diagram M, V, T envelope desain seluruh bentang

Sumbu denah: x = memanjang (horizontal), z = melintang (vertikal gambar).
Beban ekuivalen konsisten untuk beban gravitasi merata q (kN/m per panjang
SUMBU, kasus["ele"]) pada elemen miring sepanjang L (sumbu) dengan kemiringan
a: komponen lokal Wy = q cos a dan Wx = q sin a menghasilkan gaya nodal
GLOBAL  Fy_i = Fy_j = q*L/2 (vertikal), Fx = 0 (komponen aksial saling
meniadakan), dan momen  Mz_i = +q cos(a) L^2/12 ; Mz_j = -q cos(a) L^2/12.
"""

import csv
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402
from matplotlib.lines import Line2D                 # noqa: E402
from matplotlib.patches import Polygon              # noqa: E402

WARNA_TIPE = {"hollow": "#dbe9f6", "solid": "#f6e3d3", "tumpuan": "#e4f2d8"}
try:
    from core.nodes import elevasi_model
except Exception:                       # model lama (gelagar datar)
    def elevasi_model(x):
        return 0.0


# ------------------------------------------------------------------
# 1. KOORDINAT
# ------------------------------------------------------------------
def peta_koordinat(node_result, bc_list):
    """(x, y, z) tiap node; y = elevasi alinyemen relatif A1 (m)."""
    coords = {}
    for (i, j), tag in node_result["node_map"].items():
        x = node_result["stasiun"][i]["x"]
        coords[tag] = (x, elevasi_model(x), node_result["z_garis"][j])
    for b in bc_list:
        coords[b["node"]] = (b["x"], elevasi_model(b["x"]), b["z"])
    return coords


def plot_profil_elevasi(supports, section_map, out_png):
    """Elevasi dek (relatif A1) dan kelandaian memanjang per bentang."""
    urut = sorted(supports.items(), key=lambda kv: kv[1]["x"])
    x_min, x_max = section_map[0][0], section_map[-1][1]
    xs = sorted({x_min, x_max} | {d["x"] for _, d in urut}
                | {a for a, _, _ in section_map})
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(17, 5.8), sharex=True,
                                   gridspec_kw={"height_ratios": [2, 1]})
    ax1.plot(xs, [elevasi_model(x) for x in xs], color="#1f4e79", lw=1.6)
    for nm, d in urut:
        y = elevasi_model(d["x"])
        ax1.plot([d["x"]], [y], "^", color="#8e44ad", ms=7)
        ax1.annotate(nm, (d["x"], y), textcoords="offset points",
                     xytext=(0, 7), ha="center", fontsize=8,
                     fontweight="bold", color="#8e44ad")
    ax1.set_ylabel("Elevasi relatif A1 (m)")
    ax1.set_title("Alinyemen vertikal gelagar (elevasi node y = "
                  "nodes.elevasi_model; skala vertikal diperbesar)",
                  fontsize=10)
    ax1.grid(True, alpha=0.3)
    for (n1, d1), (n2, d2) in zip(urut[:-1], urut[1:]):
        g = 100 * (elevasi_model(d2["x"]) - elevasi_model(d1["x"])) \
            / (d2["x"] - d1["x"])
        ax2.hlines(g, d1["x"], d2["x"], color="#c0392b", lw=3)
        ax2.text((d1["x"] + d2["x"]) / 2, g + (0.4 if g >= 0 else -1.0),
                 "{:+.2f}%".format(g), ha="center", fontsize=8)
    ax2.axhline(0, color="k", lw=0.6)
    ax2.set_ylabel("Kelandaian (%)")
    ax2.set_xlabel("x (m)")
    ax2.set_ylim(-7.5, 7.5)
    ax2.grid(True, alpha=0.3)
    fig.tight_layout()
    return _simpan(fig, out_png)


def _rentang_unit(node_result):
    r = {}
    for s in node_result["stasiun"]:
        a, b = r.get(s["unit"], (s["x"], s["x"]))
        r[s["unit"]] = (min(a, s["x"]), max(b, s["x"]))
    return r


def _simpan(fig, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)
    print("Gambar disimpan:", path)
    return path


# ------------------------------------------------------------------
# 2-3. MODEL
# ------------------------------------------------------------------
def _gambar_model(ax, node_result, elemen_result, bc_list, coords,
                  section_map=None, label_node=False, label_elemen=False,
                  ukuran_node=6, x_lim=None):
    z_g = node_result["z_garis"]

    def dalam(x):
        return x_lim is None or x_lim[0] - 0.5 <= x <= x_lim[1] + 0.5

    ej = {}
    for st in node_result["stasiun"]:
        ej.setdefault(round(st["x"], 6), set()).add(st["unit"])

    def geser(x, unit, lebar=0.9):
        """Label stasiun EJ: unit kiri ke kiri, unit kanan ke kanan."""
        us = sorted(ej.get(round(x, 6), {unit}))
        if len(us) < 2:
            return x + 0.1, "left"
        return ((x - 0.1, "right") if unit == us[0] else (x + 0.1, "left"))

    if section_map:
        for x1, x2, tipe in section_map:
            ax.axvspan(x1, x2, color=WARNA_TIPE.get(tipe, "#eeeeee"),
                       alpha=0.8, lw=0, zorder=0)
    for e in elemen_result["memanjang"]:
        ax.plot([e["x1"], e["x2"]], [e["z"], e["z"]], color="#c0392b",
                lw=1.3, zorder=2)
        if label_elemen and dalam((e["x1"] + e["x2"]) / 2):
            ax.text((e["x1"] + e["x2"]) / 2, e["z"] + 0.12, str(e["tag"]),
                    fontsize=5, color="#c0392b", ha="center", clip_on=True)
    for e in elemen_result["melintang"]:
        ax.plot([e["x"], e["x"]], [e["z1"], e["z2"]], color="#27ae60",
                lw=0.8, zorder=2)
        if label_elemen and dalam(e["x"]):
            xl, ha = geser(e["x"], e["unit"])
            ax.text(xl, (e["z1"] + e["z2"]) / 2, str(e["tag"]),
                    fontsize=5, color="#27ae60", rotation=90, va="center",
                    ha="right" if ha == "right" else "left", clip_on=True)
    xs = [coords[t][0] for t in node_result["node_map"].values()]
    zs = [coords[t][2] for t in node_result["node_map"].values()]
    ax.scatter(xs, zs, s=ukuran_node, color="k", zorder=3)
    if label_node:
        for (i, j), tag in node_result["node_map"].items():
            x, _, z = coords[tag]
            if dalam(x):
                xl, ha = geser(x, node_result["stasiun"][i]["unit"])
                ax.text(xl, z + 0.18, str(tag), fontsize=5,
                        color="#1f4e79", clip_on=True, ha=ha)
    for b in bc_list:
        if not dalam(b["x"]):
            continue
        zg = b["z_garis"]
        ax.plot([b["x"], b["x"]], [zg, b["z"]], color="#8e44ad", lw=1.0,
                ls="--", zorder=3)
        ax.scatter([b["x"]], [b["z"]], marker="^", s=40, color="#8e44ad",
                   edgecolor="k", lw=0.4, zorder=4)
        xl, ha = geser(b["x"], b["unit"])
        ax.text(xl, b["z"] - 0.65, b["bearing"], fontsize=6, ha=ha,
                color="#8e44ad", fontweight="bold", zorder=5, clip_on=True)
    ax.set_ylim(min(z_g) - 1.4, max(z_g) + 1.0)
    if x_lim:
        ax.set_xlim(*x_lim)
    ax.set_ylabel("z (m)")
    ax.grid(True, alpha=0.2)


def _legenda_model(ax):
    h = [Line2D([0], [0], color="#c0392b", lw=1.5, label="elemen memanjang"),
         Line2D([0], [0], color="#27ae60", lw=1.0, label="elemen melintang"),
         Line2D([0], [0], marker="o", color="k", lw=0, ms=3, label="node"),
         Line2D([0], [0], marker="^", color="#8e44ad", lw=0, ms=6,
                label="bearing (lengan kaku putus-putus)")]
    for t, c in WARNA_TIPE.items():
        h.append(Polygon([[0, 0]], closed=True, color=c, label=t))
    ax.legend(handles=h, ncol=7, fontsize=7, loc="upper center",
              bbox_to_anchor=(0.5, 1.28), frameon=False)


def plot_model_denah(node_result, elemen_result, bc_list, coords,
                     section_map, out_png, supports=None):
    unit = _rentang_unit(node_result)
    n = len(unit)
    fig, axes = plt.subplots(n, 1, figsize=(17, 3.0 * n + 0.6))
    axes = [axes] if n == 1 else list(axes)
    for ax, (u, (a, b)) in zip(axes, sorted(unit.items())):
        _gambar_model(ax, node_result, elemen_result, bc_list, coords,
                      section_map, x_lim=(a - 1.5, b + 1.5))
        if supports:
            for nm, d in supports.items():
                if a - 0.5 <= d["x"] <= b + 0.5:
                    ax.axvline(d["x"], color="#8e44ad", lw=0.6, ls=":")
                    ax.text(d["x"], max(node_result["z_garis"]) + 0.55, nm,
                            ha="center", fontsize=8, fontweight="bold",
                            color="#8e44ad")
        ax.set_title("Unit {} (x = {:.2f} .. {:.2f} m)".format(u, a, b),
                     fontsize=9, loc="left")
    axes[-1].set_xlabel("x (m)")
    _legenda_model(axes[0])
    fig.suptitle("Model grillage Baros - node dan elemen "
                 "({} node grid, {} memanjang, {} melintang, {} bearing)"
                 .format(len(node_result["node_map"]),
                         len(elemen_result["memanjang"]),
                         len(elemen_result["melintang"]), len(bc_list)),
                 fontsize=11, y=1.02)
    fig.tight_layout()
    return _simpan(fig, out_png)


def plot_model_detail(node_result, elemen_result, bc_list, coords,
                      section_map, x_pusat, setengah, out_png, judul):
    fig, ax = plt.subplots(figsize=(14, 5.2))
    _gambar_model(ax, node_result, elemen_result, bc_list, coords,
                  section_map, label_node=True, label_elemen=True,
                  ukuran_node=18, x_lim=(x_pusat - setengah,
                                         x_pusat + setengah))
    ax.set_xlabel("x (m)")
    ax.set_title(judul, fontsize=10)
    _legenda_model(ax)
    fig.tight_layout()
    return _simpan(fig, out_png)


# ------------------------------------------------------------------
# 4-5. BEBAN NODAL EKUIVALEN
# ------------------------------------------------------------------
def beban_ekuivalen_nodal(kasus, elemen_result):
    """{kasus: {node: {"Fy": kN, "Mz": kNm}}} (Fy + ke atas)."""
    ele = {e["tag"]: e for e in elemen_result["memanjang"]}
    out = {}
    for nama, k in kasus.items():
        d = {}
        for tag, q in k.get("ele", {}).items():
            e = ele.get(tag)
            if e is None:
                continue
            L = e.get("L_aksial", e["x2"] - e["x1"])
            c = e.get("cos_a", 1.0)
            for n, sg in ((e["n1"], +1), (e["n2"], -1)):
                v = d.setdefault(n, {"Fy": 0.0, "Mz": 0.0})
                v["Fy"] += q * L / 2.0
                v["Mz"] += sg * q * c * L * L / 12.0
        for tag, daftar in k.get("pload", {}).items():
            e = ele[tag]
            L = e.get("L_aksial", e["x2"] - e["x1"])
            c, sn = e.get("cos_a", 1.0), e.get("sin_a", 0.0)
            for P, xl in daftar:                 # beban titik vertikal P
                a_, b_ = xl * L, L - xl * L
                py, px = P * c, P * sn
                v1 = py * b_ * b_ * (3 * a_ + b_) / L ** 3
                v2 = py * a_ * a_ * (a_ + 3 * b_) / L ** 3
                f1, f2 = px * b_ / L, px * a_ / L
                for n, vl, fl, mz in (
                        (e["n1"], v1, f1, py * a_ * b_ * b_ / L ** 2),
                        (e["n2"], v2, f2, -py * a_ * a_ * b_ / L ** 2)):
                    t = d.setdefault(n, {"Fy": 0.0, "Mz": 0.0})
                    t["Fy"] += vl * c + fl * sn       # komponen vertikal global
                    t["Mz"] += mz
        for n, fy in k.get("node", {}).items():
            d.setdefault(n, {"Fy": 0.0, "Mz": 0.0})["Fy"] += fy
        out[nama] = d
    return out


def kombinasikan(eq, faktor):
    """Jumlah berbobot beban nodal: faktor = {nama_kasus: f}."""
    d = {}
    for nama, f in faktor.items():
        for n, v in eq[nama].items():
            t = d.setdefault(n, {"Fy": 0.0, "Mz": 0.0})
            t["Fy"] += f * v["Fy"]
            t["Mz"] += f * v["Mz"]
    return d


def simpan_beban_ekuivalen(path_csv, eq, coords):
    os.makedirs(os.path.dirname(path_csv), exist_ok=True)
    with open(path_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["kasus", "node", "x_m", "z_m", "Fy_kN", "Mz_kNm"])
        for nama, d in eq.items():
            for n in sorted(d):
                x, _, z = coords[n]
                w.writerow([nama, n, round(x, 4), round(z, 4),
                            d[n]["Fy"], d[n]["Mz"]])
    print("CSV beban nodal ekuivalen:", path_csv)


def plot_beban_nodal_denah(d, node_result, coords, section_map, out_png,
                           judul):
    unit = _rentang_unit(node_result)
    n = len(unit)
    nilai = [abs(v["Fy"]) for v in d.values()] or [1.0]
    vmax = max(nilai)
    fig, axes = plt.subplots(n, 1, figsize=(17, 2.9 * n + 0.8))
    axes = [axes] if n == 1 else list(axes)
    sc = None
    for ax, (u, (a, b)) in zip(axes, sorted(unit.items())):
        for x1, x2, tipe in section_map:
            ax.axvspan(x1, x2, color=WARNA_TIPE.get(tipe, "#eee"), alpha=0.5,
                       lw=0, zorder=0)
        for t in node_result["node_map"].values():
            x, _, z = coords[t]
            if a - 1 <= x <= b + 1:
                ax.scatter([x], [z], s=3, color="#999999", zorder=1)
        px = [coords[t][0] for t in d if a - 1 <= coords[t][0] <= b + 1
              and abs(d[t]["Fy"]) > 1e-9]
        pz = [coords[t][2] for t in d if a - 1 <= coords[t][0] <= b + 1
              and abs(d[t]["Fy"]) > 1e-9]
        pv = [d[t]["Fy"] for t in d if a - 1 <= coords[t][0] <= b + 1
              and abs(d[t]["Fy"]) > 1e-9]
        if px:
            sc = ax.scatter(px, pz, c=pv, s=[10 + 150 * abs(v) / vmax
                                             for v in pv],
                            cmap="coolwarm", vmin=-vmax, vmax=vmax,
                            edgecolor="k", lw=0.3, zorder=3)
        ax.set_xlim(a - 1.5, b + 1.5)
        ax.set_ylim(min(node_result["z_garis"]) - 1,
                    max(node_result["z_garis"]) + 1)
        ax.set_ylabel("z (m)")
        ax.set_title("Unit {} (x = {:.1f} .. {:.1f} m)".format(u, a, b),
                     fontsize=9, loc="left")
        ax.grid(True, alpha=0.2)
    axes[-1].set_xlabel("x (m)")
    if sc is not None:
        cb = fig.colorbar(sc, ax=axes, shrink=0.8, pad=0.01)
        cb.set_label("Fy nodal ekuivalen (kN), - = ke bawah")
    fig.suptitle(judul, fontsize=11)
    return _simpan(fig, out_png)


def plot_beban_nodal_profil(d, node_result, elemen_result, coords, out_png,
                            judul):
    z_g = node_result["z_garis"]
    by_line = {j: [] for j in range(len(z_g))}
    for (i, j), tag in node_result["node_map"].items():
        by_line[j].append((coords[tag][0], i,
                           d.get(tag, {"Fy": 0.0})["Fy"]))
    fig, ax = plt.subplots(figsize=(17, 4.6))
    cmap = plt.get_cmap("tab10")
    for j, pts in by_line.items():
        pts.sort(key=lambda p: (p[1]))
        ax.plot([p[0] for p in pts], [p[2] for p in pts], marker="o", ms=2.5,
                lw=0.9, color=cmap(j), label="z = {:+.2f} m".format(z_g[j]))
    ax.axhline(0, color="k", lw=0.6)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("Fy nodal ekuivalen (kN)")
    ax.set_title(judul, fontsize=10)
    ax.legend(ncol=len(z_g), fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return _simpan(fig, out_png)


# ------------------------------------------------------------------
# 8. DIAGRAM GAYA TOTAL
# ------------------------------------------------------------------
def plot_gaya_total(prof, supports_unit, out_dir, judul_komb, awalan="desain"):
    """
    prof: {"Mx": {unit: [(x, lo, hi)]}, "Vx": ..., "Tx": ...}
    supports_unit: [(x, nama, unit)]
    Mengembalikan daftar path gambar [M, V, T].
    """
    info = {
        "Mx": ("Momen lentur total M (kN.m), sagging +", "#1f77b4"),
        "Vx": ("Geser total V (kN)", "#d62728"),
        "Tx": ("Torsi total T terhadap sumbu jembatan (kN.m)", "#2ca02c"),
    }
    paths = []
    for kat, (label, warna) in info.items():
        fig, ax = plt.subplots(figsize=(17, 4.4))
        for u, pts in sorted(prof[kat].items()):
            xs = [p[0] for p in pts]
            lo = [p[1] for p in pts]
            hi = [p[2] for p in pts]
            ax.fill_between(xs, lo, hi, color=warna, alpha=0.22, lw=0)
            ax.plot(xs, hi, color=warna, lw=1.0)
            ax.plot(xs, lo, color=warna, lw=1.0)
        for x, nm, _ in supports_unit:
            ax.axvline(x, color="#555555", lw=0.6, ls=":")
            ax.text(x, 1.01, nm, transform=ax.get_xaxis_transform(),
                    ha="center", va="bottom", fontsize=7)
        ax.axhline(0, color="k", lw=0.7)
        ax.set_xlabel("x (m)")
        ax.set_ylabel(label)
        ax.set_title("{} - {}".format(judul_komb, label), fontsize=10,
                     pad=16)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        paths.append(_simpan(fig, os.path.join(
            out_dir, "{}_{}.png".format(kat, awalan))))
    return paths


def simpan_profil_csv(path_csv, prof):
    os.makedirs(os.path.dirname(path_csv), exist_ok=True)
    with open(path_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["unit", "x_m", "M_min", "M_max", "V_min", "V_max",
                    "T_min", "T_max"])
        for u in sorted(prof["Mx"]):
            for a, b, c in zip(prof["Mx"][u], prof["Vx"][u], prof["Tx"][u]):
                w.writerow([u, round(a[0], 4), a[1], a[2], b[1], b[2],
                            c[1], c[2]])
    print("CSV profil gaya dalam total:", path_csv)
