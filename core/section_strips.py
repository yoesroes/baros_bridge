# core/section_strips.py
"""
Properti strip grillage dari geometri penampang (dibaca dari DXF).
Satuan: m. Sumbu: z = melintang jembatan, y = vertikal (ke atas).

Mengapa modul ini ada
---------------------
Penampang Baros hampir solid: badan tengah setebal ~1.5 m dengan sayap
tipis. Total A, Ix, J untuk SELURUH lebar tidak boleh dipasang pada tiap
garis memanjang grillage (hasilnya ~5x terlalu kaku). Modul ini memotong
penampang menjadi strip tributary, satu strip per garis memanjang:
- posisi garis aktual = centroid z strip (zbar),
- A_i                         : integral strip (jumlah = total),
- Ix_i (lentur vertikal)      : Ix strip terhadap centroid VERTIKAL PENAMPANG
                                PENUH (yc), yaitu I_lokal + A_i*(ybar_i-yc)^2.
                                Grillage planar menaruh semua garis pada satu
                                elevasi, jadi suku Steiner vertikal harus
                                dibawa Ix_i agar jumlah Ix_i = Ix total,
- Iy_i (lentur lateral)       : Ix lokal terhadap zbar_i. Suku A_i*zbar_i^2
                                sudah terbawa oleh posisi node, sehingga
                                sum(Iy_i + A_i*zbar_i^2) = Iy total,
- J_i                         : proporsional integral d^3,
- fraksi berat sendiri        : sama dengan fraksi A_i,
- elemen melintang            : properti jalur selebar dx dari profil d(z).

Fraksi dihitung dari geometri lalu DISKALA ke total per tipe di
project_data.BOX_SECTIONS (A, Ix, Iy, J). ringkasan() mengaudit properti
FINAL (keluaran properti_garis), bukan besaran geometri mentah.

Geometri (dari DXF) - lihat konstanta di bagian 1; nilai di sana yang berlaku:
- lebar 10.0 m, tinggi di CL 1.50 m, kemiringan permukaan 2%
- void tipe hollow: 2 drum D 0.500 di z = +/-0.625 m (pusat 0.725 m di atas
  dasar) + 2 drum kecil D 0.280 di z = +/-1.765 m (DRUM_KECIL_AKTIF = True).
  Luas void total 0.516 m2 = selisih A solid - A hollow.
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

def _cek_z_ref(z_ref):
    """
    z_ref = titik referensi PEMBATAS tributary (default Z_GARIS_DEFAULT,
    garis terluar tepat di tepi deck +/-B_DECK/2). Koordinat node fisik
    (centroid strip) BUKAN z_ref; menukar keduanya menggeser batas strip.
    """
    z = list(z_ref)
    if any(z[i + 1] <= z[i] for i in range(len(z) - 1)):
        raise ValueError("z_ref harus naik monoton: {}".format(z))
    tol = 1e-6
    if abs(z[0] + B_DECK / 2.0) > tol or abs(z[-1] - B_DECK / 2.0) > tol:
        raise ValueError(
            "z_ref harus berujung di tepi deck (+/-{:.3f}), bukan koordinat "
            "node. Dapat: {}. Gunakan z_node= untuk posisi node fisik."
            .format(B_DECK / 2.0, z))


def properti_garis(tipe, total, z_ref=Z_GARIS_DEFAULT, z_node=None):
    """
    Properti tiap garis memanjang.

    Parameters
    ----------
    z_ref : referensi pembatas tributary (default Z_GARIS_DEFAULT).
    z_node : posisi z FISIK node/beam grillage. Default = centroid strip
        (zbar) tipe ini. Di model: nodes.Z_GARIS (centroid strip hollow),
        yang dipakai bersama oleh semua tipe section.

    Pembagian kekakuan:
        A_i  : integral strip, diskala (jumlah = total A)
        Ix_i : Ix_global strip (terhadap yc penampang penuh); node coplanar,
               jadi suku Steiner vertikal harus dibawa beam
        Iy_i : suku A_i*z_node_i^2 sudah disediakan kinematika (jarak node
               ke sumbu jembatan). Sisanya, B = Iy_total - sum(A_i*z_node^2),
               dibagi ke strip sebanding dengan bobot geometri
               w_i = Iy_lokal_i + A_geom_i*(zbar_i^2 - z_node_i^2).
               Total Iy tetap terpenuhi walau total BOX_SECTIONS sedikit
               berbeda dari geometri DXF (selisih diserap bagian lokal).
        J_i  : proporsional integral d^3

    Konservasi (properti final):
        sum(A_i) = A, sum(Ix_i) = Ix, sum(Iy_i + A_i*z_node_i^2) = Iy,
        sum(J_i) = J.
    """
    _cek_z_ref(z_ref)
    g = _geom(tipe, tuple(z_ref))
    st = g["strips"]

    if z_node is None:
        z_node = [s["zbar"] for s in st]
    z_node = [float(z) for z in z_node]
    if len(z_node) != len(st):
        raise ValueError("z_node ({}) != jumlah strip ({})".format(
            len(z_node), len(st)))

    sA = sum(s["A"] for s in st)
    sIx = sum(s["Ix_global"] for s in st)
    sD = sum(s["d3"] for s in st)

    if min(sA, sIx, sD) <= 0.0:
        raise ValueError(
            "Jumlah A/Ix/Iy/d3 <= 0 untuk tipe {!r}".format(tipe))

    kA = total["A"] / sA
    kI = total["Ix"] / sIx

    # Iy: kurangi bagian kinematik, bagi sisanya menurut bobot geometri
    K = sum(s["A"] * kA * zn ** 2 for s, zn in zip(st, z_node))
    B = total["Iy"] - K
    w = [s["Iy"] + s["A"] * (s["zbar"] ** 2 - zn ** 2)
         for s, zn in zip(st, z_node)]
    if B <= 0.0 or min(w) <= 0.0:
        raise ValueError(
            "Distribusi Iy gagal (tipe {!r}): Iy_total - sum(A_i*z_node^2) = "
            "{:.4f}, bobot min = {:.4g}. Cek total BOX_SECTIONS vs geometri "
            "dan z_node.".format(tipe, B, min(w)))
    sw = sum(w)

    hasil = []
    for s, zn, w_i in zip(st, z_node, w):
        A_i = s["A"] * kA
        Ix_i = s["Ix_global"] * kI
        Iy_i = B * w_i / sw
        J_i = total["J"] * s["d3"] / sD

        hasil.append({
            # posisi
            "z": zn,                    # posisi node fisik (dipakai beam)
            "zbar": s["zbar"],          # centroid strip hasil partisi z_ref
            "z_ref": s["z_ref"],
            "dz_node": zn - s["zbar"],
            "z1": s["z1"], "z2": s["z2"],
            "ybar": s["ybar"],

            # properti final (masuk ke OpenSees)
            "A": A_i, "Ix": Ix_i, "Iy": Iy_i, "J": J_i,

            # audit / informasi
            "A_geom": s["A"],
            "Ix_geom": s["Ix_global"],
            "Ix_lokal": s["Ix"] * kI,
            "Iy_lokal": s["Iy"],
            "Iy_total_node": Iy_i + A_i * zn ** 2,

            "f_A": s["A"] / sA,
            "f_Ix": s["Ix_global"] / sIx,
            "f_Iy": (Iy_i + A_i * zn ** 2) / total["Iy"],
            "f_J": s["d3"] / sD,
        })

    return hasil


def fraksi_berat(tipe, z_ref=Z_GARIS_DEFAULT):
    """Fraksi berat sendiri per garis (= fraksi luas strip)."""
    _cek_z_ref(z_ref)
    st = _geom(tipe, tuple(z_ref))["strips"]
    tot = sum(s["A"] for s in st)
    return [s["A"] / tot for s in st]


def ringkasan(tipe, total, z_ref=Z_GARIS_DEFAULT, z_node=None):
    """
    Audit konservasi pada properti FINAL, memakai z_node yang sama dengan
    posisi beam di model (p["z"]).
    """
    props = properti_garis(tipe, total, z_ref, z_node)
    g = _geom(tipe, tuple(z_ref))

    sum_A = sum(p["A"] for p in props)
    sum_Ix = sum(p["Ix"] for p in props)
    sum_Ix_lokal = sum(p["Ix_lokal"] for p in props)
    sum_Iy_beam = sum(p["Iy"] for p in props)
    sum_Iy = sum(p["Iy"] + p["A"] * p["z"] ** 2 for p in props)
    sum_J = sum(p["J"] for p in props)

    return {
        "sum_A": sum_A, "sum_Ix": sum_Ix, "sum_Iy": sum_Iy, "sum_J": sum_J,
        "sum_Iy_beam": sum_Iy_beam, "sum_Ix_lokal": sum_Ix_lokal,

        "target_A": total["A"], "target_Ix": total["Ix"],
        "target_Iy": total["Iy"], "target_J": total["J"],

        "ratio_A": sum_A / total["A"],
        "ratio_Ix": sum_Ix / total["Ix"],
        "ratio_Iy": sum_Iy / total["Iy"],
        "ratio_J": sum_J / total["J"],

        "max_offset_node": max(abs(p["dz_node"]) for p in props),

        # geometri DXF vs total BOX_SECTIONS
        "geom_ratio_A": g["A"] / total["A"],
        "geom_ratio_Ix": g["Ix"] / total["Ix"],
        "geom_ratio_Iy": g["Iy"] / total["Iy"],
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
    _cek_z_ref(z_garis_ref)
    g = _geom(tipe, tuple(z_garis_ref))

    return tuple(
        s["zbar"]
        for s in g["strips"]
    )


# ============================================================
# 4. PROPERTI ELEMEN MELINTANG (JALUR SELEBAR dx)
# ============================================================

def properti_melintang(dx, tipe="solid", z_garis=None,
                       verbose=False):
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

        if verbose:
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
        "solid":  {"A": 8.566952, "Ix": 1.481379, "Iy": 35.853120, "J": 3.8232},
        "hollow": {"A": 8.051160, "Ix": 1.465182, "Iy": 35.309473, "J": 3.7537},
    }
    # posisi node fisik di model = centroid strip hollow
    Z_NODE = z_garis_centroid("hollow", Z_GARIS_DEFAULT)
    print("z_ref  :", Z_GARIS_DEFAULT)
    print("z_node :", [round(z, 4) for z in Z_NODE])

    for tipe, tot in contoh.items():
        print("=" * 70)
        print("TIPE", tipe)
        props = properti_garis(tipe, tot, Z_GARIS_DEFAULT, Z_NODE)
        r = ringkasan(tipe, tot, Z_GARIS_DEFAULT, Z_NODE)

        for p in props:
            print(
                "  z_node={:7.4f} (zbar={:7.4f})  A={:7.4f}  Ix={:8.5f}  "
                "Iy_beam={:9.5f}  J={:7.4f}".format(
                    p["z"], p["zbar"], p["A"], p["Ix"], p["Iy"], p["J"]))

        print("  KONSERVASI (jumlah / target):")
        for nama in ("A", "Ix", "Iy", "J"):
            print("    {:<3} = {:.6f} / {:.6f}  ratio={:.8f}".format(
                nama, r["sum_" + nama], r["target_" + nama],
                r["ratio_" + nama]))
        print("    Iy = sum(Iy_i + A_i*z_node^2); offset node maks "
              "{:.4f} m".format(r["max_offset_node"]))

        print("  ELEMEN MELINTANG (dx = 1.0, antar node):")
        for s_ in properti_melintang(1.0, tipe, Z_NODE):
            print("    [{:5.2f},{:5.2f}] d_eq={:.3f} Iz/dx={:.5f} J={:.5f}"
                  .format(s_["z1"], s_["z2"], s_["d_eq"], s_["Iz"], s_["J"]))

    # guard: koordinat node tidak boleh dipakai sebagai z_ref
    try:
        properti_garis("hollow", contoh["hollow"], Z_NODE)
    except ValueError as err:
        print("\nGuard z_ref OK ->", str(err)[:60], "...")
