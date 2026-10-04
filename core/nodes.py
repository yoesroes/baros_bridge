# core/nodes.py
"""
Modul Node untuk Jembatan Baros (Grillage 3D).
Satuan: m.

Generate node grillage:
- x = memanjang (dari SECTION_MAP)
- y = 0 (bidang netral)
- z = transversal (5 garis)

Total: 40 x × 5 z = 200 node.

Referensi:
- project_data.SECTION_MAP
- loads.Z_GARIS
"""

import os
import sys
import openseespy.opensees as ops


# ============================================================
# 1. KONSTANTA
# ============================================================

Z_GARIS = (-5.0, -3.5, 0.0, 3.5, 5.0)
N_Z = len(Z_GARIS)
Y_BIDANG = 0.0   # bidang netral


# ============================================================
# 2. FUNGSI
# ============================================================

def kumpulkan_x_unik(section_map):
    """
    Kumpulkan semua x unik dari SECTION_MAP.
    
    Parameters
    ----------
    section_map : list
        List of (x1, x2, tipe)
    
    Returns
    -------
    x_sorted : list
        List x terurut
    """
    x_set = set()
    for x1, x2, tipe in section_map:
        x_set.add(round(x1, 6))
        x_set.add(round(x2, 6))
    return sorted(x_set)


def buat_node(x_sorted, z_garis=Z_GARIS):
    """
    Buat node di OpenSees.
    
    Parameters
    ----------
    x_sorted : list
        List x (m)
    z_garis : tuple
        List z (m)
    
    Returns
    -------
    node_map : dict
        {(i, j): tag} — mapping index ke tag
    x_index : dict
        {x: i} — mapping x ke index
    """
    node_map = {}
    x_index = {}
    tag = 0
    
    for i, x in enumerate(x_sorted):
        x_index[round(x, 6)] = i
        for j, z in enumerate(z_garis):
            tag += 1
            ops.node(tag, x, Y_BIDANG, z)
            node_map[(i, j)] = tag
    
    return node_map, x_index


def buat_semua_node(section_map, z_garis=Z_GARIS):
    """
    Buat semua node grillage.
    
    Parameters
    ----------
    section_map : list
        List of (x1, x2, tipe)
    z_garis : tuple
        List z (m)
    
    Returns
    -------
    dict : {
        "node_map": {(i, j): tag},
        "x_index": {x: i},
        "x_sorted": list,
        "z_garis": tuple,
        "n_node": int,
    }
    """
    x_sorted = kumpulkan_x_unik(section_map)
    node_map, x_index = buat_node(x_sorted, z_garis)
    
    return {
        "node_map": node_map,
        "x_index": x_index,
        "x_sorted": x_sorted,
        "z_garis": z_garis,
        "n_node": len(x_sorted) * len(z_garis),
    }


# ============================================================
# 3. OUTPUT INFORMATIF
# ============================================================

def print_node_info(result):
    """Cetak info node."""
    x_sorted = result["x_sorted"]
    z_garis = result["z_garis"]
    
    print("=" * 65)
    print("INFO NODE GRILLAGE")
    print("=" * 65)
    print("  Jumlah x unik    : {}".format(len(x_sorted)))
    print("  Jumlah z garis   : {}".format(len(z_garis)))
    # Sebelum print koordinat
    print("  Total node: {}".format(len(ops.getNodeTags())))
    print("  Node terakhir: {}".format(ops.getNodeTags()[-1]))

    # Akses node terakhir
    last_tag = ops.getNodeTags()[-1]
    print("  Koordinat node {}: {}".format(last_tag, ops.nodeCoord(last_tag)))
    print()
    print("  x range          : {:.4f} → {:.4f} m".format(
        x_sorted[0], x_sorted[-1]))
    print("  z garis          : {}".format(z_garis))
    print("  y (bidang)       : {:.2f} m".format(Y_BIDANG))
    print()


def print_node_sample(result, n=10):
    """Cetak sample node."""
    node_map = result["node_map"]
    x_sorted = result["x_sorted"]
    z_garis = result["z_garis"]
    
    print("=" * 65)
    print("SAMPLE NODE ({} pertama)".format(n))
    print("=" * 65)
    print("{:>6s} {:>10s} {:>10s} {:>10s}".format(
        "Tag", "x (m)", "y (m)", "z (m)"))
    print("-" * 65)
    
    count = 0
    for (i, j), tag in node_map.items():
        if count >= n:
            break
        print("{:>6d} {:>10.4f} {:>10.4f} {:>10.4f}".format(
            tag, x_sorted[i], Y_BIDANG, z_garis[j]))
        count += 1
    print()


def print_node_statistik(result):
    """Cetak statistik node."""
    x_sorted = result["x_sorted"]
    z_garis = result["z_garis"]
    
    print("=" * 65)
    print("STATISTIK NODE")
    print("=" * 65)
    print("  Panjang total    : {:.4f} m".format(x_sorted[-1] - x_sorted[0]))
    print("  Lebar total      : {:.4f} m".format(z_garis[-1] - z_garis[0]))
    print("  Jarak x rata2    : {:.4f} m".format(
        (x_sorted[-1] - x_sorted[0]) / (len(x_sorted) - 1)))
    print("  Jarak z          : {}".format(
        [round(z_garis[i+1] - z_garis[i], 2) for i in range(len(z_garis)-1)]))
    print()


# ============================================================
# 4. MAIN (TEST)
# ============================================================

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(os.path.join(BASE_DIR, "Clean"))
    import project_data as pdata
    
    # Buat model
    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 6)
    
    # Buat node
    result = buat_semua_node(pdata.SECTION_MAP, Z_GARIS)
    
    # Print info
    print_node_info(result)
    print_node_sample(result, n=10)
    print_node_statistik(result)
    
    # Cek node di OpenSees
    print("=" * 65)
    print("CEK NODE DI OPENSEES")
    print("=" * 65)
    node_tags = ops.getNodeTags()
    print("  Total node di OpenSees: {}".format(len(node_tags)))
    print("  Node pertama: {}".format(node_tags[0]))
    print("  Node terakhir: {}".format(node_tags[-1]))
    
    # Cek koordinat beberapa node
    print()
    print("  Koordinat node 1:  {}".format(ops.nodeCoord(1)))
    print("  Koordinat node 5:  {}".format(ops.nodeCoord(5)))
    print("  Koordinat node 6:  {}".format(ops.nodeCoord(6)))
    last_tag = ops.getNodeTags()[-1]
    print("  Koordinat node {}: {}".format(last_tag, ops.nodeCoord(last_tag)))    
    print()
    print("SELESAI")