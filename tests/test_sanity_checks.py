from core.sanity_checks import jalankan_pemeriksaan
from core.output import tambah_reaksi_bearing


def _fixture(residual=0.0):
    kasus = {"D1": {"ele": {1: -10.0}, "node": {}, "total": -10.0}}
    hasil = {"D1": {"R": {900001: 10.0 + residual},
                     "Uy": {1: -0.01}, "Mz_i": {1: 2.0}}}
    elemen = {"memanjang": [{"tag": 1, "x1": 0.0, "x2": 1.0}]}
    bc = [{"bearing": "B1", "node": 900001, "support": "A1",
           "x": 0.0, "z": -0.76, "unit": 0, "tipe": "MD"}]
    return hasil, kasus, elemen, bc


def test_sanity_pass_equilibrium_and_load_accounting():
    hasil, kasus, elemen, bc = _fixture()
    findings = jalankan_pemeriksaan(hasil, kasus, elemen, bc)
    by_id = {x["id"]: x for x in findings}
    assert by_id["SC-03"]["status"] == "PASS"
    assert by_id["SC-04"]["status"] == "PASS"
    assert by_id["SC-05"]["status"] == "NOT ASSESSED"


def test_sanity_flags_equilibrium_error():
    hasil, kasus, elemen, bc = _fixture(residual=2.0)
    findings = jalankan_pemeriksaan(hasil, kasus, elemen, bc)
    by_id = {x["id"]: x for x in findings}
    assert by_id["SC-04"]["status"] == "ERROR"


def test_add_reaction_per_physical_bearing():
    hasil, kasus, elemen, bc = _fixture()
    tambah_reaksi_bearing(hasil, bc)
    assert hasil["D1"]["Rbearing"] == {"B1": 10.0}
