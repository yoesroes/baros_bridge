# core/loads.py
"""
Modul Beban untuk Jembatan Baros (Grillage 2D).
Satuan: kN, m, kPa.

Beban per elemen memanjang:
- Berat sendiri box girder (bervariasi per section)
- Beban mati non-struktur (aspal + air + barrier)
- Beban hidup (BTR + KEL) sesuai SNI 1725:2016

Elemen melintang TIDAK dibebani.

Kombinasi pembebanan:
- Service (Daya Layan I-IV)
- Ultimate (Kuat I-V)
- Ekstrem (Gempa)

Referensi:
- SNI 1725:2016 — Pembebanan untuk Jembatan
"""

# ============================================================
# 1. KONSTANTA BEBAN
# ============================================================

# Material (SNI 1725:2016)
FPC_BOX = 41.5e3        # kPa (41.5 MPa)
FPC_PIER = 30.0e3       # kPa (30 MPa)

GAMMA_BETON_BOX = 22 + 0.022 * (FPC_BOX / 1000)   # 22.913 kN/m³
GAMMA_BETON_PIER = 22 + 0.022 * (FPC_PIER / 1000) # 22.66 kN/m³
GAMMA_ASPAL = 22.0      # kN/m³
GAMMA_AIR = 10.0        # kN/m³

# Beban mati non-struktur
T_ASPAL = 0.075         # m
T_AIR = 0.005           # m (0.5 cm genangan)
A_BARRIER = 0.25        # m²
B_JALAN = 9.0           # m
N_SISI = 2              # jumlah sisi barrier

# Beban hidup (SNI 1725:2016 Pasal 8.3)
Q_BTR = 9.0             # kPa
P_KEL = 49.0            # kN/m
FBD = 0.4               # faktor beban dinamis


# ============================================================
# 2. FUNGSI PERHITUNGAN BEBAN
# ============================================================

def hitung_w_box(A):
    """Berat sendiri box girder per meter (kN/m)."""
    return GAMMA_BETON_BOX * A


def hitung_w_aspal():
    """Beban aspal per meter (kN/m)."""
    return GAMMA_ASPAL * T_ASPAL * B_JALAN


def hitung_w_air():
    """Beban genangan air per meter (kN/m)."""
    return GAMMA_AIR * T_AIR * B_JALAN


def hitung_w_barrier():
    """Beban barrier per meter (kN/m)."""
    return GAMMA_BETON_PIER * A_BARRIER * N_SISI


def hitung_w_non_struktur():
    """Total beban mati non-struktur (kN/m)."""
    return hitung_w_aspal() + hitung_w_air() + hitung_w_barrier()


def hitung_w_hidup():
    """Beban hidup (BTR + KEL) per meter (kN/m)."""
    w_btr = Q_BTR * B_JALAN
    w_kel = P_KEL * (1 + FBD)
    return w_btr + w_kel


def hitung_w_total(A):
    """Total beban per meter (kN/m)."""
    return hitung_w_box(A) + hitung_w_non_struktur() + hitung_w_hidup()


# ============================================================
# 3. BEBAN PER ELEMEN
# ============================================================

def hitung_beban_per_elemen(section_map, box_sections):
    """
    Hitung beban untuk setiap elemen memanjang.
    
    Parameters
    ----------
    section_map : list
        List of (x1, x2, tipe)
    box_sections : dict
        Properti penampang {tipe: {A, Ix, Iy, ...}}
    
    Returns
    -------
    elemen_data : list of dict
    """
    elemen_data = []
    
    for i, (x1, x2, tipe) in enumerate(section_map):
        ele_tag = i + 1
        L = x2 - x1
        A = box_sections[tipe]["A"]
        
        w_box = hitung_w_box(A)
        w_non_struktur = hitung_w_non_struktur()
        w_hidup = hitung_w_hidup()
        w_total = w_box + w_non_struktur + w_hidup
        
        elemen_data.append({
            "ele_tag": ele_tag,
            "x1": x1,
            "x2": x2,
            "tipe": tipe,
            "L": L,
            "A": A,
            "w_box": w_box,
            "w_non_struktur": w_non_struktur,
            "w_hidup": w_hidup,
            "w_total": w_total,
        })
    
    return elemen_data


# ============================================================
# 4. KOMBINASI PEMBEBANAN (SNI 1725:2016)
# ============================================================

KOMBINASI = {
    # Service (Daya Layan)
    "Daya Layan I":   {"D1": 1.0, "D2": 1.0, "L": 1.0, "P": 1.0},
    "Daya Layan II":  {"D1": 1.0, "D2": 1.0, "L": 1.3, "P": 1.0},
    "Daya Layan III": {"D1": 1.0, "D2": 1.0, "L": 0.8, "P": 1.0},
    "Daya Layan IV":  {"D1": 1.0, "D2": 1.0, "L": 0.0, "P": 1.0},
    
    # Ultimate (Kuat)
    "Kuat I":   {"D1": 1.2, "D2": 2.0, "L": 1.8, "P": 1.0},
    "Kuat II":  {"D1": 1.2, "D2": 2.0, "L": 1.4, "P": 1.0},
    "Kuat III": {"D1": 1.2, "D2": 2.0, "L": 0.0, "P": 1.0},
    "Kuat IV":  {"D1": 1.2, "D2": 2.0, "L": 0.0, "P": 1.0},
    "Kuat V":   {"D1": 1.2, "D2": 2.0, "L": 0.0, "P": 1.0},
    
    # Ekstrem (Gempa)
    "Ekstrem Ia": {"D1": 1.0, "D2": 1.0, "L": 0.3, "P": 1.0, "EQ": 1.0},
    "Ekstrem Ib": {"D1": 1.0, "D2": 1.0, "L": 0.3, "P": 1.0, "EQ": 1.0},
}


def hitung_w_kombinasi(w_box, w_non_struktur, w_hidup,
                       w_prategang=0.0, w_gempa=0.0,
                       kombinasi="Daya Layan I"):
    """
    Hitung beban kombinasi sesuai SNI 1725:2016.
    
    Parameters
    ----------
    w_box : float
        Beban mati utama (box girder) — D1
    w_non_struktur : float
        Beban mati tambahan (aspal, air, barrier) — D2
    w_hidup : float
        Beban hidup (BTR + KEL) — L
    w_prategang : float
        Beban prategang — P (default 0)
    w_gempa : float
        Beban gempa — EQ (default 0)
    kombinasi : str
        Nama kombinasi
    
    Returns
    -------
    w_total : float
        Beban total kombinasi (kN/m)
    """
    if kombinasi not in KOMBINASI:
        raise ValueError("Kombinasi tidak dikenal: {}".format(kombinasi))
    
    f = KOMBINASI[kombinasi]
    
    w_total = (
        f.get("D1", 0) * w_box +
        f.get("D2", 0) * w_non_struktur +
        f.get("L", 0) * w_hidup +
        f.get("P", 0) * w_prategang +
        f.get("EQ", 0) * w_gempa
    )
    
    return w_total


def hitung_semua_kombinasi(elemen_data):
    """
    Hitung semua kombinasi untuk setiap elemen.
    
    Returns
    -------
    hasil : dict
        {kombinasi: [w_total per elemen]}
    """
    hasil = {nama: [] for nama in KOMBINASI}
    
    for ele in elemen_data:
        for nama in KOMBINASI:
            w = hitung_w_kombinasi(
                ele["w_box"], ele["w_non_struktur"], ele["w_hidup"],
                kombinasi=nama
            )
            hasil[nama].append(w)
    
    return hasil


# ============================================================
# 5. OUTPUT INFORMATIF
# ============================================================

def print_parameter():
    """Cetak parameter beban."""
    print("=" * 65)
    print("PARAMETER BEBAN")
    print("=" * 65)
    print("MATERIAL:")
    print("  f'c box       = {:>8.1f} MPa".format(FPC_BOX / 1000))
    print("  f'c pier      = {:>8.1f} MPa".format(FPC_PIER / 1000))
    print("  gamma box     = {:>8.3f} kN/m3".format(GAMMA_BETON_BOX))
    print("  gamma pier    = {:>8.3f} kN/m3".format(GAMMA_BETON_PIER))
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
    print("  q BTR         = {:>8.1f} kPa".format(Q_BTR))
    print("  P KEL         = {:>8.1f} kN/m".format(P_KEL))
    print("  FBD           = {:>8.2f}".format(FBD))
    print()
    print("HASIL PERHITUNGAN:")
    print("  w aspal       = {:>8.2f} kN/m".format(hitung_w_aspal()))
    print("  w air         = {:>8.2f} kN/m".format(hitung_w_air()))
    print("  w barrier     = {:>8.2f} kN/m".format(hitung_w_barrier()))
    print("  w non-struk   = {:>8.2f} kN/m".format(hitung_w_non_struktur()))
    print("  w BTR         = {:>8.2f} kN/m".format(Q_BTR * B_JALAN))
    print("  w KEL         = {:>8.2f} kN/m".format(P_KEL * (1 + FBD)))
    print("  w hidup       = {:>8.2f} kN/m".format(hitung_w_hidup()))
    print()


def print_ringkasan(elemen_data):
    """Cetak tabel beban per elemen."""
    print("=" * 105)
    print("RINGKASAN BEBAN PER ELEMEN MEMANJANG")
    print("=" * 105)
    print("{:>4s} {:>9s} {:>9s} {:>10s} {:>8s} {:>10s} {:>10s} {:>10s}".format(
        "Tag", "x1", "x2", "Tipe", "L (m)", "A (m2)", "w_box", "w_total"))
    print("-" * 105)
    
    for ele in elemen_data:
        print("{:>4d} {:>9.3f} {:>9.3f} {:>10s} {:>8.3f} {:>10.4f} {:>10.2f} {:>10.2f}".format(
            ele["ele_tag"], ele["x1"], ele["x2"], ele["tipe"],
            ele["L"], ele["A"], ele["w_box"], ele["w_total"]))
    
    total_F = sum(e["w_total"] * e["L"] for e in elemen_data)
    print("-" * 105)
    print("Total beban elemen (w_total): {:>10.2f} kN".format(total_F))
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
                "jumlah": 0,
                "total_L": 0.0,
                "A": ele["A"],
                "w_box": ele["w_box"],
                "w_total": ele["w_total"],
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
    """Cetak tabel semua kombinasi per elemen (ringkas)."""
    print("=" * 120)
    print("SEMUA KOMBINASI PEMBEBANAN (SNI 1725:2016)")
    print("=" * 120)
    
    # Header
    kombinasi_list = list(KOMBINASI.keys())
    header = "{:>4s} {:>9s} {:>10s}".format("Tag", "x1", "Tipe")
    for k in kombinasi_list:
        header += " {:>12s}".format(k[:10])
    print(header)
    print("-" * 120)
    
    # Data per elemen
    for ele in elemen_data:
        row = "{:>4d} {:>9.3f} {:>10s}".format(
            ele["ele_tag"], ele["x1"], ele["tipe"])
        
        for k in kombinasi_list:
            w = hitung_w_kombinasi(
                ele["w_box"], ele["w_non_struktur"], ele["w_hidup"],
                kombinasi=k
            )
            row += " {:>12.2f}".format(w)
        
        print(row)
    
    print("-" * 120)
    print()


def print_max_kombinasi(elemen_data):
    """Cetak kombinasi maksimum (envelope) per elemen."""
    print("=" * 80)
    print("KOMBINASI MAKSIMUM (ENVELOPE) PER ELEMEN")
    print("=" * 80)
    print("{:>4s} {:>9s} {:>10s} {:>14s} {:>14s}".format(
        "Tag", "x1", "Tipe", "Kombinasi Max", "w_max"))
    print("-" * 80)
    
    for ele in elemen_data:
        w_max = 0.0
        nama_max = ""
        
        for k in KOMBINASI:
            w = hitung_w_kombinasi(
                ele["w_box"], ele["w_non_struktur"], ele["w_hidup"],
                kombinasi=k
            )
            if w > w_max:
                w_max = w
                nama_max = k
        
        print("{:>4d} {:>9.3f} {:>10s} {:>14s} {:>14.2f}".format(
            ele["ele_tag"], ele["x1"], ele["tipe"], nama_max, w_max))
    
    print("-" * 80)
    print()

# ============================================================
# 7. SIMPAN OUTPUT KE FILE
# ============================================================

def save_output_ke_file(elemen_data, filename="output/loads_output.txt"):
    """
    Simpan output lengkap ke file teks.
    
    Parameters
    ----------
    elemen_data : list of dict
        Data beban per elemen
    filename : str
        Path file output
    """
    import os
    
    # Buat folder output kalau belum ada
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    with open(filename, "w") as f:
        # Redirect print ke file
        import sys
        original_stdout = sys.stdout
        sys.stdout = f
        
        try:
            print("=" * 100)
            print("OUTPUT MODUL BEBAN — JEMBATAN BAROS")
            print("=" * 100)
            print()
            
            print_parameter()
            print_ringkasan(elemen_data)
            print_ringkasan_per_tipe(elemen_data)
            print_semua_kombinasi(elemen_data)
            print_max_kombinasi(elemen_data)
            
            print("=" * 100)
            print("SELESAI")
            print("=" * 100)
        finally:
            sys.stdout = original_stdout
    
    print("Output disimpan: {}".format(filename))

def save_csv(elemen_data, filename="output/loads_output.csv"):
    """Simpan beban per elemen ke CSV."""
    import os
    import csv
    
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "ele_tag", "x1", "x2", "tipe", "L", "A",
            "w_box", "w_non_struktur", "w_hidup", "w_total"
        ])
        
        for ele in elemen_data:
            writer.writerow([
                ele["ele_tag"], ele["x1"], ele["x2"], ele["tipe"],
                ele["L"], ele["A"], ele["w_box"],
                ele["w_non_struktur"], ele["w_hidup"], ele["w_total"]
            ])
    
    print("CSV disimpan: {}".format(filename))

# ============================================================
# 6. MAIN (TEST)
# ============================================================

if __name__ == "__main__":
    import sys
    sys.path.append("/home/yoesroes/Sipil/baros_bridge/Clean")
    import project_data as pd
    
    # Print parameter
    print_parameter()
    
    # Hitung beban per elemen
    elemen_data = hitung_beban_per_elemen(pd.SECTION_MAP, pd.BOX_SECTIONS)
    
    # Print ringkasan
    print_ringkasan(elemen_data)
    print_ringkasan_per_tipe(elemen_data)
    print_semua_kombinasi(elemen_data)
    print_max_kombinasi(elemen_data)
    
    # Simpan ke file
    save_output_ke_file(elemen_data, 
                        "/home/yoesroes/Sipil/baros_bridge/output/loads_output.txt")

    save_csv(elemen_data,
             "/home/yoesroes/Sipil/baros_bridge/output/loads_output.csv")

    
    # Print max kombinasi
    print_max_kombinasi(elemen_data[:10])