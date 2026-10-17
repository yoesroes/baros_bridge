# core/nodes.py
"""
Modul Node untuk Jembatan Baros (Grillage 3D).
Satuan: m.  Model: ndm = 3, ndf = 6.

STATUS: [AKTIF] langkah pertama pipeline:
    nodes -> elements -> boundary_condition -> (loads) -> analysis -> output

Generate node grillage:
- x = memanjang (dari SECTION_MAP + support)
- y = 0 (bidang netral; grillage planar, semua garis satu elevasi)
- z = transversal (5 garis, = centroid strip tributary tipe hollow)

Expansion joint (EJ) di P2 dan P7 MEMUTUS gelagar: pada x tersebut dibuat
DUA stasiun (sisi kiri 'L' = ujung unit sebelumnya, sisi kanan 'R' = awal
unit berikutnya) dengan node terpisah pada koordinat yang sama. Tidak ada
elemen memanjang di antara keduanya. Hasilnya 3 unit menerus:
    unit 0 : A1 - P2
    unit 1 : P2 - P7
    unit 2 : P7 - A2

Jumlah node dan elemen mengikuti data (jangan ditulis tetap di docstring).

Penomoran tag node: berurutan 1..n, stasiun demi stasiun (x naik), di tiap
stasiun garis j = 0..4 (z naik). Pemetaan tag ada di node_map[(i, j)].

CATATAN AUDIT
-------------
1. Posisi z node SATU set (centroid strip hollow) dipakai untuk SEMUA tipe
   section; properti tiap tipe dihitung terhadap posisi itu
   (section_strips.properti_garis(..., z_node=Z_GARIS)).
2. Stasiun dibentuk dari SELURUH x1/x2 SECTION_MAP + x SUPPORTS + grid posisi
   BGT maksimum 1 m (dibulatkan 6 desimal). Dua x yang berbeda < 1e-6 m
   akan dianggap sama.
3. Stasiun dibuat juga di overhang (x = -0.27 dan x > x A2); tidak ada
   tumpuan di sana.
4. EJ_SUPPORTS = ("P2", "P7") tertulis tetap di sini; EXPANSION_JOINTS di
   project_data (EJ.1-EJ.4) tidak dibaca.
5. Menjalankan langsung: python -m core.nodes (dari root repo).

Referensi:
- project_data.SECTION_MAP
- project_data.SUPPORTS
"""

import math

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

try:
    from project import project_data as pdata
except ImportError:
    import project_data as pdata

# ============================================================
# 1. KONSTANTA
# ============================================================

Z_GARIS_REF = Z_GARIS_DEFAULT
BGT_GRID_MAX_SPACING = 1.0  # m; resolusi posisi BGT pada arah memanjang

# Posisi FISIK node grillage = centroid tributary strip (tipe hollow).
# Z_GARIS_REF hanya referensi PEMBATAS tributary untuk section_strips;
# keduanya dibawa terpisah (z_ref vs z_garis) ke elements.py.
# JANGAN pakai Z_GARIS sebagai z_ref (menggeser batas strip).
Z_GARIS = z_garis_centroid(
    tipe="hollow",
    z_garis_ref=Z_GARIS_REF,)

N_Z = len(Z_GARIS)
Y_BIDANG = 0.0   # bidang netral

def elevasi_model(x):
    """Elevasi node relatif terhadap elevasi A1, interpolasi antar-support."""
    supports = sorted(
        (float(v["x"]), float(v["y"]))
        for v in pdata.SUPPORTS.values()
    )

    datum = float(pdata.SUPPORTS["A1"]["y"])

    if x <= supports[0][0]:
        return supports[0][1] - datum

    if x >= supports[-1][0]:
        return supports[-1][1] - datum

    for (x0, y0), (x1, y1) in zip(supports, supports[1:]):
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0)
            return y0 + t * (y1 - y0) - datum

    raise ValueError("Elevasi tidak ditemukan untuk x={}".format(x))

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

        # Tambah stasiun maksimum tiap 1 m di dalam setiap bentang. BGT
        # ditempatkan pada stasiun ini agar posisi kritis dapat disapu tanpa
        # menggantungkan hasil pada batas segmen penampang yang jarang.
        support_x = sorted(float(v["x"]) for v in supports.values())
        for x0, x1 in zip(support_x, support_x[1:]):
            n_sub = int(math.ceil((x1 - x0) / BGT_GRID_MAX_SPACING))
            for i in range(1, n_sub):
                x_set.add(round(x0 + (x1 - x0) * i / n_sub, 6))

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
            ops.node(tag, st["x"], elevasi_model(st["x"]), z)
            node_map[(i, j)] = tag

    return node_map, x_index


def buat_semua_node(section_map, supports=None, z_garis=Z_GARIS,
                    ej_supports=EJ_SUPPORTS, z_ref=Z_GARIS_REF):
    """
    Buat semua node grillage.

    Returns
    -------
    dict : {
        "node_map": {(i, j): tag},
        "x_index": {x: [i, ...]},
        "x_sorted": list x per stasiun (EJ muncul dua kali),
        "stasiun": list of dict,
        "z_garis": tuple (posisi fisik node),
        "z_ref": tuple (referensi pembatas tributary strip),
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
        "z_ref": tuple(z_ref),
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
    print("  z garis (node)   : {}".format(z_garis))
    print("  z_ref (tributary): {}".format(result["z_ref"]))

    y_node = [ops.nodeCoord(tag)[1] for tag in ops.getNodeTags()]
    print("  y (relatif A1)   : {:.4f} -> {:.4f} m".format(
        min(y_node), max(y_node)))

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
        coord = ops.nodeCoord(tag)
        print("{:>6d} {:>10.4f} {:>10.4f} {:>10.4f} {:>6d}".format(
            tag, coord[0], coord[1], coord[2], stasiun[i]["unit"]))
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
    # Jalankan dari root repo:  python -m core.nodes
    from project import project_data as pdata

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
