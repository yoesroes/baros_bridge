# core/design_review.py
"""
Pemeriksaan kewajaran hasil analisis deck dan rekomendasi desain.

Mengikuti rencana "Baros Bridge - Automated Sanity Checks and Design
Recommendation Framework". Modul ini TIDAK mengubah model OpenSees dan
TIDAK menyatakan kapasitas tanpa data kapasitas terverifikasi.

Status temuan
-------------
ERROR                analisis/data tidak valid; jangan keluarkan kesimpulan
                     desain tanpa catatan.
CAPACITY EXCEEDANCE  demand > kapasitas TERVERIFIKASI (hanya bila diberikan).
WARNING              perlu tinjauan engineer (ambang screening terlampaui).
NOT ASSESSED         data/ambang pembanding belum tersedia.
PASS                 pemeriksaan terdefinisi terpenuhi (bukan jaminan semua
                     mode kegagalan terperiksa).

Daftar pemeriksaan (ID kontinu dengan core/sanity_checks.py)
-------------------------------------------------------------
SC-01..SC-06  dari core/sanity_checks.py (SC-05 diganti: lendutan per bentang)
SC-07  keseimbangan momen global (terhadap sumbu x dan z)
SC-08  pola momen (tanda di tumpuan menerus, letak puncak sagging)
SC-09  distribusi reaksi per bearing (uplift, ketimpangan beban permanen)
SC-10  konsentrasi reaksi (reaksi permanen per meter bentang tributari)
SC-11  kontinuitas momen dan keseimbangan geser pada stasiun
SC-12  sensitivitas konfigurasi garis (dari output/sensitivitas_strip.json)
SC-13  akuntansi beban independen (D1 dari luas, D2, lebar jalan terbebani)
SC-14  perbandingan model referensi (benchmark/reference_reaksi.csv)
SC-15  pembanding terhadap TABEL BEARING (beban rencana, bukan kapasitas)
SC-16  orientasi beban dan keseimbangan horizontal (gelagar miring)
DC-01  kapasitas bearing (butuh KAPASITAS_BEARING)
DC-02  uplift / reaksi negatif
DC-03..DC-06  lentur, geser, torsi, tegangan lokal (ringkasan demand)
"""

import csv
import json
import math
import os
import statistics

from core import gaya_total, output, sanity_checks

STATUS = ("ERROR", "CAPACITY EXCEEDANCE", "WARNING", "NOT ASSESSED", "PASS")

KONFIG_DEFAULT = {
    "batas_lendutan_rasio": None,
    "tol_keseimbangan": 0.01,
    "tol_kontinuitas": 0.01,
    "ambang_beban_per_m": 1.5,
    "ambang_bearing_tabel": 1.05,
    "ambang_bearing_rendah": 0.70,
    "ambang_ketimpangan_permanen": 0.05,
    "tol_sensitivitas": 0.05,
    "tol_referensi": None,
    "tol_beban_d1": 0.02,
    "tol_lebar_jalan": 0.005,
    "kombinasi_desain": ("Strength I", "Strength II", "Strength III",
                         "Strength IV", "Strength V"),
    "kombinasi_layan": "Service I",
}


def _t(id_, nama, status, nilai, kriteria, detail, lokasi="", bukti=None):
    return {"id": id_, "nama": nama, "status": status, "nilai": nilai,
            "kriteria": kriteria, "detail": detail, "lokasi": lokasi,
            "bukti": bukti or []}


def _grup_bearing(bc_list):
    g = {}
    for b in bc_list:
        g.setdefault((b["support"], b["unit"]), []).append(b)
    return g


def _nama_grup(support, unit, grup):
    sup_unit = {u for (s, u) in grup if s == support}
    return "{}[u{}]".format(support, unit) if len(sup_unit) > 1 else support


def _rentang_unit(node_result):
    r = {}
    for s in node_result["stasiun"]:
        a, b = r.get(s["unit"], (s["x"], s["x"]))
        r[s["unit"]] = (min(a, s["x"]), max(b, s["x"]))
    return r


# ------------------------------------------------------------------
# SC-05 lendutan beban hidup per bentang
# ------------------------------------------------------------------
def sc05_lendutan(ctx, k):
    ratio = k["batas_lendutan_rasio"]
    Lenv = ctx["Lenv"]
    coords = ctx["coords"]
    node_result = ctx["node_result"]
    grid = set(node_result["node_map"].values())
    baris = []
    for b in ctx["bentang"]:
        dmax, nmax = 0.0, None
        for n in grid:
            x = coords[n][0]
            if b["x1"] - 1e-6 <= x <= b["x2"] + 1e-6:
                lo, hi = Lenv["Uy"][n]
                d = max(abs(lo), abs(hi))
                if d > dmax:
                    dmax, nmax = d, n
        baris.append({"bentang": b["nama"], "L": b["L"],
                      "delta_mm": dmax * 1000.0,
                      "L_per_delta": (b["L"] / dmax) if dmax > 0 else math.inf,
                      "node": nmax})
    ctx["tabel_lendutan"] = baris
    terburuk = min(baris, key=lambda r: r["L_per_delta"])
    detail = ("Lendutan beban hidup (BTR+KEL, envelope) terbesar: {:.1f} mm "
              "pada bentang {} (L = {:.2f} m, L/delta = {:.0f}). "
              .format(terburuk["delta_mm"], terburuk["bentang"],
                      terburuk["L"], terburuk["L_per_delta"]))
    if ratio is None:
        return _t("SC-05", "Lendutan beban hidup per bentang", "NOT ASSESSED",
                  round(terburuk["L_per_delta"]),
                  "Memerlukan batas lendutan yang ditetapkan proyek",
                  detail + "Tidak ada batas yang dikonfigurasi.",
                  lokasi=terburuk["bentang"])
    gagal = [r for r in baris if r["L_per_delta"] < ratio]
    status = "PASS" if not gagal else "WARNING"
    ket = ("Semua bentang memenuhi L/delta >= {:.0f}.".format(ratio)
           if not gagal else
           "Bentang melebihi L/{:.0f}: {}.".format(
               ratio, ", ".join(r["bentang"] for r in gagal)))
    return _t("SC-05", "Lendutan beban hidup per bentang", status,
              round(terburuk["L_per_delta"]),
              "L/delta >= {:.0f} (ambang SCREENING konfigurasi proyek; bukan "
              "kriteria kode otomatis)".format(ratio),
              detail + ket, lokasi=terburuk["bentang"],
              bukti=[{"bentang": r["bentang"], "L_m": r["L"],
                      "delta_mm": round(r["delta_mm"], 2),
                      "L_per_delta": round(r["L_per_delta"])}
                     for r in baris])


# ------------------------------------------------------------------
# SC-07 keseimbangan momen global
# ------------------------------------------------------------------
def sc07_momen(ctx, k):
    """
    Keseimbangan momen global. Beban gravitasi vertikal: momen terhadap
    sumbu z = sum(x*Fy - y*Fx), terhadap sumbu x = sum(y*Fz - z*Fy); Fx dan
    Fz hanya berasal dari reaksi horizontal (bila direkam), y = elevasi node.
    """
    ele = {e["tag"]: e for e in ctx["elemen_result"]["memanjang"]}
    coords, bc = ctx["coords"], ctx["bc_list"]
    L_ref = max(c[0] for c in coords.values()) - min(
        c[0] for c in coords.values())
    B_ref = 10.0
    terburuk = (0.0, "", 0.0)
    for nama, kas in ctx["kasus"].items():
        F = []                                 # (Fy, x, z)
        for tag, q in kas.get("ele", {}).items():
            e = ele[tag]
            L = e.get("L_aksial", e["x2"] - e["x1"])
            F.append((q * L, (e["x1"] + e["x2"]) / 2.0, e["z"]))
        for n, fy in kas.get("node", {}).items():
            F.append((fy, coords[n][0], coords[n][2]))
        h = ctx["hasil"][nama]
        R = h["R"]
        for b in bc:
            F.append((R[b["node"]], coords[b["node"]][0],
                      coords[b["node"]][2]))
        sF = sum(abs(f[0]) for f in F) or 1.0
        m_z = sum(f[0] * f[1] for f in F)
        m_x = sum(f[0] * f[2] for f in F)
        if "Rx" in h:
            m_z -= sum(coords[b["node"]][1] * h["Rx"][b["node"]] for b in bc)
            m_x += sum(coords[b["node"]][1] * h["Rz"][b["node"]] for b in bc)
        rz = abs(m_z) / (sF * L_ref)
        rx = abs(m_x) / (sF * B_ref)
        for nilai, jenis in ((rz, "momen terhadap sumbu z (x*Fy - y*Fx)"),
                             (rx, "momen terhadap sumbu x (y*Fz - z*Fy)")):
            if nilai > terburuk[0]:
                terburuk = (nilai, nama, jenis)
    tol = k["tol_keseimbangan"]
    ok = terburuk[0] <= tol
    return _t("SC-07", "Keseimbangan momen global", "PASS" if ok else "ERROR",
              terburuk[0],
              "|jumlah momen| / (sum|Fy| x lengan acuan) <= {:.2%}"
              .format(tol),
              "Residual relatif terbesar {:.3e} pada kasus {} ({}). Beban "
              "elemen, beban nodal, dan reaksi bearing diperiksa terhadap "
              "sumbu x dan z.".format(terburuk[0], terburuk[1], terburuk[2]),
              lokasi=terburuk[1])


# ------------------------------------------------------------------
# SC-08 pola momen
# ------------------------------------------------------------------
def sc08_pola_momen(ctx, k):
    seg_n = ctx["seg_n"]
    gab = ctx["env_desain"]
    total_D1 = ctx["total"]["D1"]["Mx"]
    ekstrem = ctx["ekstrem"]
    grup = _grup_bearing(ctx["bc_list"])
    sup_unit = {}
    for (s, u), bs in grup.items():
        sup_unit.setdefault(u, []).append((bs[0]["x"], s))
    catatan, bukti, masalah = [], [], []
    for u in sorted(sup_unit):
        sup = sorted(sup_unit[u])
        interior = sup[1:-1]
        # momen D1 di tumpuan menerus harus negatif (hogging)
        for x, s in interior:
            vals = [total_D1[(x1, x2, uu, kk)]
                    for (x1, x2, uu), n in seg_n.items() if uu == u
                    for kk in (0, n)
                    if abs(x1 + (x2 - x1) * kk / n - x) < 1e-6]
            m_d1 = min(vals) if vals else float("nan")
            lo_des = min(gab["Mx"][(x1, x2, uu, kk)][0]
                         for (x1, x2, uu), n in seg_n.items() if uu == u
                         for kk in (0, n)
                         if abs(x1 + (x2 - x1) * kk / n - x) < 1e-6)
            bukti.append({"unit": u, "tumpuan": s, "x": x,
                          "M_D1_kNm": round(m_d1, 1),
                          "M_desain_min_kNm": round(lo_des, 1)})
            if m_d1 >= 0:
                masalah.append("unit {} tumpuan {}: M(D1) = {:.0f} kN.m "
                               "(>= 0) pada tumpuan menerus".format(
                                   u, s, m_d1))
        r = ekstrem[u]
        mp, xp, _ = r["M_pos"]
        mn, xn, _ = r["M_neg"]
        rasio = abs(mn) / mp if mp > 0 else float("inf")
        catatan.append("unit {}: M+ = {:.0f} kN.m (x = {:.1f} m), M- = {:.0f}"
                       " kN.m (x = {:.1f} m), |M-|/M+ = {:.2f}"
                       .format(u, mp, xp, mn, xn, rasio))
        for (xa, na), (xb, nb) in zip(sup[:-1], sup[1:]):
            if xa - 1e-6 <= xp <= xb + 1e-6:
                f = (xp - xa) / (xb - xa)
                if f < 0.05 or f > 0.95:
                    masalah.append("unit {}: puncak sagging di dekat tumpuan "
                                   "(x = {:.1f} m, bentang {}-{})"
                                   .format(u, xp, na, nb))
    status = "PASS" if not masalah else "WARNING"
    detail = ("Pola konsisten dengan tumpuan menerus. " if not masalah else
              "Pola tidak lazim: " + "; ".join(masalah) + ". ") + \
        "Rasio |M-|/M+ hanya informasi, bukan kriteria. " + " | ".join(catatan)
    return _t("SC-08", "Pola momen total", status, None,
              "M(D1) negatif di tumpuan menerus; puncak sagging di dalam "
              "bentang (bukan di tumpuan)", detail, bukti=bukti)


# ------------------------------------------------------------------
# SC-09 / DC-02 distribusi reaksi
# ------------------------------------------------------------------
def tabel_reaksi_bearing(ctx, k):
    """Reaksi per bearing (kN): D1, D2, Service I dan Strength I min/max."""
    hasil, Lenv = ctx["hasil"], ctx["Lenv"]
    lay = output.kombinasi_envelope(hasil, Lenv, k["kombinasi_layan"])
    uls = {c: output.kombinasi_envelope(hasil, Lenv, c)
           for c in k["kombinasi_desain"]}
    semua = {c: output.kombinasi_envelope(hasil, Lenv, c)["Rbearing"]
             for c in ctx["kombinasi_semua"]}
    baris = []
    grup = _grup_bearing(ctx["bc_list"])
    jum = {}
    for (s, u), bs in grup.items():
        for b in bs:
            jum[b["bearing"]] = sum(
                hasil["D1"]["Rbearing"][x["bearing"]]
                + hasil["D2"]["Rbearing"][x["bearing"]] for x in bs)
    for b in sorted(ctx["bc_list"], key=lambda b: int(b["bearing"][1:])):
        bid = b["bearing"]
        uls_max = max(uls[c]["Rbearing"][bid][1] for c in uls)
        uls_min = min(uls[c]["Rbearing"][bid][0] for c in uls)
        r_all_min = min(v[bid][0] for v in semua.values())
        D = hasil["D1"]["Rbearing"][bid] + hasil["D2"]["Rbearing"][bid]
        baris.append({
            "bearing": bid, "support": b["support"], "unit": b["unit"],
            "tipe": b["tipe"], "z": b["z"],
            "D1": hasil["D1"]["Rbearing"][bid],
            "D2": hasil["D2"]["Rbearing"][bid],
            "layan_min": lay["Rbearing"][bid][0],
            "layan_max": lay["Rbearing"][bid][1],
            "uls_min": uls_min, "uls_max": uls_max,
            "R_min_semua": r_all_min,
            "bagian_permanen": D / jum[bid] if jum[bid] else float("nan"),
        })
    ctx["tabel_bearing"] = baris
    return baris


def sc09_distribusi(ctx, k):
    baris = ctx["tabel_bearing"]
    uplift = [r for r in baris if r["R_min_semua"] < -1e-6]
    grup = {}
    for r in baris:
        grup.setdefault((r["support"], r["unit"]), []).append(r)
    timpang = []
    for key, rs in grup.items():
        if len(rs) == 2:
            a = rs[0]["D1"] + rs[0]["D2"]
            b = rs[1]["D1"] + rs[1]["D2"]
            kt = abs(a - b) / max(1e-9, abs(a + b))
            if kt > k["ambang_ketimpangan_permanen"]:
                timpang.append("{}: {:.1%}".format(
                    _nama_grup(key[0], key[1], grup), kt))
    masalah = []
    if uplift:
        masalah.append("reaksi negatif (uplift) pada {}".format(
            ", ".join(r["bearing"] for r in uplift)))
    if timpang:
        masalah.append("ketimpangan beban permanen > {:.0%}: {}".format(
            k["ambang_ketimpangan_permanen"], "; ".join(timpang)))
    status = "PASS" if not masalah else "WARNING"
    maks = max(baris, key=lambda r: r["layan_max"])
    detail = ("Reaksi per bearing tersedia untuk {} bearing; reaksi layan "
              "terbesar {:.0f} kN pada {} ({}). ".format(
                  len(baris), maks["layan_max"], maks["bearing"],
                  maks["support"]))
    detail += ("Tidak ada uplift dan beban permanen simetris."
               if not masalah else "; ".join(masalah) + ".")
    return _t("SC-09", "Distribusi reaksi per bearing", status,
              len(uplift),
              "Tidak ada reaksi negatif pada kombinasi non-Extreme; beban "
              "permanen kiri-kanan seimbang (<= {:.0%})".format(
                  k["ambang_ketimpangan_permanen"]),
              detail, lokasi=", ".join(r["bearing"] for r in uplift))


def dc02_uplift(ctx, k):
    uplift = [r for r in ctx["tabel_bearing"] if r["R_min_semua"] < -1e-6]
    if not uplift:
        return _t("DC-02", "Uplift / reaksi negatif", "PASS", 0,
                  "Reaksi vertikal >= 0 pada semua kombinasi non-Extreme",
                  "Tidak ada bearing dengan reaksi negatif.")
    return _t("DC-02", "Uplift / reaksi negatif", "WARNING", len(uplift),
              "Reaksi negatif ditandai untuk tinjauan, bukan otomatis "
              "kegagalan",
              "Reaksi negatif pada: " + ", ".join(
                  "{} ({:.0f} kN)".format(r["bearing"], r["R_min_semua"])
                  for r in uplift),
              lokasi=", ".join(r["bearing"] for r in uplift))


# ------------------------------------------------------------------
# SC-10 konsentrasi reaksi
# ------------------------------------------------------------------
def sc10_konsentrasi(ctx, k):
    """
    Reaksi permanen (D1+D2) tiap tumpuan dibanding beban permanen rata-rata
    unit x panjang tributari. Pada gelagar menerus, tumpuan tengah dua
    bentang sama panjang secara teori bernilai sekitar 1.25; ambang default
    1.5 sengaja longgar agar hanya konsentrasi tidak lazim yang ditandai.
    """
    rent = _rentang_unit(ctx["node_result"])
    grup = _grup_bearing(ctx["bc_list"])
    ele = ctx["elemen_result"]["memanjang"]
    w_unit = {}
    for u, (a, b) in rent.items():
        total = sum(abs(ctx["kasus"][c]["ele"].get(e["tag"], 0.0))
                    * (e["x2"] - e["x1"])
                    for c in ("D1", "D2") for e in ele if e["unit"] == u)
        w_unit[u] = total / (b - a)
    per_unit = {}
    for (s, u), bs in grup.items():
        per_unit.setdefault(u, []).append((bs[0]["x"], s, bs))
    nilai = {}
    for u, daftar in per_unit.items():
        daftar.sort()
        a, b = rent[u]
        for i, (x, s, bs) in enumerate(daftar):
            kiri = (x - daftar[i - 1][0]) / 2 if i > 0 else x - a
            kanan = (daftar[i + 1][0] - x) / 2 if i < len(daftar) - 1 \
                else b - x
            R = sum(ctx["hasil"]["D1"]["Rbearing"][t["bearing"]]
                    + ctx["hasil"]["D2"]["Rbearing"][t["bearing"]]
                    for t in bs)
            nilai[_nama_grup(s, u, grup)] = R / ((kiri + kanan) * w_unit[u])
    tinggi = {n: v for n, v in nilai.items()
              if v > k["ambang_beban_per_m"]}
    status = "PASS" if not tinggi else "WARNING"
    maks = max(nilai, key=nilai.get)
    detail = ("Reaksi permanen / (beban rata-rata unit x lebar tributari): "
              "terbesar {} = {:.2f}, terkecil {} = {:.2f}. "
              .format(maks, nilai[maks], min(nilai, key=nilai.get),
                      min(nilai.values())))
    if tinggi:
        detail += "Melebihi ambang: " + ", ".join(
            "{} ({:.2f})".format(n, v) for n, v in tinggi.items()) + "."
    return _t("SC-10", "Konsentrasi reaksi relatif terhadap beban tributari",
              status, round(nilai[maks], 3),
              "Reaksi permanen <= {:.2f} x (beban rata-rata unit x lebar "
              "tributari); tumpuan tengah dua bentang sama panjang "
              "secara teori sekitar 1.25".format(k["ambang_beban_per_m"]),
              detail, lokasi=", ".join(tinggi),
              bukti=[{"tumpuan": n, "rasio": round(v, 3)}
                     for n, v in sorted(nilai.items())])


# ------------------------------------------------------------------
# SC-11 kontinuitas momen dan keseimbangan geser
# ------------------------------------------------------------------
def sc11_kontinuitas(ctx, k):
    segs = gaya_total.segmen_garis(ctx["elemen_result"])
    ns = ctx["node_result"]
    st_of = {}
    for (i, j), tag in ns["node_map"].items():
        st_of[tag] = (round(ns["stasiun"][i]["x"], 6), ns["stasiun"][i]["unit"])
    kiri, kanan = {}, {}
    for key in segs:
        x1, x2, u = key
        kanan[(round(x1, 6), u)] = key
        kiri[(round(x2, 6), u)] = key
    stasiun = sorted(set(kiri) | set(kanan), key=lambda s: (s[1], s[0]))
    R_st = {}
    for b in ctx["bc_list"]:
        R_st.setdefault((round(b["x"], 6), b["unit"]), []).append(b["node"])
    terburuk_m = (0.0, "", None)
    terburuk_v = (0.0, "", None)
    for nama, kas in ctx["kasus"].items():
        h = ctx["hasil"][nama]

        def jum(cat, key):
            return sum(h[cat][e["tag"]] for e in segs[key])

        def geo(key):
            e0 = segs[key][0]
            return e0.get("cos_a", 1.0), e0.get("sin_a", 0.0)

        def vert(key, ujung):
            """Gaya vertikal global pada ujung segmen = Vy cos a + N sin a."""
            c, sn = geo(key)
            n = jum("N_" + ujung, key) if "N_i" in h else 0.0
            return jum("Vy_" + ujung, key) * c + n * sn

        P_st = {}
        for n, fy in kas.get("node", {}).items():
            P_st[st_of[n]] = P_st.get(st_of[n], 0.0) + fy
        skala_m = max(1.0, max(abs(jum(c, key)) for key in segs
                               for c in ("Mz_i", "Mz_j")))
        skala_v = max(1.0, max(abs(vert(key, u)) for key in segs
                               for u in ("i", "j")))
        for st in stasiun:
            kl, kr = kiri.get(st), kanan.get(st)
            if kl and kr:
                m_kiri = jum("Mz_j", kl)
                m_kanan = -jum("Mz_i", kr)
                jm = abs(m_kanan - m_kiri) / skala_m
                if jm > terburuk_m[0]:
                    terburuk_m = (jm, nama, st)
            v_kiri = -vert(kl, "j") if kl else 0.0
            v_kanan = vert(kr, "i") if kr else 0.0
            aksi = sum(h["R"][n] for n in R_st.get(st, [])) + P_st.get(st, 0.0)
            jv = abs((v_kanan - v_kiri) - aksi) / skala_v
            if jv > terburuk_v[0]:
                terburuk_v = (jv, nama, st)
    tol = k["tol_kontinuitas"]
    nilai = max(terburuk_m[0], terburuk_v[0])
    if nilai <= tol:
        status = "PASS"
    elif nilai <= 10 * tol:
        status = "WARNING"
    else:
        status = "ERROR"
    return _t("SC-11", "Kontinuitas momen dan keseimbangan geser stasiun",
              status, nilai,
              "Loncatan momen total = 0 dan loncatan gaya vertikal (Vy cos a + "
              "N sin a) = reaksi + beban nodal pada stasiun (relatif <= "
              "{:.1%})".format(tol),
              "Selisih momen terbesar {:.2e} (kasus {}, stasiun {}); selisih "
              "geser terbesar {:.2e} (kasus {}, stasiun {}). Mencakup semua "
              "transisi hollow/solid/tumpuan dan stasiun EJ."
              .format(terburuk_m[0], terburuk_m[1], terburuk_m[2],
                      terburuk_v[0], terburuk_v[1], terburuk_v[2]),
              lokasi=str(terburuk_v[2] if terburuk_v[0] >= terburuk_m[0]
                         else terburuk_m[2]))


# ------------------------------------------------------------------
# SC-12 sensitivitas konfigurasi
# ------------------------------------------------------------------
def sc12_sensitivitas(ctx, k):
    path = os.path.join(ctx["out_dir"], "sensitivitas_strip.json")
    if not os.path.exists(path):
        return _t("SC-12", "Sensitivitas konfigurasi garis", "NOT ASSESSED",
                  None, "Memerlukan hasil beberapa konfigurasi garis",
                  "Jalankan tests/sensitivitas_strip.py untuk menghasilkan "
                  "output/sensitivitas_strip.json.")
    with open(path) as f:
        data = json.load(f)
    varian = "tepi deck" if "tepi deck" in data else next(iter(data))
    skema = data[varian]
    ref = "TUJUH" if "TUJUH" in skema else next(iter(skema))
    selisih = {}
    for nm, m in skema.items():
        if nm == ref:
            continue
        maks = 0.0
        for key, v in m.items():
            if key.startswith(("Rsup_max", "Rbrg_max", "M_tot")):
                r = skema[ref][key]
                pairs = ([(v[g], r[g]) for g in v] if isinstance(v, dict)
                         else [(v, r)])
                for a, b in pairs:
                    if abs(b) > 1e-9:
                        maks = max(maks, abs(a / b - 1))
        selisih[nm] = maks
    tol = k["tol_sensitivitas"]
    maks = max(selisih.values()) if selisih else 0.0
    status = "PASS" if maks <= tol else "WARNING"
    return _t("SC-12", "Sensitivitas konfigurasi garis", status, maks,
              "Selisih reaksi/momen total antar konfigurasi <= {:.0%} "
              "(ambang screening)".format(tol),
              "Varian beban '{}', acuan {}: ".format(varian, ref) + ", ".join(
                  "{} {:+.2%}".format(n, v) for n, v in selisih.items())
              + ". Sumber: " + os.path.basename(path) + ".",
              bukti=[{"konfigurasi": n, "selisih_maks": round(v, 4)}
                     for n, v in selisih.items()])


# ------------------------------------------------------------------
# SC-13 akuntansi beban independen
# ------------------------------------------------------------------
def _panjang_segmen(ctx):
    """[(tipe, dx, L_aksial)] per interval antar x section/tumpuan, dihitung
    langsung dari SECTION_MAP, SUPPORTS, dan alinyemen (tanpa elemen model)."""
    pdata = ctx["pdata"]
    elev = ctx.get("elevasi", lambda x: 0.0)
    xs = sorted({a for a, _, _ in pdata.SECTION_MAP}
                | {b for _, b, _ in pdata.SECTION_MAP}
                | {d["x"] for d in pdata.SUPPORTS.values()})
    out = []
    for xa, xb in zip(xs[:-1], xs[1:]):
        xm = (xa + xb) / 2.0
        tipe = next((t for a, b, t in pdata.SECTION_MAP if a <= xm <= b),
                    None)
        if tipe is None:
            continue
        dx = xb - xa
        out.append((tipe, dx, math.hypot(dx, elev(xb) - elev(xa))))
    return out


def sc13_beban(ctx, k):
    loads, pdata = ctx["loads"], ctx["pdata"]
    dasar = ctx.get("dasar_panjang") or {"D1": "aksial", "D2": "aksial"}
    temuan, bukti, status = [], [], "PASS"
    seg = _panjang_segmen(ctx)
    L_ax = sum(s[2] for s in seg)
    L_hor = sum(s[1] for s in seg)
    d1 = sum(loads.GAMMA_BETON_BOX * pdata.BOX_SECTIONS[t]["A"]
             * (la if dasar["D1"] == "aksial" else dx)
             for t, dx, la in seg)
    d1_model = -ctx["kasus"]["D1"]["total"]
    sel1 = abs(d1_model - d1) / d1
    bukti.append({"komponen": "D1 berat sendiri (dasar {})".format(
        dasar["D1"]), "model_kN": round(d1_model, 1),
        "independen_kN": round(d1, 1), "selisih": round(sel1, 5)})
    if sel1 > k["tol_beban_d1"]:
        status = "ERROR"
        temuan.append("D1 model {:.0f} kN vs luas x berat jenis x panjang "
                      "({}) {:.0f} kN ({:+.2%})".format(
                          d1_model, dasar["D1"], d1, d1_model / d1 - 1))
    d2 = loads.hitung_w_non_struktur() * (
        L_ax if dasar["D2"] == "aksial" else L_hor)
    d2_model = -ctx["kasus"]["D2"]["total"]
    sel2 = d2_model / d2 - 1
    bukti.append({"komponen": "D2 beban mati tambahan (dasar {})".format(
        dasar["D2"]), "model_kN": round(d2_model, 1),
        "independen_kN": round(d2, 1), "selisih": round(sel2, 5)})
    if abs(sel2) > k["tol_beban_d1"] / 2:
        status = "WARNING" if status == "PASS" else status
        temuan.append("D2 model {:.0f} kN vs {:.0f} kN ({:+.2%}): beban mati "
                      "tambahan berbeda dari yang diharapkan"
                      .format(d2_model, d2, sel2))
    z = ctx["node_result"]["z_garis"]
    lebar = sum(loads.lebar_jalan_per_garis(z))
    sel3 = lebar / loads.B_JALAN - 1
    bukti.append({"komponen": "lebar jalan terbebani (m)",
                  "model_kN": round(lebar, 3),
                  "independen_kN": loads.B_JALAN, "selisih": round(sel3, 5)})
    if abs(sel3) > k["tol_lebar_jalan"]:
        status = "WARNING" if status == "PASS" else status
        temuan.append(
            "lebar jalan yang masuk tributari garis hanya {:.3f} m dari {:.1f}"
            " m ({:+.1%}); periksa loads.batas_tributari (batas terluar "
            "harus sampai tepi deck)".format(lebar, loads.B_JALAN, sel3))
    detail = ("; ".join(temuan) + "." if temuan else
              "D1, D2, dan lebar jalan konsisten dengan perhitungan "
              "independen (panjang sumbu total {:.2f} m, proyeksi "
              "horizontal {:.2f} m).".format(L_ax, L_hor))
    return _t("SC-13", "Akuntansi beban independen", status,
              max(abs(sel1), abs(sel2), abs(sel3)),
              "D1 vs sum(gamma x A x L) <= {:.0%}; D2 dan lebar jalan vs "
              "nilai teoretis; dasar panjang D1/D2 = {}/{}".format(
                  k["tol_beban_d1"], dasar["D1"], dasar["D2"]), detail,
              bukti=bukti)


# ------------------------------------------------------------------
# SC-14 model referensi
# ------------------------------------------------------------------
def sc14_referensi(ctx, k):
    path = os.path.join(ctx["base_dir"], "benchmark", "reference_reaksi.csv")
    if not os.path.exists(path):
        return _t("SC-14", "Perbandingan model referensi (SAP2000/MIDAS)",
                  "NOT ASSESSED", None,
                  "Memerlukan ekspor model referensi dengan asumsi identik",
                  "Belum ada benchmark/reference_reaksi.csv. Format: kolom "
                  "bearing,kombinasi,R_kN (positif ke atas). Gunakan "
                  "template benchmark/reference_reaksi_template.csv.")
    env_c = {}
    baris = []
    with open(path) as f:
        for row in csv.DictReader(f):
            kom, bid = row["kombinasi"], row["bearing"]
            if kom not in env_c:
                env_c[kom] = output.kombinasi_envelope(
                    ctx["hasil"], ctx["Lenv"], kom)["Rbearing"]
            lo, hi = env_c[kom][bid]
            ref = float(row["R_kN"])
            model = hi if ref >= 0 else lo
            baris.append({"bearing": bid, "kombinasi": kom, "ref_kN": ref,
                          "model_kN": model,
                          "selisih_kN": model - ref,
                          "selisih_pct": 100 * (model / ref - 1) if ref
                          else float("nan")})
    maks = max(baris, key=lambda r: abs(r["selisih_pct"]))
    tol = k["tol_referensi"]
    if tol is None:
        status = "NOT ASSESSED"
        ket = "Pita penerimaan belum ditetapkan (tol_referensi)."
    else:
        status = "PASS" if abs(maks["selisih_pct"]) <= 100 * tol else "WARNING"
        ket = "Pita penerimaan {:.1%}.".format(tol)
    return _t("SC-14", "Perbandingan model referensi (SAP2000/MIDAS)", status,
              round(maks["selisih_pct"], 2),
              "Selisih reaksi per bearing vs model referensi dalam pita yang "
              "ditetapkan proyek",
              "Selisih terbesar {:+.2f}% pada {} ({}). {}".format(
                  maks["selisih_pct"], maks["bearing"], maks["kombinasi"],
                  ket), bukti=baris)


# ------------------------------------------------------------------
# SC-15 TABEL BEARING dan DC-01 kapasitas
# ------------------------------------------------------------------
def sc15_tabel(ctx, k):
    pdata = ctx["pdata"]
    tabel = getattr(pdata, "BEARING_TABEL", None)
    if not tabel:
        return _t("SC-15", "Pembanding terhadap tabel bearing", "NOT ASSESSED",
                  None, "Memerlukan BEARING_TABEL", "Data tabel tidak ada.")
    ton = getattr(pdata, "TON_KN", 9.80665)
    baris = []
    for r in ctx["tabel_bearing"]:
        t = tabel.get(r["bearing"])
        if not t:
            continue
        perm_m = r["D1"] + r["D2"]
        baris.append({
            "bearing": r["bearing"], "support": r["support"],
            "tipe_tabel": t["tipe"],
            "perm_tabel_kN": t["perm_t"] * ton, "perm_model_kN": perm_m,
            "rasio_perm": perm_m / (t["perm_t"] * ton),
            "sls_tabel_kN": t["sls_t"] * ton,
            "sls_model_kN": r["layan_max"],
            "rasio_sls": r["layan_max"] / (t["sls_t"] * ton),
        })
    ctx["tabel_vs_model"] = baris
    tinggi = [b for b in baris if b["rasio_sls"] > k["ambang_bearing_tabel"]]
    rendah = [b for b in baris if b["rasio_sls"] < k["ambang_bearing_rendah"]]
    maks = max(baris, key=lambda b: b["rasio_sls"])
    detail = ("Reaksi layan model (Service I) / beban SLS tabel: terbesar "
              "{:.2f} ({}, {}), {} dari {} bearing melebihi {:.2f}x tabel. "
              .format(maks["rasio_sls"], maks["bearing"], maks["support"],
                      len(tinggi), len(baris), k["ambang_bearing_tabel"]))
    if tinggi:
        detail += "Melebihi tabel: " + ", ".join(
            "{} ({:.2f}x)".format(b["bearing"], b["rasio_sls"])
            for b in tinggi) + ". "
    if rendah:
        detail += "{} bearing < {:.0%} tabel (model jauh lebih rendah). " \
            .format(len(rendah), k["ambang_bearing_rendah"])
    detail += ("Tabel adalah BEBAN RENCANA, bukan kapasitas; selisih tidak "
               "berarti bearing overload.")
    return _t("SC-15", "Pembanding terhadap tabel bearing (beban rencana)",
              "WARNING" if tinggi else "PASS",
              round(maks["rasio_sls"], 3),
              "Reaksi layan model <= {:.2f} x beban SLS tabel".format(
                  k["ambang_bearing_tabel"]), detail,
              lokasi=", ".join(b["bearing"] for b in tinggi), bukti=baris)


def sc16_orientasi(ctx, k):
    """
    Beban gravitasi harus vertikal global. Pada gelagar miring beban lokal-y
    yang tidak diuraikan menghasilkan komponen horizontal sehingga jumlah
    reaksi horizontal tiap unit tidak nol. Diperiksa dari reaksi Rx dan Rz.
    """
    hasil, bc = ctx["hasil"], ctx["bc_list"]
    if any("Rx" not in h for h in hasil.values()):
        return _t("SC-16", "Orientasi beban dan keseimbangan horizontal",
                  "NOT ASSESSED", None,
                  "analysis.jalankan_kasus harus merekam Rx dan Rz",
                  "Reaksi horizontal tidak tersedia pada hasil analisis.")
    ele = ctx["elemen_result"]["memanjang"]
    kemiringan = [abs(e.get("sin_a", 0.0) / max(e.get("cos_a", 1.0), 1e-9))
                  for e in ele]
    terburuk = (0.0, "", None, "")
    for nama, h in hasil.items():
        total = max(1.0, abs(ctx["kasus"][nama]["total"]))
        per = {}
        for b in bc:
            sx, sz = per.get(b["unit"], (0.0, 0.0))
            per[b["unit"]] = (sx + h["Rx"][b["node"]],
                              sz + h["Rz"][b["node"]])
        for u, (sx, sz) in per.items():
            r = max(abs(sx), abs(sz)) / total
            if r > terburuk[0]:
                terburuk = (r, nama, u, "Rx = {:.3g} kN, Rz = {:.3g} kN"
                            .format(sx, sz))
    # besaran masalah bila beban tidak diuraikan (informasi)
    info = ""
    kD1 = ctx["kasus"]["D1"]["ele"]
    horiz = {}
    for e in ele:
        q = kD1.get(e["tag"], 0.0)
        horiz[e["unit"]] = horiz.get(e["unit"], 0.0) + (
            -q * e.get("sin_a", 0.0) * e.get("L_aksial", 0.0))
    if any(abs(v) > 0 for v in horiz.values()):
        info = (" Bila D1 hanya diberikan sebagai beban lokal-y tanpa "
                "uraian, resultan horizontalnya per unit akan sekitar "
                + ", ".join("unit {}: {:+.0f} kN".format(u, v)
                            for u, v in sorted(horiz.items())) + ".")
    tol = k["tol_keseimbangan"]
    ok = terburuk[0] <= tol
    return _t("SC-16", "Orientasi beban dan keseimbangan horizontal",
              "PASS" if ok else "ERROR", terburuk[0],
              "|sum(Rx)|, |sum(Rz)| per unit / beban total <= {:.2%}; "
              "kemiringan sumbu maks {:.1%}".format(tol, max(kemiringan)),
              "Residual horizontal terbesar {:.2e} pada kasus {} (unit {}; "
              "{}).".format(terburuk[0], terburuk[1], terburuk[2], terburuk[3])
              + info, lokasi=terburuk[1])


def dc01_kapasitas(ctx, k):
    kap = getattr(ctx["pdata"], "KAPASITAS_BEARING", {}) or {}
    if not kap:
        return _t("DC-01", "Kapasitas bearing", "NOT ASSESSED", None,
                  "Demand/kapasitas terverifikasi <= 1.0",
                  "KAPASITAS_BEARING kosong: kapasitas bearing belum "
                  "diberikan, sehingga tidak ada pernyataan overload atau "
                  "aman. Reaksi demand tersedia pada tabel reaksi bearing.")
    tb = {r["bearing"]: r for r in ctx["tabel_bearing"]}
    baris, lewat, kosong = [], [], []
    for bid, r in tb.items():
        c = kap.get(bid)
        if not c:
            kosong.append(bid)
            continue
        if c.get("R_uls_kN"):
            dcr = r["uls_max"] / c["R_uls_kN"]
            baris.append({"bearing": bid, "keadaan": "ULS",
                          "demand_kN": r["uls_max"],
                          "kapasitas_kN": c["R_uls_kN"], "DCR": dcr,
                          "standar": c.get("standar", "")})
            if dcr > 1.0:
                lewat.append((bid, "ULS", dcr))
        if c.get("R_sls_kN"):
            dcr = r["layan_max"] / c["R_sls_kN"]
            baris.append({"bearing": bid, "keadaan": "SLS",
                          "demand_kN": r["layan_max"],
                          "kapasitas_kN": c["R_sls_kN"], "DCR": dcr,
                          "standar": c.get("standar", "")})
            if dcr > 1.0:
                lewat.append((bid, "SLS", dcr))
    if lewat:
        status = "CAPACITY EXCEEDANCE"
        detail = "DCR > 1.0: " + ", ".join(
            "{} {} ({:.2f})".format(b, s, d) for b, s, d in lewat) + "."
    else:
        status = "PASS" if not kosong else "NOT ASSESSED"
        detail = "Semua bearing yang diberi kapasitas memiliki DCR <= 1.0."
    if kosong:
        detail += " Kapasitas belum diberikan untuk: {}.".format(
            ", ".join(kosong))
    return _t("DC-01", "Kapasitas bearing", status,
              max((r["DCR"] for r in baris), default=None),
              "DCR = demand terkombinasi / kapasitas terverifikasi <= 1.0",
              detail, lokasi=", ".join(b for b, _, _ in lewat), bukti=baris)


def dc_demand(ctx, k):
    e = ctx["ekstrem"]
    teks = []
    for u in sorted(e):
        r = e[u]
        teks.append("unit {}: Mu+ = {:.0f} kN.m (x = {:.1f}), Mu- = {:.0f} "
                    "kN.m (x = {:.1f}), Vu = {:.0f} kN (x = {:.1f}), Tu = "
                    "{:.0f} kN.m (x = {:.1f})".format(
                        u, r["M_pos"][0], r["M_pos"][1], r["M_neg"][0],
                        r["M_neg"][1], r["V_maks"][0], r["V_maks"][1],
                        r["T_maks"][0], r["T_maks"][1]))
    ringkas = " | ".join(teks)
    out = []
    for id_, nama, kebutuhan in (
            ("DC-03", "Lentur penampang box",
             "momen tahanan penampang (As, fy, f'c, prategang, dimensi "
             "efektif)"),
            ("DC-04", "Geser penampang box",
             "tahanan geser (web, sengkang, tendon) dan kombinasi geser-"
             "puntir"),
            ("DC-05", "Torsi penampang box",
             "tahanan puntir penampang dan interaksi dengan geser")):
        out.append(_t(id_, nama, "NOT ASSESSED", None,
                      "Demand <= tahanan terverifikasi (SNI 2847/1725 atau "
                      "standar proyek)",
                      "Kapasitas penampang belum diberikan (" + kebutuhan
                      + "). Demand desain (Strength I-V): " + ringkas))
    out.append(_t("DC-06", "Tegangan lokal", "NOT ASSESSED", None,
                  "Submodel shell/solid bila tegangan lokal menentukan",
                  "Grillage tidak dapat menyelesaikan tegangan lokal "
                  "(diafragma tumpuan, angkur tendon, area bearing). "
                  "Direkomendasikan submodel terarah, bukan menyimpulkan "
                  "kegagalan dari gaya balok."))
    return out


# ------------------------------------------------------------------
# REKOMENDASI
# ------------------------------------------------------------------
ATURAN = {
    "SC-04": ("Keseimbangan vertikal gagal.",
              ["pembuatan beban tidak lengkap atau beban pada elemen yang "
               "tidak ada", "bearing tidak ter-fix pada node yang benar"],
              ["Periksa daftar beban kasus dan peta bearing (bc_list).",
               "Jangan keluarkan kesimpulan desain sebelum keseimbangan "
               "terpenuhi."]),
    "SC-05": ("Lendutan beban hidup melebihi ambang screening.",
              ["rigiditas lentur terlalu kecil", "ambang tidak sesuai "
               "kriteria proyek"],
              ["Konfirmasi kriteria lendutan proyek dan definisi bentang.",
               "Periksa EI efektif (retak/prategang) dan kombinasi yang "
               "dipakai."]),
    "SC-08": ("Pola momen tidak lazim.",
              ["kontinuitas atau kondisi tumpuan di model berbeda dari "
               "struktur", "letak beban hidup"],
              ["Bandingkan dengan sistem statis sebenarnya (menerus atau "
               "sendi pada pier)."]),
    "SC-09": ("Distribusi reaksi per bearing perlu ditinjau.",
              ["bearing menahan puntir tidak simetris", "beban hidup "
               "eksentrik"],
              ["Tinjau reaksi negatif terhadap pengekangan uplift pada "
               "bearing."]),
    "SC-10": ("Konsentrasi reaksi relatif tinggi.",
              ["pengaruh kontinuitas atau variasi penampang",
               "pemetaan beban ke garis"],
              ["Periksa penampang dan beban pada bentang di sekitar "
               "tumpuan tersebut."]),
    "SC-11": ("Kontinuitas atau keseimbangan geser stasiun tidak terpenuhi.",
              ["konvensi tanda eleForce", "elemen/beban hilang pada "
               "stasiun"],
              ["Periksa stasiun penentu pada kolom lokasi."]),
    "SC-12": ("Hasil sensitif terhadap konfigurasi garis.",
              ["distribusi kekakuan antar garis berbeda"],
              ["Tetapkan konfigurasi acuan dan pita konvergensi proyek."]),
    "SC-13": ("Akuntansi beban tidak sama dengan perhitungan independen.",
              ["batas tributari garis terluar berhenti di posisi node "
               "(bukan tepi deck)", "luas section vs berat jenis"],
              ["Ubah loads.batas_tributari agar batas terluar = "
               "+/-B_DECK/2 (seperti section_strips._batas_strip).",
               "Jalankan ulang analisis lalu ulangi SC-13."]),
    "SC-16": ("Beban gravitasi tidak vertikal pada gelagar miring.",
              ["beban merata diberikan sebagai beban lokal-y pada elemen "
               "miring tanpa uraian ke sumbu lokal"],
              ["Uraikan beban dengan analysis.komponen_lokal "
               "(Wy = q cos a, Wx = q sin a) dan ulangi analisis."]),
    "SC-15": ("Reaksi model melebihi beban SLS pada tabel bearing.",
              ["sistem statis di tabel berbeda dari model (mis. bentang "
               "sederhana vs menerus)", "kombinasi atau beban tambahan di "
               "tabel", "pembulatan pada tabel"],
              ["Beri tahu perencana bearing dan minta kapasitas aktual "
               "(isi KAPASITAS_BEARING) agar DC-01 dapat dinilai.",
               "Konfirmasi sistem statis dan beban yang dipakai pada tabel "
               "(lihat tests/investigasi_tabel_bearing.py)."]),
    "DC-01": ("Demand bearing melebihi kapasitas terverifikasi.",
              ["demand melampaui kapasitas yang dimasukkan"],
              ["Perbesar bearing atau tinjau ulang demand; konfirmasi "
               "standar dan faktor."]),
    "DC-02": ("Reaksi negatif pada bearing.",
              ["beban hidup eksentrik pada bentang pendek"],
              ["Tinjau pengekangan uplift, pengaruh kontak, dan pemodelan "
               "tumpuan."]),
}


def buat_rekomendasi(temuan):
    """Ubah temuan WARNING/ERROR/CAPACITY menjadi tindakan; NOT ASSESSED
    dikumpulkan sebagai kebutuhan data."""
    rekom, data_kurang = [], []
    for t in temuan:
        if t["status"] in ("ERROR", "CAPACITY EXCEEDANCE", "WARNING"):
            a = ATURAN.get(t["id"], ("Tinjau temuan ini.", [], []))
            rekom.append({"id": t["id"], "status": t["status"],
                          "judul": t["nama"], "ringkasan": a[0],
                          "bukti": t["detail"], "penyebab": a[1],
                          "tindakan": a[2], "lokasi": t.get("lokasi", "")})
        elif t["status"] == "NOT ASSESSED":
            data_kurang.append({"id": t["id"], "judul": t["nama"],
                                "kebutuhan": t["kriteria"],
                                "catatan": t["detail"]})
    urut = {s: i for i, s in enumerate(STATUS)}
    rekom.sort(key=lambda r: (urut[r["status"]], r["id"]))
    return rekom, data_kurang


# ------------------------------------------------------------------
# DRIVER
# ------------------------------------------------------------------
def jalankan_review(ctx, konfig=None):
    k = dict(KONFIG_DEFAULT)
    rv = getattr(ctx["pdata"], "REVIEW", {}) or {}
    k.update({key: v for key, v in rv.items() if key in KONFIG_DEFAULT})
    if konfig:
        k.update(konfig)
    ctx["konfig"] = k

    dasar = sanity_checks.jalankan_pemeriksaan(
        ctx["hasil"], ctx["kasus"], ctx["elemen_result"], ctx["bc_list"],
        toleransi_keseimbangan=k["tol_keseimbangan"], batas_lendutan_mm=None)
    dasar = [t for t in dasar if t["id"] != "SC-05"]
    for t in dasar:
        t.setdefault("lokasi", "")
        t.setdefault("bukti", [])

    tabel_reaksi_bearing(ctx, k)
    temuan = list(dasar)
    temuan.append(sc05_lendutan(ctx, k))
    temuan.append(sc07_momen(ctx, k))
    temuan.append(sc08_pola_momen(ctx, k))
    temuan.append(sc09_distribusi(ctx, k))
    temuan.append(sc10_konsentrasi(ctx, k))
    temuan.append(sc11_kontinuitas(ctx, k))
    temuan.append(sc12_sensitivitas(ctx, k))
    temuan.append(sc13_beban(ctx, k))
    temuan.append(sc14_referensi(ctx, k))
    temuan.append(sc15_tabel(ctx, k))
    temuan.append(sc16_orientasi(ctx, k))
    temuan.append(dc01_kapasitas(ctx, k))
    temuan.append(dc02_uplift(ctx, k))
    temuan.extend(dc_demand(ctx, k))
    temuan.sort(key=lambda t: (t["id"][:2] != "SC", t["id"]))
    return temuan
