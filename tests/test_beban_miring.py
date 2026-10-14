"""Tes orientasi beban gravitasi pada elemen miring (pekerjaan C).

1. Balok miring tunggal: beban gravitasi harus menghasilkan reaksi horizontal
   nol dan momen sesuai solusi analitik; beban lokal-y tanpa uraian
   menghasilkan reaksi horizontal tidak nol (membuktikan masalahnya).
2. Model Baros penuh: jumlah Rx dan Rz tiap unit nol untuk semua kasus,
   dan total beban kasus = jumlah reaksi vertikal.
"""
import math

try:
    import openseespy.opensees as ops
except ImportError:                                    # pragma: no cover
    ops = None

from core import analysis


def _balok_miring(Wy, Wx, dx=10.0, dy=2.0, q=-10.0):
    ops.wipe()
    ops.model("basic", "-ndm", 3, "-ndf", 6)
    ops.geomTransf("Linear", 1, 0.0, 0.0, 1.0)
    ops.node(1, 0.0, 0.0, 0.0)
    ops.node(2, dx, dy, 0.0)
    ops.element("elasticBeamColumn", 1, 1, 2, 1.0, 3e7, 1.25e7, 1.0, 1.0,
                0.5, 1)
    ops.fix(1, 1, 1, 1, 1, 0, 0)         # sendi
    ops.fix(2, 0, 1, 1, 1, 0, 0)         # rol memanjang
    ops.timeSeries("Linear", 1)
    ops.pattern("Plain", 1, 1)
    ops.eleLoad("-ele", 1, "-type", "-beamUniform", Wy, 0.0, Wx)
    ops.constraints("Plain")
    ops.numberer("RCM")
    ops.system("BandGeneral")
    ops.test("NormDispIncr", 1e-10, 10)
    ops.algorithm("Linear")
    ops.integrator("LoadControl", 1.0)
    ops.analysis("Static")
    ops.analyze(1)
    ops.reactions()
    return (sum(ops.nodeReaction(n)[0] for n in (1, 2)),
            sum(ops.nodeReaction(n)[1] for n in (1, 2)),
            ops.eleResponse(1, "localForce"))


def test_komponen_lokal_menjaga_resultan_vertikal():
    c, s = math.cos(math.atan2(2.0, 10.0)), math.sin(math.atan2(2.0, 10.0))
    wy, wx = analysis.komponen_lokal(-10.0, c, s)
    assert abs(wy * c + wx * s + 10.0) < 1e-12          # resultan vertikal
    assert abs(-wy * s + wx * c) < 1e-12                # resultan horizontal


def test_intensitas_aksial_dasar_panjang():
    c = 0.98
    assert analysis.intensitas_aksial("D1", -100.0, c) == -100.0
    old = dict(analysis.DASAR_PANJANG)
    try:
        analysis.DASAR_PANJANG["BTR"] = "horizontal"
        assert abs(analysis.intensitas_aksial("BTR", -100.0, c)
                   + 98.0) < 1e-12
        analysis.DASAR_PANJANG["BTR"] = "aksial"
        assert analysis.intensitas_aksial("BTR", -100.0, c) == -100.0
    finally:
        analysis.DASAR_PANJANG.clear()
        analysis.DASAR_PANJANG.update(old)


def test_balok_miring_beban_vertikal_tanpa_reaksi_horizontal():
    if ops is None:
        return
    dx, dy = 10.0, 2.0
    L = math.hypot(dx, dy)
    c, s = dx / L, dy / L
    q = -10.0                                   # kN/m per panjang sumbu
    wy, wx = analysis.komponen_lokal(q, c, s)
    rx, ry, f = _balok_miring(wy, wx)
    assert abs(rx) < 1e-7                        # beban vertikal murni
    assert abs(ry + q * L) < 1e-7                # resultan vertikal = q L
    # momen maks (tengah) = |Wy| L^2 / 8 ; Mz_j = 0 pada tumpuan sederhana
    m_mid = abs(wy) * L * L / 8.0
    s_mid = -f[5] + f[1] * (L / 2) + wy * (L / 2) ** 2 / 2
    assert abs(s_mid - m_mid) < 1e-6 * m_mid


def test_beban_lokal_y_tanpa_uraian_menghasilkan_reaksi_horizontal():
    if ops is None:
        return
    dx, dy = 10.0, 2.0
    L = math.hypot(dx, dy)
    rx, ry, _ = _balok_miring(-10.0, 0.0)        # cara lama
    assert abs(rx) > 5.0                         # komponen horizontal palsu


def test_model_baros_reaksi_horizontal_nol_semua_kasus():
    if ops is None:
        return
    from core import review
    nr, er, bcl, bentang, kasus, hasil, L_E = review.bangun_dan_jalankan()
    for nama, h in hasil.items():
        per = {}
        for b in bcl:
            sx, sz = per.get(b["unit"], (0.0, 0.0))
            per[b["unit"]] = (sx + h["Rx"][b["node"]], sz + h["Rz"][b["node"]])
        for u, (sx, sz) in per.items():
            assert abs(sx) < 1e-5 and abs(sz) < 1e-5, (nama, u, sx, sz)
        assert abs(sum(h["R"].values()) + kasus[nama]["total"]) < 1e-5
