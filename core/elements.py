# core/elements.py
"""
Modul Elemen untuk Jembatan Baros (Grillage 3D).
Satuan: kN, m, kPa.

Elemen (elasticBeamColumn, deck elastis):
- Memanjang (arah x): satu elemen per segmen per garis, KECUALI di antara
  dua stasiun expansion joint (gelagar putus).
- Melintang (arah z): satu elemen per segmen z per stasiun.
Jumlah elemen mengikuti data node (lihat hasil buat_semua_elemen()).

Perubahan utama dibanding versi sebelumnya:
- Tiap garis memanjang memakai properti STRIP-nya (section_strips),
  bukan properti seluruh penampang. Jumlah properti semua garis = total
  BOX_SECTIONS (A, Ix, J).
- Elemen melintang memakai properti jalur selebar dx (profil kedalaman
  d(z) dari DXF), bukan properti penampang penuh.
- Tipe section dicari dari titik tengah segmen (tidak perlu persis sama
  dengan SECTION_MAP).
- E, G diimpor dari materials.py.
- z_ref (batas tributary) dan z_garis (posisi fisik node) dipisah.
  Iy tiap garis dihitung terhadap posisi node, sehingga
  sum(Iy_i + A_i*z_node^2) = Iy total.
- Elemen melintang memakai tipe section di stasiun dan koordinat node
  (sebelumnya z_garis terbaca sebagai argumen `tipe`).

Sumbu lokal:
- Memanjang : vecxz = (0,0,1) -> y lokal = y global (vertikal);
  lentur vertikal memakai Iz  (Iz <- Ix strip), lateral memakai Iy.
- Melintang : vecxz = (1,0,0) -> z lokal = x global; lentur vertikal
  memakai Iz (= dx*d_eq^3/12).

Tag geomTransf: 1 = deck memanjang, 2 = deck melintang, 3 = pier.
"""

import os
import sys
import openseespy.opensees as ops

from project.materials import E_BOX, G_BOX
try:
    from core import section_strips as strips
except ImportError:
    import section_strips as strips


# ============================================================
# 1. KONSTANTA
# ============================================================

TAG_MEMANJANG_START = 1
TAG_MELINTANG_START = 1001

TRANSF_MEMANJANG = 1   # vecxz = (0, 0, 1)
TRANSF_MELINTANG = 2   # vecxz = (1, 0, 0)
TRANSF_PIER = 3        # vecxz = (1, 0, 0), dipakai pier.py


# ============================================================
# 2. TRANSFORMASI GEOMETRI
# ============================================================

def define_geom_transf():
    """Definisikan geomTransf deck (memanjang & melintang)."""
    ops.geomTransf('Linear', TRANSF_MEMANJANG, 0.0, 0.0, 1.0)
    ops.geomTransf('Linear', TRANSF_MELINTANG, 1.0, 0.0, 0.0)


# ============================================================
# 3. UTILITAS
# ============================================================

def cari_tipe_di_x(x, section_map, tol=1e-6):
    """Tipe section di posisi x (titik tengah segmen)."""
    for sx1, sx2, tipe in section_map:
        if sx1 - tol <= x <= sx2 + tol:
            return tipe
    raise ValueError("x = {} tidak ada di SECTION_MAP".format(x))


def lebar_tributari(stasiun, i):
    """
    Lebar jalur dx stasiun i (m), dibatasi pada unit yang sama:
    separuh jarak ke stasiun tetangga di unit itu.
    """
    unit = stasiun[i]["unit"]
    dx = 0.0
    if i > 0 and stasiun[i - 1]["unit"] == unit:
        dx += 0.5 * (stasiun[i]["x"] - stasiun[i - 1]["x"])
    if i < len(stasiun) - 1 and stasiun[i + 1]["unit"] == unit:
        dx += 0.5 * (stasiun[i + 1]["x"] - stasiun[i]["x"])
    return dx


# ============================================================
# 4. FUNGSI ELEMEN
# ============================================================

def buat_elemen_memanjang(node_result, section_map, box_sections,
                          E=E_BOX, G=G_BOX):
    """
    Buat elemen memanjang. Return list of dict (info tiap elemen).
    """
    node_map = node_result["node_map"]
    stasiun = node_result["stasiun"]
    z_garis = node_result["z_garis"]                       # posisi node
    z_ref = node_result.get("z_ref", strips.Z_GARIS_DEFAULT)  # batas strip

    # properti per tipe per garis (hitung sekali)
    cache = {}

    def props(tipe):
        if tipe not in cache:
            cache[tipe] = strips.properti_garis(
                tipe, box_sections[tipe], z_ref, z_garis)
        return cache[tipe]

    elemen_list = []
    ele_tag = TAG_MEMANJANG_START

    for j in range(len(z_garis)):
        for i in range(len(stasiun) - 1):
            s1, s2 = stasiun[i], stasiun[i + 1]
            if s1["unit"] != s2["unit"]:
                continue                       # expansion joint: putus

            n1 = node_map[(i, j)]
            n2 = node_map[(i + 1, j)]
            xm = 0.5 * (s1["x"] + s2["x"])
            tipe = cari_tipe_di_x(xm, section_map)
            p = props(tipe)[j]

            # urutan: A, E, G, J, Iy, Iz  (Iz = lentur vertikal = Ix strip)
            ops.element('elasticBeamColumn', ele_tag, n1, n2,
                        p["A"], E, G, p["J"], p["Iy"], p["Ix"],
                        TRANSF_MEMANJANG)

            elemen_list.append({
                "tag": ele_tag, "tipe_elemen": "memanjang",
                "n1": n1, "n2": n2, "x1": s1["x"], "x2": s2["x"],
                "z": z_garis[j], "garis": j, "unit": s1["unit"],
                "tipe_section": tipe,
                "A": p["A"], "Ix": p["Ix"], "Iy": p["Iy"], "J": p["J"],
            })
            ele_tag += 1

    return elemen_list


def buat_elemen_melintang(node_result, section_map, E=E_BOX, G=G_BOX):
    """
    Buat elemen melintang di setiap stasiun (termasuk kedua sisi EJ).
    Properti dari jalur selebar dx, tipe section di x stasiun, dan
    profil d(z) antar node (z_garis).
    """
    node_map = node_result["node_map"]
    stasiun = node_result["stasiun"]
    z_garis = node_result["z_garis"]

    elemen_list = []
    ele_tag = TAG_MELINTANG_START

    for i, st in enumerate(stasiun):
        dx = lebar_tributari(stasiun, i)
        if dx <= 0:
            raise ValueError("Stasiun {} (x={}) tanpa lebar tributari."
                             .format(i, st["x"]))
        tipe = cari_tipe_di_x(st["x"], section_map)
        sp = strips.properti_melintang(dx, tipe, z_garis)

        for j in range(len(z_garis) - 1):
            n1 = node_map[(i, j)]
            n2 = node_map[(i, j + 1)]
            p = sp[j]

            ops.element('elasticBeamColumn', ele_tag, n1, n2,
                        p["A"], E, G, p["J"], p["Iy"], p["Iz"],
                        TRANSF_MELINTANG)

            elemen_list.append({
                "tag": ele_tag, "tipe_elemen": "melintang",
                "n1": n1, "n2": n2, "x": st["x"], "unit": st["unit"],
                "z1": z_garis[j], "z2": z_garis[j + 1], "dx": dx,
                "A": p["A"], "Iz": p["Iz"], "Iy": p["Iy"], "J": p["J"],
            })
            ele_tag += 1

    return elemen_list


def buat_semua_elemen(node_result, section_map, box_sections):
    """
    Buat semua elemen (memanjang + melintang).

    Returns
    -------
    dict : {memanjang, melintang, n_memanjang, n_melintang, n_total}
    """
    define_geom_transf()

    memanjang = buat_elemen_memanjang(node_result, section_map, box_sections)
    melintang = buat_elemen_melintang(node_result, section_map)

    return {
        "memanjang": memanjang,
        "melintang": melintang,
        "n_memanjang": len(memanjang),
        "n_melintang": len(melintang),
        "n_total": len(memanjang) + len(melintang),
    }


# ============================================================
# 5. OUTPUT INFORMATIF
# ============================================================

def print_elemen_info(result, node_result=None):
    """Cetak info elemen dan verifikasi terhadap jumlah stasiun."""
    print("=" * 65)
    print("INFO ELEMEN GRILLAGE")
    print("=" * 65)
    print("  Elemen memanjang : {}".format(result["n_memanjang"]))
    print("  Elemen melintang : {}".format(result["n_melintang"]))
    print("  Total elemen     : {}".format(result["n_total"]))
    if node_result:
        n_st = len(node_result["stasiun"])
        n_z = len(node_result["z_garis"])
        n_seg = n_st - node_result["n_unit"]
        print("  Harapan memanjang: {} segmen x {} garis = {}".format(
            n_seg, n_z, n_seg * n_z))
        print("  Harapan melintang: {} stasiun x {} = {}".format(
            n_st, n_z - 1, n_st * (n_z - 1)))
    print()


def print_elemen_sample(result, n=5):
    """Cetak sample elemen."""
    print("=" * 75)
    print("SAMPLE ELEMEN MEMANJANG ({} pertama)".format(n))
    print("=" * 75)
    print("{:>6s} {:>6s} {:>6s} {:>8s} {:>8s} {:>6s} {:>8s} {:>8s}".format(
        "Tag", "n1", "n2", "x1", "x2", "z", "tipe", "A"))
    print("-" * 75)
    for e in result["memanjang"][:n]:
        print("{:>6d} {:>6d} {:>6d} {:>8.3f} {:>8.3f} {:>6.2f} {:>8s} {:>8.3f}"
              .format(e["tag"], e["n1"], e["n2"], e["x1"], e["x2"], e["z"],
                      e["tipe_section"], e["A"]))
    print()
    print("SAMPLE ELEMEN MELINTANG ({} pertama)".format(n))
    print("-" * 75)
    print("{:>6s} {:>6s} {:>6s} {:>8s} {:>6s} {:>6s} {:>8s} {:>10s}".format(
        "Tag", "n1", "n2", "x", "z1", "z2", "dx", "Iz"))
    for e in result["melintang"][:n]:
        print("{:>6d} {:>6d} {:>6d} {:>8.3f} {:>6.2f} {:>6.2f} {:>8.3f} {:>10.5f}"
              .format(e["tag"], e["n1"], e["n2"], e["x"], e["z1"], e["z2"],
                      e["dx"], e["Iz"]))
    print()


def print_verifikasi_properti(result, box_sections, section_map):
    """Jumlah A/Ix/J dan Iy+A*z_node^2 semua garis per segmen = total tipe."""
    print("=" * 75)
    print("VERIFIKASI: JUMLAH PROPERTI GARIS vs TOTAL TIPE")
    print("=" * 75)
    per_seg = {}
    for e in result["memanjang"]:
        k = (e["x1"], e["x2"])
        a = per_seg.setdefault(k, {"A": 0.0, "Ix": 0.0, "Iy": 0.0, "J": 0.0,
                                   "tipe": e["tipe_section"]})
        a["A"] += e["A"]
        a["Ix"] += e["Ix"]
        a["Iy"] += e["Iy"] + e["A"] * e["z"] ** 2   # z = posisi node aktual
        a["J"] += e["J"]
    maks = 0.0
    for k, a in per_seg.items():
        tot = box_sections[a["tipe"]]
        for nama in ("A", "Ix", "Iy", "J"):
            maks = max(maks, abs(a[nama] / tot[nama] - 1.0))
    print("  Selisih relatif maksimum (A, Ix, Iy+A*z^2, J): {:.2e}".format(
        maks))
    print()


# ============================================================
# 6. MAIN (TEST)
# ============================================================

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    from project import project_data as pdata
    from core import nodes

    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 6)

    node_result = nodes.buat_semua_node(pdata.SECTION_MAP, pdata.SUPPORTS)
    elemen_result = buat_semua_elemen(
        node_result, pdata.SECTION_MAP, pdata.BOX_SECTIONS)

    print_elemen_info(elemen_result, node_result)
    print_elemen_sample(elemen_result, n=5)
    print_verifikasi_properti(elemen_result, pdata.BOX_SECTIONS,
                              pdata.SECTION_MAP)

    ele_tags = ops.getEleTags()
    print("  Total elemen di OpenSees: {}".format(len(ele_tags)))
    print()
    print("SELESAI")
