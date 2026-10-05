# core/section_strips.py
"""
Properti strip grillage dari geometri penampang (dibaca dari DXF).
Satuan: m. Sumbu: z = melintang jembatan, y = vertikal (ke atas).

Mengapa modul ini ada
---------------------
Penampang Baros hampir solid: badan tengah setebal ~1.5 m dengan sayap
tipis (0.22 - 0.45 m). Total A, Ix, J untuk SELURUH lebar tidak boleh
dipasang pada tiap garis memanjang grillage (hasilnya 5x terlalu kaku).
Modul ini memotong penampang menjadi strip, satu strip per garis
memanjang, lalu:
- A_i, Ix_i (lentur vertikal) : integral langsung strip (jumlah = total),
- Iy_i (lentur lateral)       : integral lokal terhadap garis, tidak negatif,
- J_i                         : proporsional d^3 (strip tebal lebih kaku),
- fraksi berat sendiri        : sama dengan fraksi A_i,
- elemen melintang            : properti jalur selebar dx dari profil d(z).

Fraksi dihitung dari geometri lalu DISKALA ke total per tipe di
project_data.BOX_SECTIONS (A, Ix, Iy, J) sehingga total tetap sama dengan
hasil perhitungan penampangmu.

Geometri (dari DXF, diukur ~ +/-0.02 m):
- lebar 10.0 m, tinggi di CL 1.525 m, kemiringan permukaan 2%
- tebal ujung sayap 0.22 m, tebal pangkal sayap 0.454 m (z = 2.5665 m)
- lebar dasar badan 3.3846 m (z = +/-1.6923 m)
- void tipe hollow: 2 drum bekas D 0.572 m di z = +/-0.625 m, pusat 0.725 m
  di atas dasar. Dua lingkaran D 0.280 (z = +/-1.765 m) TIDAK dihitung
  sebagai void (luas void README hollow = 2 drum besar); aktifkan dengan
  DRUM_KECIL_AKTIF = True jika ternyata void.
"""

import math
from functools import lru_cache

# ============================================================
# 1. GEOMETRI
# ============================================================

B_DECK = 10.0
H_CROWN = 1.525          # tinggi di CL (dari dasar badan)
CROSSFALL = 0.02
T_TIP = 0.22
T_KINK = 0.454
Z_KINK = 2.5665
Z_BOT = 1.6923

Y_KINK = H_CROWN - CROSSFALL * Z_KINK - T_KINK          # muka bawah di Z_KINK
Y_TIP = H_CROWN - CROSSFALL * (B_DECK / 2.0) - T_TIP    # muka bawah di ujung

# (z, y_pusat dari dasar, diameter)
DRUM_BESAR = ((-0.625, 0.725, 0.572), (0.625, 0.725, 0.572))
DRUM_KECIL = ((-1.765, 0.875, 0.280), (1.765, 0.875, 0.280))
DRUM_KECIL_AKTIF = False

Z_GARIS_DEFAULT = (-5.0, -3.5, 0.0, 3.5, 5.0)


def y_atas(z):
    return H_CROWN - CROSSFALL * abs(z)


def y_bawah(z):
    a = abs(z)
    if a >= Z_KINK:
        return Y_TIP + (Y_KINK - Y_TIP) * (B_DECK / 2.0 - a) / (B_DECK / 2.0 - Z_KINK)
    if a >= Z_BOT:
        return Y_KINK * (a - Z_BOT) / (Z_KINK - Z_BOT)
    return 0.0


def kedalaman(z):
    return y_atas(z) - y_bawah(z)


def _chord(z, drum):
    zc, _, D = drum
    dz = abs(z - zc)
    r = D / 2.0
    return 0.0 if dz >= r else 2.0 * math.sqrt(r * r - dz * dz)


def _void_list(tipe):
    if tipe != "hollow":
        return ()
    return DRUM_BESAR + (DRUM_KECIL if DRUM_KECIL_AKTIF else ())


# ============================================================
# 2. INTEGRASI NUMERIK
# ============================================================

def _integral(f, a, b, n=1500):
    if b <= a:
        return 0.0
    h = (b - a) / n
    s = 0.5 * (f(a) + f(b))
    for k in range(1, n):
        s += f(a + k * h)
    return s * h


def _batas_strip(z_garis):
    z = list(z_garis)
    mid = [(z[i] + z[i + 1]) / 2.0 for i in range(len(z) - 1)]
    b = [-B_DECK / 2.0] + mid + [B_DECK / 2.0]
    return list(zip(b[:-1], b[1:]))


@lru_cache(maxsize=None)
def _geom(tipe, z_garis):
    """Properti geometri total dan per strip untuk satu tipe."""
    voids = _void_list(tipe)
    lo, hi = -B_DECK / 2.0, B_DECK / 2.0

    def luas(z):
        return kedalaman(z) - sum(_chord(z, v) for v in voids)

    def momen_y(z):
        ym = 0.5 * (y_atas(z) + y_bawah(z))
        return kedalaman(z) * ym - sum(_chord(z, v) * v[1] for v in voids)

    A = _integral(luas, lo, hi, 4000)
    yc = _integral(momen_y, lo, hi, 4000) / A

    def ix(z):
        d = kedalaman(z)
        ym = 0.5 * (y_atas(z) + y_bawah(z))
        val = d ** 3 / 12.0 + d * (ym - yc) ** 2
        for v in voids:
            c = _chord(z, v)
            val -= c ** 3 / 12.0 + c * (v[1] - yc) ** 2
        return val

    strips = []
    for z0, (a, b) in zip(z_garis, _batas_strip(z_garis)):
        strips.append({
            "z": z0, "z1": a, "z2": b,
            "A": _integral(luas, a, b),
            "Ix": _integral(ix, a, b),
            "S2": _integral(lambda z: z * z * luas(z), a, b),   # int z^2 dA
            "d3": _integral(lambda z: kedalaman(z) ** 3, a, b),
        })

    return {
        "yc": yc, "A": A,
        "Ix": sum(s["Ix"] for s in strips),
        "Iy": sum(s["S2"] for s in strips),
        "strips": strips,
    }


# ============================================================
# 3. PROPERTI PER GARIS MEMANJANG
# ============================================================

def properti_garis(tipe, total, z_garis=Z_GARIS_DEFAULT):
    """
    Properti tiap garis memanjang untuk satu tipe penampang.

    Parameters
    ----------
    tipe : str
        'solid' | 'hollow' | 'tumpuan' (hanya 'hollow' memakai void drum)
    total : dict
        {"A", "Ix", "Iy", "J"} total penampang (BOX_SECTIONS[tipe])
    z_garis : sequence

    Returns
    -------
    list of dict {z, A, Ix, Iy, J, f_A, f_Ix, f_J} per garis,
    ditambah kunci "_ringkasan" pada elemen pertama? -> lihat ringkasan().
    """
    g = _geom(tipe, tuple(z_garis))
    st = g["strips"]
    sA = sum(s["A"] for s in st)
    sI = sum(s["Ix"] for s in st)
    sD = sum(s["d3"] for s in st)

    kA = total["A"] / g["A"]          # skala ke total README
    kI = total["Ix"] / g["Ix"]
    kL = total["Iy"] / g["Iy"]

    hasil = []
    for s in st:
        A_i = s["A"] * kA
        Iy_lokal = max(0.0, (s["S2"] - s["A"] * s["z"] ** 2) * kL)
        hasil.append({
            "z": s["z"],
            "A": A_i,
            "Ix": s["Ix"] * kI,
            "Iy": Iy_lokal,
            "J": total["J"] * s["d3"] / sD,
            "f_A": s["A"] / sA,
            "f_Ix": s["Ix"] / sI,
            "f_J": s["d3"] / sD,
        })
    return hasil


def fraksi_berat(tipe, z_garis=Z_GARIS_DEFAULT):
    """Fraksi berat sendiri per garis (= fraksi luas strip)."""
    st = _geom(tipe, tuple(z_garis))["strips"]
    tot = sum(s["A"] for s in st)
    return [s["A"] / tot for s in st]


def ringkasan(tipe, total, z_garis=Z_GARIS_DEFAULT):
    """Cek jumlah properti garis terhadap total (untuk verifikasi)."""
    p = properti_garis(tipe, total, z_garis)
    sumA = sum(x["A"] for x in p)
    sumIx = sum(x["Ix"] for x in p)
    sumJ = sum(x["J"] for x in p)
    lateral = sum(x["Iy"] + x["A"] * x["z"] ** 2 for x in p)
    return {
        "sum_A": sumA, "sum_Ix": sumIx, "sum_J": sumJ,
        "lateral_model": lateral, "lateral_target": total["Iy"],
        "lateral_rasio": lateral / total["Iy"],
    }


# ============================================================
# 4. PROPERTI ELEMEN MELINTANG (JALUR SELEBAR dx)
# ============================================================

def properti_melintang(dx, z_garis=Z_GARIS_DEFAULT):
    """
    Properti tiap segmen melintang untuk jalur selebar dx (m) dari profil
    kedalaman d(z) penampang solid.

    Sumbu lokal elemen melintang (vecxz = (1,0,0)): x lokal = z global,
    y lokal = -y global, z lokal = x global. Karena itu
        Iz = dx * d_eq^3 / 12   (lentur vertikal)
        Iy = d_rata * dx^3 / 12 (lentur bidang horizontal)
        J  = dx * d_eq^3 / 6
    d_eq = kedalaman ekuivalen kekakuan seri sepanjang segmen:
        d_eq = (L / int dz / d^3)^(1/3).
    """
    hasil = []
    z = list(z_garis)
    for a, b in zip(z[:-1], z[1:]):
        L = b - a
        d_rata = _integral(kedalaman, a, b) / L
        d_eq = (L / _integral(lambda s: 1.0 / kedalaman(s) ** 3, a, b)) ** (1.0 / 3.0)
        hasil.append({
            "z1": a, "z2": b, "L": L,
            "d_rata": d_rata, "d_eq": d_eq,
            "A": dx * d_rata,
            "Iz": dx * d_eq ** 3 / 12.0,
            "Iy": d_rata * dx ** 3 / 12.0,
            "J": dx * d_eq ** 3 / 6.0,
        })
    return hasil


# ============================================================
# 5. MAIN (TEST)
# ============================================================

if __name__ == "__main__":
    contoh = {
        "solid":   {"A": 8.2231, "Ix": 1.4527, "Iy": 33.3927, "J": 3.8232},
        "hollow":  {"A": 7.7072, "Ix": 1.4527, "Iy": 33.3927, "J": 3.7537},
    }
    for tipe, tot in contoh.items():
        print("=" * 70)
        print("TIPE", tipe)
        for p in properti_garis(tipe, tot):
            print("  z={:5.1f}  A={:6.3f} ({:4.1f}%)  Ix={:7.4f} ({:4.1f}%)  "
                  "Iy={:6.3f}  J={:6.3f}".format(
                      p["z"], p["A"], 100 * p["f_A"], p["Ix"],
                      100 * p["f_Ix"], p["Iy"], p["J"]))
        r = ringkasan(tipe, tot)
        print("  jumlah A={:.4f} Ix={:.4f} J={:.4f}; lateral model/target "
              "= {:.2f}".format(r["sum_A"], r["sum_Ix"], r["sum_J"],
                                r["lateral_rasio"]))
    print("=" * 70)
    for s in properti_melintang(1.0):
        print("  melintang [{:5.1f},{:5.1f}] d_rata={:.3f} d_eq={:.3f} "
              "Iz/dx={:.5f}".format(s["z1"], s["z2"], s["d_rata"],
                                    s["d_eq"], s["Iz"]))
