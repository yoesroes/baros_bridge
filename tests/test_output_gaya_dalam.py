"""
Tes penyimpanan gaya dalam (core/output.py). Data sintetis, tanpa OpenSees.

Cakupan: simpan_gaya_dalam (CSV per garis) dan hasil_total_segmen
(penjumlahan 5 garis per segmen).
BELUM ada tes untuk: simpan_gaya_dalam_total, envelope_hidup,
kombinasi_envelope, tanda momen (sagging positif), maupun reaksi.
Jalankan dari root repo:  python -m pytest tests
"""

import csv

import pytest

from core import output
from core.output import (
    hasil_total_segmen,
    simpan_gaya_dalam,
    simpan_gaya_dalam_total,
)


def _elemen_result():
    return {
        "memanjang": [
            {
                "tag": tag,
                "garis": tag - 1,
                "z": z,
                "x1": 0.0,
                "x2": 30.0,
                "unit": 0,          # di model: indeks unit (int), bukan string
            }
            for tag, z in enumerate([-5.0, -3.5, 0.0, 3.5, 5.0], start=1)
        ]
    }


def _env_scalar(offset=0.0):
    return {
        "Mz_i": {tag: offset + tag for tag in range(1, 6)},
        "Mz_j": {tag: offset + 100 + tag for tag in range(1, 6)},
        "Vy_i": {tag: offset + 1000 + tag for tag in range(1, 6)},
        "Vy_j": {tag: offset + 2000 + tag for tag in range(1, 6)},
        "T_i": {tag: offset + 3000 + tag for tag in range(1, 6)},
        "T_j": {tag: offset + 3000 + tag for tag in range(1, 6)},
    }


def _env_envelope():
    return {
        "Mz_i": {tag: (tag, tag + 10) for tag in range(1, 6)},
        "Mz_j": {tag: (100 + tag, 110 + tag) for tag in range(1, 6)},
        "Vy_i": {tag: (1000 + tag, 1010 + tag) for tag in range(1, 6)},
        "Vy_j": {tag: (2000 + tag, 2010 + tag) for tag in range(1, 6)},
        "T_i": {tag: (3000 + tag, 3010 + tag) for tag in range(1, 6)},
        "T_j": {tag: (3000 + tag, 3010 + tag) for tag in range(1, 6)},
    }


def test_simpan_gaya_dalam_membuat_csv_per_garis(tmp_path):
    path = tmp_path / "gaya_dalam.csv"

    simpan_gaya_dalam(
        str(path),
        _elemen_result(),
        _env_envelope(),
    )

    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 5
    assert rows[0]["tag"] == "1"
    assert rows[0]["garis"] == "0"
    assert rows[0]["x1"] == "0.0"
    assert rows[0]["x2"] == "30.0"


def test_hasil_total_segmen_menjumlahkan_lima_garis():
    # Nilai sintetis: jumlah per kategori = jumlah tag 1..5 + offset.
    hasil = {
        "D1": _env_scalar(0.0),
        "D2": _env_scalar(100.0),
    }

    total, seg = hasil_total_segmen(
        hasil,
        _elemen_result(),
    )

    key = (0.0, 30.0, 0)

    assert seg[key] == [1, 2, 3, 4, 5]

    assert total["D1"]["Mz_i"][key] == 15.0
    assert total["D1"]["Mz_j"][key] == 515.0
    assert total["D1"]["Vy_i"][key] == 5015.0
    assert total["D1"]["Vy_j"][key] == 10015.0
    assert total["D1"]["T_i"][key] == 15015.0

    assert total["D2"]["Mz_i"][key] == 515.0
    assert total["D2"]["Mz_j"][key] == 1015.0


def test_service_iv_element_192_interior_moment_reference():
    from core import review
    from core.loads import KOMBINASI

    _, elemen_result, _, _, kasus, hasil, _ = review.bangun_dan_jalankan()
    tag = 192
    elemen = next(e for e in elemen_result["memanjang"] if e["tag"] == tag)
    factors = KOMBINASI["Service IV"]

    q = sum(factors.get(name, 0.0) * kasus[name]["ele"][tag]
            for name in ("D1", "D2"))
    wy = q * elemen["cos_a"]
    vy_i = sum(factors.get(name, 0.0) * hasil[name]["Vy_i"][tag]
               for name in ("D1", "D2"))
    mz_i = sum(factors.get(name, 0.0) * hasil[name]["Mz_i"][tag]
               for name in ("D1", "D2"))
    mz_j = sum(factors.get(name, 0.0) * hasil[name]["Mz_j"][tag]
               for name in ("D1", "D2"))

    length = elemen["L_aksial"]
    m_i_sagging_positive = -mz_i
    peak_s = -vy_i / wy
    peak_moment = (m_i_sagging_positive + vy_i * peak_s
                   + 0.5 * wy * peak_s**2)
    m_j_from_equilibrium = (
        m_i_sagging_positive + vy_i * length + 0.5 * wy * length**2
    )

    # q: kN/m; L, s: m; M: kN.m. Tolerances are absolute and independent
    # of display rounding in the audit report.
    assert peak_s == pytest.approx(4.275037593984, abs=1.0e-9)
    assert peak_moment == pytest.approx(150.572028060731, abs=1.0e-8)
    assert m_i_sagging_positive == pytest.approx(8.832619694492, abs=1.0e-9)
    assert mz_j == pytest.approx(-5.237267339575, abs=1.0e-9)
    assert m_j_from_equilibrium == pytest.approx(mz_j, abs=1.0e-8)

    minimum, maximum = output._moment_envelope_extrema(
        hasil, kasus, elemen, "Service IV")
    assert minimum[0] == pytest.approx(-5.237267339575, abs=1.0e-8)
    assert maximum[0] == pytest.approx(150.572028060731, abs=1.0e-8)
    assert maximum[1] == pytest.approx(4.275037593984, abs=1.0e-9)
    plot_positions = output._moment_envelope_plot_positions(
        hasil, kasus, elemen, "Service IV")
    assert any(position == pytest.approx(maximum[1], abs=1.0e-9)
               for position in plot_positions)
    _, plot_peak = output._moment_envelope_at(
        hasil, kasus, elemen, "Service IV", maximum[1])
    assert plot_peak == pytest.approx(maximum[0], abs=1.0e-8)


def test_strength_moment_extrema_match_positionwise_envelope_scan():
    from core import review

    _, elemen_result, _, _, kasus, hasil, _ = review.bangun_dan_jalankan()
    elemen = next(e for e in elemen_result["memanjang"] if e["tag"] == 192)
    length = elemen["L_aksial"]
    minimum, maximum = output._moment_envelope_extrema(
        hasil, kasus, elemen, "Strength I")
    samples = [output._moment_envelope_at(
        hasil, kasus, elemen, "Strength I", length * index / 4000)
        for index in range(4001)]
    scanned_min = min(value[0] for value in samples)
    scanned_max = max(value[1] for value in samples)

    assert minimum[0] <= scanned_min + 2.0e-4
    assert maximum[0] >= scanned_max - 2.0e-4
    assert maximum[0] - scanned_max < 2.0e-4
    assert scanned_min - minimum[0] < 2.0e-4


def test_plot_groups_do_not_join_elements_across_expansion_units():
    elements = [
        {"tag": 1, "garis": 0, "unit": 0, "x1": 0.0, "x2": 10.0},
        {"tag": 2, "garis": 0, "unit": 1, "x1": 10.0, "x2": 20.0},
    ]

    groups = output._kelompok_elemen_plot(elements)

    assert list(groups) == [(0, 0), (0, 1)]
    assert [[e["tag"] for e in group] for group in groups.values()] == [[1], [2]]
