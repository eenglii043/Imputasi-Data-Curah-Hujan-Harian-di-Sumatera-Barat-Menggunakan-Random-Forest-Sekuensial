# Dashboard Curah Hujan Sumatera Barat — Kerja Praktik

Dashboard ini dibuat berdasarkan laporan **“Imputasi Data Curah Hujan Harian di Sumatera Barat Menggunakan Random Forest Sekuensial”** oleh Enggli Rahmadhani (123450043).

## Fitur

1. **Beranda** — ringkasan penelitian, metodologi, dan hasil utama.
2. **Sebaran Curah Hujan** — peta Leaflet, filter tanggal maksimal 7 hari, filter kabupaten/kota, klik titik pos untuk melihat nilai harian, klasifikasi hujan, dan status asli/imputasi. Jika layer batas administrasi BIG dapat diakses oleh browser, pengguna juga dapat mengeklik poligon wilayah. Jika layer eksternal tidak tersedia, klik peta akan memilih pos terdekat.
3. **Summarize Curah Hujan** — ranking kabupaten/kota, rata-rata curah hujan per pos, maksimum harian, jumlah pos, serta tren harian, bulanan, dan tahunan 2020–2025.
4. **Keterbatasan & Kualitas Data** — komposisi status data, cakupan pengisian, dan batas interpretasi penelitian.

## Arsitektur

- **Backend Python:** FastAPI + Pandas + NumPy di `api/index.py`.
- **Frontend:** HTML/CSS/JavaScript di `public/index.html`.
- **Peta:** Leaflet + OpenStreetMap; batas administrasi opsional dimuat dari layanan geospasial BIG.
- **Grafik:** Chart.js.
- **Deploy:** konfigurasi `vercel.json` sudah disediakan.

Dashboard tidak memakai Streamlit karena Streamlit merupakan server interaktif jangka panjang, sedangkan Vercel lebih cocok untuk fungsi Python serverless dan aset statis. Pada proyek ini, pengolahan data dan API tetap memakai Python, sedangkan tab, peta, dan grafik dirender di browser.

## Menjalankan lokal di VS Code (Windows)

1. Ekstrak ZIP, lalu buka folder `curah_hujan_dashboard_vercel` di VS Code.
2. Pastikan Python 3.10 atau lebih baru telah terpasang.
3. Buka terminal VS Code dan jalankan:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn api.index:app --reload
   ```

   Jika PowerShell memblokir aktivasi virtual environment, jalankan perintah berikut pada terminal Command Prompt:

   ```bat
   .venv\Scripts\activate.bat
   ```

4. Buka `http://127.0.0.1:8000` di browser.
5. Endpoint pengecekan tersedia di `http://127.0.0.1:8000/api/health`.

## Deploy ke Vercel

1. Unggah folder proyek ini ke repository GitHub.
2. Masuk ke Vercel, pilih **Add New → Project**, lalu impor repository tersebut.
3. Framework Preset dapat dipilih **Other**. Biarkan Vercel memakai konfigurasi dari `vercel.json`; jangan menetapkan folder `public` sebagai satu-satunya root project karena fungsi Python dan folder `data` juga dibutuhkan.
4. Deploy. Setelah deploy, uji halaman utama dan endpoint `/api/health`.

Jika Vercel meminta konfigurasi build khusus, pastikan `api/index.py`, `data/**`, `public/**`, `requirements.txt`, dan `vercel.json` tetap berada pada struktur yang sama. Data matriks dan flag disertakan sebagai file proyek kecil; CSV asli 46 MB tidak dimasukkan ke paket deployment.

## Struktur folder

```text
curah_hujan_dashboard_vercel/
├── api/
│   └── index.py
├── data/
│   ├── rainfall_matrix.csv
│   ├── rainfall_flags.csv
│   ├── stations.csv
│   └── regions.csv
├── public/
│   ├── index.html
│   └── assets/
│       ├── bmkg.png
│       ├── itera.png
│       └── sains_data.png
├── scripts/
│   └── prepare_data.py
├── requirements.txt
└── vercel.json
```

## Sumber data dan cakupan

- `rainfall_matrix.csv`: matriks hasil imputasi untuk 146 pos, 2.192 tanggal, periode 1 Januari 2020–31 Desember 2025.
- `rainfall_flags.csv`: status tiap sel: `0` data asli, `1` data imputasi, `2` celah aktif belum terisi, `3` di luar rentang aktif.
- `stations.csv`: metadata pos dari `curah_hujan_gabungan(1).csv`, termasuk koordinat, nama, elevasi, serta flag apakah ID pos terdapat pada matriks hasil.
- `regions.csv`: tabel relasi awalan ID internal pos ke kode BPS kabupaten/kota. Awalan ID internal **bukan** kode BPS dan tidak boleh dipakai sebagai pengganti kode BPS.

Pemetaan kabupaten/kota disusun dari pola ID internal dan nama/lokasi pos pada berkas sumber. Daftar nama wilayah merujuk publikasi BPS Provinsi Sumatera Barat, *Master Wilayah Administrasi Provinsi Sumatera Barat 2025*: https://sumbar.bps.go.id/id/publication/2026/05/29/1b5bc784c2c0a128be036ef3/master-administrative-region-of-sumatera-barat-province-2025.html. Sebelum digunakan sebagai produk operasional, relasi ID pos–wilayah sebaiknya diverifikasi dengan metadata resmi BMKG/BPS.

## Definisi dan batas interpretasi

- Cakupan pengisian dihitung sebagai `nilai imputasi / (nilai imputasi + celah aktif tersisa)`. Pada keluaran penelitian ini: 12.730 / 13.229 = sekitar **96,23%**. Ini **bukan akurasi prediksi**.
- Nilai maksimum pada matriks adalah 434 mm/hari di pos Nanggalo, Kota Padang, pada 14 Juli 2023. Nilai ekstrem sebaiknya diverifikasi ke sumber pengamatan sebelum digunakan untuk keputusan operasional.
- Ambang kategori curah hujan harian pada dashboard mengikuti rentang yang ditetapkan dalam spesifikasi proyek: ringan 0,5–<20; sedang 20–<50; lebat 50–<100; sangat lebat 100–150; ekstrem >150 mm/hari. Nilai <0,5 mm/hari diberi label “Tidak hujan / di bawah ambang”. Pada batas yang beririsan, 20, 50, dan 100 mm/hari dimasukkan ke kategori berikutnya agar rentang tidak tumpang tindih.
- Kategori tersebut dipakai sebagai panduan interpretasi dashboard, bukan pengganti peringatan atau informasi cuaca resmi BMKG.
- Peta dasar membutuhkan koneksi internet. Batas administrasi BIG dimuat secara opsional dari layanan eksternal; bila layanan tersebut tidak dapat diakses browser, fungsi titik pos dan pencarian pos terdekat tetap tersedia.

## Catatan pengembangan

File `scripts/prepare_data.py` mendokumentasikan cara membentuk data deployment dari CSV sumber, matriks, dan flag. Jalankan ulang hanya jika sumber data diperbarui; pastikan pemetaan wilayah sudah diperiksa sebelum menerbitkan versi baru.
