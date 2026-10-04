# core/sections.py
"""
Modul Section untuk Jembatan Baros.
Satuan: kN, m, kPa.

Section deck (elastis):
- A  : luas penampang (m²)
- Ix : momen inersia terhadap sumbu kuat (m⁴)
- Iy : momen inersia terhadap sumbu lemah (m⁴)
- J  : konstanta torsi (m⁴)

Section diambil dari project_data.BOX_SECTIONS.
J diestimasi dari A, Ix, Iy (belum dihitung dari DXF).

Untuk pier, section fiber akan dibuat di modul terpisah (nanti).

Referensi:
- project_data.py — BOX_SECTIONS
"""

import os
import sys


# ============================================================
# 1. KONSTANTA SECTION
# ============================================================

# Nilai J (torsi) per tipe
# tipikal & tumpuan: dari warping analysis DXF
# hollow: estimasi proporsional (warping segfault)
J_VALUES = {
    "solid":   3.8232,    # dari tipikal
    "hollow":  3.5840,    # estimasi proporsional
    "tumpuan": 3.1660,    # dari tumpuan
}

SECTION_TYPES = ["solid", "hollow", "tumpuan"]


# ============================================================
# 2. FUNGSI SECTION
# ============================================================

def get_J(tipe, box_sections):
    """
    Ambil konstanta torsi J (m⁴).
    
    Parameters
    ----------
    tipe : str
        Tipe section
    box_sections : dict
        Data section dari project_data
    
    Returns
    -------
    J : float
        Konstanta torsi (m⁴)
    """
    # Pakai J yang sudah dihitung
    if tipe in J_VALUES:
        return J_VALUES[tipe]
    
    # Fallback: estimasi
    sec = box_sections[tipe]
    return 0.5 * (sec["Ix"] + sec["Iy"])


def get_section(tipe, box_sections):
    """
    Ambil properti section deck.
    
    Parameters
    ----------
    tipe : str
        Tipe section
    box_sections : dict
        Data section dari project_data
    
    Returns
    -------
    dict : {A, Ix, Iy, J, cx, cy}
    """
    if tipe not in box_sections:
        raise ValueError("Tipe section tidak dikenal: {}".format(tipe))
    
    sec = box_sections[tipe]
    
    return {
        "A": sec["A"],
        "Ix": sec["Ix"],
        "Iy": sec["Iy"],
        "J": get_J(tipe, box_sections),
        "cx": sec.get("cx", 0.0),
        "cy": sec.get("cy", 0.0),
    }


def get_all_sections(box_sections):
    """
    Ambil semua section.
    
    Returns
    -------
    dict : {tipe: {A, Ix, Iy, J, cx, cy}}
    """
    return {tipe: get_section(tipe, box_sections)
            for tipe in box_sections}


def get_section_by_x(x, section_map, box_sections):
    """
    Ambil section berdasarkan posisi x.
    
    Parameters
    ----------
    x : float
        Posisi memanjang (m)
    section_map : list
        List of (x1, x2, tipe)
    box_sections : dict
        Data section
    
    Returns
    -------
    dict : {tipe, A, Ix, Iy, J, ...}
    """
    for x1, x2, tipe in section_map:
        if x1 <= x <= x2:
            sec = get_section(tipe, box_sections)
            sec["tipe"] = tipe
            sec["x1"] = x1
            sec["x2"] = x2
            return sec
    
    raise ValueError("x = {} tidak ada di SECTION_MAP".format(x))


# ============================================================
# 3. OUTPUT INFORMATIF
# ============================================================

def print_section_info(box_sections):
    """Cetak info section."""
    print("=" * 75)
    print("SECTION DECK (ELASTIS)")
    print("=" * 75)
    print("{:>10s} {:>10s} {:>10s} {:>10s} {:>10s}".format(
        "Tipe", "A (m2)", "Ix (m4)", "Iy (m4)", "J (m4)"))
    print("-" * 75)
    
    for tipe in SECTION_TYPES:
        if tipe not in box_sections:
            continue
        sec = get_section(tipe, box_sections)
        print("{:>10s} {:>10.4f} {:>10.4f} {:>10.4f} {:>10.4f}".format(
            tipe, sec["A"], sec["Ix"], sec["Iy"], sec["J"]))
    
    print("-" * 75)
    print()
    print("Catatan:")
    print("  - Ix = momen inersia terhadap sumbu kuat (lentur vertikal)")
    print("  - Iy = momen inersia terhadap sumbu lemah (lentur lateral)")
    print("  - J  = konstanta torsi (dari warping analysis / estimasi)")

    print()


def print_section_by_tipe(box_sections):
    """Cetak section per tipe (detail)."""
    print("=" * 75)
    print("DETAIL SECTION PER TIPE")
    print("=" * 75)
    
    for tipe in SECTION_TYPES:
        if tipe not in box_sections:
            continue
        sec = get_section(tipe, box_sections)
        print("\nTipe: {}".format(tipe))
        print("  A  = {:>10.4f} m²".format(sec["A"]))
        print("  Ix = {:>10.4f} m⁴".format(sec["Ix"]))
        print("  Iy = {:>10.4f} m⁴".format(sec["Iy"]))
        print("  J  = {:>10.4f} m⁴".format(sec["J"]))
        print("  cx = {:>10.4f} m".format(sec["cx"]))
        print("  cy = {:>10.4f} m".format(sec["cy"]))
    print()


def print_section_per_segmen(section_map, box_sections):
    """Cetak section per segmen."""
    print("=" * 75)
    print("SECTION PER SEGMEN")
    print("=" * 75)
    print("{:>4s} {:>9s} {:>9s} {:>10s} {:>10s} {:>10s} {:>10s}".format(
        "Seg", "x1", "x2", "Tipe", "A (m2)", "Ix (m4)", "Iy (m4)"))
    print("-" * 75)
    
    for i, (x1, x2, tipe) in enumerate(section_map):
        sec = get_section(tipe, box_sections)
        print("{:>4d} {:>9.3f} {:>9.3f} {:>10s} {:>10.4f} {:>10.4f} {:>10.4f}".format(
            i + 1, x1, x2, tipe, sec["A"], sec["Ix"], sec["Iy"]))
    
    print("-" * 75)
    print()


# ============================================================
# 4. MAIN (TEST)
# ============================================================

if __name__ == "__main__":
    # Path relatif dari lokasi file
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(os.path.join(BASE_DIR, "Clean"))
    
    import project_data as pdata
    
    # Print info
    print_section_info(pdata.BOX_SECTIONS)
    print_section_by_tipe(pdata.BOX_SECTIONS)
    print_section_per_segmen(pdata.SECTION_MAP, pdata.BOX_SECTIONS)
    
    # Test get_section_by_x
    print("=" * 75)
    print("TEST get_section_by_x")
    print("=" * 75)
    for x in [0.0, 5.0, 50.0, 100.0, 200.0]:
        try:
            sec = get_section_by_x(x, pdata.SECTION_MAP, pdata.BOX_SECTIONS)
            print("x = {:>7.2f} m: tipe = {:>10s}, A = {:.4f} m²".format(
                x, sec["tipe"], sec["A"]))
        except ValueError as e:
            print("x = {:>7.2f} m: ERROR — {}".format(x, e))
    
    print()
    print("SELESAI")