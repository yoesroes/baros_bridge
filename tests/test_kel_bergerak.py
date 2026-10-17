"""Tes KEL bergerak (beban titik di dalam elemen), KEL kedua, dan SC-17."""
import math

try:
    import openseespy.opensees as ops
except ImportError:                                    # pragma: no cover
    ops = None

from core import analysis, design_review, gaya_total


def _struktur():
    stasiun = [{"x": 0.0, "unit": 0}, {"x": 10.0, "unit": 0}]
    node_map = {(0, 0): 1, (1, 0): 2, (0, 1): 3, (1, 1): 4}
    memanjang = [{"tag": 1, "unit": 0, "garis": 0, "x1": 0.0, "x2": 10.0},
                 {"tag": 2, "unit": 0, "garis": 1, "x1": 0.0, "x2": 10.0}]
    b = {"x1": 0.0, "x2": 10.0}
    return b, stasiun, node_map, memanjang


def test_kel_di_stasiun_menjadi_beban_nodal():
    b, st, nm, mem = _struktur()
    fy, pl = analysis.beban_kel_di(0.0, b, [0.5, 0.5], 100.0, st, nm, mem,
                                   [-1.0, 1.0])
    assert pl == {} and fy == {1: -50.0, 3: -50.0}


def test_kel_di_dalam_elemen_menjadi_beban_titik():
    b, st, nm, mem = _struktur()
    fy, pl = analysis.beban_kel_di(3.0, b, [0.5, 0.5], 100.0, st, nm, mem,
                                   [-1.0, 1.0])
    assert fy == {}
    assert pl == {1: [(-50.0, 0.3)], 2: [(-50.0, 0.3)]}


def test_kel_produksi_pakai_lebar_jalan_dan_dua_jalur_alternatif(monkeypatch):
    from core import loads

    z_garis = (-5.0, -2.5, 0.0, 2.5, 5.0)
    stasiun = [{"x": 0.0, "unit": 0}, {"x": 10.0, "unit": 0}]
    node_map = {(i, j): i * len(z_garis) + j + 1
                for i in range(len(stasiun)) for j in range(len(z_garis))}
    node_result = {"z_garis": z_garis, "z_ref": z_garis,
                   "stasiun": stasiun, "node_map": node_map}
    memanjang = [{"tag": j + 1, "unit": 0, "garis": j, "x1": 0.0,
                  "x2": 10.0, "L_aksial": 10.0, "cos_a": 1.0,
                  "tipe_section": "solid"} for j in range(len(z_garis))]
    elemen_result = {"memanjang": memanjang}
    supports = {"A1": {"x": 0.0}, "P1": {"x": 10.0}}
    monkeypatch.setattr(analysis.strips, "fraksi_berat",
                        lambda tipe, z_ref: [0.2] * len(z_garis))

    kasus, _ = analysis.bangun_kasus(
        node_result, elemen_result, {"solid": {"A": 1.0}}, supports,
        L_E=30.0, offsets=(0.0,), kel_fraksi=(0.0, 0.5))

    kel_stasiun = kasus["KEL|A1-P1|f=0.00|o=+0.00"]
    kel_titik = kasus["KEL|A1-P1|f=0.50|o=+0.00"]
    b_jalan = loads.lebar_jalan_per_garis(z_garis)
    expected_by_line = [-68.6 * width for width in b_jalan]
    assert loads.hitung_P_kel(L_E=30.0) == 617.4
    assert kel_stasiun["total"] == -617.4
    assert kel_titik["total"] == -617.4
    assert [kel_stasiun["node"][node_map[(0, j)]]
            for j in range(len(z_garis))] == expected_by_line
    assert [kel_titik["pload"][j + 1][0][0]
            for j in range(len(z_garis))] == expected_by_line
    assert kel_stasiun["node"] and kel_stasiun["pload"] == {}
    assert kel_titik["pload"] and kel_titik["node"] == {}

    kel_helper = loads.hitung_beban_per_elemen(
        [(0.0, 10.0, "solid")], {"solid": {"A": 1.0}},
        z_garis=z_garis, L_E=30.0)[0]["P_kel_garis"]
    assert kel_helper == [-value for value in expected_by_line]
    btr = kasus["BTR|A1-P1|o=+0.00"]
    assert btr["total"] == -9.0 * 7.25 * 10.0


def test_beban_titik_pada_balok_miring_tetap_vertikal():
    if ops is None:
        return
    dx, dy, xl, P = 10.0, 2.0, 0.3, -100.0
    L = math.hypot(dx, dy)
    c, s = dx / L, dy / L
    ops.wipe()
    ops.model("basic", "-ndm", 3, "-ndf", 6)
    ops.geomTransf("Linear", 1, 0.0, 0.0, 1.0)
    ops.node(1, 0.0, 0.0, 0.0)
    ops.node(2, dx, dy, 0.0)
    ops.element("elasticBeamColumn", 1, 1, 2, 1.0, 3e7, 1.25e7, 1.0, 1.0,
                0.5, 1)
    ops.fix(1, 1, 1, 1, 1, 0, 0)
    ops.fix(2, 0, 1, 1, 1, 0, 0)
    ops.timeSeries("Linear", 1)
    ops.pattern("Plain", 1, 1)
    ops.eleLoad("-ele", 1, "-type", "-beamPoint", P * c, 0.0, xl, P * s)
    ops.constraints("Plain")
    ops.numberer("RCM")
    ops.system("BandGeneral")
    ops.test("NormDispIncr", 1e-10, 10)
    ops.algorithm("Linear")
    ops.integrator("LoadControl", 1.0)
    ops.analysis("Static")
    ops.analyze(1)
    ops.reactions()
    rx = ops.nodeReaction(1)[0] + ops.nodeReaction(2)[0]
    r1, r2 = ops.nodeReaction(1)[1], ops.nodeReaction(2)[1]
    assert abs(rx) < 1e-7                               # beban vertikal murni
    assert abs(r2 + P * xl) < 1e-7 and abs(r1 + P * (1 - xl)) < 1e-7


def _kasus_kel_kedua():
    """Tiga bentang; respons Mx di satu kunci: KEL paling negatif di bentang
    1 (-30) dan bentang 2 (-20), bentang 3 (-5)."""
    kasus = {"D1": {"jenis": "D1"},
             "BTR|b1": {"jenis": "BTR", "offset": 0.0, "bentang": 1},
             "KEL|b1a": {"jenis": "KEL", "offset": 0.0, "bentang": 1},
             "KEL|b1b": {"jenis": "KEL", "offset": 0.0, "bentang": 1},
             "KEL|b2": {"jenis": "KEL", "offset": 0.0, "bentang": 2},
             "KEL|b3": {"jenis": "KEL", "offset": 0.0, "bentang": 3}}
    nilai = {"D1": 0.0, "BTR|b1": -10.0, "KEL|b1a": -30.0, "KEL|b1b": -12.0,
             "KEL|b2": -20.0, "KEL|b3": 5.0}
    total = {n: {"Mx": {"k": v}, "Vx": {"k": v}} for n, v in nilai.items()}
    return total, kasus


def test_kel_kedua_hanya_untuk_momen_negatif():
    total, kasus = _kasus_kel_kedua()
    sat = gaya_total.envelope_hidup_total(total, kasus, kel_kedua=False)
    dua = gaya_total.envelope_hidup_total(total, kasus, kel_kedua=True)
    assert sat["Mx"]["k"][0] == -10.0 - 30.0              # BTR + satu KEL
    assert dua["Mx"]["k"][0] == -10.0 - 30.0 - 20.0       # + KEL di bentang lain
    assert dua["Vx"]["k"] == sat["Vx"]["k"]               # geser: satu KEL
    assert dua["Mx"]["k"][1] == sat["Mx"]["k"][1]


def _ctx_kel(posisi):
    kasus = {"KEL|b|f=%.2f|o=+0.00" % f: {"jenis": "KEL", "offset": 0.0,
                                          "x": 20.0 * f} for f in posisi}
    return {"kasus": kasus, "bentang": [{"nama": "b", "x1": 0.0, "x2": 20.0,
                                         "L": 20.0}]}


def test_sc17_menandai_posisi_kel_terlalu_jarang():
    kecil = design_review.sc17_kel(_ctx_kel([0.5]),
                                   design_review.KONFIG_DEFAULT)
    rapat = design_review.sc17_kel(
        _ctx_kel([i / 10 for i in range(11)]), design_review.KONFIG_DEFAULT)
    assert kecil["status"] == "WARNING"
    assert rapat["status"] == "PASS"
