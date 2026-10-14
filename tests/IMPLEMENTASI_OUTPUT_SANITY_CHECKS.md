# Implementasi output & sanity checks — Baros Bridge

## File yang ditambahkan/diubah

- `core/output.py` — ditambah ekspor reaksi per bearing fisik dan pemanggilan sanity checks di `laporan()`.
- `core/sanity_checks.py` — modul pemeriksaan hasil tanpa mengubah model OpenSees.
- `tests/test_sanity_checks.py` — tes sintetis untuk keseimbangan, total beban, dan pemetaan bearing.

## File output baru

- `output/reaksi_bearing.json`
- `output/reaksi_bearing.csv`
- `output/sanity_checks.json`
- `output/sanity_checks.csv`

File `reaksi.json` dan `reaksi.csv` lama tetap dihasilkan.

## Status checks

- `SC-01`: kelengkapan kasus hasil.
- `SC-02`: nilai respons numerik finite.
- `SC-03`: hitung ulang total beban kasus dari beban elemen dan beban nodal, lalu bandingkan dengan `kasus['total']`. Ini mengecek konsistensi internal; bukan bukti bahwa semua beban desain yang seharusnya sudah dimasukkan.
- `SC-04`: keseimbangan vertikal `sum(Ry) + total_beban`.
- `SC-05`: batas lendutan hanya dijalankan jika batas proyek diberikan eksplisit. Saat ini `laporan()` tidak menetapkan batas universal secara otomatis.
- `SC-06`: node reaksi tersedia dan ID bearing unik.

## Tes yang dijalankan

`pytest -q tests/test_sanity_checks.py tests/test_output_gaya_dalam.py` — **5 passed**.

Seluruh tes tidak dapat dikoleksi di lingkungan pemeriksaan ini karena `openseespy` tidak terpasang (`test_grillage_equivalent_beam.py`). Jalankan ulang di environment proyek `(sipil)` yang memiliki dependensi OpenSeesPy.

## Cara menerapkan

1. Cadangkan `core/output.py` di repo lokal.
2. Salin `core/output.py` dan `core/sanity_checks.py` dari paket ini ke folder `core/` repo.
3. Salin `tests/test_sanity_checks.py` ke folder `tests/`.
4. Dari root repo jalankan:

   ```bash
   python -m pytest tests/test_sanity_checks.py tests/test_output_gaya_dalam.py -q
   python -m core.analysis
   ```

5. Periksa empat file output baru/lama di folder `output/`.

## Batasan yang disengaja

Modul ini tidak menyatakan bearing overload, tidak menerapkan `L/800` sebagai kriteria universal, dan tidak menyatakan model valid terhadap SAP2000/MIDAS. Pemeriksaan kapasitas perlu data kapasitas tiap bearing, standar desain, kombinasi faktor, serta pemetaan reaksi desain yang disetujui.
