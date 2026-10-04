loads.py
BTR: memakai lebar ekuivalen 7,25 m, sehingga 65,25 kN/m (sebelumnya 81). Untuk L > 30 m ada faktor reduksi q (P4–P5: 8,05 kPa), lewat parameter L_beban. Jika dikosongkan, q = 9 kPa (konservatif).
KEL: sekarang beban terpusat 497,35 kN (hitung_P_kel), bukan kN/m. FBD dihitung dari L_E = √(L_rata² · L_maks) = 29,4 m, jadi hasilnya tetap 0,4.
Distribusi per garis: ada fungsi baru untuk membagi beban ke 5 garis memanjang (z = −5; −3,5; 0; 3,5; 5). Hasilnya dicek oleh cek_distribusi(): jumlah per garis sama dengan total deck, jadi tidak terhitung 5×.
Kombinasi: ada hitung_kombinasi_garis() dan hitung_P_kombinasi() untuk beban terfaktor per garis.
Lain-lain: ele_tag menjadi seg_id. Path /home/yoesroes/... diganti path relatif dari lokasi file. Satu panggilan print_max_kombinasi yang menggandakan output dihapus.
confinement.py
define_cover: tegangan residual tidak lagi positif, dan parameter lambda Concrete02 yang hilang sekarang dikirim. Versi lama memberi argumen yang bergeser dan kemungkinan error di OpenSees.
Persegi: rho_x dan rho_y memakai dimensi core yang benar (sebelumnya tertukar), dan rho_s = ρx + ρy (sebelumnya rata-rata). Pada contoh pier-mu, ε_cu naik dari 0,0091 ke 0,0143.
ke sekarang memakai rumus Mander lengkap. Suku arching bidang memakai w_clear (jarak bersih antar tulangan longitudinal). Tanpa w_clear, suku itu diabaikan dan ke sedikit terlalu besar.
Lingkaran: ada pilihan spiral=True/False (hoop memakai faktor kuadrat). rho_cc bisa dihitung otomatis dari n_long.
stress() diberi pengaman pembagian nol.
rebar_layout.py
Jumlah bar default kini benar. Contoh n = 20: versi lama menempatkan 16 bar, sekarang 20.
TypeError saat n_bars_side kosong dan pembagian nol untuk n_bars_top = 1 sudah diperbaiki.
Total bar divalidasi terhadap n_bars (ValueError jika tidak cocok).
Parameter baru db_hoop (jarak as bar = cover + db_hoop + db/2) dan radius_circular().
Semua place_* mengembalikan daftar koordinat.
Yang perlu kamu cek
Asumsi distribusi: berat sendiri dibagi menurut lebar tributari, dan barrier ditaruh di garis z = ±5. Jika posisi web box berbeda, ubah distribusi_berat_sendiri().
Posisi KEL: baru distribusi melintangnya yang ada. Posisi memanjang terburuk dan pattern loading belum dibuat. Itu urusan analysis.py.
Concrete04: kode memanggilnya dengan fct tanpa et, seperti di materials.py. Jika OpenSees mengeluh atau tarikannya aneh, tambahkan et.
Perubahan yang bisa merusak pemanggil lama:
ele["w_hidup"] sekarang hanya BTR (KEL ada di P_kel).
rectangular() mewajibkan sx == sy.
place_rectangular() kini melempar ValueError jika total bar tidak cocok.
Perkiraan f'cc persegi: untuk flx ≠ fly saya masih memakai √(flx·fly). Mander sebenarnya memakai permukaan keruntuhan lima-parameter, jadi hasilnya perkiraan.