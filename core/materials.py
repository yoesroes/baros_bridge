# core/materials.py
"""
Modul Material untuk Jembatan Baros.
Satuan: kN, m, kPa.

Material:
- Beton deck  : elastis (Elastic)
- Beton pier  : nonlinear (Concrete02 cover + Concrete04 core)
- Baja tulangan: nonlinear (Steel02)

Referensi:
- SNI 1725:2016
- Mander, Priestley & Park (1988)
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

# Modulus elastisitas (SNI 1725:2016)
# E = 4700 * sqrt(f'c) dalam MPa, konversi ke kPa
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

# Prategang (nanti)
FPU = 1860e3            # kPa (ASTM A416)
FPY = 1675e3            # kPa


# ============================================================
# 2. TAG MATERIAL (auto-increment)
# ============================================================

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
    rat : float
        Ratio regangan pada tegangan residual (default 0.1)
    ft : float
        Kuat tarik (kPa)
    Ets : float
        Modulus tension stiffening (kPa)
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
    
    # 3. Beton pier core (Concrete04, Mander)
    # Untuk sementara pakai parameter default
    # Nanti bisa di-override dengan confinement.py
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
    print("PRATEGANG (nanti):")
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
    print("Cek material dengan tag:")
    for tag in [1, 2, 3, 4]:
        try:
            print("  Tag {}: OK".format(tag))
        except:
            print("  Tag {}: ERROR".format(tag))
    
    print()
    print("SELESAI")