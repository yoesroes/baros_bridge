# core/nodes.py
"""
Modul Node untuk Jembatan Baros (Grillage 3D).
Satuan: m.

Generate node grillage:
- x = memanjang (dari SECTION_MAP + support)
- y = 0 (bidang netral)
- z = transversal (5 garis)

Expansion joint (EJ) di P2 dan P7 MEMUTUS gelagar: pada x tersebut dibuat
DUA stasiun (sisi kiri 'L' = ujung unit sebelumnya, sisi kanan 'R' = awal
unit berikutnya) dengan node terpisah pada koordinat yang sama. Tidak ada
elemen memanjang di antara keduanya. Hasilnya 3 unit menerus:
    unit 0 : A1 - P2
    unit 1 : P2 - P7
    unit 2 : P7 - A2

Jumlah node dan elemen mengikuti data (jangan ditulis tetap di docstring).

Referensi:
- project_data.SECTION_MAP
- project_data.SUPPORTS
"""

import os
import sys
import openseespy.opensees as ops

try:
    from core.section_strips import (
        Z_GARIS_DEFAULT,
        z_garis_centroid,
    )
except ImportError:
    from section_strips import (
        Z_GARIS_DEFAULT,
        z_garis_centroid,
    )


# ============================================================
# 1. KONSTANTA
# ============================================================

Z_GARIS_REF = Z_GARIS_DEFAULT

# Posisi aktual garis grillage = centroid tributary strip.
# Boundary tetap berasal dari Z_GARIS_REF.
Z_GARIS = z_garis_centroid(
    tipe="hollow",
    z_garis_ref=Z_GARIS_REF,)

N_Z = len(Z_GARIS)
Y_BIDANG = 0.0   # bidang netral

EJ_SUPPORTS = ("P2", "P7")   # support dengan expansion joint (gelagar putus)


# ============================================================
# 2. FUNGSI
# ============================================================

def kumpulkan_x_unik(section_map, supports=None):
    """
    Kumpulkan x unik dari SECTION_MAP + supports.

    Returns
    -------
    x_sorted : list
        List x terurut (tanpa duplikasi EJ)
    """
    x_set = set()

    for x1, x2, tipe in section_map:
        x_set.add(round(x1, 6))
        x_set.add(round(x2, 6))

    if supports:
        for nama, data in supports.items():
            x_set.add(round(data["x"], 6))

    return sorted(x_set)


def buat_stasiun(x_unik, supports=None, ej_supports=EJ_SUPPORTS):
    """
    Bentuk daftar stasiun. Pada x yang berupa EJ dibuat dua stasiun.

    Returns
    -------
    stasiun : list of dict {x, unit, sisi}
        sisi: 'L' / 'R' untuk stasiun EJ, None untuk stasiun biasa.
    """
    x_ej = set()
    if supports:
        for nama in ej_supports:
            if nama in supports:
                x_ej.add(round(supports[nama]["x"], 6))
            else:
                print("WARNING: EJ support {} tidak ada di SUPPORTS".format(nama))

    stasiun = []
    unit = 0
    for x in x_unik:
        if x in x_ej:
            stasiun.append({"x": x, "unit": unit, "sisi": "L"})
            unit += 1
            stasiun.append({"x": x, "unit": unit, "sisi": "R"})
        else:
            stasiun.append({"x": x, "unit": unit, "sisi": None})
    return stasiun


def buat_node(stasiun, z_garis=Z_GARIS):
    """
    Buat node di OpenSees.

    Returns
    -------
    node_map : dict  {(i, j): tag}   i = indeks stasiun, j = indeks garis
    x_index  : dict  {x: [indeks stasiun]}  (2 indeks untuk stasiun EJ)
    """
    node_map = {}
    x_index = {}
    tag = 0

    for i, st in enumerate(stasiun):
        x_index.setdefault(st["x"], []).append(i)
        for j, z in enumerate(z_garis):
            tag += 1
            ops.node(tag, st["x"], Y_BIDANG, z)
            node_map[(i, j)] = tag

    return node_map, x_index


def buat_semua_node(section_map, supports=None, z_garis=Z_GARIS,
                    ej_supports=EJ_SUPPORTS):
    """
    Buat semua node grillage.

    Returns
    -------
    dict : {
        "node_map": {(i, j): tag},
        "x_index": {x: [i, ...]},
        "x_sorted": list x per stasiun (EJ muncul dua kali),
        "stasiun": list of dict,
        "z_garis": tuple,
        "n_node": int,
        "n_unit": int,
    }
    """
    x_unik = kumpulkan_x_unik(section_map, supports)
    stasiun = buat_stasiun(x_unik, supports, ej_supports)
    node_map, x_index = buat_node(stasiun, z_garis)

    return {
        "node_map": node_map,
        "x_index": x_index,
        "x_sorted": [s["x"] for s in stasiun],
        "stasiun": stasiun,
        "z_garis": z_garis,
        "n_node": len(stasiun) * len(z_garis),
        "n_unit": stasiun[-1]["unit"] + 1,
    }


# ============================================================
# 3. OUTPUT INFORMATIF
# ============================================================

def print_node_info(result):
    """Cetak info node."""
    stasiun = result["stasiun"]
    z_garis = result["z_garis"]

    print("=" * 65)
    print("INFO NODE GRILLAGE")
    print("=" * 65)
    print("  Jumlah stasiun   : {} (x unik {} + {} stasiun EJ ganda)".format(
        len(stasiun), len(result["x_index"]),
        len(stasiun) - len(result["x_index"])))
    print("  Jumlah unit      : {}".format(result["n_unit"]))
    print("  Jumlah z garis   : {}".format(len(z_garis)))
    print("  Total node       : {}".format(result["n_node"]))
    print()
    print("  x range          : {:.4f} -> {:.4f} m".format(
        stasiun[0]["x"], stasiun[-1]["x"]))
    print("  z garis          : {}".format(z_garis))
    print("  y (bidang)       : {:.2f} m".format(Y_BIDANG))
    ej = [(s["x"], s["unit"]) for s in stasiun if s["sisi"]]
    print("  Stasiun EJ (x, unit): {}".format(ej))
    print()


def print_node_sample(result, n=15):
    """Cetak sample node."""
    node_map = result["node_map"]
    stasiun = result["stasiun"]
    z_garis = result["z_garis"]

    print("=" * 65)
    print("SAMPLE NODE ({} pertama)".format(n))
    print("=" * 65)
    print("{:>6s} {:>10s} {:>10s} {:>10s} {:>6s}".format(
        "Tag", "x (m)", "y (m)", "z (m)", "Unit"))
    print("-" * 65)

    count = 0
    for (i, j), tag in sorted(node_map.items()):
        if count >= n:
            break
        print("{:>6d} {:>10.4f} {:>10.4f} {:>10.4f} {:>6d}".format(
            tag, stasiun[i]["x"], Y_BIDANG, z_garis[j], stasiun[i]["unit"]))
        count += 1
    print()


def print_node_statistik(result):
    """Cetak statistik node."""
    stasiun = result["stasiun"]
    z_garis = result["z_garis"]
    x0, x1 = stasiun[0]["x"], stasiun[-1]["x"]

    print("=" * 65)
    print("STATISTIK NODE")
    print("=" * 65)
    print("  Panjang total    : {:.4f} m".format(x1 - x0))
    print("  Lebar total      : {:.4f} m".format(z_garis[-1] - z_garis[0]))
    print("  Jarak z          : {}".format(
        [round(z_garis[i + 1] - z_garis[i], 2) for i in range(len(z_garis) - 1)]))
    for u in range(result["n_unit"]):
        xs = [s["x"] for s in stasiun if s["unit"] == u]
        print("  Unit {} : x = {:.4f} -> {:.4f} m (L = {:.4f} m)".format(
            u, xs[0], xs[-1], xs[-1] - xs[0]))
    print()


# ============================================================
# 4. MAIN (TEST)
# ============================================================

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(os.path.join(BASE_DIR, "Clean"))
    sys.path.append(os.path.join(BASE_DIR, "core"))

    import project_data as pdata

    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 6)

    result = buat_semua_node(pdata.SECTION_MAP, pdata.SUPPORTS, Z_GARIS)

    print_node_info(result)
    print_node_sample(result, n=15)
    print_node_statistik(result)

    print("=" * 65)
    print("CEK NODE DI OPENSEES")
    print("=" * 65)
    node_tags = ops.getNodeTags()
    print("  Total node di OpenSees: {} (harus {})".format(
        len(node_tags), result["n_node"]))
    last_tag = node_tags[-1]
    print("  Koordinat node {}: {}".format(last_tag, ops.nodeCoord(last_tag)))
    print()
    print("SELESAI")
