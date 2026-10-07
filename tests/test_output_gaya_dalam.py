import csv

import csv

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
                "unit": "u0",
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
    }


def _env_envelope():
    return {
        "Mz_i": {tag: (tag, tag + 10) for tag in range(1, 6)},
        "Mz_j": {tag: (100 + tag, 110 + tag) for tag in range(1, 6)},
        "Vy_i": {tag: (1000 + tag, 1010 + tag) for tag in range(1, 6)},
        "Vy_j": {tag: (2000 + tag, 2010 + tag) for tag in range(1, 6)},
        "T_i": {tag: (3000 + tag, 3010 + tag) for tag in range(1, 6)},
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
    hasil = {
        "D1": _env_scalar(0.0),
        "D2": _env_scalar(100.0),
    }

    total, seg = hasil_total_segmen(
        hasil,
        _elemen_result(),
    )

    key = (0.0, 30.0, "u0")

    assert seg[key] == [1, 2, 3, 4, 5]

    assert total["D1"]["Mz_i"][key] == 15.0
    assert total["D1"]["Mz_j"][key] == 515.0
    assert total["D1"]["Vy_i"][key] == 5015.0
    assert total["D1"]["Vy_j"][key] == 10015.0
    assert total["D1"]["T_i"][key] == 15015.0

    assert total["D2"]["Mz_i"][key] == 515.0
    assert total["D2"]["Mz_j"][key] == 1015.0