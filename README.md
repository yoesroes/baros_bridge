# Jembatan Baros — Analisis Struktur Grillage 3D

Repositori ini berisi skrip dan data untuk analisis struktur jembatan flyover beton bertulang (9 bentang, 8 pier, 2 abutment) menggunakan OpenSeesPy. Pipeline mencakup ekstraksi geometri dari DXF, perhitungan properti penampang, pemodelan 3D, dan analisis struktur.

## Ringkasan Proyek
- **Dimensi Utama**: Panjang total 204.49 m, Lebar deck 10.0 m, Tinggi box girder 1.5 m.
- **Support**: 10 titik (2 Abutment, 8 Pier) dengan 4 Expansion Joint (A1, P2, P7, A2).
- **Metode Analisis**: Grillage 3D (240 node, 427 elemen) dengan properti penampang yang bervariasi per segmen.
- **Standar Beban**: SNI 1725:2016.

## Struktur Direktori
```text
baros_bridge/
├── Clean/              # Single source of truth (project_data.py, mapping)
├── core/               # Modul analisis utama (loads, materials, sections, nodes, elements, BC)
├── components/         # Definisi komponen struktur (box_girder, pier, pile_cap, dll.)
├── Temp/               # Script eksperimen & utilitas (ekstraksi DXF, hitung J, visualisasi)
├── output/             # Hasil analisis (CSV, JSON, model FreeCAD)
├── docs/               # Catatan perubahan dan dokumentasi tambahan
└── data/DXF/           # File sumber DXF (tidak di-commit)
```

## Persiapan & Instalasi

1. **Clone dan Setup Environment**
   ```bash
   git clone https://github.com/yoesroes/baros_bridge.git
   cd baros_bridge
   python3 -m venv sipil && source sipil/bin/activate
   pip install -r requirements.txt
   ```

2. **Visualisasi (Opsional)**
   Proyek ini menggunakan FreeCAD 1.1.3+ untuk visualisasi 3D. Unduh AppImage dan berikan izin eksekusi:
   ```bash
   chmod +x FreeCAD_1.1.3-Linux-x86_64-py311.AppImage
   ```

## Alur Kerja (Workflow)

1. **Ekstraksi & Perhitungan Penampang**  
   Jalankan skrip di folder `Temp/` untuk mengekstrak geometri dari DXF dan menghitung properti ($A, I_x, I_y, J$) menggunakan `sectionproperties`.
   ```bash
   cd Temp
   python3 extract_hollow_net.py  # Contoh: ekstraksi penampang box hollow
   ```

2. **Verifikasi Data Proyek**  
   Pastikan data ter-load dengan benar dari *single source of truth*:
   ```bash
   cd Clean
   python3 -c "import project_data as pd; print('Total bentang:', len(pd.SPANS))"
   ```

3. **Pemodelan & Analisis OpenSeesPy**  
   Jalankan modul di folder `core/` secara berurutan untuk membangun model:
   ```bash
   cd core
   python3 loads.py
   python3 materials.py
   python3 sections.py
   python3 nodes.py
   python3 elements.py
   python3 boundary_condition.py
   # python3 analysis.py  # (Sedang dikembangkan)
   ```

## Status Pengembangan

- [x] Ekstraksi geometri DXF & perhitungan properti penampang (Box Girder, Pier)
- [x] Mapping penampang sepanjang bentang (38 segmen)
- [x] Pemodelan Grillage 3D (Node, Elemen, Boundary Condition)
- [x] Definisi beban (SNI 1725) dan material
- [x] **Eksekusi analisis statis & validasi keseimbangan gaya (Reaksi = Beban)** ✅
- [ ] Visualisasi gaya-gaya dalam (Momen, Geser, Torsi) dan respons perletakan
- [ ] Perbaikan bug pada modul `output.py`
- [ ] Penambahan *automated test* untuk validasi hasil analisis

---

## 🏗️ Catatan Arsitektur Repositori (Pemisahan Scope)

Repositori ini difokuskan secara khusus pada **pemodelan dan analisis global Grillage 3D** serta validasi keseimbangan gaya makro. Untuk menjaga modularitas, kebersihan kode, dan *single responsibility principle*, perhitungan detail berikut dikelola di repositori terpisah:

1. **Desain Gaya Prategang (Prestressing):** Perhitungan kebutuhan tendon, profil kabel, dan verifikasi tegangan SLS/ULS dikerjakan di repositori khusus prategang.
2. **Desain Detail Substruktur & Superstruktur:** Perhitungan kapasitas penampang lokal, *pile cap*, *bored pile*, dan analisis *p-y curve* tanah tidak disatukan dalam repositori besar ini. Repositori ini hanya bertugas menyediakan output reaksi tumpuan yang akurat sebagai *input* bagi modul desain terpisah tersebut.

## Catatan Teknis
- **Konsistensi Satuan**: Model OpenSeesPy menggunakan **kN** dan **m**. Pastikan hasil ekstraksi dari `sectionproperties` (yang sering kali dalam mm) dikonversi ke meter sebelum dimasukkan ke dalam model.
- **Konstanta Torsi (J)**: Nilai $J$ untuk penampang hollow dihitung menggunakan pendekatan *warping FEM* melalui `sectionproperties` untuk akurasi yang lebih tinggi dibanding estimasi manual.

## Lisensi & Kontak
Kode ini disediakan untuk tujuan pembelajaran dan referensi teknis. Penggunaan komersial atau redistribusi tanpa izin tidak diperbolehkan.  
Untuk kolaborasi atau pertanyaan teknis: [yusrusnika84@gmail.com](mailto:yusrusnika84@gmail.com) | GitHub: [@yoesroes](https://github.com/yoesroes)
```

