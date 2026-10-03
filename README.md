# README.md 

Buat file `README.md` di root folder `~/Sipil/baros_bridge/`:

```bash
cd ~/Sipil/baros_bridge
nano README.md
```

Paste isi berikut:

---

```markdown
# Jembatan Baros — Analisis Struktur Jembatan 9 Bentang

[![Status](https://img.shields.io/badge/status-in%20progress-yellow)]()
[![Python](https://img.shields.io/badge/python-3.12-blue)]()
[![OpenSeesPy](https://img.shields.io/badge/OpenSeesPy-3.5+-green)]()
[![FreeCAD](https://img.shields.io/badge/FreeCAD-1.1.3-orange)]()

Analisis struktur jembatan beton bertulang dengan **9 bentang**, **8 pier**, dan **2 abutment** menggunakan OpenSeesPy. Proyek ini mencakup ekstraksi data dari DXF, visualisasi 3D, dan analisis struktur.

---

## 📋 Daftar Isi

- [Deskripsi Proyek](#deskripsi-proyek)
- [Data Proyek](#data-proyek)
- [Struktur Folder](#struktur-folder)
- [Requirements](#requirements)
- [Instalasi](#instalasi)
- [Cara Pakai](#cara-pakai)
- [Alur Analisis](#alur-analisis)
- [Data yang Sudah Diekstrak](#data-yang-sudah-diekstrak)
- [Tools & Library](#tools--library)
- [Status Pengembangan](#status-pengembangan)
- [Referensi](#referensi)
- [Lisensi](#lisensi)

---

## 📖 Deskripsi Proyek

Proyek ini bertujuan untuk:

1. **Ekstraksi data geometri** dari file DXF (penampang, profil memanjang, trase)
2. **Perhitungan properti penampang** (A, Ix, Iy, J) dengan `sectionproperties`
3. **Visualisasi 3D** dengan FreeCAD / Blender
4. **Analisis struktur** dengan OpenSeesPy (reaksi per support)
5. **Pembelajaran** perilaku struktur jembatan dari atas ke bawah

**Filosofi:** Analisis dari **atas** (beban) ke **bawah** (fondasi):

```
Deck → Bearing → Pier Head → Pier → Pile Cap → Bored Pile → Tanah
```

---

## 📊 Data Proyek

### Geometri Jembatan

| Parameter | Nilai | Satuan |
|-----------|-------|--------|
| Panjang total (A1–A2) | 204.4944 | m |
| Panjang total (dengan overhang) | 206.3293 | m |
| Jumlah bentang | 9 | — |
| Jumlah pier | 8 | — |
| Jumlah abutment | 2 | — |
| Jumlah expansion joint | 4 | — |
| Lebar deck | 10.0 | m |
| Tinggi box girder | 1.5 | m |

### Posisi Support

| Support | x (m) | Elevasi (mdpl) | Tipe |
|---------|-------|----------------|------|
| A1 | 0.0000 | 740.7678 | Abutment |
| P1 | 16.2472 | 741.4288 | Pier |
| P2 | 33.7472 | 742.2948 | Pier (EJ) |
| P3 | 51.2472 | 743.1698 | Pier |
| P4 | 74.7472 | 744.1168 | Pier |
| P5 | 112.7472 | 744.1168 | Pier |
| P6 | 130.2472 | 743.4688 | Pier |
| P7 | 155.2472 | 742.2198 | Pier (EJ) |
| P8 | 180.2472 | 740.9708 | Pier |
| A2 | 204.4944 | 739.7198 | Abutment |

### Panjang Bentang

| Segmen | Panjang (m) | Gradien (%) |
|--------|-------------|-------------|
| A1–P1 | 16.2472 | +4.068 |
| P1–P2 | 17.5000 | +4.949 |
| P2–P3 | 17.5000 | +5.000 |
| P3–P4 | 23.5000 | +4.030 |
| P4–P5 | 38.0000 | 0.000 |
| P5–P6 | 17.5000 | -3.703 |
| P6–P7 | 25.0000 | -4.996 |
| P7–P8 | 25.0000 | -4.996 |
| P8–A2 | 24.2472 | -5.160 |

### Expansion Joint

| EJ | Posisi |
|----|--------|
| EJ.1 | A1 |
| EJ.2 | P2 |
| EJ.3 | P7 |
| EJ.4 | A2 |

---

## 📁 Struktur Folder

```
Baros_bridge/
├── README.md
├── .gitignore
├── requirements.txt
│
├── Clean/                          # Script final
│   ├── project_data.py             # Data lengkap proyek
│   ├── deck_9span_analysis.py      # Analisis deck 9 bentang
│   └── ...
│
├── Temp/                           # Script eksperimen
│   ├── extract_tumpuan.py          # Ekstrak penampang tumpuan
│   ├── extract_hollow_net.py       # Ekstrak penampang hollow
│   ├── extract_blockout.py         # Ekstrak penampang blockout
│   ├── extract_pier_final.py       # Ekstrak penampang pier
│   ├── extract_profil.py           # Ekstrak profil memanjang
│   ├── generate_section_map.py     # Generate mapping penampang
│   ├── freecad_jembatan2.py        # Visualisasi FreeCAD
│   └── ...
│
├── output/                         # Output
│   ├── jembatan_freecad2.FCStd     # Model 3D FreeCAD
│   ├── reaksi_deck_9span.json      # Reaksi per support
│   └── screenshots/                # Screenshot visualisasi
│
├── data/
│   └── DXF/                        # File DXF (tidak di-commit)
│       ├── Penampang_tipikal.dxf
│       ├── Penampang_hollow.dxf
│       ├── Penampang_blockout.dxf
│       ├── Penampang_tumpuan.dxf
│       ├── penampang_pier_tipikal.dxf
│       ├── potongan_memanjang.dxf
│       └── ...
│
└── docs/                           # Dokumentasi
    ├── data_summary.md
    ├── mapping_penampang.md
    └── hasil_analisis.md
```

---

## ⚙️ Requirements

### Software

| Software | Versi | Kegunaan |
|----------|-------|----------|
| Python | 3.12+ | Bahasa pemrograman |
| FreeCAD | 1.1.3+ | Visualisasi 3D (AppImage) |
| Blender | 2.79b | Visualisasi alternatif |

### Python Libraries

```
openseespy>=3.5.0
sectionproperties>=2.1.0
ezdxf>=1.0.0
numpy>=1.20
scipy>=1.10
matplotlib>=3.5
shapely>=2.0
triangle>=20220202
cad-to-shapely>=0.5
```

---

## 🚀 Instalasi

### 1. Clone Repository

```bash
git clone https://github.com/USERNAME/baros_bridge.git
cd baros_bridge
```

### 2. Buat Virtual Environment (Opsional)

```bash
python3 -m venv sipil
source sipil/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install FreeCAD (AppImage)

```bash
# Download FreeCAD AppImage
wget https://github.com/FreeCAD/FreeCAD/releases/download/1.1.3/FreeCAD_1.1.3-Linux-x86_64-py311.AppImage

# Set executable
chmod +x FreeCAD_1.1.3-Linux-x86_64-py311.AppImage

# Jalankan
./FreeCAD_1.1.3-Linux-x86_64-py311.AppImage
```

---

## 💻 Cara Pakai

### A. Ekstrak Data dari DXF

```bash
cd Temp

# Ekstrak penampang box (4 tipe)
python3 extract_tumpuan.py
python3 extract_hollow_net.py
python3 extract_blockout.py

# Ekstrak penampang pier
python3 extract_pier_final.py

# Ekstrak profil memanjang
python3 extract_profil.py
```

**Output:** Properti penampang (A, Ix, Iy) untuk tiap tipe.

### B. Generate Mapping Penampang

```bash
cd Temp
python3 generate_section_map.py
python3 merge_section_map.py
```

**Output:** `SECTION_MAP` (38 segmen).

### C. Visualisasi 3D (FreeCAD)

```bash
cd Temp
~/Desktop/FreeCAD.AppImage --console freecad_jembatan2.py
```

**Output:** `output/jembatan_freecad2.FCStd`

**Buka di GUI:**
```bash
~/Desktop/FreeCAD.AppImage output/jembatan_freecad2.FCStd
```

### D. Analisis Struktur (OpenSeesPy)

```bash
cd Clean
python3 deck_9span_analysis.py
```

**Output:** `output/reaksi_deck_9span.json`

### E. Verifikasi Data

```bash
cd Clean
python3 -c "
import sys
sys.path.append('.')
import project_data as pd

print('SUPPORTS:', len(pd.SUPPORTS))
print('SPANS:', len(pd.SPANS))
print('SECTION_MAP:', len(pd.SECTION_MAP))
print('BOX_SECTIONS:', list(pd.BOX_SECTIONS.keys()))
print('Total panjang:', pd.INFO['panjang_total'], 'm')
"
```

---

## 🔄 Alur Analisis

```
┌─────────────────────────────────────────────────────────┐
│  1. EKSTRAKSI DATA DARI DXF                             │
│     - Penampang box (tipikal, hollow, blockout, tumpuan)│
│     - Penampang pier                                     │
│     - Profil memanjang (posisi & elevasi support)        │
│     - Koordinat bearing                                  │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  2. PERHITUNGAN PROPERTI PENAMPANG                      │
│     - A, Ix, Iy, J dengan sectionproperties             │
│     - Verifikasi dengan perhitungan manual               │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  3. MAPPING PENAMPANG SEPANJANG JEMBATAN                │
│     - Tumpuan di tiap support                            │
│     - Solid di area transisi                             │
│     - Hollow di tengah bentang                           │
│     - 38 segmen                                          │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  4. VISUALISASI 3D                                      │
│     - Deck, pier head, pier, abutment                    │
│     - Stopper & bearing                                  │
│     - FreeCAD / Blender                                  │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  5. ANALISIS STRUKTUR (OpenSeesPy)                      │
│     - Model deck 9 bentang                               │
│     - Section bervariasi per segmen                      │
│     - BC di 10 support                                   │
│     - Beban mati + hidup                                 │
│     - Reaksi per support                                 │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  6. ANALISIS SUBSTRUKTUR (Next)                         │
│     - Pier (fiber section + Mander)                      │
│     - Pile cap                                           │
│     - Bored pile + soil spring                           │
└─────────────────────────────────────────────────────────┘
```

---

## 📦 Data yang Sudah Diekstrak

### 1. Penampang Box Girder

| Tipe | A (m²) | Ix (m⁴) | Iy (m⁴) | Keterangan |
|------|--------|---------|---------|------------|
| **Solid** | 8.2231 | 1.4527 | 33.3927 | Transisi (tipikal) |
| **Hollow** | 7.7072 | 1.4392 | 32.8489 | Tengah bentang |
| **Tumpuan** | 7.9670 | 1.2986 | 33.3759 | Diafragma |

### 2. Penampang Pier

| Parameter | Nilai | Satuan |
|-----------|-------|--------|
| Lebar (b) | 2000 | mm |
| Tinggi (h) | 2500 | mm |
| Radius sudut (r) | 750 | mm |
| A | 4.7180 | m² |
| Ix | 2.2961 | m⁴ |
| Iy | 1.4600 | m⁴ |
| J | 4.375 | m⁴ |

### 3. Pier Head

| Tipe | H (m) | b_mel (m) | b_mem (m) | Pier |
|------|-------|-----------|-----------|------|
| tipe_1 | 2.0 | 3.7 | 2.5 | P3, P4, P5, P6, P8 |
| tipe_2 | 1.5 | 3.7 | 2.5 | P1 |
| tipe_EJ | 2.0 | 3.7 | 3.6 | P2, P7 |

### 4. Tinggi Pier

| Support | Tinggi (m) |
|---------|------------|
| A1 | 1.5 |
| P1 | 1.0 |
| P2 | 2.1 |
| P3 | 3.5 |
| P4 | 5.3 |
| P5 | 6.8 |
| P6 | 5.2 |
| P7 | 3.4 |
| P8 | 2.4 |
| A2 | 2.9 |

### 5. Stopper

| Parameter | Nilai | Satuan |
|-----------|-------|--------|
| Tinggi | 0.5 | m |
| Lebar | 0.92 | m |
| Panjang | 1.8 | m |

### 6. Material

| Parameter | Nilai | Satuan |
|-----------|-------|--------|
| E (modulus elastis) | 30 × 10⁶ | kPa |
| G (modulus geser) | 12.5 × 10⁶ | kPa |
| f'c (beton) | 35 × 10³ | kPa |
| fy (baja) | 420 × 10³ | kPa |
| γ (berat jenis) | 24.0 | kN/m³ |

---

## 🛠️ Tools & Library

### 1. OpenSeesPy

**Fungsi:** Analisis struktur nonlinear.

```python
import openseespy.opensees as ops

ops.model('basic', '-ndm', 3, '-ndf', 6)
ops.node(1, 0, 0, 0)
ops.element('elasticBeamColumn', 1, 1, 2, A, E, G, J, Iy, Iz, 1)
ops.analyze(1)
```

### 2. sectionproperties

**Fungsi:** Hitung properti penampang dari DXF.

```python
from sectionproperties.pre import Geometry
from sectionproperties.analysis import Section

geom = Geometry.from_dxf("penampang.dxf")
geom.create_mesh(mesh_sizes=[200])
sec = Section(geometry=geom)
sec.calculate_geometric_properties()

A = sec.get_area()
Ix, Iy, Ixy = sec.get_ic()
```

### 3. ezdxf

**Fungsi:** Baca/tulis file DXF.

```python
import ezdxf

doc = ezdxf.readfile("file.dxf")
msp = doc.modelspace()

for entity in msp:
    print(entity.dxftype(), entity.dxf.layer)
```

### 4. FreeCAD

**Fungsi:** Visualisasi 3D.

```python
import FreeCAD as App
import Part

doc = App.newDocument("Jembatan")
box = Part.makeBox(L, W, H)
obj = doc.addObject("Part::Feature", "Deck")
obj.Shape = box
```

### 5. Blender 2.79b

**Fungsi:** Visualisasi 3D alternatif.

```python
import bpy
import math

bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
obj = bpy.context.active_object
obj.scale = (L/2, W/2, H/2)
```

---

## 📈 Status Pengembangan

### Selesai ✅

- [x] Ekstrak properti penampang box (4 tipe)
- [x] Ekstrak penampang pier
- [x] Ekstrak posisi & elevasi support
- [x] Ekstrak tinggi pier
- [x] Ekstrak dimensi pier head
- [x] Ekstrak dimensi stopper
- [x] Mapping penampang sepanjang jembatan (38 segmen)
- [x] Visualisasi 3D (FreeCAD)
- [x] Data lengkap di `project_data.py`

### Dalam Proses ⏳

- [ ] Analisis struktur dengan OpenSeesPy
- [ ] Hitung reaksi per support
- [ ] Verifikasi keseimbangan gaya (reaksi = beban)

### Belum Dimulai ❌

- [ ] Ekstrak dimensi pile cap
- [ ] Ekstrak dimensi bored pile
- [ ] Ekstrak parameter tanah (p-y curve)
- [ ] Analisis substruktur (pier fiber section)
- [ ] Analisis pushover
- [ ] Analisis jembatan melengkung (trase huruf C)
- [ ] Analisis superelevasi
- [ ] Analisis penampang bervariasi (blockout, diafragma)

---

## 📚 Referensi

### Standar

- **SNI 1725:2016** — Pembebanan untuk Jembatan
- **SNI 2833:2016** — Perencanaan Jembatan terhadap Beban Gempa
- **AASHTO LRFD** — Bridge Design Specifications

### Library

- [OpenSeesPy Documentation](https://openseespydoc.readthedocs.io/)
- [sectionproperties Documentation](https://sectionproperties.readthedocs.io/)
- [ezdxf Documentation](https://ezdxf.readthedocs.io/)
- [FreeCAD Documentation](https://wiki.freecad.org/)

### Paper

- Mander, J.B., Priestley, M.J.N., Park, R. (1988). "Theoretical Stress-Strain Model for Confined Concrete." *Journal of Structural Engineering*, ASCE.
- Ngan, J.W., Caprani, C.C. (2022). "ospgrillage: A bridge deck grillage analysis preprocessor for OpenSeesPy." *Journal of Open Source Software*.

---

## 📄 Lisensi

**Internal use only.** Tidak untuk distribusi publik tanpa izin.

---

## 👥 Kontributor

- **Yoesroes** — Pengembang utama

---

## 📞 Kontak

Untuk pertanyaan atau kolaborasi:
- Email: [email@example.com]
- GitHub: [@USERNAME](https://github.com/USERNAME)

---

**Terakhir diperbarui:** 3 Oktober 2026
```

---

## Cara Pakai

1. **Buat file** `README.md` di root:
   ```bash
   cd ~/Sipil/baros_bridge
   nano README.md
   ```

2. **Paste** isi di atas.

3. **Ganti** `USERNAME` dan `email@example.com` dengan data Anda.

4. **Save** (`Ctrl+O`, Enter, `Ctrl+X`).

5. **Commit** ke Git:
   ```bash
   git add README.md
   git commit -m "Add comprehensive README"
   ```

---

## Ringkasan

| Bagian | Isi |
|--------|-----|
| Deskripsi | Filosofi analisis |
| Data | Support, span, EJ |
| Struktur | Folder |
| Requirements | Software & library |
| Instalasi | Clone, venv, install |
| Cara Pakai | Ekstrak, generate, visualisasi, analisis |
| Alur | Diagram |
| Data Diekstrak | Tabel lengkap |
| Tools | OpenSeesPy, sectionproperties, dll. |
| Status | Selesai, dalam proses, belum |
| Referensi | SNI, library, paper |
| Lisensi | Internal use |

**Jalankan `nano README.md`, paste, save.** Kirim konfirmasi.