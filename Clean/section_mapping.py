# section_mapping.py
"""
Mapping tipe penampang sepanjang jembatan Baros.
Dari A1 (x=0) ke A2 (x=204.4944).
Skala DXF: 25.4 satuan/m
"""

SECTION_MAP = [
    # (x_awal, x_akhir, tipe)
    # --- Bentang A1-P1 ---
    (0.00,   1.08,   "tumpuan"),
    (1.08,   9.75,   "hollow"),
    (9.75,  11.25,   "blockout"),
    (11.25, 14.45,   "hollow"),
    (14.45, 16.25,   "tumpuan"),
    
    # --- Bentang P1-P2 ---
    (16.25, 17.15,   "tumpuan"),
    (17.15, 20.75,   "hollow"),
    (20.75, 22.25,   "blockout"),
    (22.25, 31.95,   "hollow"),
    (31.95, 33.75,   "tumpuan"),
    
    # --- Bentang P2-P3 ---
    (33.75, 34.65,   "tumpuan"),
    (34.65, 45.25,   "hollow"),
    (45.25, 46.75,   "blockout"),
    (46.75, 49.45,   "hollow"),
    (49.45, 51.25,   "tumpuan"),
    
    # --- Bentang P3-P4 ---
    (51.25, 52.15,   "tumpuan"),
    (52.15, 55.75,   "hollow"),
    (55.75, 57.25,   "blockout"),
    (57.25, 68.75,   "hollow"),
    (68.75, 70.25,   "blockout"),
    (70.25, 72.95,   "hollow"),
    (72.95, 74.75,   "tumpuan"),
    
    # --- Bentang P4-P5 ---
    (74.75, 75.65,   "tumpuan"),
    (75.65, 79.25,   "hollow"),
    (79.25, 80.75,   "blockout"),
    (80.75, 106.75,  "hollow"),
    (106.75, 108.25, "blockout"),
    (108.25, 111.85, "hollow"),
    (111.85, 113.65, "tumpuan"),
    
    # --- Bentang P5-P6 ---
    (113.65, 117.25, "hollow"),
    (117.25, 118.75, "blockout"),
    (118.75, 124.25, "hollow"),
    (124.25, 125.75, "blockout"),
    (125.75, 128.45, "hollow"),
    (128.45, 130.25, "tumpuan"),
    
    # --- Bentang P6-P7 ---
    (130.25, 132.55, "tumpuan"),
    (132.55, 136.15, "hollow"),
    (136.15, 137.65, "blockout"),
    (137.65, 153.45, "hollow"),
    (153.45, 155.25, "tumpuan"),
    
    # --- Bentang P7-P8 ---
    (155.25, 157.55, "tumpuan"),
    (157.55, 175.25, "hollow"),
    (175.25, 176.75, "blockout"),
    (176.75, 178.45, "hollow"),
    (178.45, 180.25, "tumpuan"),
    
    # --- Bentang P8-A2 ---
    (180.25, 182.55, "tumpuan"),
    (182.55, 186.15, "hollow"),
    (186.15, 187.65, "blockout"),
    (187.65, 203.14, "hollow"),
    (203.14, 204.49, "tumpuan"),
]