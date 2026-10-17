# core/review.py
"""
Jalankan analisis penuh, pemeriksaan kewajaran, rekomendasi desain,
visualisasi, dan laporan siap cetak (DOCX + PDF).

Jalankan dari root repo:
    python -m core.review
Opsi:
    --tanpa-laporan-lama   lewati output.laporan() (CSV/JSON/PNG lama)
    --nama-penyusun "Nama" nama pada sampul laporan

Keluaran di output/ dan output/laporan/:
    laporan/Laporan_Kewajaran_Desain_Baros.docx / .pdf
    laporan/gambar/*.png            denah model, beban nodal, diagram gaya
    laporan/beban_nodal_ekuivalen.csv
    laporan/gaya_total_desain_profil.csv
    laporan/review_temuan.json / .csv
"""

import contextlib
import csv
import datetime
import io
import json
import os
import subprocess
import sys

import openseespy.opensees as ops

from project import project_data as pdata
from project import materials
from core import (analysis, boundary_condition as bc, design_review,
                  elements, gaya_total, laporan_desain, loads, nodes, output,
                  section_strips, visualisasi)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _fmt(x, nd=1):
    if x is None:
        return "-"
    if isinstance(x, str):
        return x
    return "{:,.{}f}".format(x, nd)


def _commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=BASE_DIR,
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "tidak tersedia"


# ------------------------------------------------------------------
# 1. BANGUN MODEL DAN JALANKAN
# ------------------------------------------------------------------
def bangun_dan_jalankan(verbose=False):
    ops.wipe()
    ops.model("basic", "-ndm", 3, "-ndf", 6)
    node_result = nodes.buat_semua_node(pdata.SECTION_MAP, pdata.SUPPORTS)
    elemen_result = elements.buat_semua_elemen(
        node_result, pdata.SECTION_MAP, pdata.BOX_SECTIONS)
    bc_list = bc.terapkan_bc(node_result, pdata.SUPPORTS)
    bentang = analysis.daftar_bentang(pdata.SUPPORTS)
    L_E = loads.hitung_L_ekuivalen([b["L"] for b in bentang])
    kasus, bentang = analysis.bangun_kasus(
        node_result, elemen_result, pdata.BOX_SECTIONS, pdata.SUPPORTS,
        L_E=L_E)
    hasil = analysis.jalankan_semua(kasus, node_result, elemen_result,
                                    bc_list, verbose=verbose)
    return node_result, elemen_result, bc_list, bentang, kasus, hasil, L_E


# ------------------------------------------------------------------
# 2. ISI LAPORAN
# ------------------------------------------------------------------
STATUS_URUT = design_review.STATUS


def susun_laporan(d):
    k = d["konfig"]
    temuan, rekom, data_kurang = d["temuan"], d["rekom"], d["data_kurang"]
    hitung = {s: sum(1 for t in temuan if t["status"] == s)
              for s in STATUS_URUT}
    B = []

    # ---- sampul
    B.append(("title", "LAPORAN KEWAJARAN HASIL ANALISIS DAN TINJAUAN DESAIN",
              "Jembatan Baros - Model Grillage 3D (OpenSeesPy)"))
    B.append(("kv", [
        ("Proyek / jembatan", pdata.INFO["nama"]),
        ("Versi model (git)", d["commit"]),
        ("Tanggal analisis", d["tanggal"]),
        ("Disusun oleh", d["penyusun"]),
        ("Satuan", "kN, m, kPa (reaksi positif ke atas)"),
        ("Solver", d["solver"]),
        ("Status laporan", "DRAFT - SCREENING. Bukan sertifikasi desain; "
                           "tidak menggantikan pemeriksaan kode dan tinjauan "
                           "engineer."),
    ]))
    B.append(("pagebreak",))

    # ---- ringkasan eksekutif
    B.append(("h1", "1. Ringkasan eksekutif"))
    B.append(("table", {
        "header": ["Status", "Jumlah", "Arti"],
        "rows": [
            ["ERROR", hitung["ERROR"], "analisis/data tidak valid"],
            ["CAPACITY EXCEEDANCE", hitung["CAPACITY EXCEEDANCE"],
             "demand > kapasitas terverifikasi"],
            ["WARNING", hitung["WARNING"], "perlu tinjauan engineer"],
            ["NOT ASSESSED", hitung["NOT ASSESSED"],
             "data/ambang belum tersedia"],
            ["PASS", hitung["PASS"], "kriteria terkonfigurasi terpenuhi"]],
        "widths": [4.5, 2.0, 8.0], "status_col": 0, "font": 9,
        "caption": "Tabel 1. Rekap temuan ({} pemeriksaan)".format(
            len(temuan))}))
    if rekom:
        B.append(("p", "Temuan yang perlu perhatian:"))
        B.append(("bullets", [
            "[{}] {} - {}".format(r["status"], r["id"], r["ringkasan"])
            + (" " + r["bukti"] if r["bukti"] else "")
            for r in rekom]))
    B.append(("p", "Hasil utama (beban desain Strength I-V): " + "; ".join(
        "unit {} Mu+ = {} kN.m, Mu- = {} kN.m, Vu = {} kN, Tu = {} kN.m"
        .format(u, _fmt(r["M_pos"][0], 0), _fmt(r["M_neg"][0], 0),
                _fmt(r["V_maks"][0], 0), _fmt(r["T_maks"][0], 0))
        for u, r in sorted(d["ekstrem"].items())) + "."))
    B.append(("note", "Pernyataan seperti 'bearing overload' hanya dibuat "
                      "bila reaksi telah dipetakan ke bearing fisik dan "
                      "dibandingkan dengan kapasitas terverifikasi (DC-01). "
                      "Tanpa data kapasitas, laporan hanya memberi reaksi "
                      "demand dan perbandingan dengan beban rencana pada "
                      "tabel bearing."))
    B.append(("pagebreak",))

    # ---- lingkup dan asumsi
    nr, er = d["node_result"], d["elemen_result"]
    B.append(("h1", "2. Lingkup model dan asumsi"))
    B.append(("kv", [
        ("Geometri", "{} bentang, {} tumpuan (A1, P1-P8, A2), panjang total "
         "{:.2f} m; unit menerus dipisah EJ di P2 dan P7 ({} unit)".format(
             pdata.INFO["jumlah_bentang"], pdata.INFO["jumlah_support"],
             pdata.INFO["panjang_total"], nr["n_unit"])),
        ("Grillage", "{} garis memanjang pada z = {} m; {} stasiun; {} node "
         "grid, {} elemen memanjang, {} elemen melintang".format(
             len(nr["z_garis"]),
             ", ".join("{:+.2f}".format(z) for z in nr["z_garis"]),
             len(nr["stasiun"]), nr["n_node"], len(er["memanjang"]),
             len(er["melintang"]))),
        ("Referensi strip (z_ref)", ", ".join(
            "{:+.2f}".format(z) for z in nr["z_ref"]) + " m"),
        ("Penampang", "solid, hollow (4 drum void), tumpuan (diafragma); "
         "total A, Ix, Iy, J dari project_data.BOX_SECTIONS (BELUM "
         "diaudit) dan dibagi ke garis oleh section_strips"),
        ("Tumpuan", "{} bearing fisik (B1-B24) pada z = +/-0.76 m "
         "(abutment) dan +/-0.47 m (pier head); lengan kaku ke garis "
         "terdekat".format(len(d["bc_list"]))),
        ("Material", "beton box f'c = {:.1f} MPa, E = {:.3e} kPa; baja "
         "tulangan fy = {:.0f} MPa".format(loads.FPC_BOX / 1000,
                                            materials.E_BOX,
                                            materials.FY / 1000)),
        ("Beban", "D1 berat sendiri {:,.0f} kN; D2 mati tambahan {:,.0f} kN; "
         "BTR {} kPa, KEL {} kN/m, FBD {:.2f}; kombinasi SNI 1725:2016"
         .format(-d["kasus"]["D1"]["total"], -d["kasus"]["D2"]["total"],
                 loads.Q_BTR, loads.P_KEL, loads.hitung_fbd(d["L_E"]))),
    ]))
    elev = nodes.elevasi_model
    B.append(("table", {
        "header": ["Bentang", "x awal (m)", "x akhir (m)", "L horizontal (m)",
                   "Beda elevasi (m)", "Kelandaian (%)", "L sumbu (m)"],
        "rows": [[b["nama"], _fmt(b["x1"], 3), _fmt(b["x2"], 3),
                  _fmt(b["L"], 3), _fmt(elev(b["x2"]) - elev(b["x1"]), 3),
                  _fmt(100 * (elev(b["x2"]) - elev(b["x1"])) / b["L"], 2),
                  _fmt(((elev(b["x2"]) - elev(b["x1"])) ** 2
                        + b["L"] ** 2) ** 0.5, 3)]
                 for b in d["bentang"]],
        "widths": [2.6, 2.2, 2.2, 2.6, 2.6, 2.4, 2.4], "font": 8,
        "caption": "Tabel 2. Bentang (antar tumpuan) dan alinyemen vertikal "
                   "(elevasi relatif A1)"}))
    B.append(("table", {
        "header": ["Beban", "Dasar panjang kN/m", "Uraian"],
        "rows": [
            ["D1 berat sendiri", analysis.DASAR_PANJANG["D1"],
             "gamma x A per panjang sumbu gelagar"],
            ["D2 mati tambahan", analysis.DASAR_PANJANG["D2"],
             "aspal, air, barrier per panjang sumbu"],
            ["BTR", analysis.DASAR_PANJANG["BTR"],
             "q (kPa) pada luas denah lajur; dikonversi ke per panjang "
             "sumbu dengan cos a"],
            ["KEL", "titik vertikal", "beban garis lajur; nodal bila di stasiun, "
             "beban titik di dalam elemen bila tidak; digeser tiap 0.1 panjang "
             "bentang dan tepat di tumpuan"]],
        "widths": [3.2, 3.6, 10], "font": 8.5,
        "caption": "Tabel 2b. Dasar panjang dan orientasi beban. Semua beban "
                   "gravitasi diuraikan ke sumbu lokal (Wy = q cos a, "
                   "Wx = q sin a) sehingga resultan tetap vertikal."}))
    B.append(("table", {
        "header": ["Tipe", "A (m2)", "Ix (m4)", "Iy (m4)", "J (m4)",
                   "Panjang (m)"],
        "rows": [[t, _fmt(s["A"], 4), _fmt(s["Ix"], 4), _fmt(s["Iy"], 3),
                  _fmt(s["J"], 4),
                  _fmt(sum(b - a for a, b, tt in pdata.SECTION_MAP
                           if tt == t), 2)]
                 for t, s in pdata.BOX_SECTIONS.items()],
        "widths": [3, 2.5, 2.5, 2.5, 2.5, 3], "font": 8.5,
        "caption": "Tabel 3. Properti penampang total yang dipakai"}))
    B.append(("table", {
        "header": ["Bearing", "Tumpuan", "Unit", "Tipe", "z (m)",
                   "Fixity (ux,uy,uz)"],
        "rows": [[b["bearing"], b["support"], b["unit"], b["tipe"],
                  _fmt(b["z"], 2), str(b["fixity"][:3])]
                 for b in sorted(d["bc_list"],
                                 key=lambda b: int(b["bearing"][1:]))],
        "widths": [2, 2, 1.5, 2, 2, 4], "font": 8,
        "caption": "Tabel 4. Bearing dan kondisi tumpuan di model"}))
    B.append(("table", {
        "header": ["Kombinasi", "D1", "D2", "L", "Keterangan"],
        "rows": [[n, v.get("D1"), v.get("D2"), v.get("L"),
                  v.get("description", "")]
                 for n, v in loads.KOMBINASI.items()],
        "widths": [3, 1.5, 1.5, 1.5, 8], "font": 8,
        "caption": "Tabel 5. Kombinasi pembebanan (faktor numerik dalam kode)"}))
    B.append(("h2", "Keterbatasan model yang diketahui"))
    B.append(("bullets", [
        "Pier, pier head, pile cap, pondasi, dan bearing (kekakuan) tidak "
        "dimodelkan; tumpuan berupa tumpuan kaku di posisi bearing.",
        "Kasus beban yang dimodelkan hanya D1, D2, BTR, dan KEL. Beban "
        "angin, suhu, rem, prategang, dan gempa tidak ada sebagai kasus; "
        + d["catatan_kombinasi"],
        "BOX_SECTIONS belum diaudit; distribusi antar garis berasal dari "
        "geometri parametrik section_strips.",
        "Orientasi z (+ kanan menghadap +x), jarak bearing, dan sisi "
        "ganjil/genap bearing adalah asumsi dari data gambar.",
        "Gaya horizontal, movement, dan kapasitas bearing pada tabel "
        "bearing tidak dihitung di model ini.",
        "Gelagar mengikuti alinyemen vertikal (node y = elevasi relatif A1, "
        "interpolasi linear antar tumpuan) pada sumbu memanjang yang lurus; "
        "kelengkungan horizontal pada denah, superelevasi, dan kinks "
        "kelandaian antar elemen tidak dimodelkan.",
        "Grillage tidak menyelesaikan tegangan lokal (diafragma, angkur "
        "tendon, area bearing)."]))
    B.append(("pagebreak",))

    # ---- integritas
    B.append(("h1", "3. Integritas analisis"))
    inte = [t for t in temuan if t["id"] in
            ("SC-01", "SC-02", "SC-03", "SC-04", "SC-06", "SC-07", "SC-11",
             "SC-13", "SC-16", "SC-17")]
    B.append(("table", {
        "header": ["ID", "Pemeriksaan", "Status", "Detail"],
        "rows": [[t["id"], t["nama"], t["status"], t["detail"]]
                 for t in inte],
        "widths": [1.3, 3.8, 2.4, 9.5], "status_col": 2, "font": 7.5,
        "caption": "Tabel 6. Integritas numerik, keseimbangan, dan "
                   "akuntansi beban"}))
    B.append(("pagebreak",))

    # ---- respons global
    B.append(("h1", "4. Respons global"))
    B.append(("h2", "4.1 Model: node dan elemen"))
    for g in d["gambar_model"]:
        B.append(("image", g[0], 17.0, g[1]))
    B.append(("h2", "4.2 Beban nodal ekuivalen"))
    B.append(("p", "Beban merata pada elemen diubah menjadi gaya nodal "
                   "ekuivalen konsisten (Fy = wL/2 tiap ujung; Mz = +/-wL^2/12) "
                   "ditambah beban titik KEL. Total Fy semua node sama dengan "
                   "total beban kasus. Data lengkap seluruh kasus dan node "
                   "ada di beban_nodal_ekuivalen.csv."))
    B.append(("table", {
        "header": ["Kasus", "Total Fy (kN)", "Total beban kasus (kN)",
                   "Node berbeban", "Fy node maks (kN)"],
        "rows": d["ringkas_beban_nodal"],
        "widths": [5, 3, 3.5, 3, 3], "font": 8,
        "caption": "Tabel 7. Ringkasan beban nodal ekuivalen"}))
    for g in d["gambar_beban"]:
        B.append(("image", g[0], 17.0, g[1]))
    B.append(("pagebreak",))
    B.append(("h2", "4.3 Gaya dalam total: momen, geser, torsi"))
    B.append(("p", "Envelope kombinasi desain Strength I-V, jumlah semua "
                   "garis (momen sagging positif; geser = gaya ke atas di "
                   "kiri penampang; torsi terhadap sumbu jembatan = sum[T - "
                   "z*V], kaidah tangan kanan). Nilai disampel tiap sekitar "
                   "1 m di dalam elemen agar puncak parabola momen "
                   "tertangkap. KEL bergerak: dianalisis tiap 0.1 panjang "
                   "bentang (dan tepat di tumpuan); momen negatif memakai "
                   "KEL kedua pada bentang lain."))
    for g in d["gambar_gaya"]:
        B.append(("image", g[0], 17.0, g[1]))
    B.append(("table", {
        "header": ["Unit", "Mu+ (kN.m)", "x (m)", "Kombinasi", "Mu- (kN.m)",
                   "x (m)", "Kombinasi", "|Vu| (kN)", "x (m)", "|Tu| (kN.m)",
                   "x (m)"],
        "rows": [[u, _fmt(r["M_pos"][0], 0), _fmt(r["M_pos"][1], 1),
                  r["M_pos"][2], _fmt(r["M_neg"][0], 0),
                  _fmt(r["M_neg"][1], 1), r["M_neg"][2],
                  _fmt(r["V_maks"][0], 0), _fmt(r["V_maks"][1], 1),
                  _fmt(r["T_maks"][0], 0), _fmt(r["T_maks"][1], 1)]
                 for u, r in sorted(d["ekstrem"].items())],
        "widths": [1, 1.7, 1.2, 1.9, 1.7, 1.2, 1.9, 1.5, 1.2, 1.6, 1.2],
        "font": 7,
        "caption": "Tabel 8. Ekstrem gaya dalam desain per unit"}))
    B.append(("pagebreak",))
    B.append(("h2", "4.4 Reaksi per bearing"))
    tv = {r["bearing"]: r for r in d.get("tabel_vs_model", [])}
    rows = []
    for r in d["tabel_bearing"]:
        t = tv.get(r["bearing"])
        rows.append([r["bearing"], r["support"], r["tipe"],
                     _fmt(r["D1"], 0), _fmt(r["D2"], 0),
                     _fmt(r["layan_min"], 0), _fmt(r["layan_max"], 0),
                     _fmt(r["uls_max"], 0),
                     _fmt(t["sls_tabel_kN"], 0) if t else "-",
                     "{:.2f}".format(t["rasio_sls"]) if t else "-"])
    B.append(("table", {
        "header": ["Bearing", "Tumpuan", "Tipe", "D1", "D2", "Layan min",
                   "Layan maks", "Strength maks", "SLS tabel", "Model/tabel"],
        "rows": rows,
        "widths": [1.6, 1.8, 1.4, 1.5, 1.5, 1.8, 1.8, 2.0, 1.8, 1.8],
        "font": 7.5,
        "caption": "Tabel 9. Reaksi vertikal per bearing (kN, + ke atas). "
                   "Kolom SLS tabel = beban rencana pada TABEL BEARING "
                   "(bukan kapasitas)."}))
    B.append(("h2", "4.5 Lendutan beban hidup per bentang"))
    B.append(("table", {
        "header": ["Bentang", "L (m)", "delta maks (mm)", "L/delta"],
        "rows": [[r["bentang"], _fmt(r["L"], 2), _fmt(r["delta_mm"], 1),
                  _fmt(r["L_per_delta"], 0)] for r in d["tabel_lendutan"]],
        "widths": [4, 3, 3.5, 3], "font": 8.5,
        "caption": "Tabel 10. Lendutan beban hidup (BTR+KEL, envelope). "
                   "Ambang screening L/{} (bukan kriteria kode otomatis)."
                   .format(_fmt(k["batas_lendutan_rasio"], 0)
                           if k["batas_lendutan_rasio"] else "-")}))
    B.append(("pagebreak",))

    # ---- register
    B.append(("h1", "5. Register pemeriksaan kewajaran"))
    B.append(("table", {
        "header": ["ID", "Pemeriksaan", "Kriteria", "Nilai", "Status",
                   "Catatan"],
        "rows": [[t["id"], t["nama"], t["kriteria"],
                  _fmt(t["nilai"], 4) if isinstance(t["nilai"], float)
                  else (t["nilai"] if t["nilai"] is not None else "-"),
                  t["status"], t["detail"]] for t in temuan],
        "widths": [1.2, 2.8, 3.6, 1.4, 2.0, 6.0], "status_col": 4,
        "font": 6.8,
        "caption": "Tabel 11. Register pemeriksaan"}))
    B.append(("pagebreak",))

    # ---- temuan desain
    B.append(("h1", "6. Temuan dan rekomendasi desain"))
    if rekom:
        for r in rekom:
            B.append(("h2", "{} - {} [{}]".format(r["id"], r["judul"],
                                                 r["status"])))
            B.append(("p", "Ringkasan: " + r["ringkasan"]))
            B.append(("p", "Bukti: " + r["bukti"]))
            if r["penyebab"]:
                B.append(("p", "Kemungkinan penyebab:"))
                B.append(("bullets", r["penyebab"]))
            if r["tindakan"]:
                B.append(("p", "Tindakan yang disarankan:"))
                B.append(("bullets", r["tindakan"]))
    else:
        B.append(("p", "Tidak ada temuan WARNING, ERROR, atau CAPACITY "
                       "EXCEEDANCE."))
    B.append(("h2", "Data yang diperlukan agar pemeriksaan dapat dinilai"))
    B.append(("table", {
        "header": ["ID", "Pemeriksaan", "Kebutuhan"],
        "rows": [[x["id"], x["judul"], x["kebutuhan"]] for x in data_kurang],
        "widths": [1.5, 5, 10], "font": 8,
        "caption": "Tabel 12. Pemeriksaan NOT ASSESSED"}))
    B.append(("pagebreak",))

    # ---- benchmark
    B.append(("h1", "7. Perbandingan model referensi (SAP2000 / MIDAS)"))
    sc14 = next(t for t in temuan if t["id"] == "SC-14")
    B.append(("p", "Status: {}. {}".format(sc14["status"], sc14["detail"])))
    B.append(("p", "Protokol: (1) geometri, properti, material, tumpuan, "
                   "kasus, kombinasi, dan konvensi tanda identik; (2) "
                   "bandingkan besaran yang sama pada lokasi fisik yang "
                   "sama: reaksi total, reaksi per bearing, lendutan titik "
                   "terpilih, gaya penampang; (3) catat selisih absolut dan "
                   "persen dengan pita penerimaan yang ditetapkan sebelum "
                   "melihat hasil; (4) selidiki selisih, jangan menyetel "
                   "model hanya agar cocok; (5) simpan rekaman benchmark "
                   "(versi perangkat lunak, tanggal, asumsi, ekspor)."))
    if sc14["bukti"]:
        B.append(("table", {
            "header": ["Bearing", "Kombinasi", "Referensi (kN)", "Model (kN)",
                       "Selisih (kN)", "Selisih (%)"],
            "rows": [[r["bearing"], r["kombinasi"], _fmt(r["ref_kN"], 1),
                      _fmt(r["model_kN"], 1), _fmt(r["selisih_kN"], 1),
                      _fmt(r["selisih_pct"], 2)] for r in sc14["bukti"]],
            "widths": [2, 3, 3, 3, 3, 3], "font": 8,
            "caption": "Tabel 13. Perbandingan reaksi per bearing"}))
    B.append(("pagebreak",))

    # ---- kesimpulan
    B.append(("h1", "8. Kesimpulan dan keterbatasan"))
    verified = [t for t in temuan if t["status"] == "CAPACITY EXCEEDANCE"]
    B.append(("bullets", [
        "Temuan terverifikasi kapasitas: {}.".format(
            "{} item".format(len(verified)) if verified else
            "tidak ada (tidak ada kapasitas terverifikasi yang diberikan)"),
        "Peringatan screening (WARNING): {} item; wajib ditinjau engineer "
        "sebelum dipakai untuk keputusan desain.".format(hitung["WARNING"]),
        "Tidak dinilai (NOT ASSESSED): {} item karena data kapasitas, "
        "ambang, atau model referensi belum tersedia.".format(
            hitung["NOT ASSESSED"]),
        "Hasil analisis ini dihitung dari model grillage dengan asumsi pada "
        "bab 2; kesesuaian terhadap SAP2000/MIDAS belum dibuktikan.",
        "Laporan ini adalah screening otomatis; tidak menyatakan "
        "kecukupan desain menurut standar mana pun."]))

    # ---- lampiran
    B.append(("h1", "Lampiran A. Berkas keluaran"))
    B.append(("bullets", d["daftar_berkas"]))
    B.append(("h1", "Lampiran B. Konfigurasi ambang pemeriksaan"))
    B.append(("table", {
        "header": ["Parameter", "Nilai"],
        "rows": [[kk, str(v)] for kk, v in k.items()],
        "widths": [6, 10], "font": 8,
        "caption": "Tabel 14. Ambang SCREENING (ubah di project_data.REVIEW)"}))
    return B


# ------------------------------------------------------------------
# 3. DRIVER
# ------------------------------------------------------------------
def jalankan(out_dir=None, laporan_lama=True, penyusun="-"):
    out_dir = out_dir or os.path.join(BASE_DIR, "output")
    lap = os.path.join(out_dir, "laporan")
    gbr = os.path.join(lap, "gambar")
    os.makedirs(gbr, exist_ok=True)

    print(">>> Membangun model dan menjalankan analisis...")
    (node_result, elemen_result, bc_list, bentang, kasus, hasil,
     L_E) = bangun_dan_jalankan()

    if laporan_lama:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            urutan = output.tambah_reaksi_support(hasil, bc_list)
            output.laporan(hasil, kasus, node_result, bc_list, bentang,
                           out_dir, elemen_result)
        print("    output.laporan() selesai (CSV/JSON/PNG lama).")
    output.tambah_reaksi_support(hasil, bc_list)
    output.tambah_reaksi_bearing(hasil, bc_list)
    Lenv = output.envelope_hidup(hasil, kasus)
    kombinasi_semua = [c for c in loads.KOMBINASI if "Extreme" not in c]

    print(">>> Gaya dalam total (momen, geser, torsi)...")
    total, seg_n = gaya_total.total_per_kasus(hasil, kasus, elemen_result)
    desain = [c for c in loads.KOMBINASI if c.startswith("Strength")]
    env_gab, env_k, Lenv_t = gaya_total.envelope_desain(total, kasus, desain)
    ekstrem = gaya_total.ekstrem_per_unit(env_k, seg_n)
    prof = {kat: gaya_total.profil(env_gab, kat, seg_n)
            for kat in gaya_total.KATEGORI}
    sup_unit = sorted({(b["x"], b["support"], b["unit"]) for b in bc_list})
    gaya_png = visualisasi.plot_gaya_total(
        prof, sup_unit, gbr, "Envelope desain Strength I-V")
    visualisasi.simpan_profil_csv(
        os.path.join(lap, "gaya_total_desain_profil.csv"), prof)

    print(">>> Visualisasi model dan beban nodal...")
    coords = visualisasi.peta_koordinat(node_result, bc_list)
    smap = pdata.SECTION_MAP
    g_model = [
        (visualisasi.plot_model_denah(
            node_result, elemen_result, bc_list, coords, smap,
            os.path.join(gbr, "model_denah.png"), pdata.SUPPORTS),
         "Gambar 1. Denah node dan elemen per unit (latar = tipe penampang)")]
    g_model.append((visualisasi.plot_profil_elevasi(
        pdata.SUPPORTS, smap, os.path.join(gbr, "profil_elevasi.png")),
        "Gambar 2. Alinyemen vertikal dan kelandaian memanjang per bentang"))
    for nama, x in (("A1", pdata.SUPPORTS["A1"]["x"]),
                    ("P2", pdata.SUPPORTS["P2"]["x"])):
        g_model.append((visualisasi.plot_model_detail(
            node_result, elemen_result, bc_list, coords, smap, x, 6.0,
            os.path.join(gbr, "model_detail_{}.png".format(nama)),
            "Detail {}: nomor node, nomor elemen, bearing dan lengan kaku"
            .format(nama)),
            "Gambar {}. Detail di sekitar {}".format(len(g_model) + 1, nama)))

    eq = visualisasi.beban_ekuivalen_nodal(kasus, elemen_result)
    visualisasi.simpan_beban_ekuivalen(
        os.path.join(lap, "beban_nodal_ekuivalen.csv"), eq, coords)
    live_btr = max((n for n, v in kasus.items() if v["jenis"] == "BTR"
                    and abs(v["offset"]) < 1e-9),
                   key=lambda n: abs(kasus[n]["total"]))
    live_kel = min((n for n, v in kasus.items() if v["jenis"] == "KEL"
                    and abs(v["offset"]) < 1e-9
                    and v["bentang"] == kasus[live_btr]["bentang"]),
                   key=lambda n: abs((kasus[n]["f"] or 0.0) - 0.5))
    f = loads.KOMBINASI["Strength I"]
    komb = visualisasi.kombinasikan(eq, {"D1": f["D1"], "D2": f["D2"],
                                         live_btr: f["L"], live_kel: f["L"]})
    pilih = [("D1", eq["D1"], "D1 - berat sendiri"),
             ("D2", eq["D2"], "D2 - beban mati tambahan"),
             ("BTR", eq[live_btr], "BTR - {}".format(live_btr)),
             ("KEL", eq[live_kel], "KEL - {}".format(live_kel)),
             ("StrengthI", komb, "Strength I = {}D1 + {}D2 + {}(BTR+KEL) "
                                 "(bentang penentu)".format(
                                     f["D1"], f["D2"], f["L"]))]
    g_beban = []
    for kode, dd, judul in pilih:
        g_beban.append((visualisasi.plot_beban_nodal_denah(
            dd, node_result, coords, smap,
            os.path.join(gbr, "beban_nodal_{}_denah.png".format(kode)),
            "Beban nodal ekuivalen Fy - " + judul),
            "Gambar {}. Beban nodal ekuivalen (denah) - {}".format(
                len(g_model) + len(g_beban) + 1, judul)))
        g_beban.append((visualisasi.plot_beban_nodal_profil(
            dd, node_result, elemen_result, coords,
            os.path.join(gbr, "beban_nodal_{}_profil.png".format(kode)),
            "Beban nodal ekuivalen Fy sepanjang x - " + judul),
            "Gambar {}. Beban nodal ekuivalen (profil per garis) - {}"
            .format(len(g_model) + len(g_beban) + 1, judul)))
    ringkas_nodal = []
    for kode, dd, judul in pilih:
        tot = sum(v["Fy"] for v in dd.values())
        if kode in ("D1", "D2"):
            ref = kasus[kode]["total"]
        elif kode == "BTR":
            ref = kasus[live_btr]["total"]
        elif kode == "KEL":
            ref = kasus[live_kel]["total"]
        else:
            ref = (f["D1"] * kasus["D1"]["total"] + f["D2"]
                   * kasus["D2"]["total"] + f["L"] * (
                       kasus[live_btr]["total"] + kasus[live_kel]["total"]))
        ringkas_nodal.append([judul, _fmt(tot, 1), _fmt(ref, 1),
                              sum(1 for v in dd.values()
                                  if abs(v["Fy"]) > 1e-9),
                              _fmt(max(abs(v["Fy"]) for v in dd.values()), 1)])
    g_gaya = [(p, "Gambar {}. {}".format(
        len(g_model) + len(g_beban) + i + 1, c)) for i, (p, c) in enumerate(
        zip(gaya_png, ("Momen lentur total (envelope desain)",
                       "Geser total tegak lurus sumbu gelagar (envelope desain)",
                       "Torsi total terhadap sumbu jembatan (envelope "
                       "desain)")))]

    print(">>> Pemeriksaan kewajaran dan rekomendasi...")
    ctx = {"hasil": hasil, "kasus": kasus, "node_result": node_result,
           "elemen_result": elemen_result, "bc_list": bc_list,
           "bentang": bentang, "coords": coords, "Lenv": Lenv,
           "total": total, "seg_n": seg_n, "env_desain": env_gab,
           "ekstrem": ekstrem, "pdata": pdata, "loads": loads,
           "out_dir": out_dir, "base_dir": BASE_DIR,
           "kombinasi_semua": kombinasi_semua,
           "elevasi": nodes.elevasi_model,
           "dasar_panjang": analysis.DASAR_PANJANG}
    temuan = design_review.jalankan_review(ctx)
    rekom, data_kurang = design_review.buat_rekomendasi(temuan)
    for t in temuan:
        print("  [{:<19s}] {} {}".format(t["status"], t["id"], t["nama"]))

    with open(os.path.join(lap, "review_temuan.json"), "w") as fh:
        json.dump({"status": "SCREENING ONLY", "temuan": temuan,
                   "rekomendasi": rekom}, fh, indent=2, default=str)
    with open(os.path.join(lap, "review_temuan.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "nama", "status", "nilai", "kriteria", "detail",
                    "lokasi"])
        for t in temuan:
            w.writerow([t["id"], t["nama"], t["status"], t["nilai"],
                        t["kriteria"], t["detail"], t["lokasi"]])

    berkas = [
        "laporan/Laporan_Kewajaran_Desain_Baros.docx dan .pdf - laporan",
        "laporan/gambar/ - denah model, beban nodal, diagram M/V/T",
        "laporan/beban_nodal_ekuivalen.csv - Fy, Mz tiap node tiap kasus",
        "laporan/gaya_total_desain_profil.csv - profil M, V, T envelope",
        "laporan/review_temuan.json / .csv - register pemeriksaan",
        "reaksi_bearing.json / .csv, gaya_dalam*.csv, Mz/Vy/T_*.png - "
        "keluaran output.laporan()"]
    solver = os.environ.get("BAROS_SOLVER_LABEL") or "OpenSeesPy"
    sama = {}
    for nm, v in loads.KOMBINASI.items():
        kunci = tuple(sorted((a, b) for a, b in v.items()
                             if isinstance(b, (int, float))))
        sama.setdefault(kunci, []).append(nm)
    kembar = [", ".join(v) for v in sama.values() if len(v) > 1]
    catatan_kombinasi = (
        "kombinasi dengan faktor numerik identik di kode: "
        + "; ".join(kembar) + " (tinjau apakah memang sama atau masih "
        "placeholder)." if kembar else
        "tidak ada kombinasi dengan faktor numerik identik.")
    data = {"konfig": ctx["konfig"], "temuan": temuan, "rekom": rekom,
            "data_kurang": data_kurang, "node_result": node_result,
            "elemen_result": elemen_result, "bc_list": bc_list,
            "bentang": bentang, "kasus": kasus, "L_E": L_E,
            "ekstrem": ekstrem, "tabel_bearing": ctx["tabel_bearing"],
            "tabel_vs_model": ctx.get("tabel_vs_model", []),
            "tabel_lendutan": ctx["tabel_lendutan"],
            "gambar_model": g_model, "gambar_beban": g_beban,
            "gambar_gaya": g_gaya, "ringkas_beban_nodal": ringkas_nodal,
            "commit": _commit(), "penyusun": penyusun, "solver": solver,
            "tanggal": datetime.date.today().isoformat(),
            "daftar_berkas": berkas,
            "catatan_kombinasi": catatan_kombinasi}
    blok = susun_laporan(data)
    laporan_desain.render_docx(
        blok, os.path.join(lap, "Laporan_Kewajaran_Desain_Baros.docx"))
    laporan_desain.render_pdf(
        blok, os.path.join(lap, "Laporan_Kewajaran_Desain_Baros.pdf"))
    return data


if __name__ == "__main__":
    nama = "-"
    if "--nama-penyusun" in sys.argv:
        nama = sys.argv[sys.argv.index("--nama-penyusun") + 1]
    jalankan(laporan_lama="--tanpa-laporan-lama" not in sys.argv,
             penyusun=nama)
    print("SELESAI")
