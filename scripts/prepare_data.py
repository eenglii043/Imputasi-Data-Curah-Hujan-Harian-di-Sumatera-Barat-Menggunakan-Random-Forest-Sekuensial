"""Build compact deployment data files from the research CSVs.

Example (run from the project folder):
python scripts/prepare_data.py --source "../curah_hujan_gabungan(1).csv" \
  --matrix "../10_matriks_hasil_imputasi.csv" \
  --flags "../10_flag_0_asli_1_imputasi_2_sisa_3_luaraktif.csv"

The source CSV is not copied into the deployment package.
"""
import argparse
from pathlib import Path
import pandas as pd

REGIONS = {
    "1301": ("1302", "Kab. Pesisir Selatan"),
    "1302": ("1303", "Kab. Solok"),
    "1303": ("1304", "Kab. Sijunjung"),
    "1304": ("1305", "Kab. Tanah Datar"),
    "1305": ("1306", "Kab. Padang Pariaman"),
    "1306": ("1307", "Kab. Agam"),
    "1307": ("1308", "Kab. Lima Puluh Kota"),
    "1308": ("1309", "Kab. Pasaman"),
    "1309": ("1301", "Kab. Kepulauan Mentawai"),
    "1310": ("1311", "Kab. Dharmasraya"),
    "1311": ("1310", "Kab. Solok Selatan"),
    "1312": ("1312", "Kab. Pasaman Barat"),
    "1371": ("1371", "Kota Padang"),
    "1372": ("1372", "Kota Solok"),
    "1373": ("1373", "Kota Sawahlunto"),
    "1374": ("1374", "Kota Padang Panjang"),
    "1375": ("1375", "Kota Bukittinggi"),
    "1376": ("1376", "Kota Payakumbuh"),
    "1377": ("1377", "Kota Pariaman"),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="CSV data asli")
    parser.add_argument("--matrix", required=True, help="CSV matriks hasil imputasi")
    parser.add_argument("--flags", required=True, help="CSV flag status matriks")
    parser.add_argument("--out", default="data", help="Folder keluaran")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    src = pd.read_csv(args.source, low_memory=False)
    src["POS HUJAN ID"] = src["POS HUJAN ID"].astype(str)
    matrix = pd.read_csv(args.matrix, low_memory=False)
    flags = pd.read_csv(args.flags, low_memory=False)
    matrix["tanggal"] = pd.to_datetime(matrix["tanggal"]).dt.strftime("%Y-%m-%d")
    flags["tanggal"] = pd.to_datetime(flags["tanggal"]).dt.strftime("%Y-%m-%d")
    ids = [c for c in matrix.columns if c != "tanggal"]

    stations = src.groupby("POS HUJAN ID", as_index=False).agg(
        nama_pos=("NAME", "first"),
        latitude=("CURRENT LATITUDE", "first"),
        longitude=("CURRENT LONGITUDE", "first"),
        elevasi_m=("CURRENT ELEVATION M", "first"),
        tanggal_awal_sumber=("DATA TIMESTAMP", "min"),
        tanggal_akhir_sumber=("DATA TIMESTAMP", "max"),
    )
    stations["prefix_internal"] = stations["POS HUJAN ID"].str[:4]
    stations["kode_bps"] = stations["prefix_internal"].map(lambda p: REGIONS.get(p, ("", ""))[0])
    stations["kabupaten_kota"] = stations["prefix_internal"].map(lambda p: REGIONS.get(p, ("", "Belum dipetakan"))[1])
    stations["ada_di_matriks"] = stations["POS HUJAN ID"].isin(ids)
    stations.rename(columns={"POS HUJAN ID": "pos_hujan_id"}, inplace=True)
    stations.to_csv(out / "stations.csv", index=False)
    matrix.to_csv(out / "rainfall_matrix.csv", index=False)
    flags.to_csv(out / "rainfall_flags.csv", index=False)
    pd.DataFrame([{"prefix_id_internal": k, "kode_bps": v[0], "kabupaten_kota": v[1]} for k, v in REGIONS.items()]).to_csv(out / "regions.csv", index=False)
    print(f"Selesai. {len(stations)} pos sumber, {len(ids)} pos matriks, {len(matrix)} tanggal.")


if __name__ == "__main__":
    main()
