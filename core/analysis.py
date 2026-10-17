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

STATUS: [AKTIF] langkah terakhir pembentukan model dan penjalanan kasus;
hasil diolah core/output.py.

Hasil tiap kasus (jalankan_kasus), semua sumbu LOKAL OpenSees:
    R   : reaksi vertikal Ry per node tumpuan (kN, + ke atas)
    Uy  : lendutan vertikal tiap node (m)
    Mz_i, Mz_j, Vy_i, Vy_j, T_i, T_j : gaya ujung elemen memanjang
          (eleForce). Mz_i dan Mz_j untuk momen internal yang sama
          berlawanan tanda (konversi sagging-positif ada di output.py).

CATATAN AUDIT
-------------
1. Beban BTR/KEL: per bentang (pattern loading) dan per offset lajur.
   KEL bergerak: tiap bentang diberi KEL di x = x_k + f*L_k untuk semua f di
   KEL_FRAKSI_DEFAULT (0, 0.1, ..., 1.0), tepat di posisi itu. Bila x jatuh
   pada stasiun, beban diberikan sebagai beban nodal; bila tidak, sebagai
   beban titik di dalam elemen (-beamPoint) sehingga tidak dibulatkan ke
   stasiun terdekat. Envelope memilih posisi KEL terburuk per respons
   (output.envelope_hidup). Untuk momen negatif maksimum pada gelagar
   menerus, SNI 1725:2016 mensyaratkan KEL kedua yang identik pada bentang
   lain: lihat gaya_total.envelope_hidup_total (opsi kel_kedua) yang
   dipakai untuk momen total; reaksi dan gaya per garis memakai satu KEL.
2. Reduksi BTR memakai L = panjang bentang tunggal; BTR yang dibebani di
   beberapa bentang dijumlahkan di output.py tanpa reduksi L total.
3. FBD memakai L_E (hitung_L_ekuivalen dari seluruh bentang) yang
   diberikan pemanggil; L_E = None -> FBD = 0.4 (konservatif).
4. D2: lebar jalan per garis memakai batas tributari dari posisi NODE
   (loads.batas_tributari), sedangkan D1 memakai fraksi luas strip dari
   z_ref. Dua definisi tributari yang berbeda; total tetap terjaga.
5. Barrier di D2 diletakkan di garis terluar (z = +/-4.60 m), bukan di
   tepi deck (+/-5.0 m).
6. Tidak ada beban prategang, angin, temperatur, rem, maupun gempa.
7. Cek kesetimbangan memakai beban yang sama dengan yang diterapkan, jadi
   tidak mendeteksi beban yang terlewat saat disusun di bangun_kasus.
8. Orientasi beban: node memakai elevasi alinyemen (nodes.elevasi_model),
   jadi gelagar miring. Beban gravitasi D1, D2, BTR diuraikan ke sumbu lokal
   (komponen_lokal: Wy = q cos a, Wx = q sin a) sehingga resultannya tetap
   vertikal; jumlah reaksi horizontal tiap kasus diperiksa = 0. KEL sudah
   berupa beban nodal vertikal global. Dasar panjang: DASAR_PANJANG.
9. Menjalankan langsung: python -m core.analysis (dari root repo).

Referensi: core/loads.py, core/section_strips.py, core/nodes.py,
core/elements.py, core/boundary_condition.py
"""

import os
import openseespy.opensees as ops

try:
    from core import loads, section_strips as strips
except ImportError:
    import loads
    import section_strips as strips

try:
    from project import project_data as pdata
except ImportError:
    import project_data as pdata


# ============================================================
# 1. KONSTANTA
# ============================================================

TS_TAG = 1
OFFSET_DEFAULT = (0.0, 1.75, -1.75)      # m, lajur penuh 5.5 m
# posisi KEL pada bentang (0..1). 0 dan 1 = tepat di tumpuan (reaksi maks).
KEL_FRAKSI_DEFAULT = tuple(round(0.1 * i, 2) for i in range(11))
TOL_KESETIMBANGAN = 1e-6                 # relatif terhadap beban total

# Dasar panjang beban garis (kN/m). Semua beban adalah beban GRAVITASI
# (arah vertikal global), tetapi nilai kN/m-nya dapat didefinisikan per:
#   "aksial"     : per meter panjang SUMBU gelagar (berat sendiri, aspal,
#                  barrier: besaran fisik per panjang elemen)
#   "horizontal" : per meter panjang proyeksi horizontal (beban hidup
#                  lajur BTR: q kPa pada luas denah)
# Ubah di project_data.DASAR_PANJANG_BEBAN bila ketentuan proyek berbeda.
DASAR_PANJANG_DEFAULT = {"D1": "aksial", "D2": "aksial", "BTR": "horizontal"}
DASAR_PANJANG = dict(DASAR_PANJANG_DEFAULT)
DASAR_PANJANG.update(getattr(pdata, "DASAR_PANJANG_BEBAN", {}) or {})


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
# 2b. ORIENTASI BEBAN PADA ELEMEN MIRING
# ============================================================

def intensitas_aksial(jenis, w, cos_a):
    """
    Intensitas beban VERTIKAL per meter panjang sumbu elemen (kN/m, negatif
    ke bawah), dari besaran w sesuai DASAR_PANJANG[jenis].
    horizontal: gaya per panjang horizontal q_h -> per panjang sumbu
                q_h * dx/L = q_h * cos_a.
    """
    dasar = DASAR_PANJANG[jenis]
    if dasar == "aksial":
        return w
    if dasar == "horizontal":
        return w * cos_a
    raise ValueError("DASAR_PANJANG[{}] = {!r} tidak dikenal.".format(
        jenis, dasar))


def komponen_lokal(q, cos_a, sin_a):
    """
    Uraikan beban vertikal merata q (per panjang sumbu, kN/m, arah gravitasi
    = negatif) ke sumbu lokal elemen memanjang (x lokal = sumbu elemen,
    y lokal tegak lurus sumbu dalam bidang x-y, z lokal = z global):
        Wy = q * cos_a      (tegak lurus sumbu)
        Wx = q * sin_a      (sepanjang sumbu)
    Resultan vertikal komponen = Wy*cos_a + Wx*sin_a = q; resultan
    horizontal = -Wy*sin_a + Wx*cos_a = 0.
    """
    return q * cos_a, q * sin_a


def beban_kel_di(x_t, b, b_h, P_per_lebar, stasiun, node_map, memanjang,
                 z_garis):
    """
    KEL (beban garis melintang lajur) tepat di x = x_t pada bentang b.

    Beban per garis P_j = P_per_lebar * b_h[j] (kN, gravitasi, negatif).
    Bila x_t berimpit dengan stasiun pada unit bentang itu: beban nodal;
    selain itu: beban titik di dalam elemen memanjang yang memuat x_t.

    Returns (fy_nodal {node: P}, pload {tag: [(P, xL)]})  xL = fraksi 0..1
    dari ujung-i elemen (sepanjang sumbu = fraksi horizontal).
    """
    unit = next(e["unit"] for e in memanjang
                if e["x1"] >= b["x1"] - 1e-6 and e["x2"] <= b["x2"] + 1e-6)
    fy, pload = {}, {}
    i_st = next((i for i, s in enumerate(stasiun)
                 if s["unit"] == unit and abs(s["x"] - x_t) < 1e-6), None)
    for j in range(len(z_garis)):
        P = P_per_lebar * b_h[j]
        if P == 0.0:
            continue
        if i_st is not None:
            fy[node_map[(i_st, j)]] = -P
        else:
            e = next(e for e in memanjang
                     if e["unit"] == unit and e["garis"] == j
                     and e["x1"] < x_t < e["x2"])
            pload.setdefault(e["tag"], []).append(
                (-P, (x_t - e["x1"]) / (e["x2"] - e["x1"])))
    return fy, pload


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
                           "ele": {tag: q}, "node": {node: Fy},
                           "pload": {tag: [(P, xL)]}  (KEL di dalam elemen),
                           "total": beban vertikal total (kN, negatif ke bawah)}
        q = intensitas beban VERTIKAL (gravitasi) per meter panjang SUMBU
        elemen (kN/m, negatif ke bawah); jalankan_kasus menguraikannya ke
        sumbu lokal. Nilai kN/m dari loads.py didefinisikan per panjang
        aksial (D1, D2) atau per panjang horizontal (BTR) menurut
        DASAR_PANJANG; keduanya dikonversi ke per panjang aksial di sini.
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

    panjang = {e["tag"]: e["L_aksial"] for e in memanjang}
    cos_a = {e["tag"]: e["cos_a"] for e in memanjang}

    def total_ele(wy):
        """Resultan vertikal = sum(q_aksial * panjang sumbu)."""
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
        d1[e["tag"]] = intensitas_aksial(
            "D1", -loads.hitung_w_box(A) * fraksi(tipe)[j], e["cos_a"])
        d2[e["tag"]] = intensitas_aksial(
            "D2", -(w_nonstruk_m2 * b_jalan[j] + w_barrier_g[j]),
            e["cos_a"])
    kasus["D1"] = {"jenis": "D1", "bentang": None, "offset": None, "f": None,
                   "ele": d1, "node": {}, "total": total_ele(d1)}
    kasus["D2"] = {"jenis": "D2", "bentang": None, "offset": None, "f": None,
                   "ele": d2, "node": {}, "total": total_ele(d2)}

    # ---- BTR dan KEL ----
    P_kel_per_lebar = loads.hitung_P_kel_per_lebar(L_E)
    b_kel = loads.lebar_jalan_per_garis(z_garis)

    for o in offsets:
        b_h = loads.lebar_beban_hidup_per_garis(z_garis, lane_offset=o)
        for b in bentang:
            q = loads.hitung_q_btr(b["L"])

            # BTR di bentang b
            wy = {}
            for e in memanjang:
                if e["x1"] >= b["x1"] - 1e-6 and e["x2"] <= b["x2"] + 1e-6:
                    wy[e["tag"]] = intensitas_aksial(
                        "BTR", -q * b_h[e["garis"]], e["cos_a"])
            nama = "BTR|{}|o={:+.2f}".format(b["nama"], o)
            kasus[nama] = {"jenis": "BTR", "bentang": b["k"], "offset": o,
                           "f": None, "ele": wy, "node": {},
                           "total": total_ele(wy)}

            # KEL di bentang b (bergerak: tepat di x_t, tanpa pembulatan)
            for f in kel_fraksi:
                if f > 1.0 - 1e-9 and b is not bentang[-1]:
                    continue          # tumpuan bersama = f = 0 bentang berikut
                x_t = b["x1"] + f * b["L"]
                fy, pload = beban_kel_di(
                    x_t, b, b_kel, P_kel_per_lebar, stasiun, node_map,
                    memanjang, z_garis)
                total = sum(fy.values()) + sum(
                    P for lst in pload.values() for P, _ in lst)
                nama = "KEL|{}|f={:.2f}|o={:+.2f}".format(b["nama"], f, o)
                kasus[nama] = {"jenis": "KEL", "bentang": b["k"], "offset": o,
                               "f": f, "ele": {}, "node": fy,
                               "pload": pload, "total": total, "x": x_t}

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


def jalankan_kasus(nama, kasus, bc_nodes, ele_memanjang, semua_node, pid,
                   geo=None):
    """
    Jalankan satu kasus, kumpulkan respon, lalu bersihkan.

    Returns dict kategori -> {kunci: nilai}:
      R   : reaksi vertikal Ry per node tumpuan
      Uy  : lendutan vertikal tiap node
      Rx, Rz : reaksi horizontal (harus nol untuk beban vertikal)
      Mz_i, Mz_j, Vy_i, Vy_j, T_i, T_j, N_i, N_j : gaya ujung elemen
                  memanjang (lokal)

    geo : {tag: (cos_a, sin_a)} arah sumbu elemen memanjang; beban gravitasi
          diuraikan ke sumbu lokal (komponen_lokal) agar tetap vertikal.
    """
    ops.pattern('Plain', pid, TS_TAG)
    for tag, q in kasus["ele"].items():
        if geo is None or tag not in geo:
            raise ValueError("Geometri (cos_a, sin_a) elemen {} tidak "
                             "tersedia untuk menguraikan beban.".format(tag))
        wy, wx = komponen_lokal(q, *geo[tag])
        ops.eleLoad('-ele', tag, '-type', '-beamUniform', wy, 0.0, wx)
    for tag, daftar in kasus.get("pload", {}).items():
        c, sn = geo[tag]
        for P, xl in daftar:                 # P vertikal -> Py = P cos, Px = P sin
            ops.eleLoad('-ele', tag, '-type', '-beamPoint', P * c, 0.0, xl,
                        P * sn)
    for n, fy in kasus["node"].items():
        ops.load(n, 0.0, fy, 0.0, 0.0, 0.0, 0.0)

    if ops.analyze(1) != 0:
        raise RuntimeError("Analisis gagal pada kasus {}".format(nama))
    ops.reactions()

    R = {n: ops.nodeReaction(n)[1] for n in bc_nodes}
    Rx = {n: ops.nodeReaction(n)[0] for n in bc_nodes}
    Rz = {n: ops.nodeReaction(n)[2] for n in bc_nodes}
    skala = TOL_KESETIMBANGAN * max(1.0, abs(kasus["total"]))
    sisa = sum(R.values()) + kasus["total"]
    if abs(sisa) > skala:
        raise RuntimeError(
            "Kesetimbangan gagal pada {}: sum(Ry) = {:.6f}, beban = {:.6f}"
            .format(nama, sum(R.values()), kasus["total"]))
    # Beban gravitasi vertikal: jumlah reaksi horizontal harus nol.
    if abs(sum(Rx.values())) > skala or abs(sum(Rz.values())) > skala:
        raise RuntimeError(
            "Kesetimbangan horizontal gagal pada {}: sum(Rx) = {:.6f}, "
            "sum(Rz) = {:.6f} (beban vertikal tidak boleh menghasilkan "
            "reaksi horizontal; periksa orientasi beban)".format(
                nama, sum(Rx.values()), sum(Rz.values())))

    hasil = {
        "R": R, "Rx": Rx, "Rz": Rz,
        "Uy": {n: ops.nodeDisp(n)[1] for n in semua_node},
        "Mz_i": {}, "Mz_j": {},
        "Vy_i": {}, "Vy_j": {},
        "T_i": {}, "T_j": {},
        "N_i": {}, "N_j": {},
    }

    for tag in ele_memanjang:
        f = ops.eleForce(tag)

        hasil["Mz_i"][tag] = f[5]
        hasil["Mz_j"][tag] = f[11]

        hasil["Vy_i"][tag] = f[1]
        hasil["Vy_j"][tag] = f[7]

        hasil["T_i"][tag] = f[3]
        hasil["T_j"][tag] = f[9]

        hasil["N_i"][tag] = f[0]
        hasil["N_j"][tag] = f[6]


    ops.remove('loadPattern', pid)
    ops.reset()
    return hasil


def jalankan_semua(kasus, node_result, elemen_result, bc_list, verbose=True):
    """Jalankan seluruh kasus dasar. Return dict nama -> hasil."""
    setup_analysis()
    bc_nodes = sorted({b["node"] for b in bc_list})
    ele_m = [e["tag"] for e in elemen_result["memanjang"]]
    semua_node = sorted(node_result["node_map"].values())
    geo = {e["tag"]: (e["cos_a"], e["sin_a"])
           for e in elemen_result["memanjang"]}

    hasil = {}
    for pid, (nama, k) in enumerate(kasus.items(), start=1):
        hasil[nama] = jalankan_kasus(nama, k, bc_nodes, ele_m,
                                     semua_node, pid, geo=geo)
        if verbose:
            print("  [{:>3d}/{}] {:<40s} beban = {:>10.2f} kN".format(
                pid, len(kasus), nama, k["total"]))
    return hasil



# ============================================================
# 5. MAIN
# ============================================================

if __name__ == "__main__":
    # Jalankan dari root repo:  python -m core.analysis
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    from project import project_data as pdata
    from core import nodes
    from core import elements
    from core import boundary_condition as bc
    from core import output

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
