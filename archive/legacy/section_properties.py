# section_properties.py
"""
Data properti penampang jembatan Baros.
Satuan: kN, m, kPa.
"""

# ============================================================
# DATA PENAMPANG (dari ekstraksi DXF)
# ============================================================
SECTIONS = {
    "tipikal": {
        "A":  8.2231,      # m²
        "Ix": 1.4527,      # m⁴ (lentur vertikal)
        "Iy": 33.3927,     # m⁴ (lentur lateral)
        "J":  None,        # m⁴ (torsi, belum dihitung)
        "cx": 1.6886,      # m
        "cy": 0.4659,      # m
        "file": "Penampang_tipikal.dxf",
    },
    "hollow": {
        "A":  7.7072,
        "Ix": 1.4392,
        "Iy": 32.8489,
        "J":  None,
        "cx": 1.6886,
        "cy": 0.4659,
        "file": "Penampang_hollow.dxf",
    },
    "blockout": {
        "A":  5.5889,
        "Ix": 1.2139,
        "Iy": 30.0602,
        "J":  None,
        "cx": 1.5648,
        "cy": 0.5240,
        "file": "Penampang_blockout.dxf",
    },
    "tumpuan": {
        "A":  7.9670,
        "Ix": 1.2986,
        "Iy": 33.3759,
        "J":  None,
        "cx": 1.5748,
        "cy": 0.3721,
        "file": "Penampang_tumpuan.dxf",
    },
}

# ============================================================
# MATERIAL
# ============================================================
MATERIAL = {
    "E":  30e6,      # kPa (30 GPa)
    "G":  12.5e6,    # kPa
    "fpc": 35e3,     # kPa (35 MPa)
    "fy":  420e3,    # kPa (420 MPa)
    "gamma": 24.0,   # kN/m³
}