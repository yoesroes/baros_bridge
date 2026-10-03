# hybrid_deck.py
"""
Hybrid: ospgrillage untuk mesh, OpenSeesPy murni untuk BC & beban.
"""

import openseespy.opensees as ops
import ospgrillage as og

print("=" * 60)
print("HYBRID: ospgrillage mesh + OpenSeesPy BC/beban")
print("=" * 60)

# ============ 1. RESET ============
ops.wipe()

# ============ 2. MESH via ospgrillage ============
bridge = og.create_grillage(
    model_type="beam_only",
    bridge_name="HybridDeck",
    long_dim=20.0, width=8.0, skew=0.0,
    num_long_grid=2, num_trans_grid=3,
    edge_beam_dist=1.0, mesh_type="Ortho",
)

concrete = og.create_material(E=30e6, G=12.5e6)
concrete.density = 2400
section = og.create_section(A=1.0, Iz=0.1, Iy=0.1, J=0.2)
member = og.create_member(section=section, material=concrete)

for grp in ["interior_main_beam", "exterior_main_beam_1",
            "exterior_main_beam_2", "edge_beam",
            "transverse_slab", "start_edge", "end_edge"]:
    bridge.set_member(member, member=grp)

bridge.create_osp_model()
print(f"[1] Mesh dibuat: {len(ops.getNodeTags())} node, "
      f"{len(ops.getEleTags())} elemen")

# Cek koordinat untuk tahu node mana di mana
print("\n[2] Koordinat node:")
for tag in ops.getNodeTags():
    c = ops.nodeCoord(tag)
    print(f"  Node {tag}: ({c[0]:5.1f}, {c[1]:5.1f}, {c[2]:5.1f})")

# ============ 3. IDENTIFIKASI TUMPUAN & BEBAN ============
# Cari node di x=0 (kiri), x=20 (kanan), dan x=10 (tengah)
x_min = min(ops.nodeCoord(t)[0] for t in ops.getNodeTags())
x_max = max(ops.nodeCoord(t)[0] for t in ops.getNodeTags())
x_mid = (x_min + x_max) / 2.0

nodes_left = [t for t in ops.getNodeTags()
              if abs(ops.nodeCoord(t)[0] - x_min) < 1e-6]
nodes_right = [t for t in ops.getNodeTags()
               if abs(ops.nodeCoord(t)[0] - x_max) < 1e-6]
nodes_mid = [t for t in ops.getNodeTags()
             if abs(ops.nodeCoord(t)[0] - x_mid) < 1e-6]

print(f"\n[3] Identifikasi:")
print(f"  Tumpuan kiri  (x={x_min}): {nodes_left}")
print(f"  Tumpuan kanan (x={x_max}): {nodes_right}")
print(f"  Tengah        (x={x_mid}): {nodes_mid}")

# ============ 4. BC MANUAL ============
# Tumpuan kiri: pin (fix translasi)
for t in nodes_left:
    ops.fix(t, 1, 1, 1, 0, 0, 0)

# Tumpuan kanan: roller (fix vertikal & lateral)
for t in nodes_right:
    ops.fix(t, 0, 1, 1, 0, 0, 0)

print(f"\n[4] Fixed nodes: {ops.getFixedNodes()}")

# ============ 5. BEBAN MANUAL ============
ops.timeSeries('Linear', 1)
ops.pattern('Plain', 1, 1)

# Beban terdistribusi ke node tengah
P_total = -10.0   # kN
n_mid = len(nodes_mid)
for t in nodes_mid:
    ops.load(t, 0.0, P_total / n_mid, 0.0, 0.0, 0.0, 0.0)

print(f"[5] Beban {P_total} kN terdistribusi ke {n_mid} node tengah")

# ============ 6. ANALISIS MANUAL ============
ops.constraints('Transformation')
ops.numberer('RCM')
ops.system('BandGeneral')
ops.test('NormDispIncr', 1e-6, 20)
ops.algorithm('Linear')
ops.integrator('LoadControl', 1.0)
ops.analysis('Static')

ok = ops.analyze(1)
print(f"\n[6] Analyze return: {ok}")

# ============ 7. HASIL ============
if ok == 0:
    ops.reactions()
    
    print("\n=== Displacement (mm) ===")
    for tag in ops.getNodeTags():
        disp = ops.nodeDisp(tag)
        c = ops.nodeCoord(tag)
        print(f"  Node {tag} @ ({c[0]:5.1f},{c[2]:4.1f}): "
              f"uy={disp[1]*1000:8.4f} mm")
    
    print("\n=== Reaksi (kN) ===")
    total_Fy = 0.0
    for tag in ops.getFixedNodes():
        rxn = ops.nodeReaction(tag)
        print(f"  Node {tag}: Fx={rxn[0]:8.4f}, Fy={rxn[1]:8.4f}, "
              f"Fz={rxn[2]:8.4f}")
        total_Fy += rxn[1]
    print(f"\n  Total Fy = {total_Fy:.4f} kN (harus = {abs(P_total):.4f})")
else:
    print("❌ Analisis gagal")

print("\n✅ Selesai")