# core/output.py
"""
Output analisis deck Jembatan Baros: envelope, kombinasi, tabel, file.
Satuan: kN, m.

Cara kerja
----------
Hasil kasus dasar (analysis.py) dikombinasikan secara linear:

  beban hidup L (envelope, per respon):
    Lmax = sum_k max(0, BTR_k) + max_k,f KEL_k,f
    Lmin = sum_k min(0, BTR_k) + min_k,f KEL_k,f
    dihitung per offset lajur, lalu diambil yang menentukan.
  kombinasi: V = f_D1*D1 + f_D2*D2 + f_L*L   (faktor dari loads.KOMBINASI)

Keterbatasan: faktor beban mati minimum (pengurangan beban mati) belum
dipakai; envelope minimum memakai faktor D yang sama dengan maksimum.
Gaya ujung elemen berasal dari respons OpenSees localForce. N, Vy, Vz, T,
My, dan Mz berada pada sumbu lokal elemen. Vy kiri/kanan pada CSV total
adalah shear lokal; loncatannya tidak langsung sama dengan reaksi global-Y
untuk gelagar miring. Pemeriksaan keseimbangan vertikal global memerlukan
Fy_global = Vy*cos(a) + N*sin(a) pada tiap sisi.

STATUS: [AKTIF] ini adalah keluaran akhir repo (gaya dalam dan reaksi).

Keluaran (laporan() menulis ke out_dir)
---------------------------------------
    reaksi.json, reaksi.csv       reaksi vertikal total per garis tumpuan
    reaksi_bearing.json/.csv      reaksi envelope per bearing fisik (B1..B24)
    sanity_checks.json/.csv       pemeriksaan integritas/keseimbangan dasar
                                  (screening, bukan sertifikasi desain)
    gaya_dalam.csv                envelope gaya ujung PER ELEMEN (per garis),
                                  satu kombinasi (Strength I)
    gaya_dalam_total.csv          gaya dalam TOTAL penampang (jumlah 5 garis)
                                  per stasiun dan unit, ekstrem semua
                                  kombinasi non-"Extreme"
    Mz_/Vy_/T_<kombinasi>.png     diagram envelope per garis (butuh
                                  matplotlib, diimpor saat dipakai)

Konvensi tanda
--------------
- Reaksi: positif ke atas (tekan pada tumpuan).
- gaya_dalam.csv: nilai MENTAH localForce OpenSees (Mz_i dan Mz_j
  berlawanan tanda untuk momen internal yang sama).
- Plot dan gaya_dalam_total.csv: momen sagging POSITIF
  (M = -Mz_i di ujung-i, M = +Mz_j di ujung-j).
- Vy_kiri/kanan di gaya_dalam_total.csv: shear lokal pada sisi kiri/kanan
    stasiun; untuk kemiringan, transformasikan dengan N*sin(a)+Vy*cos(a)
    sebelum membandingkan loncatan terhadap reaksi vertikal global.

CATATAN AUDIT
-------------
1. Envelope L memakai superposisi linear BTR per bentang + KEL pada posisi
   yang tersedia di analysis (default hanya tengah bentang).
2. KATEGORI_GAYA memuat T_i dan T_j; plot dan gaya_dalam.csv memakai
    keduanya. Ringkasan print_gaya_dalam hanya mengambil T_i, sedangkan
    gaya_dalam_total.csv tidak mengeluarkan torsi.
3. gaya_dalam.csv hanya untuk SATU kombinasi (Strength I, kode tetap di
   laporan()); gaya_dalam_total.csv untuk semua kombinasi.
4. Gaya aksial (arah x) tidak dikeluarkan.
5. Tes tanda dan statika memeriksa konvensi gaya ujung; tes output sintetis
    memeriksa penyimpanan CSV per elemen dan penjumlahan gaya antar garis.
6. Kombinasi "Extreme" dibuang dari semua keluaran (EQ belum ada).
"""

import csv
import json
import math
import os

try:
    from core import loads
    from core import sanity_checks
except ImportError:
    import loads
    import sanity_checks


KATEGORI_GAYA = ("Mz_i", "Mz_j", "Vy_i", "Vy_j", "T_i", "T_j")


# ============================================================
# 1. REAKSI PER SUPPORT
# ============================================================

def nama_support(bc):
    """Kunci per garis tumpuan: 'P2[u0]' untuk membedakan sisi EJ."""
    return "{}[u{}]".format(bc["support"], bc["unit"])


def tambah_reaksi_support(hasil, bc_list):
    """Tambah kategori 'Rsup' = jumlah reaksi semua node satu garis tumpuan."""
    grup = {}
    for b in bc_list:
        grup.setdefault(nama_support(b), []).append(b["node"])
    for nama, h in hasil.items():
        h["Rsup"] = {g: sum(h["R"][n] for n in nodes)
                     for g, nodes in grup.items()}
    return sorted(grup, key=lambda g: next(
        b["x"] for b in bc_list if nama_support(b) == g))


def tambah_reaksi_bearing(hasil, bc_list):
    """Tambahkan reaksi per bearing fisik, tanpa menggabungkan antar bearing."""
    daftar = {}
    for b in bc_list:
        bid = b.get("bearing")
        if not bid:
            continue
        if bid in daftar:
            raise ValueError("ID bearing duplikat pada bc_list: {}".format(bid))
        daftar[bid] = b["node"]
    for nama, h in hasil.items():
        r = h.get("R", {})
        hilang = [bid for bid, node in daftar.items() if node not in r]
        if hilang:
            raise KeyError("Hasil {} tidak memiliki reaksi node untuk bearing {}".format(nama, hilang))
        h["Rbearing"] = {bid: r[node] for bid, node in daftar.items()}
    return list(daftar)


def simpan_reaksi_bearing(path_json, path_csv, hasil, Lenv, bc_list,
                          kombinasi_semua):
    """Simpan reaksi envelope per bearing fisik (positif = ke atas)."""
    folder = os.path.dirname(path_json)
    if folder:
        os.makedirs(folder, exist_ok=True)
    env = {k: kombinasi_envelope(hasil, Lenv, k)["Rbearing"]
           for k in kombinasi_semua}
    metadata = {b["bearing"]: {"support": b["support"], "x": b["x"],
                                "z": b["z"], "unit": b["unit"],
                                "tipe": b.get("tipe"), "node": b["node"]}
                for b in bc_list if b.get("bearing")}
    data = {"satuan": "kN (positif = ke atas)",
            "catatan": "Reaksi per bearing fisik; bukan kapasitas bearing.",
            "bearing": {bid: {**meta, "D1": hasil["D1"]["Rbearing"][bid],
                              "D2": hasil["D2"]["Rbearing"][bid],
                              "L_min": Lenv["Rbearing"][bid][0],
                              "L_max": Lenv["Rbearing"][bid][1],
                              "kombinasi": {k: {"min": env[k][bid][0],
                                                "max": env[k][bid][1]}
                                            for k in kombinasi_semua}}
                       for bid, meta in metadata.items()}}
    with open(path_json, "w") as f:
        json.dump(data, f, indent=2)
    with open(path_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["bearing", "support", "x_m", "z_m", "unit", "tipe",
                    "kombinasi", "R_min_kN", "R_max_kN"])
        for bid, meta in metadata.items():
            for k in kombinasi_semua:
                w.writerow([bid, meta["support"], meta["x"], meta["z"],
                            meta["unit"], meta["tipe"], k,
                            env[k][bid][0], env[k][bid][1]])
    print("Reaksi per bearing disimpan: {} dan {}".format(path_json, path_csv))


def simpan_pemeriksaan(path_json, path_csv, temuan):
    """Simpan register sanity checks ke JSON dan CSV."""
    folder = os.path.dirname(path_json)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path_json, "w") as f:
        json.dump({"status": "SCREENING ONLY", "temuan": temuan}, f, indent=2)
    with open(path_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "nama", "status", "nilai", "kriteria", "detail"])
        for t in temuan:
            w.writerow([t.get("id"), t.get("nama"), t.get("status"),
                        t.get("nilai"), t.get("kriteria"), t.get("detail")])
    print("Register sanity checks disimpan: {} dan {}".format(path_json, path_csv))


# ============================================================
# 2. ENVELOPE DAN KOMBINASI
# ============================================================

def kelompokkan(kasus):
    """Kelompokkan nama kasus BTR dan KEL per offset lajur."""
    btr, kel = {}, {}
    for nama, k in kasus.items():
        if k["jenis"] == "BTR":
            btr.setdefault(k["offset"], []).append(nama)
        elif k["jenis"] == "KEL":
            kel.setdefault(k["offset"], []).append(nama)
    return btr, kel


def envelope_hidup(hasil, kasus):
    """
    Envelope beban hidup per kategori dan kunci: {cat: {key: (Lmin, Lmax)}}
    """
    btr, kel = kelompokkan(kasus)
    if not btr or not kel:
        raise ValueError("Kasus BTR/KEL tidak ditemukan.")

    Lenv = {}
    for cat, isi in hasil["D1"].items():
        Lenv[cat] = {}
        for key in isi:
            lo, hi = float("inf"), float("-inf")
            for o in btr:
                b = [hasil[n][cat][key] for n in btr[o]]
                k = [hasil[n][cat][key] for n in kel[o]]
                hi = max(hi, sum(max(0.0, v) for v in b) + max(k))
                lo = min(lo, sum(min(0.0, v) for v in b) + min(k))
            Lenv[cat][key] = (lo, hi)
    return Lenv


def kombinasi_envelope(hasil, Lenv, kombinasi):
    """
    Envelope satu kombinasi: {cat: {key: (vmin, vmax)}}.
    """
    if kombinasi not in loads.KOMBINASI:
        raise ValueError("Kombinasi tidak dikenal: {}".format(kombinasi))
    f = loads.KOMBINASI[kombinasi]
    fD1, fD2, fL = f.get("D1", 0.0), f.get("D2", 0.0), f.get("L", 0.0)

    env = {}
    for cat, isi in hasil["D1"].items():
        env[cat] = {}
        for key in isi:
            base = fD1 * isi[key] + fD2 * hasil["D2"][cat][key]
            lo, hi = Lenv[cat][key]
            env[cat][key] = (base + fL * lo, base + fL * hi)
    return env


def _moment_curve(hasil, kasus, tag, elemen, nama_kasus):
    """Return (constant, linear, quadratic) coefficients for sagging-positive M(s)."""
    h = hasil[nama_kasus]
    q = kasus[nama_kasus].get("ele", {}).get(tag, 0.0)
    return (
        -h["Mz_i"][tag],
        h["Vy_i"][tag],
        0.5 * q * elemen.get("cos_a", 1.0),
    )


def _poly_value(poly, s):
    return poly[0] + poly[1] * s + poly[2] * s * s


def _poly_add(left, right, factor=1.0):
    return tuple(a + factor * b for a, b in zip(left, right))


def _poly_roots_in_interval(poly, length):
    """Return real roots of a quadratic in the open element interval."""
    constant, linear, quadratic = poly
    roots = []
    scale = max(1.0, abs(constant), abs(linear) * length,
                abs(quadratic) * length * length)
    tol = 1.0e-12 * scale
    if abs(quadratic) * length * length <= tol:
        if abs(linear) * length > tol:
            roots.append(-constant / linear)
    else:
        discriminant = linear * linear - 4.0 * quadratic * constant
        discriminant_tol = 1.0e-12 * max(
            1.0, linear * linear, abs(4.0 * quadratic * constant))
        if discriminant >= -discriminant_tol:
            root_disc = math.sqrt(max(0.0, discriminant))
            roots.extend(((-linear - root_disc) / (2.0 * quadratic),
                          (-linear + root_disc) / (2.0 * quadratic)))
    return [root for root in roots if 0.0 < root < length]


def _moment_envelope_branches(hasil, kasus, elemen, kombinasi):
    """Return exact low/high quadratic envelope branches and their intervals."""
    tag = elemen["tag"]
    length = elemen.get("L_aksial", elemen["x2"] - elemen["x1"])
    factors = loads.KOMBINASI[kombinasi]
    f_live = factors.get("L", 0.0)
    base = (0.0, 0.0, 0.0)
    for name in ("D1", "D2"):
        base = _poly_add(base, _moment_curve(hasil, kasus, tag, elemen, name),
                         factors.get(name, 0.0))

    btr_by_offset, kel_by_offset = kelompokkan(kasus)
    if not btr_by_offset or not kel_by_offset:
        raise ValueError("Kasus BTR/KEL tidak ditemukan.")

    branches = []

    for offset, btr_names in btr_by_offset.items():
        kel_names = kel_by_offset.get(offset, [])
        if not kel_names:
            raise ValueError("Kasus KEL tidak ditemukan untuk offset {}".format(offset))
        btr_curves = {
            name: _moment_curve(hasil, kasus, tag, elemen, name)
            for name in btr_names
        }
        kel_curves = {
            name: _moment_curve(hasil, kasus, tag, elemen, name)
            for name in kel_names
        }

        breaks = [0.0, length]
        for curve in btr_curves.values():
            breaks.extend(_poly_roots_in_interval(curve, length))
        kel_items = list(kel_curves.items())
        for index, (_, left) in enumerate(kel_items):
            for _, right in kel_items[index + 1:]:
                breaks.extend(_poly_roots_in_interval(
                    tuple(a - b for a, b in zip(left, right)), length))
        breaks.sort()
        unique_breaks = []
        for point in breaks:
            if not unique_breaks or abs(point - unique_breaks[-1]) > 1.0e-10 * max(1.0, length):
                unique_breaks.append(point)

        for left_s, right_s in zip(unique_breaks, unique_breaks[1:]):
            mid_s = 0.5 * (left_s + right_s)
            live_high = (0.0, 0.0, 0.0)
            live_low = (0.0, 0.0, 0.0)
            for curve in btr_curves.values():
                value = _poly_value(curve, mid_s)
                if value > 0.0:
                    live_high = _poly_add(live_high, curve)
                elif value < 0.0:
                    live_low = _poly_add(live_low, curve)

            kel_values = {name: _poly_value(curve, mid_s)
                          for name, curve in kel_curves.items()}
            high_kel = max(kel_values, key=kel_values.get)
            low_kel = min(kel_values, key=kel_values.get)
            live_high = _poly_add(live_high, kel_curves[high_kel])
            live_low = _poly_add(live_low, kel_curves[low_kel])

            high_curve = _poly_add(base, live_high, f_live)
            low_curve = _poly_add(base, live_low, f_live)
            high_role_curve, low_role_curve = (
                (high_curve, low_curve) if f_live >= 0.0
                else (low_curve, high_curve)
            )
            branches.append((left_s, right_s, low_role_curve, high_role_curve))
    return branches


def _moment_envelope_extrema(hasil, kasus, elemen, kombinasi):
    """Find exact signed moment extrema over element ends and live-load branches."""
    length = elemen.get("L_aksial", elemen["x2"] - elemen["x1"])
    minimum = (float("inf"), None)
    maximum = (float("-inf"), None)
    for left_s, right_s, low_curve, high_curve in _moment_envelope_branches(
            hasil, kasus, elemen, kombinasi):
        for curve, seek_min in ((low_curve, True), (high_curve, False)):
            points = [left_s, right_s]
            if abs(curve[2]) > 1.0e-15:
                stationary = -curve[1] / (2.0 * curve[2])
                if left_s < stationary < right_s:
                    points.append(stationary)
            for point in points:
                value = _poly_value(curve, point)
                if seek_min and value < minimum[0]:
                    minimum = (value, point)
                elif not seek_min and value > maximum[0]:
                    maximum = (value, point)
    return minimum, maximum


def _moment_envelope_plot_positions(hasil, kasus, elemen, kombinasi,
                                    max_step=0.5):
    """Return plot stations including envelope switches and exact extrema."""
    length = elemen.get("L_aksial", elemen["x2"] - elemen["x1"])
    positions = {0.0, length}
    count = max(1, math.ceil(length / max_step))
    positions.update(length * index / count for index in range(1, count))
    branches = _moment_envelope_branches(hasil, kasus, elemen, kombinasi)
    for left_s, right_s, low_curve, high_curve in branches:
        positions.update((left_s, right_s))
        for curve in (low_curve, high_curve):
            if abs(curve[2]) > 1.0e-15:
                stationary = -curve[1] / (2.0 * curve[2])
                if left_s < stationary < right_s:
                    positions.add(stationary)

    # The live envelope is also maximized/minimized across lane offsets.
    for index, (left_a, right_a, low_a, high_a) in enumerate(branches):
        for left_b, right_b, low_b, high_b in branches[index + 1:]:
            left_s, right_s = max(left_a, left_b), min(right_a, right_b)
            if left_s >= right_s:
                continue
            for first, second in ((low_a, low_b), (high_a, high_b)):
                difference = tuple(a - b for a, b in zip(first, second))
                positions.update(
                    root for root in _poly_roots_in_interval(difference, length)
                    if left_s < root < right_s
                )
    return sorted(positions)


def _kelompok_elemen_plot(elemen):
    """Group longitudinal elements by physical line and continuous unit."""
    groups = {}
    for element in elemen:
        groups.setdefault((element["garis"], element["unit"]), []).append(element)
    return {
        key: sorted(values, key=lambda element: element["x1"])
        for key, values in sorted(groups.items())
    }


def _moment_envelope_at(hasil, kasus, elemen, kombinasi, s):
    """Evaluate the signed moment envelope at an axial position in an element."""
    tag = elemen["tag"]
    factors = loads.KOMBINASI[kombinasi]
    base = 0.0
    for name in ("D1", "D2"):
        base += factors.get(name, 0.0) * _poly_value(
            _moment_curve(hasil, kasus, tag, elemen, name), s)

    btr_by_offset, kel_by_offset = kelompokkan(kasus)
    live_high, live_low = float("-inf"), float("inf")
    for offset, btr_names in btr_by_offset.items():
        btr_values = [
            _poly_value(_moment_curve(hasil, kasus, tag, elemen, name), s)
            for name in btr_names
        ]
        kel_values = [
            _poly_value(_moment_curve(hasil, kasus, tag, elemen, name), s)
            for name in kel_by_offset.get(offset, [])
        ]
        live_high = max(live_high,
                        sum(max(0.0, value) for value in btr_values)
                        + max(kel_values))
        live_low = min(live_low,
                       sum(min(0.0, value) for value in btr_values)
                       + min(kel_values))
    f_live = factors.get("L", 0.0)
    low, high = base + f_live * live_low, base + f_live * live_high
    return (low, high) if low <= high else (high, low)


# ============================================================
# 3. TABEL
# ============================================================

def print_reaksi(hasil, Lenv, urutan, kombinasi_list):
    """Reaksi vertikal per garis tumpuan (jumlah 5 node)."""
    env = {k: kombinasi_envelope(hasil, Lenv, k)["Rsup"]
           for k in kombinasi_list}

    print("=" * 110)
    print("REAKSI VERTIKAL PER GARIS TUMPUAN (kN) - tumpuan kaku di deck")
    print("=" * 110)
    kepala = "{:>10s} {:>10s} {:>10s} {:>10s} {:>10s}".format(
        "Tumpuan", "D1", "D2", "L max", "L min")
    for k in kombinasi_list:
        kepala += " {:>10s} {:>10s}".format(k[:8] + " min", k[:8] + " max")
    print(kepala)
    print("-" * 110)
    for g in urutan:
        baris = "{:>10s} {:>10.1f} {:>10.1f} {:>10.1f} {:>10.1f}".format(
            g, hasil["D1"]["Rsup"][g], hasil["D2"]["Rsup"][g],
            Lenv["Rsup"][g][1], Lenv["Rsup"][g][0])
        for k in kombinasi_list:
            lo, hi = env[k][g]
            baris += " {:>10.1f} {:>10.1f}".format(lo, hi)
        print(baris)
    tot = sum(hasil["D1"]["Rsup"][g] for g in urutan)
    print("-" * 110)
    print("Jumlah reaksi D1 = {:.1f} kN (harus = berat sendiri total)".format(tot))
    print("Reaksi positif = ke atas (tekan pada tumpuan).")
    print()


def print_gaya_dalam(hasil, Lenv, elemen_result, kombinasi="Strength I",
                     kasus=None):
    """
    Ekstrem momen sagging-positif sepanjang elemen; shear/torsi tetap ekstrem
    gaya ujung lokal. M = -Mz_i di ujung-i dan M = +Mz_j di ujung-j.
    """
    if kasus is None:
        raise ValueError("Kasus beban diperlukan untuk menghitung momen interior.")
    env = kombinasi_envelope(hasil, Lenv, kombinasi)
    ele = {e["tag"]: e for e in elemen_result["memanjang"]}

    print("=" * 100)
    print("GAYA DALAM EKSTREM PER GARIS - {}".format(kombinasi))
    print("=" * 100)
    print("{:>8s} {:>12s} {:>10s} {:>12s} {:>10s} {:>12s} {:>12s}".format(
        "z (m)", "Mz min", "x (m)", "Mz max", "x (m)", "|Vy| maks", "|T| maks"))
    print("-" * 100)
    for j in sorted({e["garis"] for e in ele.values()}):
        tags = [t for t, e in ele.items() if e["garis"] == j]
        mz_min = (float("inf"), None)
        mz_max = (float("-inf"), None)
        vmaks = 0.0
        tmaks = 0.0
        for t in tags:
            minimum, maximum = _moment_envelope_extrema(
                hasil, kasus, ele[t], kombinasi)
            for value, axial_position in (minimum, maximum):
                x_position = ele[t]["x1"] + axial_position * ele[t].get(
                    "cos_a", 1.0)
                if value < mz_min[0]:
                    mz_min = (value, x_position)
                if value > mz_max[0]:
                    mz_max = (value, x_position)
            for cat in ("Vy_i", "Vy_j"):
                vmaks = max(vmaks, abs(env[cat][t][0]), abs(env[cat][t][1]))
            tmaks = max(tmaks, abs(env["T_i"][t][0]), abs(env["T_i"][t][1]))
        print("{:>8.2f} {:>12.1f} {:>10.2f} {:>12.1f} {:>10.2f} {:>12.1f} "
              "{:>12.1f}".format(ele[tags[0]]["z"], mz_min[0], mz_min[1],
                                 mz_max[0], mz_max[1], vmaks, tmaks))
    print()

def plot_gaya_dalam(hasil, Lenv, elemen_result, out_dir,
                    kombinasi="Strength I", kasus=None):
    """
    Plot envelope gaya dalam per garis memanjang dan unit kontinu.

    Output:
      - Mz_<kombinasi>.png
      - Vy_<kombinasi>.png
      - T_<kombinasi>.png

    Momen diplot sepanjang elemen dari envelope kasus beban terdistribusi;
    shear dan torsi tetap memakai envelope gaya ujung lokal.
    """
    import matplotlib.pyplot as plt   # dependensi opsional (hanya untuk plot)

    if kasus is None:
        raise ValueError("Kasus beban diperlukan untuk mem-plot momen interior.")
    env = kombinasi_envelope(hasil, Lenv, kombinasi)

    ele = {
        e["tag"]: e
        for e in elemen_result["memanjang"]
    }

    grup_garis = _kelompok_elemen_plot(ele.values())

    os.makedirs(out_dir, exist_ok=True)

    # --------------------------------------------------------
    # Helper: susun titik sepanjang satu garis
    # --------------------------------------------------------
    def data_garis(elements, cat_i, cat_j, flip_i=False,
                   moment_component=False):
        data = []

        for e in elements:
            t = e["tag"]

            if moment_component:
                positions = _moment_envelope_plot_positions(
                    hasil, kasus, e, kombinasi)
                for s in positions:
                    low, high = _moment_envelope_at(
                        hasil, kasus, e, kombinasi, s)
                    x = e["x1"] + s * e.get("cos_a", 1.0)
                    data.append((x, low, high))
                continue

            lo_i, hi_i = env[cat_i][t]
            if flip_i:                     # sagging positif
                lo_i, hi_i = -hi_i, -lo_i
            data.append((e["x1"], lo_i, hi_i))

            data.append(
                (e["x2"], env[cat_j][t][0], env[cat_j][t][1])
            )

        # Urutkan menurut x. Titik dengan x sama (ujung-j segmen kiri dan
        # ujung-i segmen kanan) TIDAK digabung; keduanya digambar.
        data.sort(key=lambda p: p[0])

        return data

    # --------------------------------------------------------
    # Plot satu besaran
    # --------------------------------------------------------
    def plot_env(cat_i, cat_j, ylabel, filename, mode="signed",
                 flip_i=False, moment_component=False):
        fig, ax = plt.subplots(figsize=(14, 6))

        for (line, unit), elements in grup_garis.items():
            data = data_garis(elements, cat_i, cat_j, flip_i,
                              moment_component)

            xs = [p[0] for p in data]

            if mode == "signed":
                ymin = [p[1] for p in data]
                ymax = [p[2] for p in data]

                ax.plot(
                    xs, ymin,
                    marker="o",
                    markersize=2,
                    label="garis {} / unit {} — min".format(line, unit)
                )

                ax.plot(
                    xs, ymax,
                    linestyle="--",
                    linewidth=1.0
                )

            elif mode == "abs":
                # Envelope absolut:
                # max(|min|, |max|)
                vals = [
                    max(abs(p[1]), abs(p[2]))
                    for p in data
                ]

                ax.plot(
                    xs, vals,
                    marker="o",
                    markersize=2,
                    label="garis {} / unit {}".format(line, unit)
                )

        ax.axhline(0.0, linewidth=0.8)

        ax.set_xlabel("x (m)")
        ax.set_ylabel(ylabel)
        ax.set_title(
            "{} — {}".format(kombinasi, ylabel)
        )

        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()

        path = os.path.join(out_dir, filename)
        fig.savefig(path, dpi=150)
        plt.close(fig)

        print("Diagram disimpan:", path)

    # --------------------------------------------------------
    # Mz : tampilkan envelope min dan max
    # --------------------------------------------------------
    plot_env(
        "Mz_i",
        "Mz_j",
        "Mz (kNm), + = sagging",
        "Mz_{}.png".format(kombinasi.replace(" ", "_")),
        mode="signed",
        flip_i=True,
        moment_component=True,
    )

    # --------------------------------------------------------
    # Vy : maksimum absolut
    # --------------------------------------------------------
    plot_env(
        "Vy_i",
        "Vy_j",
        "|Vy| (kN)",
        "Vy_{}.png".format(kombinasi.replace(" ", "_")),
        mode="abs"
    )

    # --------------------------------------------------------
    # T : maksimum absolut
    # --------------------------------------------------------
    plot_env(
        "T_i",
        "T_j",
        "|T| (kNm)",
        "T_{}.png".format(kombinasi.replace(" ", "_")),
        mode="abs"
    )

def print_lendutan(hasil, Lenv, node_result, kombinasi="Service I"):
    """Lendutan vertikal terbesar ke bawah dan ke atas."""
    env = kombinasi_envelope(hasil, Lenv, kombinasi)["Uy"]
    pos = {}
    for (i, j), tag in node_result["node_map"].items():
        pos[tag] = (node_result["stasiun"][i]["x"],
                    node_result["z_garis"][j])

    bawah = min(env.items(), key=lambda kv: kv[1][0])
    atas = max(env.items(), key=lambda kv: kv[1][1])
    print("=" * 75)
    print("LENDUTAN VERTIKAL - {}".format(kombinasi))
    print("=" * 75)
    print("  Ke bawah maks : {:>9.2f} mm  di node {} (x = {:.2f} m, z = {:.2f} m)"
          .format(bawah[1][0] * 1000, bawah[0], *pos[bawah[0]]))
    print("  Ke atas maks  : {:>9.2f} mm  di node {} (x = {:.2f} m, z = {:.2f} m)"
          .format(atas[1][1] * 1000, atas[0], *pos[atas[0]]))
    print()


# ============================================================
# 4. SIMPAN FILE
# ============================================================

def simpan_reaksi(path_json, path_csv, hasil, Lenv, urutan, bentang,
                  kombinasi_semua):
    """Simpan reaksi per garis tumpuan ke JSON dan CSV."""
    folder = os.path.dirname(path_json)
    if folder:
        os.makedirs(folder, exist_ok=True)

    env = {k: kombinasi_envelope(hasil, Lenv, k)["Rsup"]
           for k in kombinasi_semua}

    data = {
        "satuan": "kN (positif = ke atas)",
        "catatan": "tumpuan kaku di deck; belum ada pier",
        "bentang": [{"k": b["k"], "nama": b["nama"], "L": b["L"]}
                    for b in bentang],
        "tumpuan": {},
    }
    for g in urutan:
        data["tumpuan"][g] = {
            "D1": hasil["D1"]["Rsup"][g],
            "D2": hasil["D2"]["Rsup"][g],
            "L_min": Lenv["Rsup"][g][0],
            "L_max": Lenv["Rsup"][g][1],
            "kombinasi": {k: {"min": env[k][g][0], "max": env[k][g][1]}
                          for k in kombinasi_semua},
        }

    with open(path_json, "w") as f:
        json.dump(data, f, indent=2)
    print("JSON disimpan: {}".format(path_json))

    with open(path_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tumpuan", "kombinasi", "R_min", "R_max"])
        for g in urutan:
            for k in kombinasi_semua:
                w.writerow([g, k, env[k][g][0], env[k][g][1]])
    print("CSV disimpan: {}".format(path_csv))


def _nilai_envelope(env, kategori, tag):
    """Ambil envelope (min, max) untuk satu tag dari hasil kombinasi."""
    values = env.get(kategori, {})
    if tag not in values:
        raise KeyError("Tag {} tidak ditemukan untuk {}".format(tag, kategori))
    return values[tag]


def simpan_gaya_dalam(path_csv, elemen_result, env):
    """
    Simpan gaya dalam setiap elemen memanjang ke CSV.
    Kolom Mz/Vy/T adalah gaya UJUNG ELEMEN mentah (lokal OpenSees):
    untuk momen internal yang sama Mz_i dan Mz_j berlawanan tanda.
    Sagging positif: M = -Mz_i (ujung-i), M = +Mz_j (ujung-j).
    """
    folder = os.path.dirname(path_csv)
    if folder:
        os.makedirs(folder, exist_ok=True)

    elemen = elemen_result.get("memanjang", [])
    garis = sorted({e["garis"] for e in elemen})
    if not elemen:
        raise ValueError("Tidak ada elemen memanjang untuk disimpan.")

    header = [
        "tag", "garis", "z", "x1", "x2",
        "Mz_i_min", "Mz_i_max", "Mz_j_min", "Mz_j_max",
        "Vy_i_min", "Vy_i_max", "Vy_j_min", "Vy_j_max",
        "T_i_min", "T_i_max", "T_j_min", "T_j_max",
    ]

    with open(path_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for e in elemen:
            tag = e["tag"]
            vals = {
                cat: _nilai_envelope(env, cat, tag)
                for cat in KATEGORI_GAYA
            }
            w.writerow([
                tag, e["garis"], e["z"], e["x1"], e["x2"],
                vals["Mz_i"][0], vals["Mz_i"][1],
                vals["Mz_j"][0], vals["Mz_j"][1],
                vals["Vy_i"][0], vals["Vy_i"][1],
                vals["Vy_j"][0], vals["Vy_j"][1],
                vals["T_i"][0], vals["T_i"][1],
                vals["T_j"][0], vals["T_j"][1],
            ])

    print("CSV gaya dalam per elemen disimpan: {}".format(path_csv))
    print("Jumlah garis longitudinal: {}".format(len(garis)))


def hasil_total_segmen(hasil, elemen_result):
    """
    Jumlahkan gaya ujung semua garis per segmen, untuk SETIAP kasus dasar.
    Key = (x1, x2, unit) dengan unit = bilangan bulat indeks unit menerus
    (0, 1, 2). Penjumlahan dilakukan per kasus SEBELUM envelope, supaya
    ekstrem total berasal dari kasus beban yang sama (simultan).

    Catatan: semua garis berada pada satu elevasi (grillage planar), jadi
    jumlah Mz dan Vy antar garis sah sebagai momen lentur vertikal dan geser
    TOTAL. Torsi terhadap sumbu gelagar lokal, dengan z positif ke kanan saat
    melihat arah +x, adalah sum(T_i - z_garis * Vy_i) pada potongan awal.
    Torsi total tidak dikeluarkan di gaya_dalam_total.csv.

    Returns
    -------
    total : {nama_kasus: {kategori: {key: jumlah}}}
    seg   : {key: [tag elemen]}
    """
    seg = {}
    for e in elemen_result["memanjang"]:
        seg.setdefault((e["x1"], e["x2"], e["unit"]), []).append(e["tag"])
    total = {}
    for nama, h in hasil.items():
        total[nama] = {
            cat: {k: sum(h[cat][t] for t in tags) for k, tags in seg.items()}
            for cat in KATEGORI_GAYA
        }
    return total, seg


def _ujung_total(env, key, ujung):
    """((M_min, M_max), (V_min, V_max)) di satu ujung segmen; M sagging +."""
    if ujung == "i":
        lo, hi = env["Mz_i"][key]
        return (-hi, -lo), env["Vy_i"][key]
    lo, hi = env["Vy_j"][key]
    return env["Mz_j"][key], (-hi, -lo)


def simpan_gaya_dalam_total(path_csv, elemen_result, hasil, kasus,
                            kombinasi_list=None):
    """
    Gaya dalam TOTAL penampang (jumlah 5 garis) per stasiun dan unit.

    Envelope dihitung pada gaya total per kasus (bukan jumlah envelope
    per garis). Stasiun EJ dipisah per unit. Momen: sagging positif.
    Vy: Vy_kiri dari ujung-j segmen kiri (tanda dibalik), Vy_kanan dari
    ujung-i segmen kanan. Keduanya adalah shear lokal; pada gelagar miring,
    keseimbangan vertikal global memakai N*sin(a) + Vy*cos(a) di setiap sisi.
    """
    folder = os.path.dirname(path_csv)
    if folder:
        os.makedirs(folder, exist_ok=True)
    if not elemen_result.get("memanjang"):
        raise ValueError("Tidak ada elemen memanjang untuk disimpan.")

    if kombinasi_list is None:
        kombinasi_list = [k for k in loads.KOMBINASI
                          if "Extreme" not in k]

    total, seg = hasil_total_segmen(hasil, elemen_result)
    Lenv = envelope_hidup(total, kasus)
    env_k = {k: kombinasi_envelope(total, Lenv, k) for k in kombinasi_list}

    stasiun = {}                      # (x, unit) -> {"kiri": key, "kanan": key}
    for key in seg:
        x1, x2, unit = key
        stasiun.setdefault((round(x1, 6), unit), {})["kanan"] = key
        stasiun.setdefault((round(x2, 6), unit), {})["kiri"] = key

    def ekstrem(key, ujung, idx_mv, idx_mm):
        """Cari (nilai, kombinasi) terkecil/terbesar di semua kombinasi."""
        if key is None:
            return None, ""
        cands = []
        for k in kombinasi_list:
            m, v = _ujung_total(env_k[k], key, ujung)
            cands.append(((m, v)[idx_mv][idx_mm], k))
        return (min if idx_mm == 0 else max)(cands, key=lambda c: c[0])

    rows = []
    for (x, unit) in sorted(stasiun):
        st = stasiun[(x, unit)]
        kn, kr = st.get("kanan"), st.get("kiri")
        key_m, uj_m = (kn, "i") if kn else (kr, "j")      # momen menerus
        r = [x, unit]
        r += list(ekstrem(key_m, uj_m, 0, 0))
        r += list(ekstrem(key_m, uj_m, 0, 1))
        for key, uj in ((kr, "j"), (kn, "i")):            # Vy kiri, kanan
            r += list(ekstrem(key, uj, 1, 0))
            r += list(ekstrem(key, uj, 1, 1))
        rows.append(r)

    with open(path_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "x", "unit",
            "Mz_total_min", "Mz_total_min_kombinasi",
            "Mz_total_max", "Mz_total_max_kombinasi",
            "Vy_kiri_min", "Vy_kiri_min_kombinasi",
            "Vy_kiri_max", "Vy_kiri_max_kombinasi",
            "Vy_kanan_min", "Vy_kanan_min_kombinasi",
            "Vy_kanan_max", "Vy_kanan_max_kombinasi",
        ])
        w.writerows(rows)

    print("CSV gaya dalam total disimpan: {}".format(path_csv))


# ============================================================
# 5. LAPORAN LENGKAP
# ============================================================

def laporan(hasil, kasus, node_result, bc_list, bentang, out_dir,
            elemen_result=None):
    """Cetak ringkasan dan simpan output analisis serta sanity checks."""
    os.makedirs(out_dir, exist_ok=True)
    urutan = tambah_reaksi_support(hasil, bc_list)
    tambah_reaksi_bearing(hasil, bc_list)
    Lenv = envelope_hidup(hasil, kasus)

    print_reaksi(hasil, Lenv, urutan, ["Service I", "Strength I"])
    print_lendutan(hasil, Lenv, node_result, "Service I")

    if elemen_result is not None:
        print_gaya_dalam(hasil, Lenv, elemen_result, "Strength I", kasus)
        plot_gaya_dalam(hasil, Lenv, elemen_result, out_dir,
                        kombinasi="Strength I", kasus=kasus)
        env = kombinasi_envelope(hasil, Lenv, "Strength I")
        simpan_gaya_dalam(os.path.join(out_dir, "gaya_dalam.csv"),
                          elemen_result, env)
        simpan_gaya_dalam_total(os.path.join(out_dir, "gaya_dalam_total.csv"),
                                elemen_result, hasil, kasus)

    kombinasi_semua = [k for k in loads.KOMBINASI if "Extreme" not in k]
    simpan_reaksi(os.path.join(out_dir, "reaksi.json"),
                  os.path.join(out_dir, "reaksi.csv"),
                  hasil, Lenv, urutan, bentang, kombinasi_semua)
    simpan_reaksi_bearing(os.path.join(out_dir, "reaksi_bearing.json"),
                          os.path.join(out_dir, "reaksi_bearing.csv"),
                          hasil, Lenv, bc_list, kombinasi_semua)

    if elemen_result is not None:
        temuan = sanity_checks.jalankan_pemeriksaan(
            hasil, kasus, elemen_result, bc_list)
        simpan_pemeriksaan(os.path.join(out_dir, "sanity_checks.json"),
                           os.path.join(out_dir, "sanity_checks.csv"), temuan)
        for t in temuan:
            print("[{}] {}: {}".format(t["status"], t["id"], t["nama"]))
    else:
        print("Sanity checks dilewati: elemen_result tidak tersedia.")
    return Lenv, urutan

