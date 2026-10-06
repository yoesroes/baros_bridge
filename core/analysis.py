# core/analysis.py
"""
Analisis statik linear deck Jembatan Baros (grillage 3D, tumpuan kaku).
Satuan: kN, m, kPa.

Model elastis -> superposisi. Kasus beban DASAR dijalankan satu per satu:
    D1                  berat sendiri (per garis, fraksi luas strip)
    D2                  beban mati tambahan (aspal, air, barrier)
    BTR | bentang k | offset o      BTR hanya di bentang k (pattern loading)
    KEL | bentang k | posisi f | o  KEL terpusat di x = x_k + f*L_k
offset o = pergeseran lajur penuh 5.5 m terhadap sumbu jalan.
Kombinasi dan envelope dibuat di output.py dari hasil kasus dasar.

Catatan pemodelan:
- Tumpuan = support kaku di node deck (reaksi = batas atas bagi pier).
  Pier, pile cap, bored pile belum tersambung.
- BTR per bentang memakai L = panjang bentang itu untuk reduksi q (L > 30 m).
- Gelagar putus di EJ (P2, P7): tiap unit menerus dianalisis bersama dalam
  satu model; antar unit tidak ada elemen.
- Tiap kasus diperiksa kesetimbangannya: jumlah reaksi vertikal + beban
  total harus nol.

Referensi: core/loads.py, core/section_strips.py, core/nodes.py,
core/elements.py, core/boundary_condition.py
"""

import os
import sys
import openseespy.opensees as ops

try:
    from core import loads, section_strips as strips
except ImportError:
    import loads
    import section_strips as strips


# ============================================================
# 1. KONSTANTA
# ============================================================

TS_TAG = 1
OFFSET_DEFAULT = (0.0, 1.75, -1.75)      # m, lajur penuh 5.5 m
KEL_FRAKSI_DEFAULT = (0.5,)              # posisi KEL pada bentang (0..1)
TOL_KESETIMBANGAN = 1e-6                 # relatif terhadap beban total


# ============================================================
# 2. BENTANG
# ============================================================

def daftar_bentang(supports):
    """
    Bentang = jarak antar support berurutan (menurut x).
    Return: list of dict {k, nama, dari, ke, x1, x2, L}
    """
    urut = sorted(supports.items(), key=lambda kv: kv[1]["x"])
    bentang = []
    for k in range(len(urut) - 1):
        (n1, d1), (n2, d2) = urut[k], urut[k + 1]
        bentang.append({
            "k": k + 1, "nama": "{}-{}".format(n1, n2),
            "dari": n1, "ke": n2,
            "x1": d1["x"], "x2": d2["x"], "L": d2["x"] - d1["x"],
        })
    return bentang


# ============================================================
# 3. KASUS BEBAN DASAR
# ============================================================

def bangun_kasus(node_result, elemen_result, box_sections, supports,
                 L_E=None, offsets=OFFSET_DEFAULT,
                 kel_fraksi=KEL_FRAKSI_DEFAULT):
    """
    Susun semua kasus beban dasar.

    Returns
    -------
    kasus : dict  nama -> {"jenis", "bentang", "offset", "f",
                           "ele": {tag: Wy}, "node": {node: Fy},
                           "total": beban vertikal total (kN, negatif ke bawah)}
    bentang : list dari daftar_bentang()
    """
    z_garis = node_result["z_garis"]   # posisi fisik node
    z_ref = node_result["z_ref"]       # referensi tributary strip
    stasiun = node_result["stasiun"]
    node_map = node_result["node_map"]
    memanjang = elemen_result["memanjang"]
    bentang = daftar_bentang(supports)

    kasus = {}
    f_berat = {}

    def fraksi(tipe):
        if tipe not in f_berat:
            f_berat[tipe] = strips.fraksi_berat(
                tipe,
                z_ref,
            )
        return f_berat[tipe]

    def total_ele(wy):
        panjang = {e["tag"]: e["x2"] - e["x1"] for e in memanjang}
        return sum(w * panjang[t] for t, w in wy.items())
    
    b_jalan = loads.lebar_jalan_per_garis(z_garis)
    w_barrier_g = loads.distribusi_barrier(z_garis)
    w_nonstruk_m2 = (
        loads.GAMMA_ASPAL * loads.T_ASPAL
        + loads.GAMMA_AIR * loads.T_AIR
    )

    # ---- D1, D2 ----
    d1 = {}
    d2 = {}
    for e in memanjang:
        j, tipe = e["garis"], e["tipe_section"]
        A = box_sections[tipe]["A"]
        d1[e["tag"]] = -loads.hitung_w_box(A) * fraksi(tipe)[j]
        d2[e["tag"]] = -(w_nonstruk_m2 * b_jalan[j] + w_barrier_g[j])
    kasus["D1"] = {"jenis": "D1", "bentang": None, "offset": None, "f": None,
                   "ele": d1, "node": {}, "total": total_ele(d1)}
    kasus["D2"] = {"jenis": "D2", "bentang": None, "offset": None, "f": None,
                   "ele": d2, "node": {}, "total": total_ele(d2)}

    # ---- BTR dan KEL ----
    P_kel_per_lebar = loads.hitung_P_kel_per_lebar(L_E)

    for o in offsets:
        b_h = loads.lebar_beban_hidup_per_garis(z_garis, lane_offset=o)
        for b in bentang:
            q = loads.hitung_q_btr(b["L"])

            # BTR di bentang b
            wy = {}
            for e in memanjang:
                if e["x1"] >= b["x1"] - 1e-6 and e["x2"] <= b["x2"] + 1e-6:
                    wy[e["tag"]] = -q * b_h[e["garis"]]
            nama = "BTR|{}|o={:+.2f}".format(b["nama"], o)
            kasus[nama] = {"jenis": "BTR", "bentang": b["k"], "offset": o,
                           "f": None, "ele": wy, "node": {},
                           "total": total_ele(wy)}

            # KEL di bentang b
            kandidat = [i for i, s in enumerate(stasiun)
                        if b["x1"] + 1e-6 < s["x"] < b["x2"] - 1e-6]
            for f in kel_fraksi:
                x_t = b["x1"] + f * b["L"]
                i = min(kandidat, key=lambda ii: abs(stasiun[ii]["x"] - x_t))
                fy = {}
                for j in range(len(z_garis)):
                    P = P_kel_per_lebar * b_h[j]
                    if P != 0.0:
                        fy[node_map[(i, j)]] = -P
                nama = "KEL|{}|f={:.2f}|o={:+.2f}".format(b["nama"], f, o)
                kasus[nama] = {"jenis": "KEL", "bentang": b["k"], "offset": o,
                               "f": f, "ele": {}, "node": fy,
                               "total": sum(fy.values()),
                               "x": stasiun[i]["x"]}

    return kasus, bentang


# ============================================================
# 4. SETUP DAN EKSEKUSI ANALISIS
# ============================================================

def setup_analysis():
    """Statik linear. 'Transformation' aman untuk rigidLink (pier/pile cap)."""
    ops.timeSeries('Linear', TS_TAG)
    ops.constraints('Transformation')
    ops.numberer('RCM')
    ops.system('BandGeneral')
    ops.test('NormDispIncr', 1.0e-8, 10)
    ops.algorithm('Linear')
    ops.integrator('LoadControl', 1.0)
    ops.analysis('Static')


def jalankan_kasus(nama, kasus, bc_nodes, ele_memanjang, semua_node, pid):
    """
    Jalankan satu kasus, kumpulkan respon, lalu bersihkan.

    Returns dict kategori -> {kunci: nilai}:
      R   : reaksi vertikal Ry per node tumpuan
      Uy  : lendutan vertikal tiap node
      Mz_i, Mz_j, Vy_i, Vy_j, T_i : gaya ujung elemen memanjang (lokal)
    """
    ops.pattern('Plain', pid, TS_TAG)
    for tag, wy in kasus["ele"].items():
        ops.eleLoad('-ele', tag, '-type', '-beamUniform', wy, 0.0, 0.0)
    for n, fy in kasus["node"].items():
        ops.load(n, 0.0, fy, 0.0, 0.0, 0.0, 0.0)

    if ops.analyze(1) != 0:
        raise RuntimeError("Analisis gagal pada kasus {}".format(nama))
    ops.reactions()

    R = {n: ops.nodeReaction(n)[1] for n in bc_nodes}
    sisa = sum(R.values()) + kasus["total"]
    if abs(sisa) > TOL_KESETIMBANGAN * max(1.0, abs(kasus["total"])):
        raise RuntimeError(
            "Kesetimbangan gagal pada {}: sum(Ry) = {:.6f}, beban = {:.6f}"
            .format(nama, sum(R.values()), kasus["total"]))

    hasil = {
        "R": R,
        "Uy": {n: ops.nodeDisp(n)[1] for n in semua_node},
        "Mz_i": {}, "Mz_j": {},
        "Vy_i": {}, "Vy_j": {},
        "T_i": {}, "T_j": {},
    }

    for tag in ele_memanjang:
        f = ops.eleForce(tag)

        hasil["Mz_i"][tag] = f[5]
        hasil["Mz_j"][tag] = f[11]

        hasil["Vy_i"][tag] = f[1]
        hasil["Vy_j"][tag] = f[7]

        hasil["T_i"][tag] = f[3]
        hasil["T_j"][tag] = f[9]


    ops.remove('loadPattern', pid)
    ops.reset()
    return hasil


def jalankan_semua(kasus, node_result, elemen_result, bc_list, verbose=True):
    """Jalankan seluruh kasus dasar. Return dict nama -> hasil."""
    setup_analysis()
    bc_nodes = sorted({b["node"] for b in bc_list})
    ele_m = [e["tag"] for e in elemen_result["memanjang"]]
    semua_node = sorted(node_result["node_map"].values())

    hasil = {}
    for pid, (nama, k) in enumerate(kasus.items(), start=1):
        hasil[nama] = jalankan_kasus(nama, k, bc_nodes, ele_m,
                                     semua_node, pid)
        if verbose:
            print("  [{:>3d}/{}] {:<40s} beban = {:>10.2f} kN".format(
                pid, len(kasus), nama, k["total"]))
    return hasil



# ============================================================
# 5. MAIN
# ============================================================

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(os.path.join(BASE_DIR, "Clean"))
    sys.path.append(os.path.join(BASE_DIR, "core"))

    import project_data as pdata
    import nodes
    import elements
    import boundary_condition as bc
    import output

    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 6)

    node_result = nodes.buat_semua_node(pdata.SECTION_MAP, pdata.SUPPORTS)
    elemen_result = elements.buat_semua_elemen(
        node_result, pdata.SECTION_MAP, pdata.BOX_SECTIONS)
    bc_list = bc.terapkan_bc(node_result, pdata.SUPPORTS)

    # Bentang dari support (m); L_E untuk FBD
    bentang = daftar_bentang(pdata.SUPPORTS)
    L_E = loads.hitung_L_ekuivalen([b["L"] for b in bentang])

    kasus, bentang = bangun_kasus(
        node_result, elemen_result, pdata.BOX_SECTIONS, pdata.SUPPORTS,
        L_E=L_E)

    print("Menjalankan {} kasus dasar...".format(len(kasus)))
    hasil = jalankan_semua(kasus, node_result, elemen_result, bc_list)

    out_dir = os.path.join(BASE_DIR, "output")
    output.laporan(hasil, kasus, node_result, bc_list, bentang, out_dir,
                   elemen_result)

    print("SELESAI")
