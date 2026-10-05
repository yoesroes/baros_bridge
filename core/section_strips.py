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
H_CROWN = 1.50          # tinggi di CL (dari dasar badan)
CROSSFALL = 0.02       #gradien deck
T_TIP = 0.21           #tebal ujung sayap
T_KINK = 0.4624        #tebal ketiak
Z_KINK = 2.7457        #jarak ketiak dari center
Z_BOT = 1.6923         #lebar setengah bottom slab

Y_KINK = H_CROWN - CROSSFALL * Z_KINK - T_KINK          # muka bawah di Z_KINK
Y_TIP = H_CROWN - CROSSFALL * (B_DECK / 2.0) - T_TIP    # muka bawah di ujung

# (z, y_pusat dari dasar, diameter)
DRUM_BESAR = ((-0.625, 0.725, 0.500), (0.625, 0.725, 0.500))
DRUM_KECIL = ((-1.765, 0.875, 0.280), (1.765, 0.875, 0.280))
DRUM_KECIL_AKTIF = True

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
    """Properti geometri total dan per tributary strip."""
    voids = _void_list(tipe)
    lo, hi = -B_DECK / 2.0, B_DECK / 2.0

    def luas(z):
        return kedalaman(z) - sum(_chord(z, v) for v in voids)

    def momen_y(z):
        ym = 0.5 * (y_atas(z) + y_bawah(z))
        return (
            kedalaman(z) * ym
            - sum(_chord(z, v) * v[1] for v in voids)
        )

    # --------------------------------------------------------
    # PROPERTI TOTAL PENAMPANG
    # --------------------------------------------------------
    A = _integral(luas, lo, hi, 4000)

    if A <= 0.0:
        raise ValueError(
            "Luas penampang <= 0 untuk tipe {!r}".format(tipe)
        )

    yc = _integral(momen_y, lo, hi, 4000) / A

    def ix_global(z):
        """
        Kontribusi Ix terhadap centroid vertikal penampang penuh.
        """
        d = kedalaman(z)
        ym = 0.5 * (y_atas(z) + y_bawah(z))

        val = (
            d ** 3 / 12.0
            + d * (ym - yc) ** 2
        )

        for v in voids:
            c = _chord(z, v)
            val -= (
                c ** 3 / 12.0
                + c * (v[1] - yc) ** 2
            )

        return val

    Ix = _integral(ix_global, lo, hi, 4000)
    Iy = _integral(
        lambda z: z * z * luas(z),
        lo, hi, 4000
    )

    # --------------------------------------------------------
    # PROPERTI TIAP TRIBUTARY STRIP
    #
    # z_garis hanya dipakai untuk menentukan batas tributary.
    # Posisi garis aktual nantinya = zbar.
    # --------------------------------------------------------
    strips = []

    for z_ref, (a, b) in zip(
        z_garis,
        _batas_strip(z_garis)
    ):
        A_i = _integral(luas, a, b)

        if A_i <= 0.0:
            raise ValueError(
                "Strip [{:.4f}, {:.4f}] memiliki A <= 0".format(a, b)
            )

        # -------------------------
        # centroid z strip
        # -------------------------
        Sz_i = _integral(
            lambda z: z * luas(z),
            a, b
        )
        zbar_i = Sz_i / A_i

        # -------------------------
        # centroid y strip
        # -------------------------
        Sy_i = _integral(
            momen_y,
            a, b
        )
        ybar_i = Sy_i / A_i

        # -------------------------
        # Ix global terhadap yc
        # -------------------------
        Ix_global_i = _integral(
            ix_global,
            a, b
        )

        # -------------------------
        # Ix lokal terhadap ybar_i
        #
        # Ix_global =
        # Ix_local + A_i*(ybar_i-yc)^2
        # -------------------------
        Ix_local_i = max(
            0.0,
            Ix_global_i
            - A_i * (ybar_i - yc) ** 2
        )

        # -------------------------
        # Iy global terhadap z=0
        # -------------------------
        Iy_global_i = _integral(
            lambda z: z * z * luas(z),
            a, b
        )

        # -------------------------
        # Iy lokal terhadap zbar_i
        #
        # Iy_global =
        # Iy_local + A_i*zbar_i^2
        # -------------------------
        Iy_local_i = max(
            0.0,
            Iy_global_i
            - A_i * zbar_i ** 2
        )

        # -------------------------
        # d^3 untuk distribusi J
        # -------------------------
        d3_i = _integral(
            lambda z: kedalaman(z) ** 3,
            a, b
        )

        strips.append({
            # referensi lama, hanya untuk audit
            "z_ref": z_ref,

            # posisi struktural baru
            "z": zbar_i,

            # batas tributary
            "z1": a,
            "z2": b,

            # centroid strip
            "zbar": zbar_i,
            "ybar": ybar_i,

            # luas
            "A": A_i,

            # lentur vertikal
            "Ix_global": Ix_global_i,
            "Ix": Ix_local_i,

            # lentur lateral
            "Iy_global": Iy_global_i,
            "Iy": Iy_local_i,

            # parameter distribusi J
            "d3": d3_i,

            "Sz": Sz_i,
            "Sy": Sy_i,
        })

    return {
        "yc": yc,
        "A": A,
        "Ix": Ix,
        "Iy": Iy,
        "strips": strips,
    }

# ============================================================
# 3. PROPERTI PER GARIS MEMANJANG
# ============================================================

def properti_garis(tipe, total, z_garis=Z_GARIS_DEFAULT):
    """
    Properti tiap garis memanjang berdasarkan tributary strip aktual.

    z_garis lama hanya digunakan untuk menentukan batas tributary.
    Posisi garis hasil akhir = centroid zbar tiap strip.
    """
    g = _geom(tipe, tuple(z_garis))
    st = g["strips"]

    # --------------------------------------------------------
    # NORMALISASI terhadap BOX_SECTIONS
    # --------------------------------------------------------
    kA = total["A"] / g["A"]
    kI = total["Ix"] / g["Ix"]
    kL = total["Iy"] / g["Iy"]

    sD = sum(s["d3"] for s in st)

    if sD <= 0.0:
        raise ValueError(
            "Jumlah d3 <= 0 untuk tipe {!r}".format(tipe)
        )

    hasil = []

    for s in st:
        A_i = s["A"] * kA
        Ix_i = s["Ix"] * kI
        Iy_i = s["Iy"] * kL
        J_i = total["J"] * s["d3"] / sD

        hasil.append({
            # posisi aktual grillage
            "z": s["z"],
            "zbar": s["zbar"],

            # referensi lama
            "z_ref": s["z_ref"],

            # tributary boundary
            "z1": s["z1"],
            "z2": s["z2"],

            # centroid vertikal strip
            "ybar": s["ybar"],

            # properti final
            "A": A_i,
            "Ix": Ix_i,
            "Iy": Iy_i,
            "J": J_i,

            # audit
            "A_geom": s["A"],
            "Ix_geom": s["Ix"],
            "Iy_geom": s["Iy"],
            "Iy_global": s["Iy_global"],

            "f_A": s["A"] / g["A"],
            "f_Ix": s["Ix"] / g["Ix"],
            "f_J": s["d3"] / sD,
        })

    return hasil


def fraksi_berat(tipe, z_garis=Z_GARIS_DEFAULT):
    """Fraksi berat sendiri per garis (= fraksi luas strip)."""
    st = _geom(tipe, tuple(z_garis))["strips"]
    tot = sum(s["A"] for s in st)
    return [s["A"] / tot for s in st]


def ringkasan(tipe, total, z_garis=Z_GARIS_DEFAULT):
    """Audit konservasi properti geometrik tributary strips."""

    g = _geom(tipe, tuple(z_garis))
    st = g["strips"]

    sumA = sum(s["A"] for s in st)

    sumIx_global = sum(
        s["Ix_global"]
        for s in st
    )

    sumIy_global = sum(
        s["Iy_global"]
        for s in st
    )

    # Rekonstruksi dengan parallel-axis theorem
    sumIx_reconstructed = sum(
        s["Ix"]
        + s["A"] * (s["ybar"] - g["yc"]) ** 2
        for s in st
    )

    sumIy_reconstructed = sum(
        s["Iy"]
        + s["A"] * s["zbar"] ** 2
        for s in st
    )

    return {
        "sum_A": sumA,

        "sum_Ix": sumIx_global,
        "sum_Ix_reconstructed": sumIx_reconstructed,

        "sum_Iy": sumIy_global,
        "sum_Iy_reconstructed": sumIy_reconstructed,

        "target_A": total["A"],
        "target_Ix": total["Ix"],
        "target_Iy": total["Iy"],
        "target_J": total["J"],

        "ratio_A": sumA / total["A"],
        "ratio_Ix": sumIx_global / total["Ix"],
        "ratio_Iy": sumIy_global / total["Iy"],
    }

def z_garis_centroid(
    tipe="hollow",
    z_garis_ref=Z_GARIS_DEFAULT,):
    """
    Hitung posisi garis grillage berdasarkan centroid z
    masing-masing tributary strip.

    z_garis_ref hanya digunakan untuk membentuk tributary
    boundary awal. Boundary TIDAK diiterasikan kembali.
    """
    g = _geom(tipe, tuple(z_garis_ref))

    return tuple(
        s["zbar"]
        for s in g["strips"]
    )


# ============================================================
# 4. PROPERTI ELEMEN MELINTANG (JALUR SELEBAR dx)
# ============================================================

def properti_melintang(dx, tipe="solid", z_garis=None):
    if z_garis is None:
        z_garis = tuple(
            s["z"] for s in _geom(
                tipe, tuple(Z_GARIS_DEFAULT)
            )["strips"]
        )

    hasil = []
    z = list(z_garis)

    for a, b in zip(z[:-1], z[1:]):
        L = b - a

        d_rata = _integral(kedalaman, a, b) / L

        d_eq = (
            L / _integral(
                lambda s: 1.0 / kedalaman(s) ** 3,
                a, b
            )
        ) ** (1.0 / 3.0)

        def J_t_rect(s):
            d = kedalaman(s)

            b = max(dx, d)   # sisi panjang
            t = min(dx, d)   # sisi pendek
            r = t / b

            return (
                b * t**3
                * (
                    1.0 / 3.0
                    - 0.21 * r * (1.0 - r**4 / 12.0)
                )
            )

        J_eq = L / _integral(
            lambda s: 1.0 / J_t_rect(s),
            a, b
        )

        J_a = J_t_rect(a)
        J_b = J_t_rect(b)
        J_mid = J_t_rect((a + b) / 2.0)

        print(
            f"    J_local: "
            f"a={J_a:.6f} "
            f"mid={J_mid:.6f} "
            f"b={J_b:.6f} "
            f"J_eq={J_eq:.6f}"
        )

        print(
            f"  torsion [{a:5.1f},{b:5.1f}] "
            f"dx={dx:.4f} "
            f"d(a)={kedalaman(a):.4f} "
            f"d(b)={kedalaman(b):.4f} "
            f"J_eq={J_eq:.6f}"
        )

        if a < 0.0 < b:
            s_mid = (a + b) / 2.0
            print(
                f"    CHECK dx-cross: "
                f"d(a)={kedalaman(a):.6f} "
                f"d(mid)={kedalaman(s_mid):.6f} "
                f"d(b)={kedalaman(b):.6f} "
                f"J_eq={J_eq:.6f}"
            )

        hasil.append({
            "z1": a,
            "z2": b,
            "L": L,
            "d_rata": d_rata,
            "d_eq": d_eq,
            "A": dx * d_rata,
            "Iz": dx * d_eq ** 3 / 12.0,
            "Iy": d_rata * dx ** 3 / 12.0,
            "J": J_eq,
        })

    return hasil


# ============================================================
# 5. MAIN (TEST)
# ============================================================

if __name__ == "__main__":
    contoh = {
    "solid":   {"A": 8.566952, "Ix": 1.481379, "Iy": 35.853120, "J": 3.8232},
    "hollow":  {"A": 8.051160, "Ix": 1.465182, "Iy": 35.309473, "J": 3.7537},
}

    for tipe, tot in contoh.items():

        print("=" * 70)
        print("TIPE", tipe)

        props = properti_garis(tipe, tot)
        r = ringkasan(tipe, tot)

        # --------------------------------------------------
        # PROPERTI TIAP GARIS MEMANJANG
        # --------------------------------------------------
        for p in props:
            print(
                "  ref={:6.3f} -> z={:7.4f}  "
                "ybar={:7.4f}  "
                "A={:7.4f} ({:5.1f}%)  "
                "Ix={:8.5f} ({:5.1f}%)  "
                "Iy_local={:9.5f}  "
                "J={:7.4f}".format(
                    p["z_ref"],
                    p["z"],
                    p["ybar"],
                    p["A"],
                    100.0 * p["f_A"],
                    p["Ix"],
                    100.0 * p["f_Ix"],
                    p["Iy"],
                    p["J"],
                )
            )

        # --------------------------------------------------
        # POSISI GARIS BARU
        # --------------------------------------------------
        print(
            "  posisi garis baru :",
            [round(p["z"], 4) for p in props],
        )

        print(
            "  centroid z check  :",
            [round(p["zbar"], 4) for p in props],
        )

        # --------------------------------------------------
        # AUDIT PROPERTI TOTAL
        # --------------------------------------------------
        print("  GEOMETRI:")

        for prop in ["A", "Ix", "Iy"]:
            print(
                f"    {prop:<3} = "
                f"{r[f'sum_{prop}']:.6f} / "
                f"{r[f'target_{prop}']:.6f}  "
                f"ratio={r[f'ratio_{prop}']:.8f}"
            )

        print(
            f"    J   = "
            f"{r['target_J']:.6f}"
        )

        # --------------------------------------------------
        # PARALLEL-AXIS CHECK
        # --------------------------------------------------
        print("  PARALLEL-AXIS CHECK:")
        print(
            f"    Ix reconstructed = "
            f"{r['sum_Ix_reconstructed']:.6f}"
        )
        print(
            f"    Iy reconstructed = "
            f"{r['sum_Iy_reconstructed']:.6f}"
        )

    # ======================================================
    # PROPERTI ELEMEN MELINTANG
    # ======================================================
    print("=" * 70)

    for s in properti_melintang(1.0, tipe):
        print(
            "  melintang [{:5.1f},{:5.1f}] "
            "d_rata={:.3f} d_eq={:.3f} "
            "Iz/dx={:.5f}".format(
                s["z1"],
                s["z2"],
                s["d_rata"],
                s["d_eq"],
                s["Iz"],
            )
        )