# Benchmark terhadap model referensi (SAP2000 / MIDAS)

1. Susun model referensi dengan geometri, properti, material, tumpuan,
   kasus beban, kombinasi, dan konvensi tanda yang IDENTIK dengan model ini.
2. Ekspor reaksi vertikal per bearing (kN, positif ke atas) per kombinasi.
3. Salin `reference_reaksi_template.csv` menjadi `reference_reaksi.csv` dan
   isi baris: `bearing,kombinasi,R_kN` (mis. `B11,Service I,6400`). Nama
   kombinasi harus sama dengan `loads.KOMBINASI`. Nilai positif dibandingkan
   dengan reaksi maksimum model; nilai negatif dengan reaksi minimum.
4. Tetapkan pita penerimaan SEBELUM melihat hasil:
   `project_data.REVIEW["tol_referensi"] = 0.05` (contoh).
5. Jalankan `python -m core.review`. Pemeriksaan SC-14 akan terisi.
6. Selisih diselidiki, bukan disetel agar cocok. Simpan versi perangkat
   lunak, tanggal, asumsi, dan berkas ekspor sebagai rekaman benchmark.
