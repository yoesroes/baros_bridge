# project/materials.py
"""
Modul Material untuk Jembatan Baros.
Satuan: kN, m, kPa.

Status per bagian
-----------------
[AKTIF]       Beton box (deck): E_BOX, G_BOX, FPC_BOX -> dipakai
              core/elements.py (E, G elemen elastis). core/loads.py
              menulis ulang f'c box untuk berat jenis (salinan sendiri).
[PLACEHOLDER] Beton pier (Concrete02 cover + Concrete04 core), baja
              tulangan (Steel02), pile, prategang: TIDAK dipakai analisis
              deck repo ini. Disiapkan untuk repo pier/pondasi
              (bersama confinement.py dan rebar_layout.py), dibiarkan apa
              adanya. Parameter core masih default, belum dari Mander.

Konvensi tanda OpenSees: tekan NEGATIF (fpc, epsc0, fpcu, epsU).

CATATAN AUDIT
-------------
1. E = 4700*sqrt(f'c) [MPa] adalah rumus SNI 2847 / ACI 318, bukan dari
   SNI 1725:2016. Cek rujukan yang dipakai.
2. Nilai f'c dan gamma juga ditulis ulang di core/loads.py (FPC_BOX,
   FPC_PIER, GAMMA_BETON_*). Dua salinan harus selalu sama. Belum ada
   pengecekan otomatis.
3. project_data.MATERIAL (E 30e6, f'c 35 MPa) TIDAK dipakai dan berbeda
   dari file ini.
4. nu = 0.2 -> G = E / (2 (1 + nu)).

Referensi:
- SNI 1725:2016 (berat jenis beton, pembebanan)
- Mander, Priestley & Park (1988) (hanya untuk bagian pier)
"""

import math
import openseespy.opensees as ops


# ============================================================
# 1. KONSTANTA MATERIAL
# ============================================================

# Beton
FPC_BOX = 41.5e3        # kPa (41.5 MPa)
FPC_PIER = 30.0e3       # kPa (30 MPa)
FPC_PILE = 30.0e3       # kPa (30 MPa)

# Modulus elastisitas beton
# E = 4700 * sqrt(f'c) dalam MPa (rumus SNI 2847 / ACI 318), konversi ke kPa
E_BOX = 4700.0 * math.sqrt(FPC_BOX / 1000.0) * 1000.0    # kPa
E_PIER = 4700.0 * math.sqrt(FPC_PIER / 1000.0) * 1000.0  # kPa
E_PILE = 4700.0 * math.sqrt(FPC_PILE / 1000.0) * 1000.0  # kPa

# Poisson ratio
NU = 0.2
G_BOX = E_BOX / (2.0 * (1.0 + NU))      # kPa
G_PIER = E_PIER / (2.0 * (1.0 + NU))    # kPa

# Baja tulangan
FY = 420e3              # kPa (BJTS 420B)
E_STEEL = 200e6         # kPa (200 GPa)
B_STEEL = 0.01          # strain hardening ratio

# Prategang [PLACEHOLDER] - belum dipakai; prategang belum dimodelkan
# (loads.KOMBINASI memakai P = 0).
FPU = 1860e3            # kPa (ASTM A416)
FPY = 1675e3            # kPa


# ============================================================
# 2. TAG MATERIAL (ditetapkan manual, bukan auto-increment)
# ============================================================
# Tag 1 dipakai deck; tag 2-4 untuk pier [PLACEHOLDER].

MAT_TAGS = {
    "beton_box": 1,
    "beton_pier_cover": 2,
    "beton_pier_core": 3,
    "baja_tulangan": 4,
}


# ============================================================
# 3. FUNGSI MATERIAL
# ============================================================

def define_beton_elastis(tag, E):
    """
    Definisikan material beton elastis.
    
    Parameters
    ----------
    tag : int
        Tag material
    E : float
        Modulus elastisitas (kPa)
    """
    ops.uniaxialMaterial('Elastic', tag, E)
    return tag


def define_concrete02(tag, fpc, epsc0, fpcu, epsU, ft, Ets, rat=0.1):
    """
    Definisikan Concrete02 (dengan kuat tarik).
    
    Parameters
    ----------
    tag : int
    fpc : float
        Kuat tekan (kPa, negatif)
    epsc0 : float
        Regangan puncak (negatif)
    fpcu : float
        Kuat tekan residual (kPa, negatif)
    epsU : float
        Regangan ultimit (negatif)
    ft : float
        Kuat tarik (kPa, positif)
    Ets : float
        Modulus tension stiffening (kPa)
    rat : float
        Rasio kemiringan unload terhadap Ec, default 0.1 (argumen
        "lambda" pada perintah OpenSees Concrete02; bukan rasio regangan).

    Catatan: urutan argumen fungsi ini (fpcu, epsU, ft, Ets, rat) berbeda
    dari urutan perintah OpenSees (fpc epsc0 fpcu epsU lambda ft Ets);
    pemetaan dilakukan di dalam fungsi.
    """
    ops.uniaxialMaterial('Concrete02', tag,
                         fpc, epsc0, fpcu, epsU, rat, ft, Ets)
    return tag


def define_concrete04(tag, fpc, epsc0, epsU, Ec, ft):
    """
    Definisikan Concrete04 (Popovics + Mander).
    
    Parameters
    ----------
    tag : int
        Tag material
    fpc : float
        Kuat tekan (kPa, negatif)
    epsc0 : float
        Regangan puncak (negatif)
    epsU : float
        Regangan ultimit (negatif)
    Ec : float
        Modulus elastisitas (kPa)
    ft : float
        Kuat tarik (kPa)
    """
    ops.uniaxialMaterial('Concrete04', tag,
                         fpc, epsc0, epsU, Ec, ft)
    return tag


def define_steel02(tag, fy, E0, b, R0=18.0, cR1=0.925, cR2=0.15):
    """
    Definisikan Steel02 (Giuffré-Menegotto-Pinto).
    
    Parameters
    ----------
    tag : int
        Tag material
    fy : float
        Tegangan leleh (kPa)
    E0 : float
        Modulus elastisitas (kPa)
    b : float
        Strain hardening ratio
    R0, cR1, cR2 : float
        Parameter kurva GMP
    """
    ops.uniaxialMaterial('Steel02', tag,
                         fy, E0, b, R0, cR1, cR2)
    return tag


# ============================================================
# 4. FUNGSI WRAPPER — DEFINISI SEMUA MATERIAL
# ============================================================

def define_all_materials():
    """
    Definisikan semua material yang dipakai.
    
    Returns
    -------
    tags : dict
        Tag material
    """
    tags = {}
    
    # 1. Beton box (elastis)
    tags["beton_box"] = define_beton_elastis(
        MAT_TAGS["beton_box"], E_BOX
    )
    
    # 2. Beton pier cover (Concrete02)
    tags["beton_pier_cover"] = define_concrete02(
        MAT_TAGS["beton_pier_cover"],
        fpc=-FPC_PIER,
        epsc0=-0.002,
        fpcu=-0.2 * FPC_PIER,
        epsU=-0.005,
        ft=0.1 * FPC_PIER,
        Ets=0.05 * E_PIER,
        rat=0.1
    )
    
    # 3. Beton pier core (Concrete04, Mander)  [PLACEHOLDER]
    # Parameter default tak terkekang (epsU = -0.02 asumsi); akan
    # di-override dengan hasil ManderConfinement (repo pier).
    tags["beton_pier_core"] = define_concrete04(
        MAT_TAGS["beton_pier_core"],
        fpc=-FPC_PIER,
        epsc0=-0.002,
        epsU=-0.02,
        Ec=E_PIER,
        ft=0.1 * FPC_PIER
    )
    
    # 4. Baja tulangan (Steel02)
    tags["baja_tulangan"] = define_steel02(
        MAT_TAGS["baja_tulangan"],
        fy=FY,
        E0=E_STEEL,
        b=B_STEEL
    )
    
    return tags


# ============================================================
# 5. OUTPUT INFORMATIF
# ============================================================

def print_material_info():
    """Cetak parameter material."""
    print("=" * 65)
    print("PARAMETER MATERIAL")
    print("=" * 65)
    print("BETON:")
    print("  f'c box       = {:>8.1f} MPa".format(FPC_BOX / 1000))
    print("  f'c pier      = {:>8.1f} MPa".format(FPC_PIER / 1000))
    print("  f'c pile      = {:>8.1f} MPa".format(FPC_PILE / 1000))
    print("  E box         = {:>8.3e} kPa".format(E_BOX))
    print("  E pier        = {:>8.3e} kPa".format(E_PIER))
    print("  G box         = {:>8.3e} kPa".format(G_BOX))
    print("  G pier        = {:>8.3e} kPa".format(G_PIER))
    print("  nu            = {:>8.2f}".format(NU))
    print()
    print("BAJA TULANGAN:")
    print("  fy            = {:>8.1f} MPa".format(FY / 1000))
    print("  E             = {:>8.3e} kPa".format(E_STEEL))
    print("  b             = {:>8.3f}".format(B_STEEL))
    print()
    print("PRATEGANG (placeholder):")
    print("  fpu           = {:>8.1f} MPa".format(FPU / 1000))
    print("  fpy           = {:>8.1f} MPa".format(FPY / 1000))
    print()


def print_tag_info():
    """Cetak tag material."""
    print("=" * 65)
    print("TAG MATERIAL")
    print("=" * 65)
    for nama, tag in MAT_TAGS.items():
        print("  {:>25s} : {}".format(nama, tag))
    print()


if __name__ == "__main__":
    # Print info
    print_material_info()
    print_tag_info()
    
    # Test definisi material (butuh OpenSees model)
    print("=" * 65)
    print("TEST DEFINISI MATERIAL")
    print("=" * 65)
    
    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 6)
    
    tags = define_all_materials()
    
    print("Material berhasil didefinisikan:")
    for nama, tag in tags.items():
        print("  {:>25s} : tag = {}".format(nama, tag))
    
    print()
    print("SELESAI")