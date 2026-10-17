# core/gaya_total.py
"""
Gaya dalam TOTAL penampang (jumlah semua garis memanjang) sepanjang bentang.

Kenapa modul ini
----------------
output.plot_gaya_dalam hanya menyambung nilai ujung elemen. Pada elemen
panjang dengan beban merata, momen di dalam elemen berbentuk parabola dan
puncak sagging tidak ada di ujung elemen. Di sini setiap segmen disampel
tiap ~DS meter memakai kesetimbangan elemen, lalu envelope dihitung dengan
fungsi output yang sama (kombinasi_envelope, envelope_hidup), sehingga tetap
konsisten dengan tabel dan CSV yang sudah ada.

Konvensi (gelagar mengikuti alinyemen; sumbu lokal elemen: x = sumbu gelagar,
y = tegak lurus sumbu dalam bidang x-y, z = z global):
  M(s) sagging +  = -sum(Mz_i) + sum(Vy_i)*s + sum(Wy)*s^2/2
  V(s)            = sum(Vy_i) + sum(Wy)*s    (geser TEGAK LURUS sumbu gelagar,
                                              yang menentukan desain geser)
  T(s) terhadap sumbu gelagar, kaidah tangan kanan:
        T(s) = sum_j [ T_i,j - z_j * (Vy_i,j + Wy_j * s) ]
  s = jarak sepanjang SUMBU dari ujung-i segmen (0..L_aksial); Wy = q cos(a)
  adalah komponen tegak lurus sumbu dari beban gravitasi q per panjang sumbu
  (kasus["ele"]); a = kemiringan sumbu. z + = kanan bila menghadap +x.
Suku z*V adalah momen puntir akibat beban/geser yang tidak simetris
terhadap sumbu; suku T_i adalah puntir internal tiap garis. Posisi x pada
grafik = koordinat HORIZONTAL (x = x1 + s cos(a)).
Beban titik di dalam elemen (KEL bergerak, kasus["pload"] = {tag: [(P, xL)]},
P vertikal gravitasi negatif, xL fraksi dari ujung-i) menambah, untuk s > a_p
(a_p = xL * L_aksial) dan komponen tegak lurus Py = P cos(a):
  M(s) += Py*(s - a_p) ; V(s) += Py ; T(s) += -z*Py.
"""

import math

from core import output

KATEGORI = ("Mx", "Vx", "Tx")
DS_DEFAULT = 1.0           # jarak sampel (m)
N_MAKS = 80                # batas jumlah sampel per segmen


def segmen_garis(elemen_result):
    """{(x1, x2, unit): [elemen memanjang]} terurut menurut x."""
    seg = {}
    for e in elemen_result["memanjang"]:
        seg.setdefault((e["x1"], e["x2"], e["unit"]), []).append(e)
    return dict(sorted(seg.items(), key=lambda kv: (kv[0][2], kv[0][0])))


def panjang_aksial(eles, x1, x2):
    """Panjang sumbu segmen (sama untuk semua garis); mundur ke dx bila
    elemen belum membawa L_aksial (model lama, gelagar datar)."""
    return eles[0].get("L_aksial", x2 - x1)


def jumlah_sampel(L, ds=DS_DEFAULT):
    return max(2, min(N_MAKS, int(math.ceil(L / ds))))


def total_per_kasus(hasil, kasus, elemen_result, ds=DS_DEFAULT):
    """
    Gaya dalam total per kasus dasar pada titik sampel.

    Returns
    -------
    total : {kasus: {"Mx": {kunci: v}, "Vx": {...}, "Tx": {...}}}
            kunci = (x1, x2, unit, k) ; titik x = x1 + k/N*(x2-x1)
    seg   : {(x1, x2, unit): N}
    """
    segs = segmen_garis(elemen_result)
    seg_n = {key: jumlah_sampel(panjang_aksial(eles, key[0], key[1]), ds)
             for key, eles in segs.items()}
    total = {}
    for nama, h in hasil.items():
        w_kasus = kasus[nama].get("ele", {})
        p_kasus = kasus[nama].get("pload", {})
        d = {c: {} for c in KATEGORI}
        for (x1, x2, u), eles in segs.items():
            L = panjang_aksial(eles, x1, x2)
            n = seg_n[(x1, x2, u)]
            smz = sum(h["Mz_i"][e["tag"]] for e in eles)
            for k in range(n + 1):
                s = L * k / n
                m = -smz
                v = 0.0
                t = 0.0
                for e in eles:
                    tg = e["tag"]
                    wy = w_kasus.get(tg, 0.0) * e.get("cos_a", 1.0)
                    vy = h["Vy_i"][tg]
                    m += vy * s + wy * s * s / 2.0
                    v += vy + wy * s
                    t += h["T_i"][tg] - e["z"] * (vy + wy * s)
                    for P, xl in p_kasus.get(tg, ()):
                        a_p = xl * L
                        if s > a_p:                 # beban titik di kiri s
                            py = P * e.get("cos_a", 1.0)
                            m += py * (s - a_p)
                            v += py
                            t += -e["z"] * py
                key = (x1, x2, u, k)
                d["Mx"][key] = m
                d["Vx"][key] = v
                d["Tx"][key] = t
        total[nama] = d
    return total, seg_n


def titik_x(key, seg_n):
    """Koordinat horizontal titik sampel."""
    x1, x2, u, k = key
    return x1 + (x2 - x1) * k / seg_n[(x1, x2, u)]


def envelope_desain(total, kasus, kombinasi_list, kel_kedua=True):
    """
    Envelope gabungan beberapa kombinasi.

    Returns
    -------
    env_gab : {kat: {kunci: (lo, hi)}}
    env_k   : {kombinasi: {kat: {kunci: (lo, hi)}}}
    Lenv    : envelope beban hidup (output.envelope_hidup)
    """
    Lenv = envelope_hidup_total(total, kasus, kel_kedua=kel_kedua)
    env_k = {k: output.kombinasi_envelope(total, Lenv, k)
             for k in kombinasi_list}
    gab = {}
    for k, env in env_k.items():
        for kat, isi in env.items():
            g = gab.setdefault(kat, {})
            for key, (lo, hi) in isi.items():
                if key in g:
                    g[key] = (min(g[key][0], lo), max(g[key][1], hi))
                else:
                    g[key] = (lo, hi)
    return gab, env_k, Lenv


def profil(env, kat, seg_n):
    """Titik terurut per unit: {unit: [(x, lo, hi), ...]} (loncatan = 2 titik)."""
    out = {}
    for (x1, x2, u), n in seg_n.items():
        for k in range(n + 1):
            lo, hi = env[kat][(x1, x2, u, k)]
            out.setdefault(u, []).append((x1 + (x2 - x1) * k / n, lo, hi))
    return out


def ekstrem_per_unit(env_k, seg_n):
    """
    Ekstrem desain per unit beserta kombinasi penentu.
    Return {unit: {"M_pos": (nilai, x, komb), "M_neg":..., "V_maks":...,
                   "T_maks":...}}
    """
    hasil = {}
    for kombinasi, env in env_k.items():
        for (x1, x2, u), n in seg_n.items():
            r = hasil.setdefault(u, {
                "M_pos": (float("-inf"), None, ""),
                "M_neg": (float("inf"), None, ""),
                "V_maks": (0.0, None, ""),
                "T_maks": (0.0, None, ""),
            })
            for k in range(n + 1):
                key = (x1, x2, u, k)
                x = x1 + (x2 - x1) * k / n
                mlo, mhi = env["Mx"][key]
                if mhi > r["M_pos"][0]:
                    r["M_pos"] = (mhi, x, kombinasi)
                if mlo < r["M_neg"][0]:
                    r["M_neg"] = (mlo, x, kombinasi)
                vlo, vhi = env["Vx"][key]
                if max(abs(vlo), abs(vhi)) > r["V_maks"][0]:
                    r["V_maks"] = (max(abs(vlo), abs(vhi)), x, kombinasi)
                tlo, thi = env["Tx"][key]
                if max(abs(tlo), abs(thi)) > r["T_maks"][0]:
                    r["T_maks"] = (max(abs(tlo), abs(thi)), x, kombinasi)
    return hasil


def envelope_hidup_total(total, kasus, kel_kedua=True):
    """
    Envelope beban hidup untuk gaya dalam TOTAL (kategori Mx, Vx, Tx).

    Sama dengan output.envelope_hidup (BTR per bentang bersifat independen
    sehingga ekstrem = jumlah bagian positif/negatif; satu KEL pada posisi
    terburuk) tetapi, bila kel_kedua, momen negatif maksimum (kategori Mx,
    sisi bawah) menambahkan KEL KEDUA yang identik pada bentang lain
    (SNI 1725:2016 untuk jembatan menerus): dua nilai KEL paling negatif
    dari dua bentang berbeda. Kategori lain tetap memakai satu KEL.
    """
    btr, kel = output.kelompokkan(kasus)
    if not btr or not kel:
        raise ValueError("Kasus BTR/KEL tidak ditemukan.")
    Lenv = {}
    for cat, isi in total["D1"].items():
        Lenv[cat] = {}
        for key in isi:
            lo, hi = float("inf"), float("-inf")
            for o in btr:
                b = [total[n][cat][key] for n in btr[o]]
                kv = [(total[n][cat][key], kasus[n]["bentang"])
                      for n in kel[o]]
                hi = max(hi, sum(max(0.0, v) for v in b)
                         + max(v for v, _ in kv))
                lo_o = sum(min(0.0, v) for v in b) + min(v for v, _ in kv)
                if kel_kedua and cat == "Mx":
                    v1, k1 = min(kv)
                    lain = [v for v, kk in kv if kk != k1]
                    if lain:
                        lo_o = sum(min(0.0, v) for v in b) + v1 \
                            + min(0.0, min(lain))
                lo = min(lo, lo_o)
            Lenv[cat][key] = (lo, hi)
    return Lenv
