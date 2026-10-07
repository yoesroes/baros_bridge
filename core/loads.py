# core/loads.py
"""
Modul Beban untuk Jembatan Baros (Grillage 2D).
Satuan: kN, m, kPa.

Beban per elemen memanjang:
- Berat sendiri box girder (bervariasi per section)
- Beban mati non-struktur (aspal + air + barrier)
- Beban hidup lajur "D" (BTR + KEL) sesuai SNI 1725:2016 Pasal 8.3

Perubahan utama dibanding versi sebelumnya:
- BTR memakai lebar ekuivalen (5.5 m x 100% + sisa x 50%) dan faktor
  reduksi q untuk L > 30 m.
- KEL diperlakukan sebagai BEBAN TERPUSAT (kN), bukan beban merata (kN/m),
  dengan FBD yang bergantung pada panjang bentang ekuivalen.
- Semua beban dapat dibagi ke garis memanjang grillage (z_garis) lewat
  lebar tributari, sehingga total beban terjaga (tidak terhitung 5x).
- Elemen melintang TIDAK dibebani.
- `ele_tag` diganti `seg_id` (nomor segmen); tag elemen OpenSees sebaiknya
  dibuat di elements.py dari pasangan (garis, seg_id).

Referensi:
- SNI 1725:2016 - Pembebanan untuk Jembatan
"""

import math
import os
import sys
from contextlib import redirect_stdout

# ============================================================
# 1. KONSTANTA BEBAN
# ============================================================

# Material (SNI 1725:2016)
FPC_BOX = 41.5e3        # kPa (41.5 MPa)
FPC_PIER = 30.0e3       # kPa (30 MPa)

GAMMA_BETON_BOX = 22 + 0.022 * (FPC_BOX / 1000)   # 22.913 kN/m3
GAMMA_BETON_PIER = 22 + 0.022 * (FPC_PIER / 1000) # 22.66 kN/m3
GAMMA_BETON_BARRIER = GAMMA_BETON_PIER            # asumsi f'c barrier = 30 MPa
GAMMA_ASPAL = 22.0      # kN/m3
GAMMA_AIR = 10.0        # kN/m3

# Beban mati non-struktur
T_ASPAL = 0.075         # m
T_AIR = 0.005           # m (0.5 cm genangan)
A_BARRIER = 0.25        # m2 per barrier
B_JALAN = 9.0           # m (lebar lajur kendaraan)
B_DECK = 10.0           # m (lebar total deck)
N_SISI = 2              # jumlah sisi barrier

# Beban hidup (SNI 1725:2016 Pasal 8.3)
Q_BTR = 9.0             # kPa, BTR untuk L <= 30 m
P_KEL = 49.0            # kN/m per meter lebar transversal
FBD = 0.4               # default FBD untuk L_E <= 50 m
LEBAR_LAJUR_PENUH = 5.5 # m, lebar yang dibebani 100%
L_BTR_BATAS = 30.0      # m, batas reduksi BTR

# Posisi garis memanjang grillage (koordinat z, m)
Z_GARIS = (-5.0, -3.5, 0.0, 3.5, 5.0)


# ============================================================
# 2. FUNGSI PERHITUNGAN BEBAN (TOTAL DECK)
# ============================================================

def hitung_w_box(A):
    """Berat sendiri box girder per meter (kN/m), seluruh deck."""
    return GAMMA_BETON_BOX * A


def hitung_w_aspal():
    """Beban aspal per meter (kN/m)."""
    return GAMMA_ASPAL * T_ASPAL * B_JALAN


def hitung_w_air():
    """Beban genangan air per meter (kN/m)."""
    return GAMMA_AIR * T_AIR * B_JALAN


def hitung_w_barrier():
    """Beban barrier per meter (kN/m), jumlah kedua sisi."""
    return GAMMA_BETON_BARRIER * A_BARRIER * N_SISI


def hitung_w_non_struktur():
    """Total beban mati non-struktur (kN/m)."""
    return hitung_w_aspal() + hitung_w_air() + hitung_w_barrier()


# ---------------- Beban hidup lajur "D" ----------------

def lebar_ekuivalen(B=B_JALAN):
    """
    Lebar ekuivalen beban lajur: 5.5 m pertama 100%, sisanya 50%.
    B = 9.0 m -> 5.5 + 0.5 * 3.5 = 7.25 m.
    """
    if B <= LEBAR_LAJUR_PENUH:
        return B
    return LEBAR_LAJUR_PENUH + 0.5 * (B - LEBAR_LAJUR_PENUH)


def hitung_q_btr(L=None):
    """
    Intensitas BTR (kPa).
    L <= 30 m : q = 9.0
    L  > 30 m : q = 9.0 * (0.5 + 15 / L)
    L = panjang total yang dibebani. Jika None -> 9.0 (konservatif).
    """
    if L is None or L <= L_BTR_BATAS:
        return Q_BTR
    return Q_BTR * (0.5 + 15.0 / L)


def hitung_L_ekuivalen(bentang):
    """
    Panjang bentang ekuivalen jembatan menerus:
    L_E = sqrt(L_rata2 * L_maks).
    """
    bentang = list(bentang)
    L_av = sum(bentang) / len(bentang)
    return math.sqrt(L_av * max(bentang))


def hitung_fbd(L_E=None):
    """
    Faktor beban dinamis KEL (SNI 1725:2016).
    L_E <= 50   : 0.4
    50 < L_E < 90 : 0.525 - 0.0025 * L_E
    L_E >= 90   : 0.3
    """
    if L_E is None or L_E <= 50.0:
        return FBD
    if L_E < 90.0:
        return 0.525 - 0.0025 * L_E
    return 0.3


def hitung_w_btr(L=None, B=B_JALAN):
    """BTR per meter memanjang (kN/m), seluruh lebar lajur."""
    return hitung_q_btr(L) * lebar_ekuivalen(B)


def hitung_P_kel(L_E=None, B=B_JALAN):
    """
    KEL sebagai gaya terpusat (kN) untuk seluruh lebar lajur:
    P = p * lebar_ekuivalen * (1 + FBD).
    """
    return P_KEL * lebar_ekuivalen(B) * (1.0 + hitung_fbd(L_E))


def hitung_P_kel_per_lebar(L_E=None):
    """
    Intensitas KEL terhadap lebar transversal.

    Satuan:
        kN/m lebar transversal
    """
    return P_KEL * (1.0 + hitung_fbd(L_E))

def hitung_w_hidup(L=None):
    """
    Beban hidup MERATA (BTR saja) per meter (kN/m).
    KEL adalah beban terpusat -> lihat hitung_P_kel().
    """
    return hitung_w_btr(L)


def hitung_w_total(A, L=None):
    """Total beban merata per meter (kN/m): box + non-struktur + BTR."""
    return hitung_w_box(A) + hitung_w_non_struktur() + hitung_w_hidup(L)


# ============================================================
# 3. DISTRIBUSI KE GARIS MEMANJANG GRILLAGE
# ============================================================

def _overlap(a1, a2, b1, b2):
    """Panjang irisan interval [a1,a2] dan [b1,b2]."""
    return max(0.0, min(a2, b2) - max(a1, b1))


def batas_tributari(z_garis=Z_GARIS):
    """
    Batas tributari tiap garis: dari tengah-tengah ke garis tetangga.
    Garis terluar dibatasi sampai posisinya sendiri.
    Return: list of (z_awal, z_akhir).
    """
    z = list(z_garis)
    if len(z) < 2 or z != sorted(z):
        raise ValueError("z_garis harus >= 2 titik dan terurut naik.")
    mid = [(z[i] + z[i + 1]) / 2.0 for i in range(len(z) - 1)]
    batas = [z[0]] + mid + [z[-1]]
    return list(zip(batas[:-1], batas[1:]))


def distribusi_berat_sendiri(z_garis=Z_GARIS):
    """
    Fraksi berat sendiri box per garis (proporsional lebar tributari).
    Ganti dengan fraksi berdasarkan posisi web jika datanya tersedia.
    """
    lebar = [b - a for a, b in batas_tributari(z_garis)]
    total = sum(lebar)
    return [w / total for w in lebar]


def lebar_jalan_per_garis(z_garis=Z_GARIS, B=B_JALAN):
    """Lebar lajur kendaraan (m) yang jatuh di tributari tiap garis."""
    return [_overlap(a, b, -B / 2.0, B / 2.0)
            for a, b in batas_tributari(z_garis)]


def distribusi_barrier(z_garis=Z_GARIS):
    """
    Beban barrier (kN/m) per garis: satu barrier di tiap garis terluar
    (asumsi barrier berada di tepi deck).
    """
    w_satu = GAMMA_BETON_BARRIER * A_BARRIER
    hasil = [0.0] * len(z_garis)
    hasil[0] += w_satu
    hasil[-1] += w_satu
    if N_SISI != 2:
        raise ValueError("distribusi_barrier mengasumsikan N_SISI = 2.")
    return hasil


def lebar_beban_hidup_per_garis(z_garis=Z_GARIS, B=B_JALAN,
                                lane_offset=0.0):
    """
    Lebar efektif beban hidup (m) per garis: 100% pada lajur penuh 5.5 m
    (berpusat di z = lane_offset), 50% pada sisa lebar jalan.
    Jumlah semua garis = lebar_ekuivalen(B) = 7.25 m (B = 9 m).
    """
    b_pen = min(LEBAR_LAJUR_PENUH, B)
    batas_geser = (B - b_pen) / 2.0
    if abs(lane_offset) > batas_geser + 1e-9:
        raise ValueError(
            "lane_offset {:.3f} m membuat lajur penuh keluar dari jalan "
            "(maks +/- {:.3f} m).".format(lane_offset, batas_geser))
    penuh = (lane_offset - b_pen / 2.0, lane_offset + b_pen / 2.0)

    hasil = []
    for a, b in batas_tributari(z_garis):
        w_jalan = _overlap(a, b, -B / 2.0, B / 2.0)
        w_penuh = _overlap(a, b, *penuh)
        hasil.append(w_penuh + 0.5 * (w_jalan - w_penuh))
    return hasil


# ============================================================
# 4. BEBAN PER ELEMEN (PER SEGMEN)
# ============================================================

def hitung_beban_per_elemen(section_map, box_sections, z_garis=Z_GARIS,
                            L_beban=None, L_E=None, lane_offset=0.0,
                            f_berat=None):
    """
    Hitung beban untuk setiap segmen memanjang, total dan per garis.

    Parameters
    ----------
    section_map : list
        List of (x1, x2, tipe)
    box_sections : dict
        Properti penampang {tipe: {A, Ix, Iy, ...}}
    z_garis : sequence
        Koordinat z garis memanjang grillage.
    L_beban : float, optional
        Panjang yang dibebani untuk reduksi BTR. None -> q = 9 kPa
        (konservatif).
    L_E : float, optional
        Panjang bentang ekuivalen untuk FBD. None -> FBD = 0.4.
    lane_offset : float
        Pergeseran lajur penuh 5.5 m terhadap sumbu jalan (m).
    f_berat : list | dict | None
        Fraksi berat sendiri per garis. list = sama untuk semua tipe;
        dict {tipe: list} = per tipe. None -> proporsional lebar tributari.
        Untuk penampang Baros pakai section_strips.fraksi_berat(tipe)
        (berat sendiri sebanding dengan luas strip, bukan lebar).

    Returns
    -------
    elemen_data : list of dict
        Satuan beban merata kN/m; P_kel dalam kN.
        Kunci *_garis berisi list sepanjang len(z_garis).
    """
    f_default = distribusi_berat_sendiri(z_garis)
    b_jalan = lebar_jalan_per_garis(z_garis)
    w_barrier_g = distribusi_barrier(z_garis)
    b_hidup = lebar_beban_hidup_per_garis(z_garis, lane_offset=lane_offset)

    q = hitung_q_btr(L_beban)
    P_kel_per_lebar = hitung_P_kel_per_lebar(L_E)
    w_nonstruk_m2 = GAMMA_ASPAL * T_ASPAL + GAMMA_AIR * T_AIR  # kPa

    w_non_struktur = hitung_w_non_struktur()
    w_hidup = hitung_w_hidup(L_beban)
    P_kel = hitung_P_kel(L_E)

    w_nonstruk_g = [w_nonstruk_m2 * b + wb
                    for b, wb in zip(b_jalan, w_barrier_g)]
    w_hidup_g = [q * b for b in b_hidup]
    P_kel_g = [P_kel_per_lebar * b for b in b_hidup]

    elemen_data = []
    for i, (x1, x2, tipe) in enumerate(section_map):
        A = box_sections[tipe]["A"]
        w_box = hitung_w_box(A)
        if f_berat is None:
            f_i = f_default
        elif isinstance(f_berat, dict):
            f_i = f_berat[tipe]
        else:
            f_i = f_berat
        if abs(sum(f_i) - 1.0) > 1e-9:
            raise ValueError("Jumlah f_berat harus 1 (tipe {}).".format(tipe))

        elemen_data.append({
            "seg_id": i + 1,
            "x1": x1,
            "x2": x2,
            "tipe": tipe,
            "L": x2 - x1,
            "A": A,
            "w_box": w_box,
            "w_non_struktur": w_non_struktur,
            "w_hidup": w_hidup,           # BTR saja (kN/m)
            "w_total": w_box + w_non_struktur + w_hidup,
            "P_kel": P_kel,               # kN (terpusat)
            "z_garis": list(z_garis),
            "w_box_garis": [w_box * f for f in f_i],
            "w_non_struktur_garis": w_nonstruk_g,
            "w_hidup_garis": w_hidup_g,
            "P_kel_garis": P_kel_g,
        })

    return elemen_data


def cek_distribusi(elemen_data, tol=1e-6):
    """Pastikan jumlah beban per garis sama dengan total deck."""
    for e in elemen_data:
        pasangan = [
            ("w_box", e["w_box_garis"]),
            ("w_non_struktur", e["w_non_struktur_garis"]),
            ("w_hidup", e["w_hidup_garis"]),
            ("P_kel", e["P_kel_garis"]),
        ]
        for nama, garis in pasangan:
            if abs(sum(garis) - e[nama]) > tol:
                raise AssertionError(
                    "Segmen {}: sum({}_garis) = {:.6f} != {:.6f}".format(
                        e["seg_id"], nama, sum(garis), e[nama]))
    return True


# ============================================================
# 5. KOMBINASI PEMBEBANAN (SNI 1725:2016)
# ============================================================

KOMBINASI = {
    # ========================================================
    # SERVICE
    # ========================================================
    "Service I": {
        "D1": 1.0, "D2": 1.0, "L": 1.0, "P": 1.0,
        "description": "D1 + D2 + L + P",
    },
    "Service II": {
        "D1": 1.0, "D2": 1.0, "L": 1.3, "P": 1.0,
        "description": "D1 + D2 + 1.3L + P",
    },
    "Service III": {
        "D1": 1.0, "D2": 1.0, "L": 0.8, "P": 1.0,
        "description": "D1 + D2 + 0.8L + P",
    },
    "Service IV": {
        "D1": 1.0, "D2": 1.0, "L": 0.0, "P": 1.0,
        "description": "D1 + D2 + P",
    },

    # ========================================================
    # STRENGTH
    # ========================================================
    "Strength I": {
        "D1": 1.2, "D2": 2.0, "L": 1.8, "P": 1.0,
        "description": "1.2D1 + 2.0D2 + 1.8L + P",
    },
    "Strength II": {
        "D1": 1.2, "D2": 2.0, "L": 1.4, "P": 1.0,
        "description": "1.2D1 + 2.0D2 + 1.4L + P",
    },
    "Strength III": {
        "D1": 1.2, "D2": 2.0, "L": 0.0, "P": 1.0,
        "description": "1.2D1 + 2.0D2 + P + EWs",
    },
    "Strength IV": {
        "D1": 1.2, "D2": 2.0, "L": 0.0, "P": 1.0,
        "description": "1.2D1 + 2.0D2 + P",
    },
    "Strength V": {
        "D1": 1.2, "D2": 2.0, "L": 0.0, "P": 1.0,
        "description": "1.2D1 + 2.0D2 + P + EWs + EWL",
    },

    # ========================================================
    # EXTREME EVENT
    # ========================================================
    "Extreme Event I": {
        "D1": 1.0, "D2": 1.0, "L": 0.3, "P": 1.0, "EQ": 1.0,
        "description": "D1 + D2 + 0.3L + P + EQ",
    },
    "Extreme Event II": {
        "D1": 1.0, "D2": 1.0, "L": 0.3, "P": 1.0, "EQ": 1.0,
        "description": "D1 + D2 + 0.3L + P + EQ",
    },
}


def hitung_w_kombinasi(w_box, w_non_struktur, w_hidup,
                       w_prategang=0.0, w_gempa=0.0,
                       kombinasi="Service I"):
    """
    Beban MERATA kombinasi (kN/m): D1*w_box + D2*w_non_struktur
    + L*w_hidup(BTR) + P*w_prategang + EQ*w_gempa.
    Komponen KEL dikombinasikan terpisah: hitung_P_kombinasi().
    """
    if kombinasi not in KOMBINASI:
        raise ValueError("Kombinasi tidak dikenal: {}".format(kombinasi))

    f = KOMBINASI[kombinasi]

    return (
        f.get("D1", 0) * w_box +
        f.get("D2", 0) * w_non_struktur +
        f.get("L", 0) * w_hidup +
        f.get("P", 0) * w_prategang +
        f.get("EQ", 0) * w_gempa
    )


def hitung_P_kombinasi(P_kel, kombinasi="Service I"):
    """Beban terpusat KEL terfaktor (kN) untuk kombinasi tertentu."""
    if kombinasi not in KOMBINASI:
        raise ValueError("Kombinasi tidak dikenal: {}".format(kombinasi))
    return KOMBINASI[kombinasi].get("L", 0) * P_kel


def hitung_kombinasi_garis(ele, kombinasi="Strength I"):
    """
    Beban terfaktor per garis untuk satu segmen.
    Return: {"w": [kN/m per garis], "P": [kN per garis]}
    """
    w = [hitung_w_kombinasi(b, n, h, kombinasi=kombinasi)
         for b, n, h in zip(ele["w_box_garis"],
                            ele["w_non_struktur_garis"],
                            ele["w_hidup_garis"])]
    P = [hitung_P_kombinasi(p, kombinasi) for p in ele["P_kel_garis"]]
    return {"w": w, "P": P}


def hitung_semua_kombinasi(elemen_data):
    """
    Hitung semua kombinasi (beban merata, seluruh deck) per segmen.

    Returns
    -------
    hasil : dict
        {kombinasi: [w_total per segmen]}
    """
    hasil = {nama: [] for nama in KOMBINASI}
    for ele in elemen_data:
        for nama in KOMBINASI:
            hasil[nama].append(hitung_w_kombinasi(
                ele["w_box"], ele["w_non_struktur"], ele["w_hidup"],
                kombinasi=nama))
    return hasil


# ============================================================
# 6. OUTPUT INFORMATIF
# ============================================================

def print_parameter(L_beban=None, L_E=None):
    """Cetak parameter beban."""
    print("=" * 65)
    print("PARAMETER BEBAN")
    print("=" * 65)
    print("MATERIAL:")
    print("  f'c box       = {:>8.1f} MPa".format(FPC_BOX / 1000))
    print("  f'c pier      = {:>8.1f} MPa".format(FPC_PIER / 1000))
    print("  gamma box     = {:>8.3f} kN/m3".format(GAMMA_BETON_BOX))
    print("  gamma barrier = {:>8.3f} kN/m3".format(GAMMA_BETON_BARRIER))
    print()
    print("BEBAN MATI NON-STRUKTUR:")
    print("  gamma aspal   = {:>8.1f} kN/m3".format(GAMMA_ASPAL))
    print("  t aspal       = {:>8.3f} m".format(T_ASPAL))
    print("  gamma air     = {:>8.1f} kN/m3".format(GAMMA_AIR))
    print("  t air         = {:>8.3f} m".format(T_AIR))
    print("  A barrier     = {:>8.3f} m2".format(A_BARRIER))
    print("  b jalan       = {:>8.1f} m".format(B_JALAN))
    print()
    print("BEBAN HIDUP (SNI 1725:2016):")
    print("  q BTR         = {:>8.3f} kPa".format(hitung_q_btr(L_beban)))
    print("  p KEL         = {:>8.1f} kN/m".format(P_KEL))
    print("  L_E           = {}".format(
        "-" if L_E is None else "{:.2f} m".format(L_E)))
    print("  FBD           = {:>8.3f}".format(hitung_fbd(L_E)))
    print("  b ekuivalen   = {:>8.3f} m".format(lebar_ekuivalen()))
    print()
    print("HASIL PERHITUNGAN:")
    print("  w aspal       = {:>8.2f} kN/m".format(hitung_w_aspal()))
    print("  w air         = {:>8.2f} kN/m".format(hitung_w_air()))
    print("  w barrier     = {:>8.2f} kN/m".format(hitung_w_barrier()))
    print("  w non-struk   = {:>8.2f} kN/m".format(hitung_w_non_struktur()))
    print("  w BTR (hidup) = {:>8.2f} kN/m".format(hitung_w_btr(L_beban)))
    print("  P KEL         = {:>8.2f} kN  (terpusat, seluruh lajur)".format(
        hitung_P_kel(L_E)))
    print()


def print_ringkasan(elemen_data):
    """Cetak tabel beban per segmen."""
    print("=" * 105)
    print("RINGKASAN BEBAN MERATA PER SEGMEN (SELURUH DECK)")
    print("=" * 105)
    print("{:>4s} {:>9s} {:>9s} {:>10s} {:>8s} {:>10s} {:>10s} {:>10s}".format(
        "Seg", "x1", "x2", "Tipe", "L (m)", "A (m2)", "w_box", "w_total"))
    print("-" * 105)

    for ele in elemen_data:
        print("{:>4d} {:>9.3f} {:>9.3f} {:>10s} {:>8.3f} {:>10.4f} "
              "{:>10.2f} {:>10.2f}".format(
                  ele["seg_id"], ele["x1"], ele["x2"], ele["tipe"],
                  ele["L"], ele["A"], ele["w_box"], ele["w_total"]))

    total_F = sum(e["w_total"] * e["L"] for e in elemen_data)
    print("-" * 105)
    print("Total beban merata (w_total x L): {:>10.2f} kN".format(total_F))
    print("Catatan: w_total = box + non-struktur + BTR (tanpa faktor).")
    print("         KEL terpusat dikeluarkan terpisah: {:.2f} kN".format(
        elemen_data[0]["P_kel"]))
    print()


def print_distribusi_garis(ele):
    """Cetak distribusi beban per garis memanjang untuk satu segmen."""
    print("=" * 80)
    print("DISTRIBUSI PER GARIS MEMANJANG (segmen {}, tipe {})".format(
        ele["seg_id"], ele["tipe"]))
    print("=" * 80)
    print("{:>8s} {:>10s} {:>12s} {:>12s} {:>12s}".format(
        "z (m)", "w_box", "w_non_struk", "w_BTR", "P_KEL (kN)"))
    print("-" * 80)
    for i, z in enumerate(ele["z_garis"]):
        print("{:>8.2f} {:>10.2f} {:>12.2f} {:>12.2f} {:>12.2f}".format(
            z, ele["w_box_garis"][i], ele["w_non_struktur_garis"][i],
            ele["w_hidup_garis"][i], ele["P_kel_garis"][i]))
    print("-" * 80)
    print("{:>8s} {:>10.2f} {:>12.2f} {:>12.2f} {:>12.2f}".format(
        "jumlah", sum(ele["w_box_garis"]),
        sum(ele["w_non_struktur_garis"]), sum(ele["w_hidup_garis"]),
        sum(ele["P_kel_garis"])))
    print()


def print_ringkasan_per_tipe(elemen_data):
    """Cetak ringkasan per tipe penampang."""
    print("=" * 70)
    print("RINGKASAN PER TIPE PENAMPANG")
    print("=" * 70)

    tipe_data = {}
    for ele in elemen_data:
        tipe = ele["tipe"]
        if tipe not in tipe_data:
            tipe_data[tipe] = {
                "jumlah": 0, "total_L": 0.0, "A": ele["A"],
                "w_box": ele["w_box"], "w_total": ele["w_total"],
            }
        tipe_data[tipe]["jumlah"] += 1
        tipe_data[tipe]["total_L"] += ele["L"]

    print("{:>10s} {:>8s} {:>10s} {:>10s} {:>10s} {:>10s}".format(
        "Tipe", "Jumlah", "L (m)", "A (m2)", "w_box", "w_total"))
    print("-" * 70)
    for tipe, data in tipe_data.items():
        print("{:>10s} {:>8d} {:>10.2f} {:>10.4f} {:>10.2f} {:>10.2f}".format(
            tipe, data["jumlah"], data["total_L"],
            data["A"], data["w_box"], data["w_total"]))
    print()


def print_semua_kombinasi(elemen_data):
    """Cetak tabel semua kombinasi per segmen (beban merata, ringkas)."""
    print("=" * 120)
    print("SEMUA KOMBINASI PEMBEBANAN - BEBAN MERATA (SNI 1725:2016)")
    print("=" * 120)

    kombinasi_list = list(KOMBINASI.keys())
    header = "{:>4s} {:>9s} {:>10s}".format("Seg", "x1", "Tipe")
    for k in kombinasi_list:
        header += " {:>12s}".format(k[:10])
    print(header)
    print("-" * 120)

    for ele in elemen_data:
        row = "{:>4d} {:>9.3f} {:>10s}".format(
            ele["seg_id"], ele["x1"], ele["tipe"])
        for k in kombinasi_list:
            w = hitung_w_kombinasi(
                ele["w_box"], ele["w_non_struktur"], ele["w_hidup"],
                kombinasi=k)
            row += " {:>12.2f}".format(w)
        print(row)

    print("-" * 120)
    print()


def print_max_kombinasi(elemen_data):
    """Cetak kombinasi maksimum (envelope) per segmen."""
    print("=" * 80)
    print("KOMBINASI MAKSIMUM (ENVELOPE) PER SEGMEN")
    print("=" * 80)
    print("{:>4s} {:>9s} {:>10s} {:>14s} {:>14s}".format(
        "Seg", "x1", "Tipe", "Kombinasi Max", "w_max"))
    print("-" * 80)

    for ele in elemen_data:
        w_max, nama_max = float("-inf"), ""
        for k in KOMBINASI:
            w = hitung_w_kombinasi(
                ele["w_box"], ele["w_non_struktur"], ele["w_hidup"],
                kombinasi=k)
            if w > w_max:
                w_max, nama_max = w, k

        print("{:>4d} {:>9.3f} {:>10s} {:>14s} {:>14.2f}".format(
            ele["seg_id"], ele["x1"], ele["tipe"], nama_max, w_max))

    print("-" * 80)
    print()


# ============================================================
# 7. SIMPAN OUTPUT KE FILE
# ============================================================

def save_output_ke_file(elemen_data, filename="output/loads_output.txt",
                        L_beban=None, L_E=None):
    """Simpan output lengkap ke file teks."""
    folder = os.path.dirname(filename)
    if folder:
        os.makedirs(folder, exist_ok=True)

    with open(filename, "w") as f, redirect_stdout(f):
        print("=" * 100)
        print("OUTPUT MODUL BEBAN - JEMBATAN BAROS")
        print("=" * 100)
        print()
        print_parameter(L_beban, L_E)
        print_ringkasan(elemen_data)
        print_distribusi_garis(elemen_data[0])
        print_ringkasan_per_tipe(elemen_data)
        print_semua_kombinasi(elemen_data)
        print_max_kombinasi(elemen_data)
        print("=" * 100)
        print("SELESAI")
        print("=" * 100)

    print("Output disimpan: {}".format(filename))


def save_csv(elemen_data, filename="output/loads_output.csv"):
    """Simpan beban per segmen (total deck) ke CSV."""
    import csv

    folder = os.path.dirname(filename)
    if folder:
        os.makedirs(folder, exist_ok=True)

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "seg_id", "x1", "x2", "tipe", "L", "A",
            "w_box", "w_non_struktur", "w_hidup_BTR", "w_total", "P_KEL"
        ])
        for ele in elemen_data:
            writer.writerow([
                ele["seg_id"], ele["x1"], ele["x2"], ele["tipe"],
                ele["L"], ele["A"], ele["w_box"], ele["w_non_struktur"],
                ele["w_hidup"], ele["w_total"], ele["P_kel"]
            ])

    print("CSV disimpan: {}".format(filename))


def save_csv_garis(elemen_data, filename="output/loads_garis.csv"):
    """Simpan beban per segmen per garis memanjang ke CSV."""
    import csv

    folder = os.path.dirname(filename)
    if folder:
        os.makedirs(folder, exist_ok=True)

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "seg_id", "garis", "z", "w_box", "w_non_struktur",
            "w_hidup_BTR", "P_KEL"
        ])
        for ele in elemen_data:
            for j, z in enumerate(ele["z_garis"]):
                writer.writerow([
                    ele["seg_id"], j + 1, z,
                    ele["w_box_garis"][j], ele["w_non_struktur_garis"][j],
                    ele["w_hidup_garis"][j], ele["P_kel_garis"][j]
                ])

    print("CSV disimpan: {}".format(filename))


# ============================================================
# 8. MAIN (TEST)
# ============================================================

if __name__ == "__main__":
    # core/loads.py -> root proyek = satu tingkat di atas core/
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    from project import project_data as pdata

    # Bentang (m) dari README; ganti dengan pdata.SPANS bila formatnya list panjang
    BENTANG = [16.2472, 17.5, 17.5, 23.5, 38.0, 17.5, 25.0, 25.0, 24.2472]
    L_E = hitung_L_ekuivalen(BENTANG)
    L_BEBAN = None   # None -> q BTR = 9 kPa (konservatif)

    print_parameter(L_BEBAN, L_E)

    elemen_data = hitung_beban_per_elemen(
        pdata.SECTION_MAP, pdata.BOX_SECTIONS,
        L_beban=L_BEBAN, L_E=L_E)
    cek_distribusi(elemen_data)

    print_ringkasan(elemen_data)
    print_distribusi_garis(elemen_data[0])
    print_ringkasan_per_tipe(elemen_data)
    print_semua_kombinasi(elemen_data)
    print_max_kombinasi(elemen_data)

    out = os.path.join(BASE_DIR, "output")
    save_output_ke_file(elemen_data, os.path.join(out, "loads_output.txt"),
                        L_BEBAN, L_E)
    save_csv(elemen_data, os.path.join(out, "loads_output.csv"))
    save_csv_garis(elemen_data, os.path.join(out, "loads_garis.csv"))
