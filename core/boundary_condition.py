# core/boundary_condition.py
"""
Modul Boundary Condition untuk Jembatan Baros (Grillage 3D).
Satuan: m.

BC (fixity = ux, uy, uz, rx, ry, rz):
- Tetap arah x ("pin")  : (1,1,1,0,0,0)
- Roller                : (0,1,1,0,0,0)

Gelagar terputus di EJ (P2, P7) menjadi 3 unit. Tiap unit WAJIB punya
tepat satu support tetap arah x, kalau tidak unit itu bebas bergerak
dalam x (matriks kekakuan singular). Pilihan default di TETAP_X_PER_UNIT:
    unit 0 (A1-P2)  : A1   (sama seperti sebelumnya)
    unit 1 (P2-P7)  : P4   <- ASUMSI, sesuaikan dengan gambar bearing
    unit 2 (P7-A2)  : P8   <- ASUMSI, sesuaikan dengan gambar bearing
Pada support EJ (P2, P7) ada dua garis bearing (satu per unit), keduanya
dibuat roller kecuali dipilih tetap.

Setiap garis support punya satu node per garis memanjang.

Referensi:
- core/nodes.py
- project_data.SUPPORTS
"""

import os
import sys
import openseespy.opensees as ops


# ============================================================
# 1. KONSTANTA
# ============================================================

FIX_PIN = (1, 1, 1, 0, 0, 0)
FIX_ROLLER = (0, 1, 1, 0, 0, 0)

# unit -> nama support yang tetap arah x
TETAP_X_PER_UNIT = {0: "A1", 1: "P4", 2: "P8"}


# ============================================================
# 2. FUNGSI BC
# ============================================================

def terapkan_bc(node_result, supports, tetap_x=None):
    """
    Terapkan BC di semua support.

    Parameters
    ----------
    node_result : dict
        Hasil nodes.buat_semua_node()
    supports : dict
        project_data.SUPPORTS
    tetap_x : dict, optional
        {unit: nama_support} yang tetap arah x. Default TETAP_X_PER_UNIT.

    Returns
    -------
    bc_list : list of dict
    """
    tetap_x = TETAP_X_PER_UNIT if tetap_x is None else tetap_x

    node_map = node_result["node_map"]
    x_index = node_result["x_index"]
    stasiun = node_result["stasiun"]
    z_garis = node_result["z_garis"]
    n_unit = node_result["n_unit"]

    # validasi: tiap unit tepat satu support tetap
    for u in range(n_unit):
        if u not in tetap_x:
            raise ValueError("Unit {} belum punya support tetap arah x."
                             .format(u))
    nama_ada = set(supports.keys())
    for u, nama in tetap_x.items():
        if nama not in nama_ada:
            raise ValueError("Support tetap '{}' (unit {}) tidak ada di "
                             "SUPPORTS.".format(nama, u))

    bc_list = []
    terpasang = {u: 0 for u in range(n_unit)}

    for nama, data in supports.items():
        x_sup = round(data["x"], 6)
        if x_sup not in x_index:
            print("WARNING: x = {} ({}) tidak ada di node".format(x_sup, nama))
            continue

        for i in x_index[x_sup]:                 # 1 stasiun, 2 bila EJ
            unit = stasiun[i]["unit"]
            tetap = (tetap_x.get(unit) == nama)
            fixity = FIX_PIN if tetap else FIX_ROLLER
            if tetap:
                terpasang[unit] += 1

            for j in range(len(z_garis)):
                tag = node_map[(i, j)]
                ops.fix(tag, *fixity)
                bc_list.append({
                    "support": nama, "x": x_sup, "z": z_garis[j],
                    "node": tag, "fixity": fixity, "unit": unit,
                    "tipe": "pin" if tetap else "roller",
                })

    for u, n in terpasang.items():
        if n != 1:
            raise ValueError("Unit {}: support tetap terpasang {} kali "
                             "(harus 1).".format(u, n))

    return bc_list


# ============================================================
# 3. OUTPUT INFORMATIF
# ============================================================

def print_bc_info(bc_list):
    """Cetak info BC."""
    print("=" * 75)
    print("INFO BOUNDARY CONDITION")
    print("=" * 75)
    print("  Total node di-fix : {}".format(len(bc_list)))
    print()

    hitung = {}
    for bc in bc_list:
        k = (bc["support"], bc["unit"])
        hitung[k] = hitung.get(k, 0) + 1

    print("  Node per support (unit):")
    for (s, u), c in hitung.items():
        print("    {} (unit {}) : {} node".format(s, u, c))
    print()


def print_bc_sample(bc_list, n=15):
    """Cetak sample BC."""
    print("=" * 75)
    print("SAMPLE BC ({} pertama)".format(n))
    print("=" * 75)
    print("{:>6s} {:>6s} {:>5s} {:>7s} {:>8s} {:>8s} {:>16s}".format(
        "Node", "Sup", "Unit", "Tipe", "x (m)", "z (m)", "Fixity"))
    print("-" * 75)
    for bc in bc_list[:n]:
        print("{:>6d} {:>6s} {:>5d} {:>7s} {:>8.3f} {:>8.2f} {:>16s}".format(
            bc["node"], bc["support"], bc["unit"], bc["tipe"],
            bc["x"], bc["z"], str(bc["fixity"])))
    print()


def print_bc_per_support(bc_list):
    """Cetak BC per support (dan unit)."""
    print("=" * 75)
    print("BC PER SUPPORT")
    print("=" * 75)

    grup = {}
    for bc in bc_list:
        grup.setdefault((bc["support"], bc["unit"]), []).append(bc)

    for (s, u) in sorted(grup.keys(), key=lambda k: (grup[k][0]["x"], k[1])):
        bcs = grup[(s, u)]
        print("  {} unit {} (x = {:.4f} m): {}  nodes={}".format(
            s, u, bcs[0]["x"], bcs[0]["tipe"], [b["node"] for b in bcs]))
    print()


# ============================================================
# 4. MAIN (TEST)
# ============================================================

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(os.path.join(BASE_DIR, "Clean"))
    sys.path.append(os.path.join(BASE_DIR, "core"))

    import project_data as pdata
    import nodes

    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 6)

    node_result = nodes.buat_semua_node(pdata.SECTION_MAP, pdata.SUPPORTS)
    bc_list = terapkan_bc(node_result, pdata.SUPPORTS)

    print_bc_info(bc_list)
    print_bc_sample(bc_list, n=15)
    print_bc_per_support(bc_list)

    fixed_nodes = ops.getFixedNodes()
    print("  Total node di-fix di OpenSees: {}".format(len(fixed_nodes)))
    print()
    print("SELESAI")
