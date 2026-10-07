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
Konvensi gaya ujung elemen (Mz, Vy, T) = gaya OpenSees (eleForce, sumbu
lokal). Verifikasi tanda dengan balok sederhana sebelum dipakai desain.
"""

import csv
import json
import os

try:
    from core import loads
except ImportError:
    import loads


KATEGORI_GAYA = ("Mz_i", "Mz_j", "Vy_i", "Vy_j", "T_i")


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


def print_gaya_dalam(hasil, Lenv, elemen_result, kombinasi="Strength I"):
    """
    Ekstrem Mz dan Vy per garis memanjang untuk satu kombinasi.
    Mz memakai konvensi sagging positif: M = -Mz_i di ujung-i dan
    M = +Mz_j di ujung-j (eleForce memberi gaya ujung elemen, sehingga
    Mz_i dan Mz_j untuk momen internal yang sama berlawanan tanda).
    """
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
            for cat, sisi in (("Mz_i", "x1"), ("Mz_j", "x2")):
                lo, hi = env[cat][t]
                if cat == "Mz_i":          # ujung-i: tanda dibalik (sagging +)
                    lo, hi = -hi, -lo
                if lo < mz_min[0]:
                    mz_min = (lo, ele[t][sisi])
                if hi > mz_max[0]:
                    mz_max = (hi, ele[t][sisi])
            for cat in ("Vy_i", "Vy_j"):
                vmaks = max(vmaks, abs(env[cat][t][0]), abs(env[cat][t][1]))
            tmaks = max(tmaks, abs(env["T_i"][t][0]), abs(env["T_i"][t][1]))
        print("{:>8.2f} {:>12.1f} {:>10.2f} {:>12.1f} {:>10.2f} {:>12.1f} "
              "{:>12.1f}".format(ele[tags[0]]["z"], mz_min[0], mz_min[1],
                                 mz_max[0], mz_max[1], vmaks, tmaks))
    print()

def plot_gaya_dalam(hasil, Lenv, elemen_result, out_dir,
                    kombinasi="Strength I"):
    """
    Plot envelope gaya dalam satu kombinasi untuk 5 garis memanjang.

    Output:
      - Mz_<kombinasi>.png
      - Vy_<kombinasi>.png
      - T_<kombinasi>.png

    Nilai envelope dihitung dengan kombinasi_envelope(), sehingga
    konsisten dengan tabel print_gaya_dalam().
    """
    import os
    import matplotlib.pyplot as plt

    env = kombinasi_envelope(hasil, Lenv, kombinasi)

    ele = {
        e["tag"]: e
        for e in elemen_result["memanjang"]
    }

    garis = sorted({
        e["garis"] for e in ele.values()
    })

    os.makedirs(out_dir, exist_ok=True)

    # --------------------------------------------------------
    # Helper: susun titik sepanjang satu garis
    # --------------------------------------------------------
    def data_garis(j, cat_i, cat_j, flip_i=False):
        data = []

        tags = sorted(
            [t for t, e in ele.items() if e["garis"] == j],
            key=lambda t: ele[t]["x1"]
        )

        for t in tags:
            e = ele[t]

            lo_i, hi_i = env[cat_i][t]
            if flip_i:                     # sagging positif
                lo_i, hi_i = -hi_i, -lo_i
            data.append((e["x1"], lo_i, hi_i))

            data.append(
                (e["x2"], env[cat_j][t][0], env[cat_j][t][1])
            )

        # Gabungkan titik dengan x sama
        data.sort(key=lambda p: p[0])

        return data

    # --------------------------------------------------------
    # Plot satu besaran
    # --------------------------------------------------------
    def plot_env(cat_i, cat_j, ylabel, filename, mode="signed",
                 flip_i=False):
        fig, ax = plt.subplots(figsize=(14, 6))

        for j in garis:
            data = data_garis(j, cat_i, cat_j, flip_i)

            xs = [p[0] for p in data]

            if mode == "signed":
                ymin = [p[1] for p in data]
                ymax = [p[2] for p in data]

                ax.plot(
                    xs, ymin,
                    marker="o",
                    markersize=2,
                    label="z = {:.2f} m — min".format(
                        ele[next(
                            t for t in ele
                            if ele[t]["garis"] == j
                        )]["z"]
                    )
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
                    label="z = {:.2f} m".format(
                        ele[next(
                            t for t in ele
                            if ele[t]["garis"] == j
                        )]["z"]
                    )
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
        flip_i=True
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
        "T_i_min", "T_i_max",
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
            ])

    print("CSV gaya dalam per elemen disimpan: {}".format(path_csv))
    print("Jumlah garis longitudinal: {}".format(len(garis)))


def hasil_total_segmen(hasil, elemen_result):
    """
    Jumlahkan gaya ujung kelima garis per segmen, untuk SETIAP kasus dasar.
    Key = (x1, x2, unit). Penjumlahan dilakukan per kasus SEBELUM envelope,
    supaya ekstrem total berasal dari kasus beban yang sama (simultan).
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
    ujung-i segmen kanan; keduanya berbeda di tumpuan (loncatan = reaksi).
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
    """Cetak ringkasan dan simpan reaksi.json / reaksi.csv."""
    urutan = tambah_reaksi_support(hasil, bc_list)
    Lenv = envelope_hidup(hasil, kasus)

    print_reaksi(hasil, Lenv, urutan, ["Service I", "Strength I"])
    print_lendutan(hasil, Lenv, node_result, "Service I")

    if elemen_result is not None:
        print_gaya_dalam(hasil, Lenv, elemen_result, "Strength I")

        plot_gaya_dalam(
            hasil,
            Lenv,
            elemen_result,
            out_dir,
            kombinasi="Strength I"
        )

        env = kombinasi_envelope(hasil, Lenv, "Strength I")
        simpan_gaya_dalam(
            os.path.join(out_dir, "gaya_dalam.csv"),
            elemen_result,
            env,
        )
        simpan_gaya_dalam_total(
            os.path.join(out_dir, "gaya_dalam_total.csv"),
            elemen_result,
            hasil,
            kasus,
        )

    simpan_reaksi(os.path.join(out_dir, "reaksi.json"),
                  os.path.join(out_dir, "reaksi.csv"),
                  hasil, Lenv, urutan, bentang,
                  [k for k in loads.KOMBINASI if "Extreme" not in k])
    return Lenv, urutan
