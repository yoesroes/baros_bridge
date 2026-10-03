# extract_final.py
import ezdxf
from ezdxf.math import Matrix44
from sectionproperties.pre import Geometry
from sectionproperties.analysis import Section

# --- KONFIGURASI ---
DXF_INPUT = "/home/yoesroes/Sipil/baros/Source/DXF/Penampang_tumpuan.dxf"
DXF_SCALED = "Penampang_scaled.dxf"
SCALE = 39.37
MESH = 1000.0

# 1. Skala DXF
doc = ezdxf.readfile(DXF_INPUT)
for entity in doc.modelspace():
    entity.transform(Matrix44.scale(SCALE, SCALE, 1))
doc.saveas(DXF_SCALED)
print(f"[1] DXF diskalakan x{SCALE}")

# 2. Baca & mesh
geom = Geometry.from_dxf(dxf_filepath=DXF_SCALED)
geom.create_mesh(mesh_sizes=[MESH])
print(f"[2] Mesh size: {MESH} mm")

# 3. Hitung properti geometri (TANPA warping)
sec = Section(geometry=geom)
sec.calculate_geometric_properties()

A = sec.get_area()
Ix, Iy, Ixy = sec.get_ic()
cx, cy = sec.get_c()

# 4. Konversi ke m
A_m2 = A / 1e6
Ix_m4 = Ix / 1e12
Iy_m4 = Iy / 1e12
Ixy_m4 = Ixy / 1e12
cx_m = cx / 1000.0
cy_m = cy / 1000.0

print(f"\nA   = {A_m2:.4f} m2")
print(f"Ix  = {Ix_m4:.4f} m4")
print(f"Iy  = {Iy_m4:.4f} m4")
print(f"Ixy = {Ixy_m4:.4f} m4")
print(f"cx  = {cx_m:.4f} m")
print(f"cy  = {cy_m:.4f} m")