"""Verifikasi independen M, V, T total terhadap statika (butuh OpenSeesPy).

Gaya dalam total dari gaya_total dibandingkan dengan M, V, T yang dihitung
langsung dari beban luar dan reaksi bearing di sisi kiri penampang. Ini
menguji konvensi tanda eleForce, suku z*V pada torsi, dan pemetaan bearing.
"""
import math


def _statika(nama, x, u, sisi, kasus, ele, coords, st_unit, bc_list, hasil,
             cos_cut, sin_cut, elev):
    """M, V, T pada potongan di x (horizontal) dari gaya luar di kiri
    potongan (beban gravitasi, reaksi bearing Ry, Rx, Rz).

    V : komponen tegak lurus sumbu gelagar = cos_cut * sum(Fy)
    T : momen terhadap sumbu gelagar miring e = (cos, sin, 0):
        Fy di lateral z   -> -z*Fy*cos
        Rx di lateral z   -> +z*Rx*sin
        Rz di (x_F, y_F)  -> Rz*(cos*(y_F-y_c) - sin*(x_F-x_c))
    """
    V = M = T = 0.0
    for tag, q in kasus[nama]["ele"].items():
        e = ele[tag]
        if e["unit"] != u:
            continue
        dxl = max(0.0, min(x, e["x2"]) - e["x1"])      # bagian horizontal
        if dxl <= 0:
            continue
        F = q * dxl / e["cos_a"]                       # q per panjang sumbu
        V += F
        M += F * (x - (e["x1"] + dxl / 2))
        T += -e["z"] * F * cos_cut

    def kiri(xf):
        return xf <= x + 1e-7 if sisi == "i" else xf < x - 1e-7

    for tag, daftar in kasus[nama].get("pload", {}).items():
        e = ele[tag]
        if e["unit"] != u:
            continue
        for P, xl in daftar:                         # KEL di dalam elemen
            xp = e["x1"] + xl * (e["x2"] - e["x1"])
            if kiri(xp):
                V += P
                M += P * (x - xp)
                T += -e["z"] * P * cos_cut

    for n, fy in kasus[nama]["node"].items():
        xf, z = coords[n]
        if st_unit[n] == u and kiri(xf):
            V += fy
            M += fy * (x - xf)
            T += -z * fy * cos_cut
    y_c = elev(x)
    for b in bc_list:
        if b["unit"] == u and kiri(b["x"]):
            R = hasil[nama]["R"][b["node"]]
            V += R
            M += R * (x - b["x"])
            T += -b["z"] * R * cos_cut
            T += sin_cut * b["z"] * hasil[nama]["Rx"][b["node"]]
            T += hasil[nama]["Rz"][b["node"]] * (
                cos_cut * (elev(b["x"]) - y_c) - sin_cut * (b["x"] - x))
    return M, V * cos_cut, T


def test_gaya_total_sesuai_statika():
    try:
        import openseespy.opensees  # noqa: F401
    except ImportError:
        return
    from core import gaya_total, review
    from core.nodes import elevasi_model
    nr, er, bcl, bentang, kasus, hasil, L_E = review.bangun_dan_jalankan()
    total, seg_n = gaya_total.total_per_kasus(hasil, kasus, er)
    ele = {e["tag"]: e for e in er["memanjang"]}
    coords, st_unit = {}, {}
    for (i, j), t in nr["node_map"].items():
        coords[t] = (nr["stasiun"][i]["x"], nr["z_garis"][j])
        st_unit[t] = nr["stasiun"][i]["unit"]
    ele_seg = {(e["x1"], e["x2"], e["unit"]): (e["cos_a"], e["sin_a"])
               for e in er["memanjang"]}
    uji = ["D1", "D2"]
    uji += [n for n in kasus if n.startswith("BTR|P1-P2|o=+1.75")][:1]
    uji += [n for n in kasus if n.startswith("KEL|P6-P7|f=0.50|o=-1.75")][:1]
    uji += [n for n in kasus if n.startswith("KEL|P4-P5|f=0.30|o=+1.75")][:1]
    uji += [n for n in kasus if n.startswith("KEL|P7-P8|f=0.70|o=+0.00")][:1]
    uji += [n for n in kasus if n.startswith("BTR|P4-P5|o=+1.75")][:1]
    uji += [n for n in kasus if n.startswith("KEL|P4-P5|f=0.50|o=-1.75")][:1]
    for nama in uji:
        skala = {c: max(1.0, max(abs(v) for v in total[nama][c].values()))
                 for c in ("Mx", "Vx", "Tx")}
        for (x1, x2, u), n in seg_n.items():
            for k in range(n + 1):
                x = x1 + (x2 - x1) * k / n
                cos_cut, sin_cut = ele_seg[(x1, x2, u)]
                M, V, T = _statika(nama, x, u, "j" if k == n else "i", kasus,
                                   ele, coords, st_unit, bcl, hasil, cos_cut,
                                   sin_cut, elevasi_model)
                for c, v in (("Mx", M), ("Vx", V), ("Tx", T)):
                    err = abs(total[nama][c][(x1, x2, u, k)] - v) / skala[c]
                    assert err < 1e-6, (nama, c, x, err)
