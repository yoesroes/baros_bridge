
```markdown
# Jembatan Baros — Analisis Struktur Jembatan 9 Bentang

[![Status](https://img.shields.io/badge/status-in%20progress-yellow)]()
[![Python](https://img.shields.io/badge/python-3.12-blue)]()
[![OpenSeesPy](https://img.shields.io/badge/OpenSeesPy-3.5+-green)]()
[![FreeCAD](https://img.shields.io/badge/FreeCAD-1.1.3-orange)]()

Analisis struktur jembatan flyover beton bertulang dengan **9 bentang**, **8 pier**, dan **2 abutment** menggunakan OpenSeesPy. Proyek ini mencakup ekstraksi data dari DXF, visualisasi 3D, dan analisis struktur.

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
- [Modul Core](#modul-core)
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
baros_bridge/
├── README.md
├── .gitignore
├── requirements.txt
│
├── Clean/                          # Data & script final
│   ├── project_data.py             # SINGLE SOURCE OF TRUTH
│   ├── plot_mapping.py             # Plot mapping penampang
│   └── ...
│
├── core/                           # Modul inti
│   ├── loads.py                    # Beban (SNI 1725)
│   ├── materials.py                # Material
│   ├── sections.py                 # Section
│   ├── nodes.py                    # Node grillage
│   ├── elements.py                 # Elemen grillage
│   ├── boundary_condition.py       # BC
│   ├── analysis.py                 # Analisis (next)
│   ├── output.py                   # Output (next)
│   │
│   ├── confinement.py              # Mander (pier)
│   ├── rebar_layout.py             # Rebar (pier)
│   └── bridge.py                   # Orchestrator
│
├── components/                     # Komponen struktur
│   ├── box_girder.py               # Box girder
│   ├── pier_head.py                # Pier head
│   ├── pier.py                     # Pier
│   ├── pile_cap.py                 # Pile cap
│   └── bored_pile.py               # Bored pile
│
├── Temp/                           # Script eksperimen
│   ├── extract_*.py                # Ekstraksi DXF
│   ├── hitung_J*.py                # Hitung J
│   ├── fix_hollow*.py              # Perbaiki DXF
│   ├── freecad_*.py                # Visualisasi FreeCAD
│   └── ...
│
├── output/                         # Output
│   ├── loads_output.txt            # Output beban
│   ├── loads_output.csv            # Output beban (CSV)
│   ├── loads_garis.csv             # Output beban per garis
│   ├── section_J.json              # Nilai J
│   ├── jembatan_freecad2.FCStd     # Model 3D FreeCAD
│   └── screenshots/                # Screenshot
│
├── archive/
│   └── legacy/                     # File lama (tidak dipakai)
│       ├── section_mapping.py
│       ├── support_data.py
│       └── section_properties.py
│
├── docs/                           # Dokumentasi
│   ├── CHANGELOG.md
│   └── Catatan perubahan.md
│
└── data/
    └── DXF/                        # File DXF (tidak di-commit)
        ├── scaled/                 # DXF scaled (×39.37)
        └── ...
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
git clone https://github.com/yoesroes/baros_bridge.git
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

### B. Generate Mapping Penampang

```bash
cd Temp
python3 generate_section_map.py
python3 merge_section_map.py
```

### C. Visualisasi 3D (FreeCAD)

```bash
cd Temp
~/Desktop/FreeCAD.AppImage --console freecad_jembatan2.py
```

**Buka di GUI:**
```bash
~/Desktop/FreeCAD.AppImage output/jembatan_freecad2.FCStd
```

### D. Analisis Struktur (OpenSeesPy)

```bash
cd core

# Step 1: Beban
python3 loads.py

# Step 2: Material
python3 materials.py

# Step 3: Section
python3 sections.py

# Step 4: Node
python3 nodes.py

# Step 5: Elemen
python3 elements.py

# Step 6: BC
python3 boundary_condition.py
```

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
│     - Penampang box (tipikal, hollow, tumpuan)          │
│     - Penampang pier                                     │
│     - Profil memanjang (posisi & elevasi support)        │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  2. PERHITUNGAN PROPERTI PENAMPANG                      │
│     - A, Ix, Iy, J dengan sectionproperties             │
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
│     - FreeCAD                                            │
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

| Tipe | A (m²) | Ix (m⁴) | Iy (m⁴) | J (m⁴) | Sumber J |
|------|--------|---------|---------|--------|----------|
| **Solid** | 8.2231 | 1.4527 | 33.3927 | 3.8232 | Warping |
| **Hollow** | 7.7072 | 1.4392 | 32.8489 | 3.5840 | Estimasi |
| **Tumpuan** | 7.9670 | 1.2986 | 33.3759 | 3.1660 | Warping |

**Catatan:**
- Ix = momen inersia terhadap sumbu **vertikal** (lentur vertikal)
- Iy = momen inersia terhadap sumbu **lateral** (lentur lateral)
- J = konstanta torsi

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
| E box | 30.27 × 10⁶ | kPa |
| E pier | 25.74 × 10⁶ | kPa |
| f'c box | 41.5 | MPa |
| f'c pier | 30 | MPa |
| fy | 420 | MPa |
| γ beton | 22.913 | kN/m³ |

### 7. Beban (SNI 1725:2016)

| Komponen | Nilai | Satuan |
|----------|-------|--------|
| BTR | 65.25 | kN/m |
| KEL | 497.35 | kN |
| w aspal | 14.85 | kN/m |
| w air | 0.45 | kN/m |
| w barrier | 11.33 | kN/m |
| w non-struktur | 26.63 | kN/m |

---

## 🧩 Modul Core

| Modul | Fungsi | Status |
|-------|--------|:------:|
| `loads.py` | Beban (SNI 1725) | ✅ |
| `materials.py` | Material | ✅ |
| `sections.py` | Section | ✅ |
| `nodes.py` | Node grillage (240) | ✅ |
| `elements.py` | Elemen grillage (346) | ✅ |
| `boundary_condition.py` | BC (50 node) | ✅ |
| `analysis.py` | Analisis | ⏳ |
| `output.py` | Output | ⏳ |
| `confinement.py` | Mander (pier) | ✅ |
| `rebar_layout.py` | Rebar (pier) | ✅ |

### Model Grillage

| Item | Nilai |
|------|:-----:|
| Tipe | Grillage 3D |
| Node | 240 (48 x × 5 z) |
| Elemen memanjang | 235 |
| Elemen melintang | 192 |
| Total elemen | 427 |
| Section | Bervariasi per segmen |
| BC | 50 node di-fix (10 support × 5) |

---

## 🛠️ Tools & Library

### 1. OpenSeesPy — Analisis struktur

### 2. sectionproperties — Properti penampang dari DXF

### 3. ezdxf — Baca/tulis DXF

### 4. FreeCAD — Visualisasi 3D

### 5. Blender 2.79b — Visualisasi alternatif

---

## 📈 Status Pengembangan

### Selesai ✅

- [x] Ekstrak properti penampang box (3 tipe)
- [x] Ekstrak penampang pier
- [x] Ekstrak posisi & elevasi support
- [x] Ekstrak tinggi pier
- [x] Ekstrak dimensi pier head
- [x] Ekstrak dimensi stopper
- [x] Mapping penampang sepanjang jembatan (38 segmen)
- [x] Visualisasi 3D (FreeCAD)
- [x] Data lengkap di `project_data.py`
- [x] **Step 1: Modul beban** (`loads.py`)
- [x] **Step 2: Material** (`materials.py`)
- [x] **Step 3: Section** (`sections.py`)
- [x] **Step 4: Node** (`nodes.py` — 240 node)
- [x] **Step 5: Elemen** (`elements.py` — 346 elemen)
- [x] **Step 6: BC** (`boundary_condition.py` — 50 node)

### Dalam Proses ⏳

- [ ] **Step 7: Analisis** (`analysis.py`)
- [ ] **Step 8: Output** (`output.py`)
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
- [ ] Pattern loading

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

Copyright (c) 2026 Yus Rusnika. All Rights Reserved.

Proyek ini tersedia untuk **tujuan pembelajaran**. Anda boleh melihat,
mempelajari, dan mengambil inspirasi dari kode ini. Namun, Anda **tidak
diizinkan** untuk:
- Mengklaim kode ini sebagai milik Anda
- Menggunakannya untuk keperluan komersial
- Mendistribusikan ulang tanpa izin

Untuk pertanyaan tentang penggunaan, hubungi [yusrusnika84@gmail.com].

---

## 👥 Kontributor

- **Yus Rusnika** — Pengembang utama

---

## 📞 Kontak

Untuk pertanyaan atau kolaborasi:
- Email: yusrusnika84@gmail.com
- GitHub: [@yoesroes](https://github.com/yoesroes)

---

**Terakhir diperbarui:** 5 Oktober 2026
```

