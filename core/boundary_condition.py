# core/boundary_condition.py
"""
Modul Boundary Condition untuk Jembatan Baros (Grillage 3D).
Satuan: m.

BC dibuat PER BEARING sesuai TABLE BEARING (project_data.BEARINGS), bukan
lagi di semua garis memanjang.

Cara kerja
----------
Untuk tiap bearing (B1..B24):
  1. Node bearing dibuat di (x tumpuan, y = elevasi_model(x), z bearing),
      dengan y relatif terhadap elevasi A1. z = -/+ jarak/2 (ganjil = kiri
      dilihat dari A1, lihat project_data.BEARING_KIRI_Z).
  2. Node bearing dihubungkan ke node garis memanjang TERDEKAT pada stasiun
     tumpuan itu lewat lengan kaku melintang (elasticBeamColumn sangat
     kaku). Jadi dua bearing menahan translasi vertikal DAN rotasi terhadap
     sumbu x (puntir) node garis tersebut, dan gaya dari garis lain mengalir
     lewat elemen melintang (diafragma tumpuan).
  3. Node bearing di-fix menurut tipenya:
        MD   (0,1,0,0,0,0)   OD-L (0,1,1,0,0,0)
        OD-T (1,1,0,0,0,0)   FIX  (1,1,1,0,0,0)
     (ux memanjang, uy vertikal, uz melintang).
Reaksi tiap bearing = reaksi node bearing (ops.nodeReaction).

bc_list tetap berisi satu entri per node yang di-fix, dengan kunci lama
(support, x, z, node, fixity, unit, tipe) ditambah "bearing" (id) dan
"node_garis" (node garis tempat lengan terhubung). "tipe" kini berisi tipe
bearing.

Validasi: tiap unit harus punya tepat SATU garis tumpuan yang menahan arah
x (FIX atau OD-T), dan minimal satu bearing yang menahan uz.

CATATAN AUDIT
-------------
1. Jarak bearing (1.52 m abutment, 0.94 m pier head) dan sisi ganjil/genap
   berasal dari gambar; orientasi +z = kanan adalah ASUMSI
   (BEARING_KIRI_Z).
2. Lengan kaku: A = I = J = LENGAN_KAKU (m2 / m4). Terlalu besar
   memperburuk kondisi matriks, terlalu kecil membuat lengan fleksibel.
3. Garis lampiran = garis memanjang terdekat ke z bearing. Pada skema garis
   berbeda, node terdekat bisa berbeda (mis. abutment, z = +/-0.76 m: garis
   z = 0 pada 5 garis, tetapi garis z = +/-1.46 pada 7 garis).
4. Pier head dan pondasi tidak dimodelkan (repo terpisah).

Referensi:
- core/nodes.py, core/elements.py
- project_data.SUPPORTS, project_data.BEARINGS
"""

import openseespy.opensees as ops

from project.materials import E_BOX, G_BOX
from core import elements
from core.nodes import elevasi_model


# ============================================================
# 1. KONSTANTA
# ============================================================

FIXITY_TIPE = {
    "MD":   (0, 1, 0, 0, 0, 0),
    "OD-L": (0, 1, 1, 0, 0, 0),
    "OD-T": (1, 1, 0, 0, 0, 0),
    "FIX":  (1, 1, 1, 0, 0, 0),
}

TAG_NODE_BEARING = 900001      # node bearing
TAG_ELE_LENGAN = 900001        # elemen lengan kaku (ruang tag elemen sendiri)
LENGAN_KAKU = 100.0            # A = J = Iy = Iz lengan (m2 / m4)


# ============================================================
# 2. FUNGSI BC
# ============================================================

def _z_bearing(id_bearing, jarak, kiri_z):
    """Ganjil = kiri (dilihat dari A1), genap = kanan."""
    nomor = int(id_bearing.lstrip("Bb"))
    arah = kiri_z if nomor % 2 == 1 else -kiri_z
    return arah * jarak / 2.0


def terapkan_bc(node_result, supports, bearings=None, jarak=None,
                kiri_z=None):
    """
    Terapkan BC per bearing.

    Parameters
    ----------
    node_result : dict
        Hasil nodes.buat_semua_node()
    supports : dict
        project_data.SUPPORTS
    bearings, jarak, kiri_z : optional
        Default dari project_data (BEARINGS, BEARING_JARAK,
        BEARING_KIRI_Z).

    Returns
    -------
    bc_list : list of dict
    """
    if bearings is None or jarak is None or kiri_z is None:
        from project import project_data as pdata
        bearings = pdata.BEARINGS if bearings is None else bearings
        jarak = pdata.BEARING_JARAK if jarak is None else jarak
        kiri_z = pdata.BEARING_KIRI_Z if kiri_z is None else kiri_z

    node_map = node_result["node_map"]
    x_index = node_result["x_index"]
    stasiun = node_result["stasiun"]
    z_garis = node_result["z_garis"]
    n_unit = node_result["n_unit"]

    nama_ada = set(supports.keys())
    for b in bearings:
        if b[1] not in nama_ada:
            raise ValueError("Bearing {}: support '{}' tidak ada di "
                             "SUPPORTS.".format(b[0], b[1]))
        if b[3] not in FIXITY_TIPE:
            raise ValueError("Bearing {}: tipe '{}' tidak dikenal."
                             .format(b[0], b[3]))

    bc_list = []
    tahan_x = {u: set() for u in range(n_unit)}   # unit -> {support}
    tahan_z = {u: 0 for u in range(n_unit)}
    n_b = 0

    for nama, data in supports.items():
        x_sup = round(data["x"], 6)
        if x_sup not in x_index:
            print("WARNING: x = {} ({}) tidak ada di node".format(x_sup, nama))
            continue
        tipe_sup = data.get("type", "pier")
        jr = jarak["abutment" if tipe_sup == "abutment" else "pier"]

        for i in x_index[x_sup]:                 # 1 stasiun, 2 bila EJ
            st = stasiun[i]
            unit, sisi = st["unit"], st["sisi"]
            daftar = [b for b in bearings if b[1] == nama and b[2] == sisi]
            if not daftar:
                raise ValueError("Support {} (sisi {}) tidak punya bearing "
                                 "di BEARINGS.".format(nama, sisi))

            for id_b, _, _, tipe in daftar:
                zb = _z_bearing(id_b, jr, kiri_z)
                j = min(range(len(z_garis)),
                        key=lambda k: abs(z_garis[k] - zb))
                n_garis = node_map[(i, j)]

                n_node = TAG_NODE_BEARING + n_b
                n_ele = TAG_ELE_LENGAN + n_b
                n_b += 1
                ops.node(n_node, x_sup, elevasi_model(x_sup), zb)
                ops.element('elasticBeamColumn', n_ele, n_garis, n_node,
                            LENGAN_KAKU, E_BOX, G_BOX, LENGAN_KAKU,
                            LENGAN_KAKU, LENGAN_KAKU,
                            elements.TRANSF_MELINTANG)

                fixity = FIXITY_TIPE[tipe]
                ops.fix(n_node, *fixity)
                if fixity[0]:
                    tahan_x[unit].add((nama, sisi))
                if fixity[2]:
                    tahan_z[unit] += 1

                bc_list.append({
                    "support": nama, "x": x_sup, "z": zb,
                    "node": n_node, "node_garis": n_garis,
                    "z_garis": z_garis[j], "bearing": id_b,
                    "fixity": fixity, "unit": unit, "tipe": tipe,
                })

    for u in range(n_unit):
        if len(tahan_x[u]) != 1:
            raise ValueError(
                "Unit {}: garis tumpuan penahan arah x = {} (harus tepat "
                "1).".format(u, sorted(tahan_x[u])))
        if tahan_z[u] == 0:
            raise ValueError("Unit {}: tidak ada bearing penahan uz."
                             .format(u))

    return bc_list


# ============================================================
# 3. OUTPUT INFORMATIF
# ============================================================

def print_bc_info(bc_list):
    """Cetak info BC."""
    print("=" * 75)
    print("INFO BOUNDARY CONDITION (PER BEARING)")
    print("=" * 75)
    print("  Total node bearing di-fix : {}".format(len(bc_list)))
    print()

    hitung = {}
    for bc in bc_list:
        k = (bc["support"], bc["unit"])
        hitung[k] = hitung.get(k, 0) + 1

    print("  Bearing per support (unit):")
    for (s, u), c in hitung.items():
        print("    {} (unit {}) : {} bearing".format(s, u, c))
    print()

def print_bc_sample(bc_list, n=15):
    """Cetak sample BC beserta koordinat node bearing."""
    print("=" * 100)
    print("SAMPLE BC ({} pertama)".format(n))
    print("=" * 100)
    print("{:>7s} {:>5s} {:>5s} {:>6s} {:>9s} "
          "{:>9s} {:>9s} {:>8s} {:>16s}".format(
              "Node", "ID", "Sup", "Unit", "Tipe",
              "y (m)", "z (m)", "z garis", "Fixity"))
    print("-" * 100)

    for bc in bc_list[:n]:
        coord = ops.nodeCoord(bc["node"])
        print("{:>7d} {:>5s} {:>5s} {:>6d} {:>9s} "
              "{:>9.4f} {:>9.3f} {:>8.3f} {:>16s}".format(
                  bc["node"], bc["bearing"], bc["support"],
                  bc["unit"], bc["tipe"], coord[1], coord[2],
                  bc["z_garis"], str(bc["fixity"])))
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
        print("  {} unit {} (x = {:.4f} m): {}".format(
            s, u, bcs[0]["x"],
            "  ".join("{}={}@z{:+.2f}".format(b["bearing"], b["tipe"], b["z"])
                      for b in bcs)))
    print()


# ============================================================
# 4. MAIN (TEST)
# ============================================================

if __name__ == "__main__":
    # Jalankan dari root repo:  python -m core.boundary_condition
    from project import project_data as pdata
    from core import nodes

    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 6)

    node_result = nodes.buat_semua_node(pdata.SECTION_MAP, pdata.SUPPORTS)
    elements.define_geom_transf()
    bc_list = terapkan_bc(node_result, pdata.SUPPORTS)

    print_bc_info(bc_list)
    print_bc_sample(bc_list, n=24)
    print_bc_per_support(bc_list)

    print("SELESAI")
