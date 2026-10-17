"""Tes unit untuk gaya_total, beban ekuivalen nodal, dan design_review.

Tes memakai data sintetis kecil (tanpa menjalankan OpenSees). Jalankan:
    python -m pytest tests/test_design_review.py
"""
import types

from core import design_review, gaya_total, visualisasi


def _balok_sederhana(z=1.0):
    """Satu balok L = 10 m, w = -10 kN/m, tumpuan sederhana (R = 50)."""
    elemen = {"memanjang": [{"tag": 1, "n1": 1, "n2": 2, "x1": 0.0,
                             "x2": 10.0, "unit": 0, "z": z}]}
    kasus = {"D1": {"jenis": "D1", "bentang": None, "offset": None, "f": None,
                    "ele": {1: -10.0}, "node": {}, "total": -100.0}}
    hasil = {"D1": {"Mz_i": {1: 0.0}, "Mz_j": {1: 0.0}, "Vy_i": {1: 50.0},
                    "Vy_j": {1: 50.0}, "T_i": {1: 0.0}, "T_j": {1: 0.0}}}
    return hasil, kasus, elemen


def test_gaya_total_momen_geser_balok_sederhana():
    hasil, kasus, elemen = _balok_sederhana()
    total, seg_n = gaya_total.total_per_kasus(hasil, kasus, elemen, ds=1.0)
    n = seg_n[(0.0, 10.0, 0)]
    mid = total["D1"]["Mx"][(0.0, 10.0, 0, n // 2)]
    assert abs(mid - 125.0) < 1e-9                 # wL^2/8 di tengah bentang
    assert abs(total["D1"]["Mx"][(0.0, 10.0, 0, n)]) < 1e-9
    assert abs(total["D1"]["Vx"][(0.0, 10.0, 0, 0)] - 50.0) < 1e-9
    assert abs(total["D1"]["Vx"][(0.0, 10.0, 0, n)] + 50.0) < 1e-9


def test_gaya_total_torsi_dari_geser_eksentrik():
    hasil, kasus, elemen = _balok_sederhana(z=2.0)
    total, seg_n = gaya_total.total_per_kasus(hasil, kasus, elemen, ds=1.0)
    n = seg_n[(0.0, 10.0, 0)]
    # T = T_i - z*V ; V(0) = 50 -> -100 ; V(L) = -50 -> +100
    assert abs(total["D1"]["Tx"][(0.0, 10.0, 0, 0)] + 100.0) < 1e-9
    assert abs(total["D1"]["Tx"][(0.0, 10.0, 0, n)] - 100.0) < 1e-9


def test_beban_ekuivalen_nodal_konsisten():
    elemen = {"memanjang": [{"tag": 1, "n1": 1, "n2": 2, "x1": 0.0,
                             "x2": 4.0, "unit": 0, "z": 0.0}]}
    kasus = {"K": {"ele": {1: -10.0}, "node": {2: -5.0}, "total": -45.0}}
    eq = visualisasi.beban_ekuivalen_nodal(kasus, elemen)["K"]
    assert abs(eq[1]["Fy"] + 20.0) < 1e-12
    assert abs(eq[2]["Fy"] + 25.0) < 1e-12          # -20 dari elemen -5 titik
    assert abs(sum(v["Fy"] for v in eq.values()) + 45.0) < 1e-12
    assert abs(eq[1]["Mz"] - (-10.0 * 16 / 12)) < 1e-12
    assert abs(eq[2]["Mz"] + (-10.0 * 16 / 12)) < 1e-12


def _ctx_bearing(capacity):
    pdata = types.SimpleNamespace(KAPASITAS_BEARING=capacity)
    tabel = [{"bearing": "B11", "support": "P4", "unit": 1, "tipe": "MD",
              "z": -0.47, "D1": 3000.0, "D2": 400.0, "layan_min": 3200.0,
              "layan_max": 6400.0, "uls_min": 3500.0, "uls_max": 8800.0,
              "R_min_semua": 3200.0, "bagian_permanen": 0.5}]
    return {"pdata": pdata, "tabel_bearing": tabel}


def test_dc01_tanpa_kapasitas_tidak_menyatakan_overload():
    t = design_review.dc01_kapasitas(_ctx_bearing({}),
                                     design_review.KONFIG_DEFAULT)
    assert t["status"] == "NOT ASSESSED"
    rekom, kurang = design_review.buat_rekomendasi([t])
    assert rekom == [] and kurang[0]["id"] == "DC-01"
    assert "overload" not in (t["detail"] + t["nama"]).lower().replace(
        "tidak ada pernyataan overload", "")


def test_dc01_kapasitas_terlampaui():
    cap = {"B11": {"R_uls_kN": 8000.0, "R_sls_kN": 7000.0,
                   "standar": "uji"}}
    t = design_review.dc01_kapasitas(_ctx_bearing(cap),
                                     design_review.KONFIG_DEFAULT)
    assert t["status"] == "CAPACITY EXCEEDANCE"
    assert abs(t["nilai"] - 8800.0 / 8000.0) < 1e-12


def test_dc01_kapasitas_cukup():
    cap = {"B11": {"R_uls_kN": 12000.0, "R_sls_kN": 9000.0}}
    t = design_review.dc01_kapasitas(_ctx_bearing(cap),
                                     design_review.KONFIG_DEFAULT)
    assert t["status"] == "PASS"


def test_urutan_rekomendasi():
    f = lambda i, s: {"id": i, "nama": i, "status": s, "kriteria": "-",
                      "detail": "-", "lokasi": ""}
    rekom, _ = design_review.buat_rekomendasi([
        f("SC-10", "WARNING"), f("SC-04", "ERROR"),
        f("DC-01", "CAPACITY EXCEEDANCE"), f("SC-01", "PASS")])
    assert [r["status"] for r in rekom] == [
        "ERROR", "CAPACITY EXCEEDANCE", "WARNING"]


def _ctx_sc13(z_garis, faktor_d2=1.0):
    from core import loads
    from project import project_data as pdata
    L = sum(b - a for a, b, _ in pdata.SECTION_MAP)
    d1 = sum(loads.GAMMA_BETON_BOX * pdata.BOX_SECTIONS[t]["A"] * (b - a)
             for a, b, t in pdata.SECTION_MAP)
    d2 = loads.hitung_w_non_struktur() * L * faktor_d2
    return {"loads": loads, "pdata": pdata,
            "kasus": {"D1": {"total": -d1}, "D2": {"total": -d2}},
            "node_result": {"z_garis": z_garis}}


def test_sc13_lebar_jalan_tidak_bergantung_posisi_node():
    """loads.batas_tributari harus menutup seluruh lebar deck (+/-B/2)."""
    for z in ((-4.343, -2.182, 0.0, 2.182, 4.343),
              (-4.604, -2.668, 0.0, 2.668, 4.604)):
        t = design_review.sc13_beban(_ctx_sc13(z),
                                     design_review.KONFIG_DEFAULT)
        assert t["status"] == "PASS", (z, t["detail"])


def test_sc13_mendeteksi_d2_yang_hilang():
    t = design_review.sc13_beban(
        _ctx_sc13((-4.343, -2.182, 0.0, 2.182, 4.343), faktor_d2=0.95),
        design_review.KONFIG_DEFAULT)
    assert t["status"] == "WARNING"
    assert "D2" in t["detail"]


# ---------------- SC-18, SC-19, SC-20 ----------------
def _pdata_salinan(**ubah):
    import copy
    import types
    from project import project_data as pdata
    d = {k: copy.deepcopy(v) for k, v in vars(pdata).items()
         if not k.startswith("__")}
    d.update(ubah)
    return types.SimpleNamespace(**d)


def test_sc18_data_referensi_konsisten_dan_mendeteksi_selisih():
    k = design_review.KONFIG_DEFAULT
    pd = _pdata_salinan()
    assert design_review.sc18_data_referensi({"pdata": pd}, k)["status"] == \
        "PASS"
    salah = list(pd.SPANS)
    n1, n2, L, kel = salah[0]
    salah[0] = (n1, n2, L, 0.661)                      # meter, bukan persen
    t = design_review.sc18_data_referensi(
        {"pdata": _pdata_salinan(SPANS=salah)}, k)
    assert t["status"] == "WARNING" and "A1-P1" in t["detail"]
    info = dict(pd.INFO)
    info["selisih_elevasi"] = 4.397                    # nama lama ambigu
    t = design_review.sc18_data_referensi(
        {"pdata": _pdata_salinan(INFO=info)}, k)
    assert t["status"] == "WARNING" and "ambigu" in t["detail"]


def test_sc19_diafragma_menandai_penempatan_tidak_seragam():
    k = design_review.KONFIG_DEFAULT
    t = design_review.sc19_diafragma({"pdata": _pdata_salinan()}, k)
    assert t["status"] == "WARNING"
    for nama in ("P3", "P8", "A2"):
        assert nama in t["lokasi"]
    sm = [(0.0, 10.0, "tumpuan"), (10.0, 20.0, "hollow")]
    pd = _pdata_salinan(SECTION_MAP=sm, SUPPORTS={
        "A1": {"x": 5.0, "y": 0.0, "type": "pier"}})
    assert design_review.sc19_diafragma({"pdata": pd}, k)["status"] == "PASS"


def test_sc20_dasar_faktor():
    from core import loads
    k = design_review.KONFIG_DEFAULT
    ctx = {"pdata": _pdata_salinan(), "loads": loads}
    assert design_review.sc20_dasar_faktor(ctx, k)["status"] == "NOT ASSESSED"
    cocok = _pdata_salinan(
        DASAR_REGULASI="uji",
        KOMBINASI_REFERENSI={"Strength I": {"D1": 1.2, "D2": 2.0, "L": 1.8}})
    assert design_review.sc20_dasar_faktor(
        {"pdata": cocok, "loads": loads}, k)["status"] == "PASS"
    beda = _pdata_salinan(
        DASAR_REGULASI="uji",
        KOMBINASI_REFERENSI={"Strength I": {"D1": 1.25, "D2": 1.5,
                                            "L": 1.75}})
    t = design_review.sc20_dasar_faktor({"pdata": beda, "loads": loads}, k)
    assert t["status"] == "WARNING" and "Strength I D1" in t["detail"]
