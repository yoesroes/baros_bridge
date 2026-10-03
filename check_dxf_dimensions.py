# extract_section_properties.py
"""
Ekstrak properti penampang dari DXF menggunakan sectionproperties.

DXF: Penampang_tipikal.dxf
Skala DXF: 1:39.37 (perlu skala ulang ×39.37)
Output: A, Ix, Iy, J dalam satuan m², m⁴
"""

import os
import math
from sectionproperties.analysis import Section
from sectionproperties.pre import Geometry


# ============================================================
# 1. KONFIGURASI
# ============================================================
DXF_PATH = "/home/yoesroes/Sipil/baros/Source/DXF/Penampang_tipikal.dxf"

# Skala DXF → 1:1 (ukuran sebenarnya)
# DXF: tinggi 38.1 mm, sebenarnya 1500 mm → skala = 1500/38.1 = 39.37
SCALE_FACTOR = 39.37

# Mesh size (mm) — semakin kecil semakin akurat tapi lambat
# Untuk box girder besar, 50 mm cukup
MESH_SIZE = 50.0

# Output file
OUTPUT_JSON = "section_properties.json"


# ============================================================
# 2. FUNGSI UTAMA
# ============================================================
def extract_section_properties(dxf_path, scale_factor, mesh_size):
    """
    Baca DXF, skala ulang, hitung properti penampang.
    
    Returns
    -------
    dict : {A, Ix, Iy, J, cx, cy, ...}
    """
    print("=" * 60)
    print("EKSTRAK PROPERTI PENAMPANG DARI DXF")
    print("=" * 60)
    
    # --- 2a. Cek file ---
    if not os.path.exists(dxf_path):
        raise FileNotFoundError(f"File tidak ditemukan: {dxf_path}")
    
    file_size = os.path.getsize(dxf_path) / 1024
    print(f"\n[1] File: {dxf_path}")
    print(f"    Ukuran: {file_size:.2f} KB")
    
    # --- 2b. Baca DXF ---
    print(f"\n[2] Membaca DXF...")
    geom = Geometry.from_dxf(dxf_filepath=dxf_path)
    print(f"    ✅ DXF berhasil dibaca")
    
    # --- 2c. Skala ulang ---
    print(f"\n[3] Skala ulang ×{scale_factor}...")
    geom.scale(scale_factor)
    print(f"    ✅ Geometri diskalakan")
    
    # --- 2d. Buat mesh ---
    print(f"\n[4] Membuat mesh (size = {mesh_size} mm)...")
    geom.create_mesh(mesh_sizes=[mesh_size])
    print(f"    ✅ Mesh dibuat")
    
    # --- 2e. Analisis ---
    print(f"\n[5] Menghitung properti...")
    sec = Section(geometry=geom)
    sec.calculate_geometric_properties()
    print(f"    ✅ Properti dihitung")
    
    # --- 2f. Ambil hasil (dalam mm) ---
    A_mm2 = sec.get_area()
    Ix_mm4, Iy_mm4 = sec.get_ic()       # centroidal moment of inertia
    J_mm4 = sec.get_j()
    cx, cy = sec.get_c()
    
    # Konversi ke m
    A_m2 = A_mm2 / 1e6
    Ix_m4 = Ix_mm4 / 1e12
    Iy_m4 = Iy_mm4 / 1e12
    J_m4 = J_mm4 / 1e12
    cx_m = cx / 1000.0
    cy_m = cy / 1000.0
    
    # --- 2g. Output ---
    print("\n" + "=" * 60)
    print("HASIL")
    print("=" * 60)
    print(f"\n  Luas (A)       : {A_m2:.6f} m²  ({A_mm2:.2f} mm²)")
    print(f"  Ix (centroidal): {Ix_m4:.6f} m⁴  ({Ix_mm4:.2e} mm⁴)")
    print(f"  Iy (centroidal): {Iy_m4:.6f} m⁴  ({Iy_mm4:.2e} mm⁴)")
    print(f"  J (torsi)      : {J_m4:.6f} m⁴  ({J_mm4:.2e} mm⁴)")
    print(f"  Centroid       : ({cx_m:.6f}, {cy_m:.6f}) m")
    
    # --- 2h. Sanity check ---
    print("\n" + "=" * 60)
    print("SANITY CHECK")
    print("=" * 60)
    
    # Cek A
    if 1.0 < A_m2 < 20.0:
        print(f"  ✅ A = {A_m2:.4f} m² — dalam rentang wajar (1–20 m²)")
    else:
        print(f"  ⚠️  A = {A_m2:.4f} m² — di luar rentang wajar (1–20 m²)")
    
    # Cek Ix (untuk box girder 10m × 1.5m)
    # Estimasi kasar: I ≈ (1/12) × b × h³ × factor
    # = (1/12) × 10 × 1.5³ × 0.7 ≈ 1.97 m⁴
    if 0.5 < Ix_m4 < 10.0:
        print(f"  ✅ Ix = {Ix_m4:.4f} m⁴ — dalam rentang wajar")
    else:
        print(f"  ⚠️  Ix = {Ix_m4:.4f} m⁴ — di luar rentang wajar")
    
    # Cek J
    if J_m4 > 0:
        print(f"  ✅ J = {J_m4:.4f} m⁴ — positif")
    else:
        print(f"  ⚠️  J = {J_m4:.4f} m⁴ — tidak valid")
    
    # Cek centroid (untuk penampang simetris, cx ≈ 0)
    if abs(cx_m) < 0.5:
        print(f"  ✅ Centroid x = {cx_m:.4f} m — mendekati simetris")
    else:
        print(f"  ⚠️  Centroid x = {cx_m:.4f} m — tidak simetris")
    
    return {
        "A_m2": A_m2,
        "Ix_m4": Ix_m4,
        "Iy_m4": Iy_m4,
        "J_m4": J_m4,
        "cx_m": cx_m,
        "cy_m": cy_m,
        "scale_factor": scale_factor,
        "mesh_size_mm": mesh_size,
        "dxf_path": dxf_path,
    }


# ============================================================
# 3. SIMPAN KE JSON
# ============================================================
def save_to_json(data, output_path):
    import json
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n💾 Hasil disimpan ke: {output_path}")


# ============================================================
# 4. MAIN
# ============================================================
if __name__ == "__main__":
    try:
        result = extract_section_properties(
            dxf_path=DXF_PATH,
            scale_factor=SCALE_FACTOR,
            mesh_size=MESH_SIZE,
        )
        
        save_to_json(result, OUTPUT_JSON)
        
        print("\n" + "=" * 60)
        print("✅ SELESAI")
        print("=" * 60)
    
    except FileNotFoundError as e:
        print(f"\n❌ File tidak ditemukan: {e}")
        print("   Cek path DXF di bagian KONFIGURASI.")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()