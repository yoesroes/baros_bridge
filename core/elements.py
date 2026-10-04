# core/elements.py
"""
Modul Elemen untuk Jembatan Baros (Grillage 3D).
Satuan: kN, m, kPa.

Elemen:
- Memanjang (arah x): 39 segmen × 5 z = 195 elemen
- Melintang (arah z): 39 x × 4 z = 156 elemen
- Total: 351 elemen

Tipe: elasticBeamColumn (deck elastis)
Section: dari sections.py (per segmen)
Transformasi:
- Memanjang: vecxz = (0, 0, 1)
- Melintang: vecxz = (1, 0, 0)

Referensi:
- core/nodes.py
- core/sections.py
- project_data.py
"""

import os
import sys
import openseespy.opensees as ops


# ============================================================
# 1. KONSTANTA
# ============================================================

E_BOX = 30.27e6     # kPa (modulus elastis beton box)
G_BOX = E_BOX / (2.0 * (1.0 + 0.2))   # kPa (Poisson 0.2)

TAG_MEMANJANG_START = 1
TAG_MELINTANG_START = 1001

TRANSF_MEMANJANG = 1   # vecxz = (0, 0, 1)
TRANSF_MELINTANG = 2   # vecxz = (1, 0, 0)


# ============================================================
# 2. TRANSFORMASI GEOMETRI
# ============================================================

def define_geom_transf():
    """Definisikan 2 geomTransf untuk 2 arah."""
    ops.geomTransf('Linear', TRANSF_MEMANJANG, 0.0, 0.0, 1.0)
    ops.geomTransf('Linear', TRANSF_MELINTANG, 1.0, 0.0, 0.0)


# ============================================================
# 3. FUNGSI ELEMEN
# ============================================================

def buat_elemen_memanjang(node_map, x_sorted, z_garis,
                          section_map, box_sections,
                          E=E_BOX, G=G_BOX):
    """
    Buat elemen memanjang (arah x).
    
    Parameters
    ----------
    node_map : dict
        {(i, j): tag}
    x_sorted : list
        List x
    z_garis : tuple
        List z
    section_map : list
        List of (x1, x2, tipe)
    box_sections : dict
        Properti section
    E, G : float
        Modulus elastis & geser
    
    Returns
    -------
    elemen_list : list of dict
        Info elemen memanjang
    """
    elemen_list = []
    ele_tag = TAG_MEMANJANG_START
    
    n_x = len(x_sorted)
    n_z = len(z_garis)
    
    for j in range(n_z):           # loop z (5)
        for i in range(n_x - 1):   # loop x (39)
            # Node
            n1 = node_map[(i, j)]
            n2 = node_map[(i + 1, j)]
            
            # Section (dari segmen)
            x1 = x_sorted[i]
            x2 = x_sorted[i + 1]
            tipe = cari_tipe(x1, x2, section_map)
            sec = box_sections[tipe]
            
            A = sec["A"]
            Ix = sec["Ix"]
            Iy = sec["Iy"]
            J = get_J(tipe, box_sections)
            
            # Buat elemen
            ops.element('elasticBeamColumn', ele_tag,
                        n1, n2, A, E, G, J, Iy, Ix,
                        TRANSF_MEMANJANG)
            
            elemen_list.append({
                "tag": ele_tag,
                "tipe_elemen": "memanjang",
                "n1": n1,
                "n2": n2,
                "x1": x1,
                "x2": x2,
                "z": z_garis[j],
                "tipe_section": tipe,
                "A": A,
                "Ix": Ix,
                "Iy": Iy,
                "J": J,
            })
            
            ele_tag += 1
    
    return elemen_list


def buat_elemen_melintang(node_map, x_sorted, z_garis,
                          section_map, box_sections,
                          E=E_BOX, G=G_BOX):
    """
    Buat elemen melintang (arah z).
    
    Section melintang = section memanjang di x itu.
    """
    elemen_list = []
    ele_tag = TAG_MELINTANG_START
    
    n_x = len(x_sorted)
    n_z = len(z_garis)
    
    for i in range(n_x):           # loop x (39)
        for j in range(n_z - 1):   # loop z (4)
            # Node
            n1 = node_map[(i, j)]
            n2 = node_map[(i, j + 1)]
            
            # Section (dari x itu)
            x = x_sorted[i]
            tipe = cari_tipe_x(x, section_map)
            sec = box_sections[tipe]
            
            A = sec["A"]
            Ix = sec["Ix"]
            Iy = sec["Iy"]
            J = get_J(tipe, box_sections)
            
            # Buat elemen
            ops.element('elasticBeamColumn', ele_tag,
                        n1, n2, A, E, G, J, Iy, Ix,
                        TRANSF_MELINTANG)
            
            elemen_list.append({
                "tag": ele_tag,
                "tipe_elemen": "melintang",
                "n1": n1,
                "n2": n2,
                "x": x,
                "z1": z_garis[j],
                "z2": z_garis[j + 1],
                "tipe_section": tipe,
                "A": A,
                "Ix": Ix,
                "Iy": Iy,
                "J": J,
            })
            
            ele_tag += 1
    
    return elemen_list


def cari_tipe(x1, x2, section_map):
    """Cari tipe section untuk segmen [x1, x2]."""
    for sx1, sx2, tipe in section_map:
        if abs(sx1 - x1) < 1e-6 and abs(sx2 - x2) < 1e-6:
            return tipe
    raise ValueError("Segmen ({}, {}) tidak ada di SECTION_MAP".format(x1, x2))


def cari_tipe_x(x, section_map):
    """Cari tipe section untuk posisi x."""
    for sx1, sx2, tipe in section_map:
        if sx1 <= x <= sx2:
            return tipe
    # Fallback: cari yang paling dekat
    for sx1, sx2, tipe in section_map:
        if abs(x - sx1) < 1e-6 or abs(x - sx2) < 1e-6:
            return tipe
    raise ValueError("x = {} tidak ada di SECTION_MAP".format(x))


def get_J(tipe, box_sections):
    """Ambil J dari sections.py."""
    # Import dari sections.py
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    import sections
    return sections.get_J(tipe, box_sections)


def buat_semua_elemen(node_result, section_map, box_sections):
    """
    Buat semua elemen (memanjang + melintang).
    
    Parameters
    ----------
    node_result : dict
        Hasil dari nodes.buat_semua_node()
    section_map : list
        SECTION_MAP
    box_sections : dict
        BOX_SECTIONS
    
    Returns
    -------
    dict : {
        "memanjang": list,
        "melintang": list,
        "n_memanjang": int,
        "n_melintang": int,
        "n_total": int,
    }
    """
    node_map = node_result["node_map"]
    x_sorted = node_result["x_sorted"]
    z_garis = node_result["z_garis"]
    
    # Transformasi
    define_geom_transf()
    
    # Elemen memanjang
    memanjang = buat_elemen_memanjang(
        node_map, x_sorted, z_garis, section_map, box_sections)
    
    # Elemen melintang
    melintang = buat_elemen_melintang(
        node_map, x_sorted, z_garis, section_map, box_sections)
    
    return {
        "memanjang": memanjang,
        "melintang": melintang,
        "n_memanjang": len(memanjang),
        "n_melintang": len(melintang),
        "n_total": len(memanjang) + len(melintang),
    }


# ============================================================
# 4. OUTPUT INFORMATIF
# ============================================================

def print_elemen_info(result):
    """Cetak info elemen."""
    print("=" * 65)
    print("INFO ELEMEN GRILLAGE")
    print("=" * 65)
    print("  Elemen memanjang : {}".format(result["n_memanjang"]))
    print("  Elemen melintang : {}".format(result["n_melintang"]))
    print("  Total elemen     : {}".format(result["n_total"]))
    print()


def print_elemen_sample(result, n=5):
    """Cetak sample elemen."""
    print("=" * 65)
    print("SAMPLE ELEMEN MEMANJANG ({} pertama)".format(n))
    print("=" * 65)
    print("{:>6s} {:>6s} {:>6s} {:>8s} {:>8s} {:>10s} {:>10s}".format(
        "Tag", "n1", "n2", "x1", "x2", "z", "tipe"))
    print("-" * 65)
    for e in result["memanjang"][:n]:
        print("{:>6d} {:>6d} {:>6d} {:>8.3f} {:>8.3f} {:>10.2f} {:>10s}".format(
            e["tag"], e["n1"], e["n2"], e["x1"], e["x2"], e["z"], e["tipe_section"]))
    print()
    
    print("=" * 65)
    print("SAMPLE ELEMEN MELINTANG ({} pertama)".format(n))
    print("=" * 65)
    print("{:>6s} {:>6s} {:>6s} {:>8s} {:>8s} {:>8s} {:>10s}".format(
        "Tag", "n1", "n2", "x", "z1", "z2", "tipe"))
    print("-" * 65)
    for e in result["melintang"][:n]:
        print("{:>6d} {:>6d} {:>6d} {:>8.3f} {:>8.2f} {:>8.2f} {:>10s}".format(
            e["tag"], e["n1"], e["n2"], e["x"], e["z1"], e["z2"], e["tipe_section"]))
    print()


def print_elemen_statistik(result):
    """Cetak statistik elemen."""
    print("=" * 65)
    print("STATISTIK ELEMEN")
    print("=" * 65)
    
    # Hitung panjang total
    L_memanjang = sum(e["x2"] - e["x1"] for e in result["memanjang"])
    L_melintang = sum(abs(e["z2"] - e["z1"]) for e in result["melintang"])
    
    print("  Panjang memanjang total : {:.2f} m".format(L_memanjang))
    print("  Panjang melintang total : {:.2f} m".format(L_melintang))
    print()


# ============================================================
# 5. MAIN (TEST)
# ============================================================

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(os.path.join(BASE_DIR, "Clean"))
    sys.path.append(os.path.join(BASE_DIR, "core"))
    
    import project_data as pdata
    import nodes
    
    # Buat model
    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 6)
    
    # Buat node
    node_result = nodes.buat_semua_node(pdata.SECTION_MAP, pdata.SUPPORTS)
    
    # Buat elemen
    elemen_result = buat_semua_elemen(
        node_result, pdata.SECTION_MAP, pdata.BOX_SECTIONS)
    
    # Print info
    print_elemen_info(elemen_result)
    print_elemen_sample(elemen_result, n=5)
    print_elemen_statistik(elemen_result)
    
    # Cek elemen di OpenSees
    print("=" * 65)
    print("CEK ELEMEN DI OPENSEES")
    print("=" * 65)
    ele_tags = ops.getEleTags()
    print("  Total elemen di OpenSees: {}".format(len(ele_tags)))
    print("  Elemen pertama: {}".format(ele_tags[0]))
    print("  Elemen terakhir: {}".format(ele_tags[-1]))
    
    # Cek elemen
    print()
    print("  Elemen 1:  nodes={}".format(ops.eleNodes(1)))
    print("  Elemen 195: nodes={}".format(ops.eleNodes(195)))
    print("  Elemen 1001: nodes={}".format(ops.eleNodes(1001)))
    print("  Elemen 1156: nodes={}".format(ops.eleNodes(1156)))
    
    print()
    print("SELESAI")