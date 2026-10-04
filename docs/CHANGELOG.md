# CHANGELOG — Baros Bridge

Catatan perubahan kode per tanggal. Format mengikuti [Keep a Changelog](https://keepachangelog.com/).

---

## [Unreleased] — 2026-10-04

### Perbaikan Utama (berdasarkan review)

#### `core/loads.py`

**BTR (Beban Terbagi Rata)**
- Lebar ekuivalen diubah dari 9.00 m menjadi **7.25 m**
  (5.5 m × 100% + 3.5 m × 50%), sesuai SNI 1725:2016 Pasal 8.3.1.
- Intensitas q kini bergantung panjang yang dibebani:
  - L ≤ 30 m: q = 9.0 kPa
  - L > 30 m: q = 9.0 × (0.5 + 15/L) kPa
- Efek: w_BTR turun dari 81.0 kN/m → **65.25 kN/m** (untuk L ≤ 30 m).
  Untuk P4–P5 (L = 38 m): q = 8.05 kPa.

**KEL (Beban Garis)**
- Diperlakukan sebagai **beban terpusat (kN)**, bukan beban merata (kN/m).
- P_KEL = 49 kN/m × lebar ekuivalen × (1 + FBD) = **497.35 kN**.
- FBD dihitung dari L_E = √(L_rata² · L_maks) = 29.4 m → FBD = 0.4.

**Distribusi ke 5 Garis Memanjang**
- Fungsi baru: `batas_tributari()`, `distribusi_berat_sendiri()`,
  `distribusi_barrier()`, `lebar_beban_hidup_per_garis()`.
- Beban dibagi ke 5 garis (z = −5; −3.5; 0; 3.5; 5) menurut lebar tributari.
- Verifikasi: `cek_distribusi()` memastikan Σ beban per garis = total deck
  (tidak terhitung 5×).

**Kombinasi**
- `hitung_kombinasi_garis()` — beban terfaktor per garis per segmen.
- `hitung_P_kombinasi()` — KEL terfaktor untuk kombinasi tertentu.

**Lain-lain**
- `ele_tag` → **`seg_id`** (menghindari bentrok dengan tag 355 elemen).
- Path absolut `/home/yoesroes/...` → **path relatif** dari lokasi file.
- Duplikasi output `print_max_kombinasi()` dihapus.

#### `core/confinement.py`

**`ManderConcrete.define_cover()`**
- Tegangan residual (`fpcu`) tidak lagi terbalik tanda.
- Parameter `lambda` (rat) Concrete02 yang hilang sekarang dikirim.
- Versi lama: argumen bergeser → error di OpenSees.

**Rectangular Section**
- `rho_x` dan `rho_y` memakai **dimensi core yang benar** (sebelumnya tertukar).
- `rho_s = rho_x + rho_y` (sebelumnya rata-rata).
- Efek pada pier contoh: ε_cu naik dari **0.0091 → 0.0143**.
- `ke` memakai **rumus Mander lengkap** (arching in-plane + kedua arah s').
- Suku arching: `w_clear` = jarak bersih antar tulangan longitudinal.
  Tanpa `w_clear`, suku diabaikan → `ke` sedikit terlalu besar.

**Circular Section**
- Pilihan `spiral=True/False` (hoop memakai faktor kuadrat).
- `rho_cc` bisa dihitung otomatis dari `n_long`.

**`stress()`**
- Ditambah pengaman pembagian nol (`Esec >= Ec`).

#### `core/rebar_layout.py`

- Jumlah bar default **benar** (n total, bukan n − 4).
  Contoh: n = 20 → versi lama menempatkan 16 bar, sekarang 20.
- `TypeError` saat `n_bars_side` kosong diperbaiki.
- Pembagian nol untuk `n_bars_top = 1` dihilangkan.
- Total bar **divalidasi** terhadap `n_bars` (ValueError bila tidak cocok).
- Parameter baru `db_hoop` (jarak as bar = cover + db_hoop + db/2).
- Method baru `radius_circular()`.
- Semua `place_*` mengembalikan daftar koordinat untuk verifikasi/plot.

---

### Breaking Changes (Perlu Cek Pemanggil Lama)

| Perubahan | Dampak |
|-----------|--------|
| `ele["w_hidup"]` sekarang **hanya BTR** (KEL ada di `P_kel`) | Kode yang memakai `w_hidup` untuk total beban hidup perlu disesuaikan |
| `ManderConfinement.rectangular()` mewajibkan **`sx == sy`** | Pemanggil dengan sx ≠ sy akan error |
| `place_rectangular()` melempar **ValueError** jika total bar ≠ n_bars | Pemanggil lama yang mengandalkan default n−4 perlu eksplisit |
| `ele_tag` → **`seg_id`** | Kode yang akses `ele["ele_tag"]` perlu diubah |

---

### Yang Masih Perlu Ditambahkan

| Item | Status | Catatan |
|------|:------:|---------|
| Pattern loading | ❌ | Untuk momen & reaksi ekstrem di deck menerus |
| Posisi memanjang KEL | ❌ | Hanya distribusi melintang yang sudah ada |
| Concrete04 dengan `et` | ⚠️ | Jika OpenSees minta atau tarikan aneh |
| Distribusi berat sendiri | ⚠️ | Saat ini pakai lebar tributari; ubah jika posisi web box berbeda |
| Mander untuk flx ≠ fly | ⚠️ | Saat ini pakai √(flx·fly); Mander pakai permukaan 5-parameter |

---

### Catatan Teknis

**Asumsi distribusi**
- Berat sendiri dibagi menurut lebar tributari.
- Barrier ditaruh di garis z = ±5 (tepi deck).
- Jika posisi web box berbeda, ubah `distribusi_berat_sendiri()`.

**KEL**
- Baru distribusi melintang yang ada.
- Posisi memanjang terburuk & pattern loading → urusan `analysis.py`.

**Concrete04**
- Dipanggil dengan `fct` tanpa `et` (seperti di `materials.py`).
- Jika OpenSees mengeluh atau tarikan aneh, tambahkan `et`.

---

### File yang Diubah

| File | Perubahan |
|------|-----------|
| `core/loads.py` | BTR, KEL, distribusi 5 garis, kombinasi, `seg_id` |
| `core/confinement.py` | `define_cover`, rectangular Mander penuh, spiral/hoop |
| `core/rebar_layout.py` | `place_rectangular`, validasi, `db_hoop`, return coords |

---

### Cara Verifikasi

```bash
# 1. Jalankan loads.py
cd ~/Sipil/baros_bridge
python3 core/loads.py

# 2. Cek distribusi
#    Output harus menunjukkan:
#    - w_BTR = 65.25 kN/m (bukan 81.0)
#    - P_KEL = 497.35 kN (bukan 68.6 kN/m)
#    - Σ w_*_garis = w_total (tidak 5×)

# 3. Cek confinement.py
python3 core/confinement.py

# 4. Cek rebar_layout.py
python3 core/rebar_layout.py

Referensi
SNI 1725:2016 — Pembebanan untuk Jembatan

Pasal 8.3.1 — BTR (Beban Terbagi Rata)

Pasal 8.3.2 — KEL (Beban Garis)

Pasal 8.3.3 — FBD (Faktor Beban Dinamis)

Mander, Priestley & Park (1988) — Theoretical Stress-Strain Model for Confined Concrete