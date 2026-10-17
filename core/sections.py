# core/sections.py
"""
Pembaca properti section TOTAL (penampang penuh) dari BOX_SECTIONS.
Satuan: kN, m, kPa.

STATUS: [LEGACY / MANDIRI] Modul ini TIDAK dipakai pipeline grillage
(nodes -> elements -> boundary_condition -> loads -> analysis -> output).
elements.py memakai section_strips.properti_garis(), yang membaca
BOX_SECTIONS langsung dan membagi total ke 5 garis memanjang.
Modul ini hanya untuk melihat/mencetak total per tipe dan cek manual.

Properti total deck (penampang penuh, 1 balok ekuivalen):
- A  : luas penampang (m2)
- Ix : inersia sumbu horizontal -> lentur VERTIKAL (m4)
        (= "Iz" pada elemen OpenSees memanjang)
- Iy : inersia sumbu vertikal   -> lentur LATERAL (m4)
- J  : konstanta torsi (m4)
- cx, cy : centroid (m); tidak dipakai pipeline.

Sumber: project_data.BOX_SECTIONS (BELUM DIAUDIT, lihat catatan di sana).

CATATAN AUDIT
-------------
1. get_J memprioritaskan BOX_SECTIONS[tipe]["J"] di atas J_VALUES.
    Nilai keduanya saat ini sama (3.8232 / 3.7533 / 3.1661), sehingga
    J_VALUES hanya menjadi fallback bila BOX_SECTIONS tidak memuat J.
2. get_section_by_x memakai batas inklusif x1 <= x <= x2: pada x yang
   tepat di batas segmen, tipe segmen PERTAMA yang menang. Pipeline tidak
   memakainya (elements.cari_tipe_di_x dipakai pada titik tengah segmen).

Pier: section fiber ada di repo terpisah (bukan di sini).
"""


# ============================================================
# 1. KONSTANTA SECTION
# ============================================================

# Nilai J (torsi) hasil warping analysis per tipe (m4), dipakai hanya
# sebagai FALLBACK bila BOX_SECTIONS[tipe] tidak memuat "J" (lihat get_J).
# CATATAN: BOX_SECTIONS saat ini memuat J = 3.8232/3.7533/3.1661, sehingga nilai
# di bawah tidak terpakai. Perbedaan itu belum diselesaikan (audit).
J_VALUES = {
    "solid":   3.8232,    # warping analysis
    "hollow":  3.7533,    # warping analysis (void drum)
    "tumpuan": 3.1661,    # warping analysis; lebih kecil dari hollow,
                          # perlu dicek kewajarannya
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
    # 1) J dari BOX_SECTIONS (sumber utama)
    sec = box_sections.get(tipe, {})
    if "J" in sec:
        return sec["J"]

    # 2) J_VALUES lokal
    if tipe in J_VALUES:
        return J_VALUES[tipe]

    # Tanpa estimasi diam-diam: J harus dari analisis penampang
    raise ValueError("J untuk tipe '{}' belum ada (BOX_SECTIONS/J_VALUES)."
                     .format(tipe))



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
    print("  - Ix = inersia sumbu horizontal (lentur vertikal)")
    print("  - Iy = inersia sumbu vertikal (lentur lateral)")
    print("  - J  = konstanta torsi (dari BOX_SECTIONS; belum diaudit)")

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
    # Jalankan dari root repo:  python -m core.sections
    from project import project_data as pdata
    
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