# Temp/fix_hollow.py
"""
Perbaiki DXF hollow: polygonize dari LINE.
Jalankan: python3 Temp/fix_hollow.py
"""

import os
import math
import ezdxf
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union
from sectionproperties.pre import Geometry
from sectionproperties.analysis import Section

DXF_INPUT = "/home/yoesroes/Sipil/baros/Source/DXF/scaled/Penampang_hollow_scaled.dxf"
MESH_SIZE = 200.0


def extract_lines(dxf_path, layer_keep):
    """Ekstrak LINE/LWPOLYLINE dari layer tertentu."""
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    
    lines = []
    for e in msp:
        if e.dxf.layer not in layer_keep:
            continue
        
        t = e.dxftype()
        pts = []
        
        if t == 'LINE':
            s = e.dxf.start
            en = e.dxf.end
            pts = [(s.x, s.y), (en.x, en.y)]
        elif t == 'LWPOLYLINE':
            pts = [(p[0], p[1]) for p in e.get_points()]
            if e.closed:
                pts.append(pts[0])
        elif t == 'CIRCLE':
            c = e.dxf.center
            r = e.dxf.radius
            n = 40
            pts = [(c.x + r * math.cos(2 * math.pi * i / n),
                    c.y + r * math.sin(2 * math.pi * i / n))
                   for i in range(n + 1)]
        
        if len(pts) >= 2:
            lines.append(LineString(pts))
    
    return lines


if __name__ == "__main__":
    print("=" * 60)
    print("PERBAIKI DXF HOLLOW")
    print("=" * 60)
    
    # Ekstrak garis dari layer box
    lines = extract_lines(DXF_INPUT, layer_keep=['box'])
    print("Segmen box: {}".format(len(lines)))
    
    # Polygonize
    polys = list(polygonize(unary_union(lines)))
    print("Polygon: {}".format(len(polys)))
    
    if not polys:
        print("ERROR: Tidak ada polygon")
        raise SystemExit(1)
    
    for i, p in enumerate(polys):
        print("  Polygon {}: luas = {:.2f}, valid = {}".format(
            i, p.area, p.is_valid))
    
    # Ambil polygon terbesar
    main_poly = max(polys, key=lambda p: p.area)
    print("\nPolygon utama: luas = {:.4f} m²".format(main_poly.area / 1e6))
    
    # Buat geometry & mesh
    geom = Geometry(geom=main_poly)
    geom.create_mesh(mesh_sizes=[MESH_SIZE])
    
    # Analisis
    sec = Section(geometry=geom)
    sec.calculate_geometric_properties()
    
    A = sec.get_area() / 1e6
    Ix, Iy, Ixy = sec.get_ic()
    Ix = Ix / 1e12
    Iy = Iy / 1e12
    
    print("\nProperti geometri:")
    print("  A  = {:.4f} m²".format(A))
    print("  Ix = {:.4f} m⁴".format(Ix))
    print("  Iy = {:.4f} m⁴".format(Iy))
    
    # Warping
    print("\nWarping analysis...")
    try:
        sec.calculate_warping_properties()
        J = sec.get_j() / 1e12
        print("  J  = {:.4f} m⁴ ✅".format(J))
    except Exception as e:
        print("  Gagal: {}".format(e))