# project/project_data.py
"""
Data masukan jembatan Baros (satu-satunya sumber data geometri deck).
Satuan: kN, m, kPa (kecuali dinyatakan lain pada tiap blok).

Tujuan repo ini: menghasilkan GAYA DALAM dan REAKSI deck (grillage 3D,
tumpuan kaku). Pier, pier head, pile cap, bored pile, bearing dan stopper
akan berada di repo terpisah.

Status tiap blok
----------------
[AKTIF]       dipakai pipeline core/ (nodes, elements, boundary_condition,
              loads, analysis):
                  SUPPORTS, SECTION_MAP, BOX_SECTIONS, BEARINGS (+BEARING_JARAK,
              BEARING_KIRI_Z)
[REFERENSI]   tidak dipakai kode, hanya dokumentasi/cek manual:
                  SPANS, EXPANSION_JOINTS, INFO
[PLACEHOLDER] BUKAN bagian pipeline repo ini (disiapkan untuk repo pier /
              pondasi), tidak dibaca modul mana pun di core/. Nilainya
              belum diaudit:
                  PIER_HEIGHT, PIER_SECTION, PIERHEAD, PIERHEAD_TYPE,
                  STOPPER, MATERIAL, BEARING, DECK

Sumbu: x = memanjang jembatan, z = melintang, y = vertikal (ke atas).

CATATAN AUDIT
-------------
1. BOX_SECTIONS sudah diaudit (lihat catatan di blok itu).
2. SECTION_MAP mencakup x = -0.27 ... 206.0593 (termasuk overhang),
   sedangkan SUPPORTS hanya x = 0 ... 204.4944.
3. Konsistensi antar blok (SUPPORTS vs SPANS vs INFO) belum dicek otomatis.
"""

# ============================================================
# GEOMETRI TRANSVERSAL DECK                         [SOURCE OF TRUTH]
# ============================================================
# Referensi batas tributari lima strip grillage (m), dari hasil ukur fisik.
# Ini BUKAN posisi node fisik; posisi node dihitung sebagai centroid strip.
Z_GARIS_REF = (-5.0, -2.5182, 0.0, 2.5182, 5.0)
DECK_WIDTH = 10.0
ROAD_WIDTH = 9.0

# ============================================================
# SUPPORT                                                  [AKTIF]
# ============================================================
# x : posisi memanjang (m, dari A1); y : elevasi dek di tumpuan (m, dpl).
# "y" TIDAK dipakai grillage (model planar, y = 0 bidang netral).
# "type" : "abutment" / "pier" (informasi saja; BC dibuat di
#          boundary_condition.py dari nama, bukan dari type).
SUPPORTS = {
    "A1": {"x": 0.0000,    "y": 740.7678, "type": "abutment"},
    "P1": {"x": 16.2472,   "y": 741.4288, "type": "pier"},
    "P2": {"x": 33.7472,   "y": 742.2948, "type": "pier"},
    "P3": {"x": 51.2472,   "y": 743.1698, "type": "pier"},
    "P4": {"x": 74.7472,   "y": 744.1168, "type": "pier"},
    "P5": {"x": 112.7472,  "y": 744.1168, "type": "pier"},
    "P6": {"x": 130.2472,  "y": 743.4688, "type": "pier"},
    "P7": {"x": 155.2472,  "y": 742.2198, "type": "pier"},
    "P8": {"x": 180.2472,  "y": 740.9708, "type": "pier"},
    "A2": {"x": 204.4944,  "y": 739.7198, "type": "abutment"},
}

# [REFERENSI] Bentang: (dari, ke, panjang L (m), KELANDAIAN (%)).
# Kolom ke-4 = 100 x beda elevasi / L (mis. A1-P1: 0.661 m / 16.2472 m = 4.068 %),
# BUKAN selisih elevasi dalam meter. Diperiksa otomatis oleh SC-18.
# Kode memakai analysis.daftar_bentang(SUPPORTS), BUKAN list ini; list ini
# hanya untuk pembanding manual (jumlah L harus = 204.4944 m).
SPANS = [
    ("A1", "P1", 16.2472, +4.068),
    ("P1", "P2", 17.5000, +4.949),
    ("P2", "P3", 17.5000, +5.000),
    ("P3", "P4", 23.5000, +4.030),
    ("P4", "P5", 38.0000,  0.000),
    ("P5", "P6", 17.5000, -3.703),
    ("P6", "P7", 25.0000, -4.996),
    ("P7", "P8", 25.0000, -4.996),
    ("P8", "A2", 24.2472, -5.160),
]

# [REFERENSI] Lokasi expansion joint. Yang MEMUTUS gelagar di model hanya
# P2 dan P7 (nodes.EJ_SUPPORTS). EJ.1 (A1) dan EJ.4 (A2) berada di ujung
# jembatan sehingga tidak membagi gelagar menjadi unit tambahan.
EXPANSION_JOINTS = {
    "EJ.1": "A1",
    "EJ.2": "P2",
    "EJ.3": "P7",
    "EJ.4": "A2",
}

# ============================================================
# BOX SECTIONS (Kondisi SERVICE)             [AKTIF]
# ============================================================
# ***** AUDIT NUMERIK SELESAI - BERDASARKAN GEOMETRI DXF *****
# Properti penampang dihitung dari DXF scaled menggunakan
# integrasi geometri (Green) dan finite element (sectionproperties).
# Konvergensi J diperiksa menggunakan tiga ukuran mesh dengan
# toleransi 0.5%. Hasil A, Ix, dan Iy konsisten antara Green dan FE.
#
# Dipakai sebagai TOTAL properti penampang penuh per tipe.
# section_strips.py membagi total ini ke 5 garis memanjang dan
# menskalakan kontribusinya agar jumlah properti sesuai total di sini.
#
# Satuan: A (m2); Ix, Iy, J (m4); cx, cy (m).
#   Ix : inersia lentur VERTIKAL (sumbu horizontal) -> Iz elemen OpenSees
#   Iy : inersia lentur LATERAL (sumbu vertikal)   -> Iy elemen OpenSees
#   cx, cy : koordinat centroid global DXF; tidak dipakai langsung
#            oleh pipeline analisis, hanya dibaca sections.get_section.
#   file, deskripsi : informasi penampang.
#
# Hasil audit numerik:
#   solid   : A=8.2231, Ix=1.4527, Iy=33.3927, J=3.8232
#   hollow  : A=7.7073, Ix=1.4388, Iy=32.8494, J=3.7533
#   tumpuan : A=7.9676, Ix=1.3008, Iy=33.3705, J=3.1661
#
# J dihitung dengan sectionproperties; perubahan mesh terakhir
# masing-masing memenuhi toleransi konvergensi 0.5%.
# Nilai BOX_SECTIONS merupakan sumber properti yang diprioritaskan
# oleh sections.get_J; jangan menganggap sections.J_VALUES sebagai
# nilai yang digunakan model jika nilainya berbeda.
#
# Catatan interpretasi:
#   (a) Ketiga tipe memiliki geometri DXF masing-masing. Penampang
#       solid, hollow, dan tumpuan memang berbeda sesuai desain.
#   (b) Luas penampang tumpuan lebih kecil daripada solid. Hal ini
#       tidak otomatis menunjukkan kesalahan karena geometri daerah
#       tumpuan memiliki pengurangan akibat kebutuhan stopper.
#   (c) Nilai properti yang tercantum adalah total per tipe penampang.
#       Distribusi properti ke lima garis grillage mengikuti
#       implementasi section_strips.py.
#   (d) Nilai properti berlaku menurut tipe yang dipilih melalui
#       SECTION_MAP; pastikan pemetaan tipe terhadap segmen jembatan
#       sesuai dengan geometri desain.
#
# Batas audit:
#   Audit ini memverifikasi konsistensi numerik terhadap geometri
#   yang dibaca dari DXF, bukan validasi independen terhadap gambar
#   rencana atau metode pembagian properti ke lima garis grillage.
BOX_SECTIONS = {
    "solid": {
        "A":  8.2231,
        "Ix": 1.4527,
        "Iy": 33.3927,
        "J":  3.8232,      # ← dari warping
        "cx": 1.6886,
        "cy": 0.4659,
        "file": "Penampang_tipikal.dxf",
        "deskripsi": "Solid (transisi)",
    },
    "hollow": {
        "A":  7.7073,
        "Ix": 1.4388,
        "Iy": 32.8494,
        "J":  3.7533,
        "cx": 1.6886,
        "cy": 0.4729,

        "file": "Penampang_hollow.dxf",
        "deskripsi": "Hollow (4 drum void)",
    },
    "tumpuan": {
        "A":  7.9676,
        "Ix": 1.3008,
        "Iy": 33.3705,
        "J":  3.1661,      # ← dari warping
        "cx": 1.5748,
        "cy": 0.3717,

        "file": "Penampang_tumpuan.dxf",
        "deskripsi": "Tumpuan (dengan diafragma)",
    },
}

# ============================================================
# SECTION MAP (SERVICE) - 38 segmen                         [AKTIF]
# ============================================================
# (x1, x2, tipe) berurutan dan menyambung (x2 segmen i = x1 segmen i+1).
# Seluruh x1/x2 menjadi stasiun node (nodes.kumpulkan_x_unik) bersama
# posisi SUPPORTS. Tipe yang sah: kunci BOX_SECTIONS.
# x = -0.27 ... 206.0593 (overhang 0.27 m di A1 dan 1.5649 m di A2).
SECTION_MAP = [
    (-0.2700,    0.0000, "solid"),
    (0.0000,    1.0800, "tumpuan"),
    (1.0800,    1.3300, "solid"),
    (1.3300,   10.0800, "hollow"),
    (10.0800,   15.6800, "solid"),
    (15.6800,   17.4800, "tumpuan"),
    (17.4800,   23.0800, "solid"),
    (23.0800,   32.8050, "hollow"),
    (32.8050,   33.0390, "solid"),
    (33.0390,   35.7390, "tumpuan"),
    (35.7390,   36.2550, "solid"),
    (36.2550,   45.9793, "hollow"),
    (45.9793,   51.5793, "solid"),
    (51.5793,   53.3793, "tumpuan"),
    (53.3793,   58.9793, "solid"),
    (58.9793,   69.4793, "hollow"),
    (69.4793,   75.0793, "solid"),
    (75.0793,   76.8793, "tumpuan"),
    (76.8793,   82.4793, "solid"),
    (82.4793,  107.4793, "hollow"),
    (107.4793,  113.0793, "solid"),
    (113.0793,  114.8793, "tumpuan"),
    (114.8793,  120.4793, "solid"),
    (120.4793,  124.9793, "hollow"),
    (124.9793,  130.5793, "solid"),
    (130.5793,  132.3793, "tumpuan"),
    (132.3793,  137.9793, "solid"),
    (137.9793,  155.2043, "hollow"),
    (155.2043,  155.5793, "solid"),
    (155.5793,  157.3793, "tumpuan"),
    (157.3793,  157.7543, "solid"),
    (157.7543,  174.9793, "hollow"),
    (174.9793,  180.5793, "solid"),
    (180.5793,  182.3793, "tumpuan"),
    (182.3793,  187.9793, "solid"),
    (187.9793,  204.7293, "hollow"),
    (204.7293,  204.9793, "solid"),
    (204.9793,  206.0593, "tumpuan"),
]

# ============================================================
# BEARING (TABLE BEARING)                                  [AKTIF]
# ============================================================
# Sumber: tabel bearing (B1-B24) dan gambar denah. Dipakai
# boundary_condition.terapkan_bc: tumpuan vertikal HANYA di posisi bearing,
# bukan di semua garis memanjang.
#
# Tipe -> fixity bearing (ux = memanjang, uy = vertikal, uz = melintang):
#   "MD"   multi-arah       : uy saja                 (0,1,0)
#   "OD-L" satu arah, bebas MEMANJANG, tahan melintang (0,1,1)
#   "OD-T" satu arah, bebas MELINTANG, tahan memanjang (1,1,0)
#   "FIX"  tetap                                      (1,1,1)
# OD-L / OD-T dibaca dari kolom gaya horizontal tabel: OD dengan gaya
# melintang > 0 dan memanjang = 0 -> OD-L; OD dengan gaya memanjang > 0 dan
# melintang = 0 (B3, B8, B22) -> OD-T. Rotasi tidak ditahan.
#
# sisi: None untuk support biasa; "L"/"R" untuk support EJ (P2, P7):
#   "L" = ujung unit sebelumnya, "R" = awal unit berikutnya.
#
# Posisi z: nomor ganjil di sisi KIRI bila dilihat dari arah A1, genap di
# kanan. BEARING_KIRI_Z = -1 mengasumsikan +z = kanan (sistem tangan kanan,
# x ke depan, y ke atas). Ubah ke +1 bila model memakai orientasi lain.
# Jarak antar bearing (m): abutment 1.52, pier head 0.94, simetris terhadap
# sumbu penampang (z = 0). Diasumsikan simetris; periksa gambar.
BEARING_JARAK = {"abutment": 1.52, "pier": 0.94}
BEARING_KIRI_Z = -1

BEARINGS = [
    # (id,   support, sisi, tipe)
    ("B1",  "A1", None, "MD"),
    ("B2",  "A1", None, "OD-L"),
    ("B3",  "P1", None, "OD-T"),
    ("B4",  "P1", None, "FIX"),
    ("B5",  "P2", "L",  "MD"),
    ("B6",  "P2", "L",  "OD-L"),
    ("B7",  "P2", "R",  "FIX"),
    ("B8",  "P2", "R",  "OD-T"),
    ("B9",  "P3", None, "MD"),
    ("B10", "P3", None, "OD-L"),
    ("B11", "P4", None, "MD"),
    ("B12", "P4", None, "OD-L"),
    ("B13", "P5", None, "MD"),
    ("B14", "P5", None, "OD-L"),
    ("B15", "P6", None, "MD"),
    ("B16", "P6", None, "OD-L"),
    ("B17", "P7", "L",  "MD"),
    ("B18", "P7", "L",  "OD-L"),
    ("B19", "P7", "R",  "MD"),
    ("B20", "P7", "R",  "OD-L"),
    ("B21", "P8", None, "FIX"),
    ("B22", "P8", None, "OD-T"),
    ("B23", "A2", None, "MD"),
    ("B24", "A2", None, "OD-L"),
]

# ============================================================
# DASAR PANJANG BEBAN GARIS                                [AKTIF]
# ============================================================
# Semua beban D1, D2, BTR adalah beban GRAVITASI (vertikal global). Karena
# gelagar mengikuti alinyemen (node y = nodes.elevasi_model), nilai kN/m
# harus dinyatakan terhadap suatu panjang:
#   "aksial"     per meter panjang SUMBU gelagar
#   "horizontal" per meter panjang proyeksi horizontal
# D1 (gamma*A) dan D2 (aspal, air, barrier) adalah besaran per panjang
# elemen -> "aksial". BTR (q kPa pada luas denah lajur) -> "horizontal".
# analysis.intensitas_aksial mengonversi ke per panjang sumbu lalu
# analysis.komponen_lokal menguraikannya ke sumbu lokal elemen.
# KEL berupa beban nodal vertikal global (tidak terpengaruh).
DASAR_PANJANG_BEBAN = {"D1": "aksial", "D2": "aksial", "BTR": "horizontal"}

# ============================================================
# TABEL BEARING (BEBAN RENCANA)                            [AKTIF]
# ============================================================
# Disalin dari TABLE BEARING gambar rencana (dibaca dari tangkapan layar;
# PERIKSA ULANG terhadap dokumen asli). Satuan: gaya ton-force, movement mm.
#   perm_t     : gaya aksial PERMANEN        sls_t : gaya aksial SLS
#   hx_long_t, hx_trans_t : gaya horizontal SLS (memanjang, melintang)
#   mov_long_mm, mov_trans_mm : movement horizontal
# Ini BEBAN RENCANA yang tertulis pada tabel, BUKAN kapasitas bearing.
# Dipakai hanya sebagai pembanding (design_review SC-15).
TON_KN = 9.80665
BEARING_TABEL = {
    "B1":  {"tipe": "MD",  "perm_t": 100, "sls_t": 150, "hx_long_t": 0,  "hx_trans_t": 0,   "mov_long_mm": 7,  "mov_trans_mm": 0},
    "B2":  {"tipe": "OD",  "perm_t": 100, "sls_t": 250, "hx_long_t": 0,  "hx_trans_t": 50,  "mov_long_mm": 8,  "mov_trans_mm": 0},
    "B3":  {"tipe": "OD",  "perm_t": 200, "sls_t": 350, "hx_long_t": 40, "hx_trans_t": 0,   "mov_long_mm": 0,  "mov_trans_mm": 8},
    "B4":  {"tipe": "FIX", "perm_t": 200, "sls_t": 400, "hx_long_t": 30, "hx_trans_t": 110, "mov_long_mm": 0,  "mov_trans_mm": 0},
    "B5":  {"tipe": "MD",  "perm_t": 100, "sls_t": 150, "hx_long_t": 0,  "hx_trans_t": 0,   "mov_long_mm": 8,  "mov_trans_mm": 0},
    "B6":  {"tipe": "OD",  "perm_t": 100, "sls_t": 200, "hx_long_t": 0,  "hx_trans_t": 50,  "mov_long_mm": 8,  "mov_trans_mm": 0},
    "B7":  {"tipe": "FIX", "perm_t": 100, "sls_t": 250, "hx_long_t": 50, "hx_trans_t": 70,  "mov_long_mm": 0,  "mov_trans_mm": 0},
    "B8":  {"tipe": "OD",  "perm_t": 100, "sls_t": 150, "hx_long_t": 80, "hx_trans_t": 0,   "mov_long_mm": 0,  "mov_trans_mm": 0},
    "B9":  {"tipe": "MD",  "perm_t": 250, "sls_t": 450, "hx_long_t": 0,  "hx_trans_t": 0,   "mov_long_mm": 8,  "mov_trans_mm": 0},
    "B10": {"tipe": "OD",  "perm_t": 250, "sls_t": 400, "hx_long_t": 0,  "hx_trans_t": 50,  "mov_long_mm": 8,  "mov_trans_mm": 0},
    "B11": {"tipe": "MD",  "perm_t": 300, "sls_t": 650, "hx_long_t": 0,  "hx_trans_t": 0,   "mov_long_mm": 20, "mov_trans_mm": 0},
    "B12": {"tipe": "OD",  "perm_t": 300, "sls_t": 600, "hx_long_t": 0,  "hx_trans_t": 40,  "mov_long_mm": 19, "mov_trans_mm": 0},
    "B13": {"tipe": "MD",  "perm_t": 300, "sls_t": 600, "hx_long_t": 0,  "hx_trans_t": 0,   "mov_long_mm": 35, "mov_trans_mm": 0},
    "B14": {"tipe": "OD",  "perm_t": 300, "sls_t": 600, "hx_long_t": 0,  "hx_trans_t": 30,  "mov_long_mm": 34, "mov_trans_mm": 0},
    "B15": {"tipe": "MD",  "perm_t": 250, "sls_t": 450, "hx_long_t": 0,  "hx_trans_t": 0,   "mov_long_mm": 43, "mov_trans_mm": 0},
    "B16": {"tipe": "OD",  "perm_t": 250, "sls_t": 450, "hx_long_t": 0,  "hx_trans_t": 140, "mov_long_mm": 42, "mov_trans_mm": 0},
    "B17": {"tipe": "MD",  "perm_t": 150, "sls_t": 300, "hx_long_t": 0,  "hx_trans_t": 0,   "mov_long_mm": 52, "mov_trans_mm": 0},
    "B18": {"tipe": "OD",  "perm_t": 150, "sls_t": 250, "hx_long_t": 0,  "hx_trans_t": 70,  "mov_long_mm": 52, "mov_trans_mm": 0},
    "B19": {"tipe": "MD",  "perm_t": 150, "sls_t": 250, "hx_long_t": 0,  "hx_trans_t": 0,   "mov_long_mm": 12, "mov_trans_mm": 0},
    "B20": {"tipe": "OD",  "perm_t": 150, "sls_t": 250, "hx_long_t": 0,  "hx_trans_t": 10,  "mov_long_mm": 12, "mov_trans_mm": 0},
    "B21": {"tipe": "FIX", "perm_t": 250, "sls_t": 500, "hx_long_t": 10, "hx_trans_t": 20,  "mov_long_mm": 0,  "mov_trans_mm": 0},
    "B22": {"tipe": "OD",  "perm_t": 250, "sls_t": 500, "hx_long_t": 10, "hx_trans_t": 0,   "mov_long_mm": 0,  "mov_trans_mm": 0},
    "B23": {"tipe": "MD",  "perm_t": 150, "sls_t": 250, "hx_long_t": 0,  "hx_trans_t": 0,   "mov_long_mm": 11, "mov_trans_mm": 0},
    "B24": {"tipe": "OD",  "perm_t": 150, "sls_t": 250, "hx_long_t": 0,  "hx_trans_t": 10,  "mov_long_mm": 11, "mov_trans_mm": 0},
}

# ============================================================
# KAPASITAS BEARING (DIISI OLEH PERENCANA)                 [AKTIF]
# ============================================================
# KOSONG = pemeriksaan kapasitas bearing "NOT ASSESSED". Isi hanya dengan
# kapasitas TERVERIFIKASI (brosur pabrikan / perhitungan), satuan kN:
#   KAPASITAS_BEARING = {
#       "B11": {"R_uls_kN": 9000.0, "R_sls_kN": 6500.0,
#               "standar": "SNI 1725:2016 + brosur pabrikan"},
#   }
# R_uls dibandingkan dengan reaksi maksimum kombinasi Strength; R_sls dengan
# Service I.
KAPASITAS_BEARING = {}

# ============================================================
# DASAR REGULASI FAKTOR KOMBINASI (DIISI OLEH PERENCANA)   [AKTIF]
# ============================================================
# Salin dari dokumen standar yang berlaku pada kontrak (bukan dari ingatan).
# Kosong = SC-20 "NOT ASSESSED". Contoh bentuk:
#   DASAR_REGULASI = "SNI 1725:2016 <pasal/tabel>"
#   KOMBINASI_REFERENSI = {"Strength I": {"D1": ..., "D2": ..., "L": ...}}
# D1 = berat sendiri (MS), D2 = beban mati tambahan (MA), L = beban lajur
# D (TD). Faktor MS bergantung bahan/cara konstruksi (pracetak vs cor di
# tempat) dan keadaan (biasa vs terkurangi).
DASAR_REGULASI = ""
KOMBINASI_REFERENSI = {}

# ============================================================
# KONFIGURASI REVIEW (pemeriksaan kewajaran)               [AKTIF]
# ============================================================
# Ambang di bawah adalah ambang SCREENING, bukan kriteria kode. Ubah sesuai
# persetujuan proyek. None = pemeriksaan tidak dinilai.
REVIEW = {
    # lendutan beban hidup per bentang <= L / rasio. L/800 hanya contoh
    # (lazim untuk beban hidup kendaraan); None = tidak dinilai.
    "batas_lendutan_rasio": 800.0,
    "tol_keseimbangan": 0.01,        # SC-04, SC-07 (relatif)
    "tol_kontinuitas": 0.01,         # SC-11 (relatif terhadap gaya maks kasus)
    "ambang_beban_per_m": 1.5,       # SC-10: reaksi permanen / (beban rata-rata x tributari)
    "ambang_bearing_tabel": 1.05,    # SC-15: rasio model/tabel > ambang -> WARNING
    "tol_sensitivitas": 0.05,        # SC-12: selisih antar konfigurasi garis
    "tol_referensi": None,           # SC-14: pita penerimaan model referensi
    "tol_beban_d1": 0.02,            # SC-13: D1 model vs integrasi luas
    "tol_diafragma_m": 0.5,          # SC-19: pusat diafragma vs garis support (m)
    "ambang_kel_gap": 0.10,          # SC-17: jarak posisi KEL / panjang bentang
}

# ============================================================
# BLOK BERIKUT [PLACEHOLDER] - BUKAN BAGIAN REPO INI
# ============================================================
# Disiapkan untuk repo pier/pondasi. Tidak dibaca oleh core/. Nilai belum
# diaudit dan dibiarkan apa adanya. Jangan memakainya untuk analisis deck.

# ============================================================
# PIER HEIGHT                                       [PLACEHOLDER]
# ============================================================
# Tinggi pier (m) per support, termasuk kunci abutmen A1/A2.
PIER_HEIGHT = {
    "A1": 1.5, "P1": 1.0, "P2": 2.1, "P3": 3.5, "P4": 5.3,
    "P5": 6.8, "P6": 5.2, "P7": 3.4, "P8": 2.4, "A2": 2.9,
}

# ============================================================
# PIER SECTION                                      [PLACEHOLDER]
# ============================================================
# PERHATIAN SATUAN: b, h, r dalam MILIMETER (berbeda dari satuan file
# ini yang meter). A (m2), Ix, Iy, J (m4) dalam meter.
PIER_SECTION = {
    "b": 2000, "h": 2500, "r": 750,
    "A": 4.7180, "Ix": 2.2961, "Iy": 1.4600, "J": 4.375,
}

# ============================================================
# PIER HEAD                                         [PLACEHOLDER]
# ============================================================
# H tinggi, b_mel lebar melintang, b_mem lebar memanjang (m).
PIERHEAD = {
    "tipe_1":  {"H": 2.0, "b_mel": 3.7, "b_mem": 2.5},
    "tipe_2":  {"H": 1.5, "b_mel": 3.7, "b_mem": 2.5},
    "tipe_EJ": {"H": 2.0, "b_mel": 3.7, "b_mem": 3.6},
}

PIERHEAD_TYPE = {
    "P1": "tipe_2", "P2": "tipe_EJ", "P3": "tipe_1",
    "P4": "tipe_1", "P5": "tipe_1", "P6": "tipe_1",
    "P7": "tipe_EJ", "P8": "tipe_1",
}

# ============================================================
# STOPPER, MATERIAL, BEARING, DECK                  [PLACEHOLDER]
# ============================================================
STOPPER = {"H": 0.5, "b": 0.92, "L": 1.8}

# MATERIAL TIDAK DIPAKAI. Nilai material yang berlaku ada di
# project/materials.py (f'c box 41.5 MPa -> E = 4700*sqrt(f'c) = 3.03e7 kPa,
# gamma beton box = 22 + 0.022*f'c = 22.913 kN/m3). Nilai di bawah
# (E 30e6, f'c 35 MPa, gamma 24) bertentangan dengan itu.
MATERIAL = {
    "E": 30e6, "G": 12.5e6, "fpc": 35e3, "fy": 420e3, "gamma": 24.0,
}

BEARING = {"H": 0.3, "b": 0.5, "L": 0.5, "tipe": "pot bearing"}

# DECK: lebar diambil dari DECK_WIDTH (sumber tunggal geometri transversal).
# skala_dxf : faktor skala pembacaan DXF (tidak dipakai section_strips,
# yang memakai geometri parametrik sendiri).
DECK = {"lebar": DECK_WIDTH, "tinggi": 1.5, "skala_dxf": 39.37}

# ============================================================
# INFO                                                [REFERENSI]
# ============================================================
# Ringkasan manual; tidak dibaca kode. Cocokkan dengan SUPPORTS /
# SECTION_MAP saat audit (jumlah_segmen_mapping = len(SECTION_MAP) = 38;
# panjang_total = 206.0593 - (-0.27) = 206.3293 m; panjang_A1_A2 = x A2).
INFO = {
    "nama": "Jembatan Baros",
    "panjang_A1_A2": 204.4944,
    "panjang_total": 206.3293,   # dengan overhang
    "elevasi_A1": 740.7678,
    "elevasi_A2": 739.7198,
    "elevasi_puncak": 744.1168,
    "rentang_elevasi": 4.397,            # elevasi tertinggi - terendah (P4/P5 - A2)
    "selisih_elevasi_A1_A2": -1.048,    # elevasi A2 - elevasi A1
    "jumlah_bentang": 9,
    "jumlah_support": 10,
    "jumlah_pier": 8,
    "jumlah_abutment": 2,
    "jumlah_EJ": 4,
    "jumlah_segmen_mapping": 38,
}