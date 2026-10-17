# Jembatan Baros — Analisis Struktur Grillage 3D

Repositori ini berisi pipeline analisis struktur jembatan flyover beton bertulang (9 bentang, 8 pier, 2 abutment) menggunakan OpenSeesPy. Pipeline mencakup pemodelan grillage 3D, analisis statis, validasi keseimbangan gaya, dan review desain.

## Ringkasan Proyek

- **Dimensi Utama**: Panjang total 206.33 m (A1–A2: 204.49 m), Lebar deck 10.0 m, Tinggi box girder 1.5 m.
- **Support**: 10 titik (2 Abutment, 8 Pier) dengan 24 bearing dan 4 Expansion Joint (A1, P2, P7, A2).
- **Metode Analisis**: Grillage 3D (5 garis memanjang, 38 segmen penampang) dengan properti bervariasi per segmen.
- **Standar Beban**: SNI 1725:2016.
- **Kombinasi**: Service I–IV, Strength I–V, Extreme Event I–II.

## Struktur Direktori

```
├── project/            # Data proyek & material (single source of truth)
│   ├── __init__.py
│   ├── project_data.py # Geometri, section, bearing, beban
│   └── materials.py    # Parameter material (beton, baja)
├── core/               # Pipeline analisis utama
│   ├── __init__.py
│   ├── nodes.py              # Generate node grillage 3D
│   ├── elements.py           # Elemen memanjang & melintang
│   ├── section_strips.py     # Distribusi properti ke 5 garis
│   ├── sections.py           # Pembaca properti section total
│   ├── boundary_condition.py # BC bearing (MD, OD, FIX)
│   ├── loads.py              # Beban (D1, D2, BTR, KEL) & kombinasi
│   ├── analysis.py           # Eksekusi analisis statis
│   ├── output.py             # Output gaya dalam & reaksi
│   ├── gaya_total.py         # Integrasi gaya total
│   ├── sanity_checks.py      # Pemeriksaan kewajaran (SC-01 s/d SC-15)
│   ├── design_review.py      # Review desain bearing & lendutan
│   ├── review.py             # Runner review terpadu
│   ├── laporan_desain.py     # Generator laporan desain
│   ├── visualisasi.py        # Visualisasi hasil
│   └── bridge.py             # (Legacy) Model jembatan terpadu
├── tests/              # Automated tests (pytest)
├── benchmark/          # Benchmark vs model referensi (SAP2000/MIDAS)
├── docs/               # Dokumentasi tambahan
├── Clean/              # Data bersih
└── archive/legacy      # Arsip kode lama
```

## Pipeline Analisis

Urutan eksekusi pipeline (dari root repo):

```bash
python -m core.nodes              # 1. Generate node
python -m core.elements           # 2. Buat elemen
python -m core.boundary_condition # 3. Terapkan BC bearing
python -m core.loads              # 4. Hitung beban
python -m core.analysis           # 5. Analisis statis
python -m core.output             # 6. Output gaya dalam
python -m core.review             # 7. Review & sanity checks
```

## Persiapan & Instalasi

```bash
git clone https://github.com/yoesroes/baros_bridge.git
cd baros_bridge
python3 -m venv sipil && source sipil/bin/activate
pip install -r requirements.txt
```

## Testing

```bash
pytest                    # Jalankan semua test
pytest -v                 # Verbose
pytest tests/test_sanity_checks.py  # Test tertentu
```

## Status Pengembangan

- [x] Pemodelan Grillage 3D (Node, Elemen, BC bearing)
- [x] Definisi beban (SNI 1725) dan kombinasi
- [x] Eksekusi analisis statis & validasi keseimbangan gaya
- [x] Sanity checks (SC-01 s/d SC-15)
- [x] Design review (bearing, lendutan)
- [x] Automated tests
- [ ] Visualisasi gaya-gaya dalam interaktif
- [ ] Perbaikan bug pada modul `output.py`

## Catatan Arsitektur

Repositori ini difokuskan pada **pemodelan dan analisis global Grillage 3D** serta validasi keseimbangan gaya makro. Perhitungan detail berikut dikelola di repositori terpisah:

1. **Desain Gaya Prategang** — perhitungan tendon, profil kabel, verifikasi SLS/ULS.
2. **Desain Detail Substruktur & Superstruktur** — kapasitas penampang lokal, pile cap, bored pile, analisis p-y curve.

## Catatan Teknis

- **Satuan**: kN, m, kPa.
- **Konstanta Torsi (J)**: Dihitung dengan warping FEM melalui `sectionproperties`.
- **Konsistensi**: `project/project_data.py` adalah single source of truth untuk geometri.

### Pembebanan Lalu Lintas

Lebar jalan model (`ROAD_WIDTH`) adalah **9.00 m**. Untuk KEL/BGT, proyek
menerapkan intensitas nominal kode `P_KEL = 49.0 kN/m` pada seluruh lebar jalan
bersih. Dengan `FBD = 0.4`, intensitas transversal setelah FBD adalah **68.6
kN/m**, sehingga target magnitudo satu KEL adalah **617.40 kN** (`68.6 × 9.00`).

Penerapan pada lebar penuh 9.00 m merupakan **asumsi pemodelan konservatif
proyek** untuk mengantisipasi pembebanan, termasuk ketika sebagian area jalan
digunakan sepeda dan sepeda motor. Ini adalah keputusan proyek, bukan klaim
bahwa SNI 1725:2016 atau AASHTO mewajibkan penerapan KEL pada lebar penuh tersebut.

Aturan lebar ekuivalen 5.5 m × 100% + sisa × 50% (7.25 m untuk jalan 9.00 m)
tetap digunakan kode untuk BTR; aturan itu tidak digunakan untuk distribusi
KEL/BGT.

## Lisensi & Kontak

Kode ini disediakan untuk tujuan pembelajaran dan referensi teknis.

yusrusnika84@gmail.com | GitHub: [@yoesroes](https://github.com/yoesroes)
