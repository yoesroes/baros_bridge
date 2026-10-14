"""Pemeriksaan integritas numerik dan kewajaran dasar hasil analisis deck.

Satuan default: kN, m. Modul ini tidak menyatakan kapasitas desain tanpa data
kapasitas dan standar desain yang eksplisit.
"""
from __future__ import annotations

import math


def _status(ok):
    return "PASS" if ok else "ERROR"


def jalankan_pemeriksaan(hasil, kasus, elemen_result, bc_list,
                         toleransi_keseimbangan=0.01,
                         batas_lendutan_mm=None):
    """Kembalikan daftar temuan terstruktur; tidak mengubah hasil analisis."""
    temuan = []
    panjang = {e["tag"]: float(e.get("L_aksial", e["x2"] - e["x1"]))
               for e in elemen_result.get("memanjang", [])}

    # SC-01: kasus dan data respons tersedia serta numerik.
    missing = sorted(set(kasus) - set(hasil))
    temuan.append({
        "id": "SC-01", "nama": "Kelengkapan kasus analisis",
        "status": _status(not missing),
        "nilai": len(hasil), "kriteria": "Semua kasus yang diminta memiliki hasil",
        "detail": "Kasus tanpa hasil: {}".format(missing) if missing else
                  "Semua {} kasus memiliki hasil.".format(len(kasus)),
    })

    invalid = []
    for nama, h in hasil.items():
        for kategori, nilai in h.items():
            if not isinstance(nilai, dict):
                continue
            for key, value in nilai.items():
                if not isinstance(value, (int, float)) or not math.isfinite(value):
                    invalid.append("{}:{}:{}".format(nama, kategori, key))
    temuan.append({
        "id": "SC-02", "nama": "Integritas nilai numerik",
        "status": _status(not invalid), "nilai": len(invalid),
        "kriteria": "Tidak ada nilai nonnumerik, NaN, atau tak hingga",
        "detail": "Nilai tidak valid: {}".format(invalid[:20]) if invalid else
                  "Seluruh nilai respons berupa angka finite.",
    })

    # SC-03: bandingkan beban total kasus dengan integrasi ulang beban elemen
    # dan jumlah beban nodal, lalu bandingkan dengan reaksi hasil analisis.
    load_errors, eq_errors = [], []
    for nama, k in kasus.items():
        if nama not in hasil:
            continue
        w_total = sum(float(w) * panjang.get(tag, 0.0)
                      for tag, w in k.get("ele", {}).items())
        p_total = sum(float(p) for p in k.get("node", {}).values())
        total_hitung = w_total + p_total
        total_kasus = float(k.get("total", 0.0))
        scale_load = max(1.0, abs(total_hitung), abs(total_kasus))
        load_err = abs(total_hitung - total_kasus) / scale_load
        if load_err > toleransi_keseimbangan:
            load_errors.append({"kasus": nama, "relatif": load_err,
                                "total_tercatat": total_kasus,
                                "total_hitung": total_hitung})

        reaksi = hasil[nama].get("R", {})
        sum_r = sum(float(v) for v in reaksi.values())
        # Reaksi positif ke atas, beban positif/negatif mengikuti model; untuk
        # beban gravitasi negatif, sum(R) + total_beban harus mendekati nol.
        residual = abs(sum_r + total_kasus) / max(1.0, abs(total_kasus))
        if residual > toleransi_keseimbangan:
            eq_errors.append({"kasus": nama, "relatif": residual,
                              "sum_R": sum_r, "total_beban": total_kasus})

    temuan.append({
        "id": "SC-03", "nama": "Audit independen total beban",
        "status": _status(not load_errors), "nilai": len(load_errors),
        "kriteria": "Integrasi ulang beban elemen + beban nodal cocok dengan total kasus",
        "detail": "Selisih: {}".format(load_errors[:10]) if load_errors else
                  "Total beban cocok untuk seluruh kasus yang tersedia.",
    })
    temuan.append({
        "id": "SC-04", "nama": "Keseimbangan vertikal reaksi",
        "status": _status(not eq_errors), "nilai": len(eq_errors),
        "kriteria": "|sum(Ry) + total beban| / max(1, |total beban|) <= {:.3%}".format(toleransi_keseimbangan),
        "detail": "Kasus tidak seimbang: {}".format(eq_errors[:10]) if eq_errors else
                  "Reaksi seimbang terhadap total beban kasus.",
    })

    # SC-05: batas lendutan opsional; tidak menerapkan L/800 secara otomatis.
    if batas_lendutan_mm is not None:
        max_u = max((abs(float(u)) * 1000.0
                     for h in hasil.values()
                     for u in h.get("Uy", {}).values()), default=0.0)
        ok = max_u <= float(batas_lendutan_mm)
        temuan.append({
            "id": "SC-05", "nama": "Penyaringan lendutan",
            "status": "PASS" if ok else "WARNING", "nilai": max_u,
            "kriteria": "|Uy|max <= {:.3f} mm (batas masukan pengguna)".format(batas_lendutan_mm),
            "detail": "Nilai ini hanya screening; bukan verifikasi semua kriteria layan.",
        })
    else:
        temuan.append({
            "id": "SC-05", "nama": "Penyaringan lendutan",
            "status": "NOT ASSESSED", "nilai": None,
            "kriteria": "Memerlukan batas lendutan yang ditetapkan untuk proyek",
            "detail": "Lendutan tetap dilaporkan; tidak ada batas universal yang diasumsikan.",
        })

    # SC-06: validasi peta node reaksi ke bearing fisik.
    mapped_nodes = {b["node"] for b in bc_list}
    missing_nodes = sorted(mapped_nodes - set(hasil.get("D1", {}).get("R", {})))
    ids = [b.get("bearing") for b in bc_list]
    duplicate_ids = sorted({i for i in ids if ids.count(i) > 1})
    ok_map = not missing_nodes and not duplicate_ids
    temuan.append({
        "id": "SC-06", "nama": "Pemetaan bearing fisik",
        "status": _status(ok_map), "nilai": len(bc_list),
        "kriteria": "Node reaksi tersedia dan ID bearing tidak duplikat",
        "detail": "Node hilang={}, ID duplikat={}".format(missing_nodes, duplicate_ids),
    })
    return temuan
