# Step 1 — Modul Beban (Loads)

**Proyek:** Jembatan Baros — Analisis Deck 9 Bentang  
**Tanggal:** 4 Oktober 2026  
**Status:** Draft — menunggu konfirmasi parameter  
**Tujuan:** Menghitung beban per elemen (per segmen deck) untuk analisis OpenSeesPy

---

## 1. Latar Belakang

Deck jembatan dibagi menjadi **38 elemen** berdasarkan `SECTION_MAP`. Setiap elemen memiliki:
- **Tipe penampang** (solid, hollow, tumpuan)
- **Luas penampang (A)** yang berbeda
- **Beban** yang berbeda (tergantung A)

Karena itu, beban harus dihitung **per elemen**, bukan global.

---

## 2. Komponen Beban

### 2.1 Beban Mati Struktural (Berat Sendiri Box)

| Parameter | Simbol | Satuan | Nilai | Sumber |
|-----------|--------|--------|-------|--------|
| Berat jenis beton | γ_beton | kN/m³ | 24.0 | SNI 1725:2016 |
| Luas penampang | A | m² | bervariasi | Ekstraksi DXF |

**Rumus:**
w_box = γ_beton × A_section


**Contoh:**
- Solid: w_box = 24 × 8.2231 = **197.35 kN/m**
- Hollow: w_box = 24 × 7.7072 = **184.97 kN/m**
- Tumpuan: w_box = 24 × 7.9670 = **191.21 kN/m**

---

### 2.2 Beban Mati Non-Struktural

#### a. Aspal

| Parameter | Simbol | Satuan | Nilai | Sumber |
|-----------|--------|--------|-------|--------|
| Berat jenis aspal | γ_aspal | kN/m³ | 22.0 | Asumsi |
| Tebal aspal | t_aspal | m | 0.075 | Asumsi |
| Lebar jalan | b_jalan | m | 9.0 | Gambar |

**Rumus:**
w_aspal = γ_aspal × t_aspal × b_jalan
= 22.0 × 0.075 × 9.0
= 14.85 kN/m



#### c. Parapet / Railing

| Parameter | Simbol | Satuan | Nilai | Sumber |
|-----------|--------|--------|-------|--------|
| Beban parapet | w_parapet | kN/m | 5.0 | Asumsi |
| Jumlah sisi | n_sisi | — | 2 | Gambar |

**Rumus:**
w_parapet = w_parapet × n_sisi
= 5.0 × 2
= 10.0 kN/m


**Total beban mati non-struktural:**
w_non_struktur = w_aspal + w_trotoar + w_parapet
= 14.85 + 24.0 + 10.0
= 48.85 kN/m


---

### 2.3 Beban Hidup

| Parameter | Simbol | Satuan | Nilai | Sumber |
|-----------|--------|--------|-------|--------|
| BTR (beban terbagi rata) | q_BTR | kPa | 9.0 untuk L ≤ 30 m | Konstanta model |
| Lebar jalan model | ROAD_WIDTH | m | 9.00 | Data proyek |
| Lebar ekuivalen BTR | b_ekuivalen | m | 7.25 | 5.5 m penuh + 50% sisa |
| Intensitas nominal KEL/BGT | P_KEL | kN/m transversal | 49.0 | Konstanta kode saat ini |
| Faktor dinamis KEL (kasus ini) | FBD | — | 0.4 | L_E ≤ 50 m |

**BTR (L ≤ 30 m):**
w_BTR = q_BTR × b_ekuivalen
= 9.0 × [5.5 + 0.5 × (9.00 - 5.5)]
= 9.0 × 7.25 = **65.25 kN/m**

Untuk L > 30 m, q_BTR direduksi sesuai fungsi `hitung_q_btr(L)`; 7.25 m
merupakan lebar ekuivalen BTR dan bukan basis lebar KEL.

**KEL/BGT:** intensitas transversal setelah FBD = 49.0 × (1 + 0.4) =
**68.6 kN/m**. Proyek menerapkan KEL pada seluruh `ROAD_WIDTH = 9.00 m`,
sehingga target magnitudo satu KEL = 68.6 × 9.00 = **617.40 kN**.

Penggunaan lebar penuh 9.00 m adalah asumsi pemodelan konservatif proyek untuk
mengantisipasi pembebanan, termasuk pada area yang digunakan sepeda dan sepeda
motor. Ini keputusan proyek, bukan klaim bahwa SNI 1725:2016 atau AASHTO
mewajibkan penerapan KEL dengan basis lebar yang sama.

---

### 2.4 Beban Total
w_total = w_box + w_non_struktur + w_BTR


**Contoh per elemen:**

| Elemen | Tipe | A (m²) | w_box | w_non_struk | w_hidup | w_total |
|--------|------|--------|-------|-------------|---------|---------|
| 1 | solid | 8.2231 | 197.35 | 48.85 | 65.25 | 311.45 |
| 2 | tumpuan | 7.9670 | 191.21 | 48.85 | 65.25 | 305.31 |
| 4 | hollow | 7.7072 | 184.97 | 48.85 | 65.25 | 299.07 |

---

## 3. Kombinasi Beban

### 3.1 Service (Analisis Awal)
1.0 D + 1.0 L

Di mana:
- **D** = beban mati (struktural + non-struktural)
- **L** = beban hidup

### 3.2 Ultimate (Untuk Desain)

**Catatan:** Untuk analisis awal, pakai **service** (1.0 D + 1.0 L).

---

## 4. Asumsi yang Digunakan

| # | Asumsi | Nilai | Alasan |
|---|--------|-------|--------|
| 1 | γ_beton | 24 kN/m³ | SNI 1725:2016 |
| 2 | γ_aspal | 22 kN/m³ | Standar aspal |
| 3 | t_aspal | 0.075 m | Asumsi umum |
| 4 | b_jalan | 9.0 m | Dari gambar |
| 5 | A_trotoar | 0.5 m² | Asumsi umum |
| 6 | n_sisi trotoar | 2 | Dari gambar |
| 7 | w_parapet | 5 kN/m | Asumsi umum |
| 8 | n_sisi parapet | 2 | Dari gambar |
| 9 | q_UDL | 9 kPa | SNI 1725:2016 |
| 10 | Kombinasi | 1.0 D + 1.0 L | Service |

---

## 5. Struktur Output

Setiap elemen akan menghasilkan dictionary:

```python
{
    "ele_tag": 1,
    "x1": -0.27,
    "x2": 0.00,
    "tipe": "solid",
    "A": 8.2231,
    "Ix": 1.4527,
    "Iy": 33.3927,
    "L": 0.27,
    "w_box": 197.35,
    "w_non_struktur": 48.85,
    "w_hidup": 81.0,
    "w_total": 327.20,
}
