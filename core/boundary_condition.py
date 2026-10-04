# core/bc.py
"""
Modul Boundary Condition untuk Jembatan Baros (Grillage 3D).
Satuan: m.

BC:
- A1     : pin   (1,1,1,0,0,0)
- P1-P8  : roller (0,1,1,0,0,0)
- A2     : roller (0,1,1,0,0,0)

Setiap support punya 5 node transversal.

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

# Tipe support
SUPPORT_TYPE = {
    "A1": "pin",
    "A2": "roller",
    # P1-P8: roller (default)
}


# ============================================================
# 2. FUNGSI BC
# ============================================================

def terapkan_bc(node_result, supports):
    """
    Terapkan BC di semua support.
    
    Parameters
    ----------
    node_result : dict
        Hasil dari nodes.buat_semua_node()
    supports : dict
        Data support dari project_data.SUPPORTS
    
    Returns
    -------
    bc_list : list of dict
        Info BC yang diterapkan
    """
    node_map = node_result["node_map"]
    x_index = node_result["x_index"]
    x_sorted = node_result["x_sorted"]
    z_garis = node_result["z_garis"]
    n_z = len(z_garis)
    
    bc_list = []
    
    for nama, data in supports.items():
        x_sup = round(data["x"], 6)
        
        # Cari index x
        if x_sup not in x_index:
            print("WARNING: x = {} tidak ada di node".format(x_sup))
            continue
        
        i = x_index[x_sup]
        
        # Tentukan fixity
        tipe = SUPPORT_TYPE.get(nama, "roller")
        if tipe == "pin":
            fixity = FIX_PIN
        else:
            fixity = FIX_ROLLER
        
        # Terapkan di semua z (5 node)
        for j in range(n_z):
            tag = node_map[(i, j)]
            ops.fix(tag, *fixity)
            bc_list.append({
                "support": nama,
                "x": x_sup,
                "z": z_garis[j],
                "node": tag,
                "fixity": fixity,
                "tipe": tipe,
            })
    
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
    
    # Per support
    support_count = {}
    for bc in bc_list:
        s = bc["support"]
        support_count[s] = support_count.get(s, 0) + 1
    
    print("  Node per support:")
    for s, c in support_count.items():
        print("    {} : {} node".format(s, c))
    print()


def print_bc_sample(bc_list, n=15):
    """Cetak sample BC."""
    print("=" * 75)
    print("SAMPLE BC ({} pertama)".format(n))
    print("=" * 75)
    print("{:>6s} {:>6s} {:>6s} {:>8s} {:>8s} {:>20s}".format(
        "Node", "Sup", "Tipe", "x (m)", "z (m)", "Fixity"))
    print("-" * 75)
    
    for bc in bc_list[:n]:
        print("{:>6d} {:>6s} {:>6s} {:>8.3f} {:>8.2f} {:>20s}".format(
            bc["node"], bc["support"], bc["tipe"],
            bc["x"], bc["z"], str(bc["fixity"])))
    print()


def print_bc_per_support(bc_list):
    """Cetak BC per support."""
    print("=" * 75)
    print("BC PER SUPPORT")
    print("=" * 75)
    
    # Group by support
    support_data = {}
    for bc in bc_list:
        s = bc["support"]
        if s not in support_data:
            support_data[s] = []
        support_data[s].append(bc)
    
    for s in sorted(support_data.keys()):
        bcs = support_data[s]
        x = bcs[0]["x"]
        tipe = bcs[0]["tipe"]
        fixity = bcs[0]["fixity"]
        nodes = [bc["node"] for bc in bcs]
        
        print("  {} (x = {:.4f} m):".format(s, x))
        print("    Tipe   : {}".format(tipe))
        print("    Fixity : {}".format(fixity))
        print("    Nodes  : {}".format(nodes))
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
    
    # Buat model
    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 6)
    
    # Buat node
    node_result = nodes.buat_semua_node(pdata.SECTION_MAP, pdata.SUPPORTS)

    
    # Terapkan BC
    bc_list = terapkan_bc(node_result, pdata.SUPPORTS)
    
    # Print info
    print_bc_info(bc_list)
    print_bc_sample(bc_list, n=15)
    print_bc_per_support(bc_list)
    
    # Cek BC di OpenSees
    print("=" * 75)
    print("CEK BC DI OPENSEES")
    print("=" * 75)
    fixed_nodes = ops.getFixedNodes()
    print("  Total node di-fix: {}".format(len(fixed_nodes)))
    print("  Node pertama: {}".format(fixed_nodes[0]))
    print("  Node terakhir: {}".format(fixed_nodes[-1]))
    
    # Cek fixity beberapa node
    print()
    for tag in [1, 5, 40, 100, 195]:
        try:
            dofs = ops.getFixedDOFs(tag)
            print("  Node {}: fixity = {}".format(tag, dofs))
        except Exception as e:
            print("  Node {}: error".format(tag))
    
    print()
    print("SELESAI")