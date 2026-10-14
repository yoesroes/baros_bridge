"""Cross-check segment-start forces between output and gaya_total.

At the i end, gaya_total defines Mx=-sum(Mz_i) and Vx=sum(Vy_i).
The j end is deliberately excluded: gaya_total evaluates it from i-end
forces plus distributed-load equilibrium, while output reports j-end
section forces. A direct comparison needs an independently established
load/sign convention and is not inferred here.
"""

import pytest


def test_gaya_total_di_ujung_i_sama_dengan_jumlah_gaya_output():
    pytest.importorskip("openseespy.opensees")
    from core import gaya_total, output, review

    _, elemen_result, _, _, kasus, hasil, _ = review.bangun_dan_jalankan()
    total, seg_n = gaya_total.total_per_kasus(hasil, kasus, elemen_result)

    # Include dead-load cases and representative distributed BTR/KEL cases.
    kasus_uji = [nama for nama in ("D1", "D2") if nama in hasil]
    kasus_uji += [
        nama for nama in kasus
        if nama.startswith("BTR|") or nama.startswith("KEL|")
    ][:2]
    assert kasus_uji

    segmen = gaya_total.segmen_garis(elemen_result)
    for nama in kasus_uji:
        for key, eles in segmen.items():
            x1, x2, unit = key
            start_key = (x1, x2, unit, 0)
            n = seg_n[key]
            assert n >= 1

            # output's per-element endpoint forces, aggregated across all
            # longitudinal lines in this segment.
            output_mx_i = -sum(hasil[nama]["Mz_i"][e["tag"]] for e in eles)
            output_vx_i = sum(hasil[nama]["Vy_i"][e["tag"]] for e in eles)

            assert total[nama]["Mx"][start_key] == pytest.approx(
                output_mx_i, rel=1e-10, abs=1e-8
            ), (nama, key, "Mx at i end")
            assert total[nama]["Vx"][start_key] == pytest.approx(
                output_vx_i, rel=1e-10, abs=1e-8
            ), (nama, key, "Vx at i end")

            # Ensure the sampled segment actually has a distinct far endpoint.
            end_key = (x1, x2, unit, n)
            assert end_key in total[nama]["Mx"]
            assert end_key in total[nama]["Vx"]

    # Guard against accidentally changing the documented endpoint convention.
    assert "Mz_i" in output.KATEGORI_GAYA
